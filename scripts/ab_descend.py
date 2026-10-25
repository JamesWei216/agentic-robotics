#!/usr/bin/env python3
"""A/B the descend strategy for the 2nd part of a batch (kinematic branch issue).

Observed: on libero_bolt_multi t5, after the first part is placed, the arm comes
back over the table in a *straight-elbow* branch (j2 ~= 1.29, j4 ~= -0.79) and the
last descend leg to z=0.910 stalls ~25 mm high with **no contact at all** -- it is
not a collision, the branch cannot reach. The isolated probe (arm starts from
home, bent elbow j2 ~= 1.17) reaches the same pose and the grasp holds.

Each strategy below builds a fresh env, sorts the first part for real, then tries
to grasp the second one:

  A  current: pre-grasp at +0.10 (speed 0.030) then 60/30/0 mm legs (speed 0.012)
  B  slow approach: pre-grasp at +0.10 with speed 0.012, then legs
  C  bent waypoint: (x-0.06, y, 1.00) then (x, y, 0.96) then legs
  D  flipped wrist: same as A but the other jaw side (yaw 180 deg)

    MUJOCO_GL=egl PYTHONPATH=.:/home/wei/work/g05/LIBERO-master \
      /home/wei/work/g05/GalaxeaVLA-main/.venv/bin/python \
      scripts/ab_descend.py libero_bolt_multi 5 1000 [A,B,C,D]
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
JOINTS = [f"robot0_joint{i}" for i in range(1, 8)]


def jl(ex):
    return [round(float(ex.u.sim.data.get_joint_qpos(j)), 2) for j in JOINTS]


def build(suite_name, task_idx, seed, n_items):
    suite = get_benchmark_dict()[suite_name]()
    task = suite.get_task(task_idx)
    bddl = pathlib.Path(get_libero_path("bddl_files")) / suite_name / task.bddl_file
    np.random.seed(seed)
    env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256,
                            horizon=400 + 800 * n_items)
    env.seed(seed)
    env.reset()
    ex = Expert(env)
    for _ in range(30):
        ex.step(np.zeros(3), np.zeros(3), -1.0)
    return env, ex


def trial(strategy, suite_name, task_idx, seed, pairs):
    env, ex = build(suite_name, task_idx, seed, max(1, len(pairs)))
    home = (ex.ee()[0].copy(), ex.ee()[1].copy())
    # sort the first part for real, then go home (same pre-state as the agent)
    ex.grasp(pairs[0]["object"])
    ex.transfer(pairs[0]["bin"])
    ex.move_to(home[0], home[1], grip=-1.0, max_steps=120, speed=0.020)

    obj = pairs[1]["object"]
    gp = ex.grasp_point(obj)
    axis = ex.bolt_axis(obj)
    R = ex.grasp_orientation(axis, R_cur=ex.ee()[1])
    if strategy == "D":
        R_alt = ex.grasp_orientation(axis, R_cur=None)
        if np.allclose(R_alt, R):
            R_alt = ex.grasp_orientation(-axis, R_cur=None)
        R = R_alt

    pre_speed = 0.012 if strategy == "B" else 0.030
    ep, _ = ex.move_to(gp + np.array([0, 0, 0.10]), R, grip=-1.0,
                       max_steps=200 if strategy == "B" else 100, speed=pre_speed)
    if strategy == "E":
        # force a bent elbow: go low and close to the base first, then slide out
        ex.move_to(np.array([gp[0] - 0.12, gp[1], 0.98]), R, grip=-1.0, max_steps=150,
                   speed=0.015)
        ex.move_to(np.array([gp[0] - 0.04, gp[1], 0.945]), R, grip=-1.0, max_steps=120,
                   speed=0.010)
        ex.move_to(np.array([gp[0], gp[1], 0.935]), R, grip=-1.0, max_steps=120,
                   speed=0.008)
    if strategy == "F":
        ex.move_to(np.array([gp[0] - 0.06, gp[1], 0.995]), R, grip=-1.0, max_steps=150,
                   speed=0.012)
        ex.move_to(np.array([gp[0], gp[1], 0.960]), R, grip=-1.0, max_steps=150,
                   speed=0.008)
    if strategy == "G":
        # dive at an offset xy first (bent), then slide in at low height
        ex.move_to(np.array([gp[0] - 0.05, gp[1], 0.930]), R, grip=-1.0, max_steps=150,
                   speed=0.012)
        ex.move_to(np.array([gp[0], gp[1], 0.925]), R, grip=-1.0, max_steps=120,
                   speed=0.006)
    if strategy == "C":
        ex.move_to(np.array([gp[0] - 0.06, gp[1], 1.00]), R, grip=-1.0, max_steps=120,
                   speed=0.020)
        ex.move_to(np.array([gp[0], gp[1], 0.96]), R, grip=-1.0, max_steps=120,
                   speed=0.015)

    errs = []
    for off in (0.060, 0.030, 0.0):
        leg = np.array([gp[0], gp[1], gp[2] + off])
        if ex.ee()[0][2] <= leg[2] + 0.003:
            continue
        p, _ = ex.move_to(leg, R, grip=-1.0, tol_p=0.006, max_steps=45, speed=0.012)
        errs.append(round(float(p) * 1000, 1))
    z = float(ex.ee()[0][2])
    j = jl(ex)

    for _ in range(35):
        ex.step(np.zeros(3), np.zeros(3), 1.0)
    jaw = float(np.abs(ex.fingers_qpos()).mean())
    z0 = float(ex.body_pos(obj)[2])
    ex.move_to(gp + np.array([0, 0, 0.12]), R, grip=1.0, max_steps=150, speed=0.015)
    lifted = float(ex.body_pos(obj)[2]) - z0
    held = lifted > 0.02
    ok_all = bool(env.check_success())
    print(f"  {strategy}: pre_err={float(ep)*1000:5.1f}mm legs={errs} "
          f"z={z:.3f} j={j} jaw={jaw:.4f} lifted={lifted:.3f} held={held} "
          f"goal={ok_all}")
    env.close()
    return held


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    suite_name = args[0] if args else "libero_bolt_multi"
    task_idx = int(args[1]) if len(args) > 1 else 5
    seed = int(args[2]) if len(args) > 2 else 1000
    strategies = (args[3].split(",") if len(args) > 3 else ["A", "B", "C", "D"])
    pairs = json.loads((ROOT / "config" / "missions.json").read_text())[suite_name][str(task_idx)]
    print(f"suite={suite_name} task={task_idx} seed={seed} obj={pairs[1]['object']}")
    for st in strategies:
        trial(st, suite_name, task_idx, seed, pairs)


if __name__ == "__main__":
    main()
