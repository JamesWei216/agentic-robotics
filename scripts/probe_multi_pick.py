#!/usr/bin/env python3
"""Diagnose the "second part" grasp failures in the multi-bolt suite.

For one (suite, task, seed) it replays the episode layout and, for every part in
the mission, reports:
  * the part's settled xy and the grasp point,
  * whether the pre-grasp pose / descend are reachable (residual error),
  * joint 4 at each pose (the elbow limit that saturates the OSC controller),
  * whether the grasp actually holds.

Usage:
    MUJOCO_GL=egl PYTHONPATH=.:/home/wei/work/g05/LIBERO-master \
      /home/wei/work/g05/GalaxeaVLA-main/.venv/bin/python \
      scripts/probe_multi_pick.py libero_bolt_multi 5 1000 [--place-first]

--place-first   actually sort the earlier parts first (default: only inspect the
                layout, which is enough for reach measurements).
"""
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from agent.skills.expert import Expert  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def q4(ex):
    try:
        return round(float(ex.u.sim.data.get_joint_qpos("robot0_joint4")), 3)
    except Exception:
        return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    suite_name = args[0] if args else "libero_bolt_multi"
    task_idx = int(args[1]) if len(args) > 1 else 5
    seed = int(args[2]) if len(args) > 2 else 1000
    place_first = "--place-first" in sys.argv

    missions = json.loads((ROOT / "config" / "missions.json").read_text())
    pairs = missions[suite_name][str(task_idx)]
    n_items = max(1, len(pairs))

    suite = get_benchmark_dict()[suite_name]()
    task = suite.get_task(task_idx)
    bddl = pathlib.Path(get_libero_path("bddl_files")) / suite_name / task.bddl_file
    print(f"suite={suite_name} task={task_idx} seed={seed} items={n_items}")
    print(f"bddl={bddl.name}")

    np.random.seed(seed)                      # same protocol as Robot.from_env()
    env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256,
                            camera_widths=256, horizon=400 + 800 * n_items)
    env.seed(seed)
    env.reset()
    ex = Expert(env)
    for _ in range(30):
        ex.step(np.zeros(3), np.zeros(3), -1.0)

    print("\n== settled layout ==")
    for name in sorted({p["object"] for p in pairs}):
        try:
            pos = ex.body_pos(name)
            gp = ex.grasp_point(name)
            print(f"  {name:16s} xy=({pos[0]:+.3f},{pos[1]:+.3f}) z={pos[2]:.3f} "
                  f"grasp=({gp[0]:+.3f},{gp[1]:+.3f},{gp[2]:.3f})")
        except Exception as exc:  # noqa: BLE001
            print(f"  {name:16s} <missing: {exc}>")

    print("\n== bins ==")
    for name in sorted({p["bin"] for p in pairs if p.get("bin")}):
        try:
            b = ex.body_pos(name)
            print(f"  {name:20s} xy=({b[0]:+.3f},{b[1]:+.3f}) z={b[2]:.3f}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {name:20s} <missing: {exc}>")

    print("\n== reach test (home -> pre-grasp -> descend) ==")
    home_pos, home_rot = ex.ee()[0].copy(), ex.ee()[1].copy()
    for i, pair in enumerate(pairs):
        name = pair["object"]
        if place_first and i > 0:
            # sort the previous pair for real, so residual postures/occluders match
            prev = pairs[i - 1]
            ex.move_to(home_pos, home_rot, grip=-1.0, max_steps=120, speed=0.020)
            ex.grasp(prev["object"])
            ex.transfer(prev["bin"])
        try:
            gp = ex.grasp_point(name)
            axis = ex.bolt_axis(name)
            R = ex.grasp_orientation(axis, R_cur=ex.ee()[1])
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i}] {name}: no pose ({exc})")
            continue
        ex.move_to(home_pos, home_rot, grip=-1.0, max_steps=120, speed=0.020)
        for pre_h in (0.10, 0.16):
            tgt = gp + np.array([0.0, 0.0, pre_h])
            ep, _eo = ex.move_to(tgt, R, grip=-1.0, max_steps=150)
            r_mid, _ = ex.move_to(gp + np.array([0.0, 0.0, 0.035]), R, grip=-1.0,
                                  tol_p=0.006, max_steps=100)
            j = q4(ex)
            print(f"  [{i}] {name} pre_h={pre_h:.2f}: pre_err={float(ep)*1000:5.1f}mm "
                  f"desc_err={float(r_mid)*1000:5.1f}mm j4={j}")
            # back up before the next probe
            ex.move_to(home_pos, home_rot, grip=-1.0, max_steps=120, speed=0.020)

        # real grasp attempt from the canonical pre_h
        ok, log = ex.grasp(name, verbose=True)
        print(f"  [{i}] {name} grasp -> held={ok} j4={q4(ex)} ee="
              f"{np.round(ex.ee()[0], 3)}")
        if ok:
            ex.transfer(pair["bin"])
            print(f"       transferred -> success={bool(env.check_success())} "
                  f"steps={getattr(env, 'timestep', -1)}")
        print()

    env.close()


if __name__ == "__main__":
    main()
