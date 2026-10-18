#!/usr/bin/env python3
"""Find the correct camera-frame sign convention for back-projection.

Tries sy, sz in {+1,-1} (and both pixel-origin conventions) and reports the
distance at which the back-projected cloud reproduces the ground-truth object
centres.  Diagnosis only.
"""
import itertools
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402
from robosuite.utils.camera_utils import (  # noqa: E402
    get_camera_extrinsic_matrix, get_camera_intrinsic_matrix, get_real_depth_map)

SUITE, TASK, SEED = "libero_bolt_v2", 0, 1000
suite = get_benchmark_dict()[SUITE]()
task = suite.get_task(TASK)
bddl = pathlib.Path(get_libero_path("bddl_files")) / SUITE / task.bddl_file
env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256,
                         camera_depths=True)
env.seed(SEED)
obs = env.reset()
sim = env.env.sim
K = get_camera_intrinsic_matrix(sim, "agentview", 256, 256)
E = np.asarray(get_camera_extrinsic_matrix(sim, "agentview"), dtype=float)
depth = np.asarray(get_real_depth_map(sim, np.asarray(obs["agentview_depth"]).squeeze()))
fx, fy = K[0, 0], K[1, 1]
cx, cy = K[0, 2], K[1, 2]
gts = {n[:-4]: np.asarray(obs[n]) for n in obs
       if n.endswith("_pos") and (n.startswith("bolt") or n.startswith("parts_bin"))
       and "to_robot0" not in n}
print("cam pos:", np.round(E[:3, 3], 3))
print("cam z axis (view dir):", np.round(E[:3, 2], 3))

rows, cols = np.meshgrid(np.arange(256), np.arange(256), indexing="ij")
z = depth
best = None
for sy, sz, flip_row in itertools.product((1, -1), (1, -1), (False, True)):
    r = (255 - rows) if flip_row else rows
    xc = (cols - cx) * z / fx
    yc = (r - cy) * z / fy
    p_cam = np.stack([xc, sy * yc, sz * z, np.ones_like(z)], axis=-1)
    pts = (E @ p_cam.reshape(-1, 4).T).T[:, :3].reshape(256, 256, 3)
    tot, zerr = 0.0, 0.0
    for name, gt in gts.items():
        d = np.linalg.norm(pts - gt[None, None, :], axis=-1)
        m = d.min()
        tot += m
        zerr += abs(pts.reshape(-1, 3)[np.argmin(d), 2] - gt[2])
    n = len(gts)
    print(f"sy={sy:+d} sz={sz:+d} flip_row={int(flip_row)}: "
          f"mean nearest dist {tot / n * 1000:6.1f} mm, mean |dz| {zerr / n * 1000:6.1f} mm")
