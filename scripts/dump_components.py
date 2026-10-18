#!/usr/bin/env python3
"""Dump every segmentation component with its 3-D geometry, and compare with
ground truth (test oracle)."""
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402
import robosuite.utils.transform_utils as T  # noqa: E402

from agent.skills.perception import (CameraModel, segment_masks, _components,  # noqa: E402
                                     _bolt_record, _bin_record)

SUITE = sys.argv[1] if len(sys.argv) > 1 else "libero_bolt_v2"
TASK = int(sys.argv[2]) if len(sys.argv) > 2 else 0
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 1000

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
img = obs["agentview_image"]
masks = segment_masks(img)
gts = {n[:-4]: np.asarray(obs[n]) for n in obs if n.endswith("_pos")
       and (n.startswith("bolt") or n.startswith("parts_bin")) and "to_robot0" not in n}
print("GT:", {k: np.round(v, 3).tolist() for k, v in gts.items()})
for k, m in masks.items():
    print(f"\n--- mask {k}: {int(m.sum())} px ---")
    for rows, cols in _components(m, min_px=40):
        r0, r1, c0, c1 = rows.min(), rows.max(), cols.min(), cols.max()
        rec = _bolt_record(rows, cols, depth, cam) if k == "steel" else None
        head = f"  comp px={len(rows):5d} rows[{r0},{r1}] cols[{c0},{c1}]"
        if rec:
            d = {n: float(np.linalg.norm(rec["center"] - g)) for n, g in gts.items()
                 if n.startswith("bolt")}
            near = min(d, key=d.get)
            head += (f" len={rec['length'] * 1000:5.1f}mm w={rec['width'] * 1000:5.1f}mm"
                     f" kind={rec['kind']:10s} c={np.round(rec['center'], 3)}"
                     f" nearest={near} d={d[near] * 1000:5.1f}mm"
                     f" axis={np.round(rec['axis'], 2)}")
        print(head)

print("\n--- bins in detail ---")
for colour in ("blue", "red"):
    comps = _components(masks[colour], min_px=150)
    if not comps:
        continue
    rows = np.concatenate([c[0] for c in comps])
    cols = np.concatenate([c[1] for c in comps])
    rec = _bin_record(rows, cols, depth, cam, colour)
    print(f" {colour}: {rec}")
# ground truth contain_region
for name in ("parts_bin_blue_1", "parts_bin_red_1"):
    sid = sim.model.site_name2id(f"{name}_contain_region")
    print(f" GT {name} contain_region pos={np.round(sim.data.site_xpos[sid],4)}"
          f" size={np.round(sim.model.site_size[sid],4)}")
