#!/usr/bin/env python3
"""Probe why the v2 t6 transit stalls: print wrist joint values vs limits and
the grasp yaw for several seeds."""
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402
import robosuite.utils.transform_utils as T  # noqa: E402

from agent.skills.expert import Expert  # noqa: E402

SUITE = "libero_bolt_v2"
TASK = int(sys.argv[1]) if len(sys.argv) > 1 else 6
SEEDS = [int(s) for s in sys.argv[2:]] or [1000, 1001, 1003]


def joint_report(ex, tag):
    r = ex.r
    q = np.asarray(r._joint_positions)
    sim = ex.u.sim
    m = sim.model
    idx, lo, hi, names = [], [], [], []
    for jid in range(m.njnt):
        nm = m.joint_id2name(jid)
        if nm.startswith(f"robot0_joint"):
            idx.append(jid)
            names.append(nm)
            l, h = m.jnt_range[jid]
            lo.append(l)
            hi.append(h)
    lo, hi = np.array(lo), np.array(hi)
    print(f"  [{tag}] q={np.round(q, 3)}")
    flags = []
    for i in range(min(len(q), len(lo))):
        span = hi[i] - lo[i]
        if span > 1e-6 and min(q[i] - lo[i], hi[i] - q[i]) < 0.08 * span:
            flags.append(f"j{i + 1}={q[i]:.3f}[{lo[i]:.2f},{hi[i]:.2f}]")
    print(f"  [{tag}] near-limit: " + ("  ".join(flags) if flags else "none"))


for seed in SEEDS:
    suite = get_benchmark_dict()[SUITE]()
    task = suite.get_task(TASK)
    bddl = pathlib.Path(get_libero_path("bddl_files")) / SUITE / task.bddl_file
    env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=64, camera_widths=64)
    env.seed(seed)
    env.reset()
    ex = Expert(env)
    ax = ex.bolt_axis("bolt_large_1")
    R = ex.grasp_orientation(ax, R_cur=ex.ee()[1])
    yaw = np.degrees(T.mat2euler(R)[2])
    print(f"seed {seed}: bolt axis {np.round(ax,3)} grasp yaw {yaw:.1f} deg "
          f"bin {np.round(ex.body_pos('parts_bin_red_1'),3)}")
    joint_report(ex, "home")
    ok, _ = ex.grasp("bolt_large_1")
    joint_report(ex, "after-lift")
    sp = ex.body_pos("parts_bin_red_1")
    tgt = np.array([sp[0], sp[1], 1.20])
    err = ex.move_to(tgt, R, grip=1.0, max_steps=200, speed=0.015, tol_p=0.02)
    print(f"  transit err={err[0]:.4f} ee={np.round(ex.ee()[0],3)}")
    joint_report(ex, "at-stall")
