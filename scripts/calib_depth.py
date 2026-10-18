#!/usr/bin/env python3
"""Calibrate the depth sensor against the known table plane.

The workcell table top is a plane at z=0.90. Reconstructing the whole image gives
a peak at the table. Compare the peak with 0.90 to get the depth scale/bias, then
re-check the object positions.
"""
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

from agent.skills.perception import CameraModel  # noqa: E402

SUITE, TASK, SEED = "libero_bolt_v2", 0, 1000
suite = get_benchmark_dict()[SUITE]()
task = suite.get_task(TASK)
bddl = pathlib.Path(get_libero_path("bddl_files")) / SUITE / task.bddl_file
env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256,
                         camera_depths=True)
env.seed(SEED)
obs = env.reset()
sim = env.env.sim
cam = CameraModel(sim, "agentview", 256, 256)
depth = cam.depth_metric(sim, np.asarray(obs["agentview_depth"]))
rows, cols = np.meshgrid(np.arange(256), np.arange(256), indexing="ij")
pts = cam.pixels_to_world(rows.reshape(-1), cols.reshape(-1), depth).reshape(256, 256, 3)

z = pts[..., 2]
sel = (z > 0.80) & (z < 1.00)
print("workspace pixels:", int(sel.sum()))
hist, edges = np.histogram(z[sel], bins=40, range=(0.80, 1.00))
top = np.argsort(hist)[-5:]
for i in sorted(top):
    print(f"  z {edges[i]:.4f}-{edges[i + 1]:.4f}: {hist[i]}")
peak = edges[int(np.argmax(hist))]
print(f"table plane peak at z={peak:.4f} (true 0.9000), ratio={0.90 / peak:.5f}")

for name in ("bolt_small_1", "bolt_large_1"):
    gt = np.asarray(obs[f"{name}_pos"])
    d = np.linalg.norm(pts - gt[None, None, :], axis=-1)
    r, c = np.unravel_index(np.argmin(d), d.shape)
    print(f"{name}: nearest (r={r},c={c}) z_est={pts[r, c, 2]:.4f} xyz={np.round(pts[r,c],3)} gt={np.round(gt,3)}")
    # what would the point be with the depth scaled?
    for s in (0.90 / peak, 1.0):
        dpt = depth[r, c] * s
        fx, fy = cam.K[0, 0], cam.K[1, 1]
        cx, cy = cam.K[0, 2], cam.K[1, 2]
        r_td = 255 - r
        xy = np.array([(c - cx) * dpt / fx, (r_td - cy) * dpt / fy, dpt, 1.0])
        w = (cam.cam2world @ xy)[:3]
        print(f"   scale {s:.4f} -> {np.round(w,3)}  err={np.linalg.norm(w - gt) * 1000:.1f} mm")
