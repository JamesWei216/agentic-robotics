#!/usr/bin/env python3
"""Test recovery strategies for the v2 t6 transit stall (EE blocked near x~0.08
with the elbow joint at its lower limit).

Strategy A: descend/raise first, then approach the bin from a high altitude.
Strategy B: retreat to a neutral pose near the base, then approach again.
"""
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

from agent.skills.expert import Expert  # noqa: E402

TASK, SEED = 6, int(sys.argv[1]) if len(sys.argv) > 1 else 1001
STRATEGY = sys.argv[2] if len(sys.argv) > 2 else "B"

suite = get_benchmark_dict()["libero_bolt_v2"]()
task = suite.get_task(TASK)
bddl = pathlib.Path(get_libero_path("bddl_files")) / "libero_bolt_v2" / task.bddl_file
env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=64, camera_widths=64)
env.seed(SEED)
env.reset()
ex = Expert(env)


def leg(target, msteps=200, tol=0.02, speed=0.015, tag=""):
    err = ex.move_to(np.asarray(target), R_GRASP, grip=1.0, max_steps=msteps,
                     speed=speed, tol_p=tol)
    ee = np.round(ex.ee()[0], 3)
    print(f"  {tag:22s} -> {np.round(np.asarray(target),3)} steps_err={err[0]:.4f} ee={ee}")
    return err[0], ee


ok, _ = ex.grasp("bolt_large_1")
if not ok:
    print("grasp failed")
    sys.exit(1)
R_GRASP = ex._held["R_grasp"]
lift_h = ex._held["lift_h"]
head = ex._held["head"]
bin_pos = ex.body_pos("parts_bin_red_1")
bin_xy = bin_pos[:2]
print(f"seed {SEED} strategy {STRATEGY}: bin {np.round(bin_pos,3)} "
      f"pick-ee {np.round(ex.ee()[0],3)} head {np.round(head,3)}")

HI = max(head[2] + lift_h, ex.table_z + 0.30)

if STRATEGY == "repro":
    # the current over_table route
    leg([ex.ee()[0][0], ex.ee()[0][1], HI], 120, tag="leg1 up")
    leg([bin_xy[0], bin_xy[1], HI], 200, tag="leg2 over bin")
    leg([bin_xy[0], bin_xy[1], head[2] + lift_h], 250, tag="leg3 down")
elif STRATEGY == "A":
    # climb higher than HI, then traverse, then descend
    hi2 = HI + 0.14
    leg([ex.ee()[0][0], ex.ee()[0][1], hi2], 160, tag="climb")
    leg([bin_xy[0] * 0.5, bin_xy[1] * 0.5, hi2], 200, tag="halfway")
    leg([bin_xy[0], bin_xy[1], hi2], 220, tag="over bin high")
    leg([bin_xy[0], bin_xy[1], head[2] + lift_h], 250, tag="descend")
elif STRATEGY == "B":
    # reproduce the stall first, then retreat to a neutral bent-arm pose
    leg([ex.ee()[0][0], ex.ee()[0][1], HI], 120, tag="stall leg1")
    leg([bin_xy[0], bin_xy[1], HI], 200, tag="stall leg2")
    leg([0.16, 0.00, ex.table_z + 0.22], 150, tag="retreat neutral")
    leg([0.05, 0.10, ex.table_z + 0.30], 150, tag="swing mid")
    leg([bin_xy[0], bin_xy[1], ex.table_z + 0.30], 200, tag="re-approach")
    leg([bin_xy[0], bin_xy[1], head[2] + lift_h], 250, tag="descend")
elif STRATEGY == "C":
    # direct: no intermediate z-leg, straight to the bin at HI
    leg([bin_xy[0], bin_xy[1], HI], 250, tag="direct over bin")
    leg([bin_xy[0], bin_xy[1], head[2] + lift_h], 250, tag="descend")

err_xy = np.linalg.norm(ex.ee()[0][:2] - bin_xy)
print(f"final xy err to bin: {err_xy * 1000:.1f} mm")
