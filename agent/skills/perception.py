"""RGB-D perception for the bolt-sorting workcell.

No simulator ground truth is used here: the module only reads the camera image,
the depth buffer, and the camera *calibration* (intrinsics/extrinsics, which a
real cell has from calibration). Everything else is geometry:

  1. colour segmentation  -> bins (blue / red) and steel parts (low saturation,
     blue channel >= red channel, which separates steel from the beige table)
  2. depth back-projection -> metric 3-D points for every segment
  3. PCA on a part's point cloud -> lying axis + length -> small (62 mm) vs
     large (103 mm) bolt
  4. bin geometry from depth -> rim height, cavity floor, inner centre

The output is a `VisionScene` that mimics the three ground-truth pose lookups
the scripted primitives need (`body_pos`, `body_rot`, `site_state`), so the same
Expert code runs in both modes and the difference is measurable.

Used from `api.Robot.scan()` when AGENT_PERCEPTION=vision.
"""
from __future__ import annotations

import numpy as np

try:  # scipy is already a LIBERO dependency
    from scipy import ndimage as ndi
except Exception:  # pragma: no cover
    ndi = None

import robosuite.utils.transform_utils as T
from robosuite.utils.camera_utils import (
    get_camera_extrinsic_matrix,
    get_camera_intrinsic_matrix,
    get_real_depth_map,
)

EPS = 1e-9

# geometry we *do* know a priori (the cell is built to handle these two parts)
BOLT_LEN = {"bolt_small": 0.062, "bolt_large": 0.103}
BOLT_AF = {"bolt_small": 0.022, "bolt_large": 0.038}       # across flats (height)
BOLT_HEAD_H = {"bolt_small": 0.010, "bolt_large": 0.018}
BOLT_SHANK = {"bolt_small": 0.052, "bolt_large": 0.085}
BOLT_SHANK_D = {"bolt_small": 0.013, "bolt_large": 0.024}
TABLE_Z = 0.90


