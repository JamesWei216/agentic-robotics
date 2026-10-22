#!/usr/bin/env python3
"""Smoke test for the libero_bolt suite.

1. builds every task, resets it and reports object heights / placement sanity
2. functionally validates the goal predicate by teleporting the target bolt
   into its bin and calling env.check_success()
3. renders a preview image (agentview + wrist) for the first task
"""
import argparse
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402


def obj_pos(env, name):
    return env.sim.data.body_xpos[env.env.obj_body_id[name]].copy()


def teleport_into_bin(env, obj, bin_name, drop=0.012):
    """Put `obj` above the middle of the bin's contain region and let it settle."""
    sim = env.env.sim
    site = f"{bin_name}_contain_region"
    target = sim.data.get_site_xpos(site).copy()
    joint = [j for j in sim.model.joint_names if j.startswith(obj + "_") and "joint" in j][0]
    sim.data.set_joint_qpos(joint, np.array([target[0], target[1], target[2] - drop,
                                             1.0, 0.0, 0.0, 0.0]))
    sim.forward()
    return joint


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="libero_bolt")
    ap.add_argument("--preview", default="/home/wei/work/g05/bolt-sorting/preview_bolt_scene.png")
    ap.add_argument("--max_tasks", type=int, default=0)
    ap.add_argument("--steps", type=int, default=0, help="settle steps after teleport")
    args = ap.parse_args()

    suite = get_benchmark_dict()[args.suite]()
    n = args.max_tasks or suite.get_num_tasks()
    print(f"suite={args.suite} tasks={suite.get_num_tasks()} (testing {n})\n")

    bddl_dir = pathlib.Path(get_libero_path("bddl_files")) / args.suite
    n_ok = 0
    for i in range(n):
        task = suite.get_task(i)
        bddl = bddl_dir / task.bddl_file
        env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256,
                                 camera_widths=256)
        env.seed(7)
        env.reset()
        print(f"[task {i}] {task.language}")
        for name in ("bolt_small_1", "bolt_large_1", "parts_bin_blue_1",
                     "parts_bin_red_1"):
            print(f"    {name:18s} pos={np.round(obj_pos(env, name), 4)}")

        # --- functional goal check: teleport target bolt(s) into their bin --
        goals = task.language
        pairs = [("bolt_small_1", "parts_bin_blue_1"),
                 ("bolt_large_1", "parts_bin_red_1")]
        ok_before = env.check_success()
        moved = []
        sort_both = ("sort" in goals)
        for obj, bin_name in pairs:
            if sort_both or obj.split("_")[1] in goals:
                j = teleport_into_bin(env, obj, bin_name)
                moved.append(j)
        if args.steps:
            for _ in range(args.steps):
                env.step(np.array([0.0] * 6 + [-1.0], dtype=np.float32))
        ok_after = env.check_success()
        print(f"    success: before={ok_before}  after teleport-into-bin={ok_after}"
              f"  ({', '.join(moved)})")
        n_ok += int(bool(ok_after) and not ok_before)

        if i == 0:
            img = np.concatenate([env.sim.render(camera_name="agentview", height=256,
                                                 width=256),
                                  env.sim.render(camera_name="robot0_eye_in_hand",
                                                 height=256, width=256)], axis=1)
            try:
                import imageio
                imageio.imwrite(args.preview, img[::-1])
                print(f"    preview -> {args.preview}")
            except Exception as exc:                       # noqa: BLE001
                print("    preview failed:", exc)
        env.close()
        print()

    print(f"goal predicate validated on {n_ok}/{n} tasks")


if __name__ == "__main__":
    main()
