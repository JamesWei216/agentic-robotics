#!/usr/bin/env python3
"""Check the depth back-projection chain: back-project every pixel, then look up
the nearest back-projected point to each ground-truth object position."""
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
img = obs["agentview_image"]

rows, cols = np.meshgrid(np.arange(256), np.arange(256), indexing="ij")
pts = cam.pixels_to_world(rows.reshape(-1), cols.reshape(-1), depth)
pts = pts.reshape(256, 256, 3)
print("world z range:", np.round(np.percentile(pts[..., 2], [1, 5, 50, 95, 99]), 3))
table = np.abs(pts[..., 2] - 0.90) < 0.02
print("pixels near table plane z=0.90:", int(table.sum()))
for name in ("bolt_small_1", "bolt_large_1", "parts_bin_blue_1", "parts_bin_red_1"):
    gt = np.asarray(obs[f"{name}_pos"])
    d = np.linalg.norm(pts - gt[None, None, :], axis=-1)
    r, c = np.unravel_index(np.argmin(d), d.shape)
    print(f"{name:18s} gt {np.round(gt, 3)} nearest px (r={r},c={c}) "
          f"dist={d[r, c] * 1000:5.1f} mm rgb={img[r, c]} "
          f"z_est={pts[r, c, 2]:.3f}")