# --------------------------------------------------------------------- colour
def rgb_to_hsv(img: np.ndarray):
    """uint8 RGB -> (hue deg, sat 0-1, val 0-1), vectorised."""
    a = img.astype(np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx = a.max(axis=-1)
    mn = a.min(axis=-1)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-6
    idx = m & (mx == r)
    h[idx] = ((g[idx] - b[idx]) / d[idx]) % 6
    idx = m & (mx == g)
    h[idx] = (b[idx] - r[idx]) / d[idx] + 2
    idx = m & (mx == b)
    h[idx] = (r[idx] - g[idx]) / d[idx] + 4
    h *= 60.0
    s = np.where(mx > 1e-6, d / np.maximum(mx, EPS), 0.0)
    return h, s, mx


def segment_masks(img: np.ndarray):
    """Colour masks for the two bins and for the steel parts."""
    h, s, v = rgb_to_hsv(img)
    blue = (h >= 200) & (h <= 250) & (s >= 0.45) & (v >= 0.12)
    red = ((h <= 20) | (h >= 340)) & (s >= 0.45) & (v >= 0.12)
    # steel: low saturation, blue channel at least as strong as red (the table is
    # warm beige, the arm is neutral grey -- the z gate in detect() drops the arm)
    b = img[..., 2].astype(np.int16)
    r = img[..., 0].astype(np.int16)
    steel = (s <= 0.22) & (b >= r - 3) & (v >= 0.10) & (v <= 0.88)
    return {"blue": blue, "red": red, "steel": steel}


# --------------------------------------------------------------------- camera
class CameraModel:
    def __init__(self, sim, camera: str, height: int, width: int):
        self.camera = camera
        self.height = height
        self.width = width
        self.K = get_camera_intrinsic_matrix(sim, camera, height, width)
        # rigid camera->world transform (robosuite applies the axis correction so
        # +y is image-down and +z is the view direction)
        cam2world = get_camera_extrinsic_matrix(sim, camera)
        self.cam2world = np.asarray(cam2world, dtype=float)
        self.world2cam = np.linalg.inv(self.cam2world)

    def depth_metric(self, sim, depth_raw: np.ndarray) -> np.ndarray:
        raw = np.asarray(depth_raw, dtype=np.float64).squeeze()
        return np.asarray(get_real_depth_map(sim, raw))

    def pixels_to_world(self, rows, cols, depth_metric):
        """Back-project image pixels to world coordinates.

        Row convention: the RGB/depth buffers that reach the agent are stored
        bottom-up, while the camera intrinsics/extrinsics use the usual top-down
        convention. Measured on this cell (nearest back-projected point to four
        known object centres): 81 mm mean error without the row flip, 9 mm with
        it, and 1.7 m with a flipped z -- so the row flip below is what matches
        the calibration.
        """
        depth_metric = np.asarray(depth_metric).squeeze()
        r_buf = np.asarray(rows, dtype=int).reshape(-1)
        cols = np.asarray(cols, dtype=float).reshape(-1)
        # depth is sampled at the buffer row (the mask and the depth buffer are
        # index-aligned), but the vertical pixel coordinate fed to the intrinsics
        # has to be in top-down order.
        r_td = (self.height - 1) - r_buf.astype(float)
        z = np.asarray(depth_metric[r_buf, cols.astype(int)], dtype=float).reshape(-1)
        fx, fy = self.K[0, 0], self.K[1, 1]
        cx, cy = self.K[0, 2], self.K[1, 2]
        x = (cols - cx) * z / fx
        y = (r_td - cy) * z / fy
        pts = np.stack([x, y, z, np.ones_like(z)], axis=1)
        return (self.cam2world @ pts.T).T[:, :3]


# ------------------------------------------------------------------ detections
def _components(mask, min_px=25):
    if ndi is None:
        raise RuntimeError("scipy is required for vision perception")
    lab, n = ndi.label(mask)
    out = []
    for i in range(1, n + 1):
        rows, cols = np.where(lab == i)
        if rows.size >= min_px:
            out.append((rows, cols))
    return out


def _bolt_record(rows, cols, depth, cam: CameraModel):
    pts = cam.pixels_to_world(rows, cols, depth)
    keep = (pts[:, 2] > TABLE_Z - 0.03) & (pts[:, 2] < TABLE_Z + 0.06)
    pts = pts[keep]
    if len(pts) < 50:
        return None
    c = pts.mean(axis=0)
    # reject anything outside the robot's work area (the arm itself, the floor)
    if abs(c[0]) > 0.35 or abs(c[1]) > 0.35:
        return None
    q = pts - c
    # PCA in the table plane: the lying bolt's long axis
    qxy = q.copy()
    qxy[:, 2] = 0.0
    w, vecs = np.linalg.eigh(qxy.T @ qxy)
    axis = vecs[:, np.argmax(w)]
    if axis[0] < 0:
        axis = -axis
    proj = qxy @ axis
    length = float(proj.max() - proj.min())
    width = float(np.percentile(np.abs(qxy @ vecs[:, np.argsort(w)[0]]), 95) * 2)
    # part-size gate: the two bolts are 62 / 103 mm long and <= 38 mm across, so
    # longer or wider blobs are arm segments, shadows or the table edge.
    if not (0.035 <= length <= 0.150) or width > 0.060:
        return None
    # which end carries the hex head? The head is taller than the shank, so the
    # top surface at the head end sits AF - shank_d higher (9 mm small, 14 mm
    # large on this cell). Compares the world-z of the two length-wise thirds.
    span = proj.max() - proj.min()
    head_sign = 1.0
    if span > 0.03:
        lo = proj < proj.min() + 0.30 * span
        hi = proj > proj.max() - 0.30 * span
        z_lo = float(np.percentile(pts[lo][:, 2], 90)) if lo.any() else 0.0
        z_hi = float(np.percentile(pts[hi][:, 2], 90)) if hi.any() else 0.0
        head_sign = 1.0 if z_hi >= z_lo else -1.0
    kind = "bolt_large" if length > 0.080 else "bolt_small"
    return dict(center=c, top_z=float(np.percentile(pts[:, 2], 90)),
                axis=axis / (np.linalg.norm(axis) + EPS), head_sign=head_sign,
                length=length, width=width, kind=kind, n_px=int(len(pts)))


def _bin_record(rows, cols, depth, cam: CameraModel, colour: str):
    pts = cam.pixels_to_world(rows, cols, depth)
    keep = (pts[:, 2] > TABLE_Z - 0.05) & (pts[:, 2] < TABLE_Z + 0.25)
    pts = pts[keep]
    if len(pts) < 60:
        return None
    z = pts[:, 2]
    rim = float(np.percentile(z, 95))
    floor = float(np.percentile(z, 5))
    inner = pts[z < rim - 0.012]
    if len(inner) < 30:
        inner = pts
    centre = inner.mean(axis=0)
    # inner half-width from the spread of the interior pixels
    half = float(np.percentile(np.linalg.norm(inner[:, :2] - centre[:2], axis=1), 90))
    return dict(colour=colour, centre=centre, rim_z=rim, cavity_floor=floor,
                half=half, n_px=int(len(pts)))


def perceive(obs, sim, camera="agentview", debug=False):
    """obs -> VisionScene. Uses only image + depth + calibration."""
    img = np.asarray(obs[f"{camera}_image"])
    depth_raw = obs.get(f"{camera}_depth")
    if depth_raw is None:
        raise RuntimeError("perception needs camera_depths=True")
    h, w = img.shape[:2]
    cam = CameraModel(sim, camera, h, w)
    depth = cam.depth_metric(sim, np.asarray(depth_raw))
    masks = segment_masks(img)

    bolts, bins = [], []
    for rows, cols in _components(masks["steel"], min_px=40):
        rec = _bolt_record(rows, cols, depth, cam)
        if rec:
            bolts.append(rec)
    for colour in ("blue", "red"):
        comps = _components(masks[colour], min_px=150)
        if not comps:
            continue
        rows = np.concatenate([c[0] for c in comps])
        cols = np.concatenate([c[1] for c in comps])
        rec = _bin_record(rows, cols, depth, cam, colour)
        if rec:
            bins.append(rec)
    if debug:
        print(f"  [perception] bolts={len(bolts)} bins={len(bins)}")
    return VisionScene(bolts, bins)


class VisionScene:
    """Detections + the pose lookups the scripted primitives expect.

    Naming mirrors the harness convention (bolt_small_1, parts_bin_blue_1, ...)
    and is assigned deterministically from the detections themselves: parts are
    sorted by (y, x) inside their size class, bins by colour. For the tasks used
    here the names only have to be *self-consistent* -- the goal predicate is
    evaluated by the environment, and both bolts of a class share one bin.
    """

    def __init__(self, bolts, bins):
        self.raw_bolts = bolts
        self.raw_bins = bins
        self.bolts, self.bins = {}, {}

        def key(b):
            return (round(float(b["center"][1]), 3), round(float(b["center"][0]), 3))

        for kind in ("bolt_small", "bolt_large"):
            group = sorted([b for b in bolts if b["kind"] == kind], key=key)
            for i, b in enumerate(group, start=1):
                self.bolts[f"{kind}_{i}"] = b
        for b in bins:
            name = "parts_bin_blue_1" if b["colour"] == "blue" else "parts_bin_red_1"
            self.bins[name] = b

    # -- diagnostics -------------------------------------------------------
    def summary(self):
        out = []
        for name, b in self.bolts.items():
            out.append(dict(id=name, kind=b["kind"],
                            pos=[round(float(v), 4) for v in b["center"]],
                            axis=[round(float(v), 3) for v in b["axis"]],
                            length_mm=round(b["length"] * 1000, 1),
                            px=b["n_px"]))
        for name, b in self.bins.items():
            out.append(dict(id=name, kind=b["colour"],
                            pos=[round(float(v), 4) for v in b["centre"]],
                            rim_z=round(b["rim_z"], 4),
                            floor_z=round(b["cavity_floor"], 4),
                            px=b["n_px"]))
        return out

    # -- pose lookups (same signatures as Expert's ground-truth helpers) ----
    def has_bolt(self, name):
        return name in self.bolts

    def has_bin(self, name):
        return name in self.bins

    def body_pos(self, name):
        b = self.bolts.get(name)
        if b is None:
            raise KeyError(f"perception: {name} not visible")
        p = np.asarray(b["center"], dtype=float).copy()
        p[2] = TABLE_Z
        return p

    def grasp_point(self, name):
        """Grasp the shank, mid-way, at the shank's top surface.

        Measured trade-offs on this cell (vision mode, 10-episode probes):
          * gripping the hex head (the validated scripted recipe) closes on air
            once the z target comes from the depth image, because the OSC keeps a
            3-8 mm height bias and the pads are only 16 mm tall;
          * gripping the shank at `table + shank_d/2 + 7 mm` works for the large
            bolt (4/4 episodes) and grips the small bolt's 13 mm shank weakly
            (pads close to ~5 mm, the part slips during the first climb).
        So this is the recipe we ship: shank, index-free (no head-end ambiguity),
        height from the calibrated table plane + part geometry.
        """
        b = self.bolts[name]
        kind = b["kind"]
        axis = np.asarray(b["axis"], dtype=float)
        p = np.asarray(b["center"], dtype=float).copy()
        p[:2] += 0.0 * axis[:2]
        p[2] = TABLE_Z + BOLT_SHANK_D[kind] / 2 + 0.007
        return p

    def body_rot(self, name):
        """Rotation with x along the detected long axis, z up."""
        b = self.bolts[name]
        x = np.asarray(b["axis"], dtype=float)
        x = np.array([x[0], x[1], 0.0])
        x /= np.linalg.norm(x) + EPS
        z = np.array([0.0, 0.0, 1.0])
        y = np.cross(z, x)
        return np.stack([x, y, z], axis=1)

    def bolt_length(self, name):
        b = self.bolts[name]
        return BOLT_LEN[b["kind"]] if abs(b["length"] - BOLT_LEN[b["kind"]]) > 0.02 \
            else float(b["length"])

    def site_state(self, site_name):
        """Synthesise (pos, rot, size) for `<bin>_contain_region` from vision."""
        bin_name = site_name.replace("_contain_region", "")
        b = self.bins.get(bin_name)
        if b is None:
            raise KeyError(f"perception: bin for {site_name} not visible")
        half = float(np.clip(b["half"], 0.055, 0.13))
        height = max(b["rim_z"] - b["cavity_floor"], 0.01)
        pos = np.array([b["centre"][0], b["centre"][1],
                        b["cavity_floor"] + height / 2])
        size = np.array([half, half, height / 2])
        return pos, np.eye(3), size


def validate_against_truth(scene: VisionScene, truth: dict, verbose=True):
    """Development aid: compare detections with simulator ground truth."""
    errs = []
    for name, gt in truth.items():
        if name.startswith("parts_bin"):
            got = scene.bins.get(name)
            if got is None:
                errs.append((name, None))
                continue
            e = float(np.linalg.norm(got["centre"][:2] - np.asarray(gt)[:2]))
        else:
            got = scene.bolts.get(name)
            if got is None:
                errs.append((name, None))
                continue
            e = float(np.linalg.norm(got["center"] - np.asarray(gt)))
        errs.append((name, e))
    if verbose:
        for name, e in errs:
            print(f"  {name:18s} " + ("MISSED" if e is None else f"err={e * 1000:6.1f} mm"))
    return errs


# --------------------------------------------------------------- in-hand check
WRIST_CAMERA = "robot0_eye_in_hand"
IN_HAND_PX = 600        # measured: 176-260 px with empty jaws, 1172 / 3316 with a part


def in_hand_pixels(obs, camera=WRIST_CAMERA, roi=(0.25, 0.85, 0.25, 0.75)):
    """Steel pixels in the central band of the wrist view.

    Empty jaws read 176-260 px on this cell (the finger bodies themselves), a
    gripped bolt reads 1172 (small) / 3316 (large) px, so the count is a clean
    in-hand detector that needs no object pose at all.
    """
    img = np.asarray(obs[f"{camera}_image"])
    steel = segment_masks(img)["steel"]
    h, w = steel.shape
    band = steel[int(h * roi[0]):int(h * roi[1]), int(w * roi[2]):int(w * roi[3])]
    return int(band.sum())


def part_in_hand(obs, threshold=IN_HAND_PX):
    return in_hand_pixels(obs) >= threshold
