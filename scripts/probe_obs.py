#!/usr/bin/env python3
"""Inspect what the LIBERO obs actually gives us for vision: image keys, depth,
camera intrinsics/extrinsics, and how the bins/bolts look in HSV."""
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

suite = get_benchmark_dict()["libero_bolt_v2"]()
task = suite.get_task(6)
bddl = pathlib.Path(get_libero_path("bddl_files")) / "libero_bolt_v2" / task.bddl_file
env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256)
env.seed(1000)
obs = env.reset()
print("obs keys:", sorted(obs.keys()))
for k, v in obs.items():
    print(" ", k, getattr(v, "shape", type(v)), getattr(v, "dtype", ""))

u = env.env
print("\ncamera names:", u.camera_names)
print("camera heights/widths:", u.camera_heights, u.camera_widths)
cam = "agentview"
print("cam_pos:", u.sim.data.cam_xpos[u.camera_name2id(cam)])
print("cam_xmat:\n", u.sim.data.cam_xmat[u.camera_name2id(cam)].reshape(3, 3))
print("fovy:", u.sim.model.cam_fovy[u.camera_name2id(cam)])
d = obs.get("agentview_depth")
if d is not None:
    print("depth min/max/mean:", float(d.min()), float(d.max()), float(d.mean()))
img = obs["agentview_image"]
print("image dtype/range:", img.dtype, int(img.min()), int(img.max()))
from PIL import Image
Image.fromarray(img.astype(np.uint8)).save("/tmp/agentview.png")
print("saved /tmp/agentview.png")
