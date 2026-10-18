#!/usr/bin/env python3
"""Trace the slow v2 t6 place path (large bolt -> red box).

Usage: python scripts/diag_t6.py [task_idx] [seed]
Prints every primitive leg with its step count and residual error so we can see
which transit leg burns the budget.
"""
import pathlib
import sys
import time

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

from agent.skills.expert import Expert, EpisodeDone  # noqa: E402

SUITE = sys.argv[1] if len(sys.argv) > 1 else "libero_bolt_v2"
TASK = int(sys.argv[2]) if len(sys.argv) > 2 else 6
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 1001


def main():
    suite = get_benchmark_dict()[SUITE]()
    task = suite.get_task(TASK)
    bddl = pathlib.Path(get_libero_path("bddl_files")) / SUITE / task.bddl_file
    print(f"suite={SUITE} task={TASK} seed={SEED} bddl={task.bddl_file}")
    env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=64, camera_widths=64)
    env.seed(SEED)
    env.reset()
    ex = Expert(env)

    # instrument step counting per primitive
    original_move = ex.move_to
    stats = []

    def traced_move(target_pos, target_ori, grip=-1.0, tol_p=0.010,
                    tol_o=0.20, max_steps=100, speed=0.030, **kw):
        t0 = time.time()
        err_p, err_o = 1e9, 1e9
        used = 0
        for i in range(max_steps):
            p, R = ex.ee()
            ep = np.asarray(target_pos) - p
            import robosuite.utils.transform_utils as T
            R_err = np.asarray(target_ori) @ R.T
            ax = T.quat2axisangle(T.mat2quat(R_err))
            err_p, err_o = np.linalg.norm(ep), np.linalg.norm(ax)
            ex.step(np.clip(ep, -speed, speed), np.clip(ax, -0.30, 0.30), grip)
            used = i + 1
            if err_p < tol_p and err_o < tol_o:
                break
        stats.append(dict(tgt=np.round(np.asarray(target_pos), 3).tolist(),
                          steps=used, max=max_steps, tol=tol_p,
                          err=round(float(err_p), 4),
                          ok=err_p < tol_p and err_o < tol_o))
        print(f"  move -> {np.round(np.asarray(target_pos),3)} "
              f"steps={used}/{max_steps} err={err_p:.4f} "
              f"{'OK' if stats[-1]['ok'] else 'MISS'} grip={grip}")
        return err_p, err_o

    ex.move_to = traced_move

    items = task.language if hasattr(task, "language") else ""
    print("language:", items)
    log, log2 = [], []
    try:
        ok, log = ex.grasp("bolt_large_1", verbose=True)
        print("grasp_ok:", ok)
        if ok:
            ok2, log2 = ex.transfer("parts_bin_red_1", verbose=True)
            print("transfer_ok:", ok2)
    except EpisodeDone:
        print("!! env terminated mid-plan (done=True)")
    print("done:", env.env.done, "check_success:", env.env._check_success(),
          "timestep:", env.env.timestep, "horizon:", env.env.horizon)
    for nm in ("bolt_large_1", "parts_bin_red_1"):
        print("pos", nm, np.round(ex.body_pos(nm), 3))
    sp, _, ss = ex.site_state("parts_bin_red_1_contain_region")
    print("red contain_region", np.round(sp, 3), "size", np.round(ss, 4))
    print("\n=== legs ===")
    for name, err in log + log2:
        if isinstance(err, tuple):
            err = tuple(round(float(e), 4) for e in err)
        print(f"  {name:16s} {err}")


if __name__ == "__main__":
    main()
