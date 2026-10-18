#!/usr/bin/env python3
"""Offline colour calibration for the vision perception module.

Uses the instance segmentation of the *development* renderer to label pixels,
then reports the HSV statistics per object class so perception.py can use plain
RGB thresholds at run time.  Segmentation labels are NOT used at run time.
"""
import pathlib
import sys

import numpy as np
import colorsys

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs.env_wrapper import SegmentationRenderEnv  # noqa: E402


def hsv_stats(rgb_pixels):
    px = rgb_pixels.astype(np.float32) / 255.0
    hsv = np.array([colorsys.rgb_to_hsv(*p) for p in px])
    h, s, v = hsv[:, 0] * 360.0, hsv[:, 1], hsv[:, 2]
    return dict(n=len(px),
                h=tuple(np.round(np.percentile(h, [5, 50, 95]), 1)),
                s=tuple(np.round(np.percentile(s, [5, 50, 95]), 3)),
                v=tuple(np.round(np.percentile(v, [5, 50, 95]), 3)),
                rgb_med=tuple(int(x) for x in np.median(rgb_pixels, axis=0)))


for suite_name, task_idx in (("libero_bolt_v2", 6), ("libero_bolt_multi", 6)):
    suite = get_benchmark_dict()[suite_name]()
    task = suite.get_task(task_idx)
    bddl = pathlib.Path(get_libero_path("bddl_files")) / suite_name / task.bddl_file
    env = SegmentationRenderEnv(bddl_file_name=bddl, camera_heights=256,
                                camera_widths=256)
    env.seed(1000)
    obs = env.reset()
    seg = np.asarray(obs["agentview_segmentation_instance"]).squeeze()
    rgb = obs["agentview_image"]
    print(f"\n=== {suite_name} t{task_idx} {task.bddl_file} ===")
    print("seg unique:", np.unique(seg)[:12], "instance_to_id:", env.instance_to_id)
    for name, sid in env.instance_to_id.items():
        mask = seg == sid
        if mask.sum() < 30:
            continue
        print(f"  {name:18s} px={mask.sum():6d}", hsv_stats(rgb[mask]))
    # table / background
    bg = seg == 0
    if bg.sum() > 30:
        print(f"  {'background':18s} px={bg.sum():6d}", hsv_stats(rgb[bg]))
    from PIL import Image
    Image.fromarray(rgb).save(f"/tmp/vis_{suite_name}.png")
    env.close()
