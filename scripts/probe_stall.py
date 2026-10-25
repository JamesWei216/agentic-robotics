#!/usr/bin/env python3
"""Why does the descend stall on the "second" part? Step-by-step probe.

Loads one (suite, task, seed), picks one object, and descends in 10 mm steps
while printing the EE pose error, every joint angle, and the contact pairs that
involve the gripper fingers. Use it to tell apart three candidate causes:
joint-limit saturation, a collision with the bin/table, and a wrong grasp pose.

    MUJOCO_GL=egl PYTHONPATH=.:/home/wei/work/g05/LIBERO-master \
      /home/wei/work/g05/GalaxeaVLA-main/.venv/bin/python \
      scripts/probe_stall.py libero_bolt_multi 5 1000 bolt_small_2
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
JOINTS = ["robot0_joint1", "robot0_joint2", "robot0_joint3",
          "robot0_joint4", "robot0_joint5", "robot0_joint6", "robot0_joint7"]


def joints(ex):
    return [round(float(ex.u.sim.data.get_joint_qpos(j)), 2) for j in JOINTS]


def finger_contacts(ex, max_n=6):
    """Names of bodies/geoms currently touching the two finger geoms."""
    sim = ex.u.sim
    fg = set()
    for side in ("left", "right"):
        try:
            gid = sim.model.geom_name2id(f"gripper0_{side}finger")
            fg.add(gid)
        except Exception:
            pass
    out = []
    for c in sim.data.contact[:sim.data.ncon]:
        if c.geom1 in fg or c.geom2 in fg:
            other = c.geom2 if c.geom1 in fg else c.geom1
            name = sim.model.geom_id2name(other) or f"geom{other}"
            if name not in out:
                out.append(name)
    return out[:max_n]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    suite_name = args[0] if args else "libero_bolt_multi"
    task_idx = int(args[1]) if len(args) > 1 else 5
    seed = int(args[2]) if len(args) > 2 else 1000
    obj = args[3] if len(args) > 3 else "bolt_small_2"

    pairs = json.loads((ROOT / "config" / "missions.json").read_text())[suite_name][str(task_idx)]
    suite = get_benchmark_dict()[suite_name]()
    task = suite.get_task(task_idx)
    bddl = pathlib.Path(get_libero_path("bddl_files")) / suite_name / task.bddl_file

    np.random.seed(seed)
    env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256,
                            horizon=400 + 800 * max(1, len(pairs)))
    env.seed(seed)
    env.reset()
    ex = Expert(env)
    for _ in range(30):
        ex.step(np.zeros(3), np.zeros(3), -1.0)

    home_pos, home_rot = ex.ee()[0].copy(), ex.ee()[1].copy()
    gp = ex.grasp_point(obj)
    axis = ex.bolt_axis(obj)
    R = ex.grasp_orientation(axis, R_cur=ex.ee()[1])
    print(f"obj={obj} body={np.round(ex.body_pos(obj), 4)} grasp_point={np.round(gp, 4)}")
    print(f"axis={np.round(axis, 3)}  R_grasp_z={np.round(R[:, 2], 3)} "
          f"x={np.round(R[:, 0], 3)}")
    print(f"joints@settle {joints(ex)}")

    ex.move_to(home_pos, home_rot, grip=-1.0, max_steps=120, speed=0.020)
    ep, eo = ex.move_to(gp + np.array([0, 0, 0.10]), R, grip=-1.0, max_steps=150)
    print(f"\npre-grasp: err_p={ep*1000:.1f}mm err_o={eo:.3f} ee={np.round(ex.ee()[0],3)} "
          f"joints={joints(ex)} contacts={finger_contacts(ex)}")

    print("\nstep-down (10 mm per leg, 40 steps each):")
    for dz in (0.07, 0.06, 0.05, 0.04, 0.03, 0.02, 0.01, 0.0):
        tgt = gp + np.array([0.0, 0.0, dz])
        p, eo = ex.move_to(tgt, R, grip=-1.0, tol_p=0.004, max_steps=40, speed=0.010)
        ee = ex.ee()[0]
        print(f"  dz={dz*1000:5.1f}mm tgt_z={tgt[2]:.3f} ee={np.round(ee,3)} "
              f"err={p*1000:5.1f}mm err_o={eo:.2f} j={joints(ex)} c={finger_contacts(ex)}")

    print("\nclose + lift:")
    for _ in range(35):
        ex.step(np.zeros(3), np.zeros(3), 1.0)
    jaw = float(np.abs(ex.fingers_qpos()).mean())
    z0 = ex.body_pos(obj)[2]
    p, _ = ex.move_to(gp + np.array([0, 0, 0.12]), R, grip=1.0, max_steps=150, speed=0.015)
    print(f"  jaw={jaw:.4f} bolt_z0={z0:.4f} bolt_z={ex.body_pos(obj)[2]:.4f} "
          f"lift_err={p*1000:.1f}mm contacts={finger_contacts(ex)}")
    env.close()


if __name__ == "__main__":
    main()
