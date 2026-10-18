#!/usr/bin/env python3
"""Vision-mode single episode with verbose primitive logs, following the mission
from config/missions.json (object -> bin pairs)."""
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

from agent.skills.expert import Expert, EpisodeDone  # noqa: E402
from agent.skills.perception import perceive  # noqa: E402

SUITE = sys.argv[1] if len(sys.argv) > 1 else "libero_bolt_v2"
TASK = int(sys.argv[2]) if len(sys.argv) > 2 else 1
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 1000

missions = json.loads(pathlib.Path("config/missions.json").read_text())
mission = missions[SUITE][str(TASK)]
print("mission:", mission)

suite = get_benchmark_dict()[SUITE]()
task = suite.get_task(TASK)
bddl = pathlib.Path(get_libero_path("bddl_files")) / SUITE / task.bddl_file
env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256,
                         horizon=2000, camera_depths=True)
env.seed(SEED)
obs = env.reset()
ex = Expert(env)
last = {"obs": obs}
ex.recorder = lambda o, a: last.__setitem__("obs", o)


def refresh():
    scene = perceive(last["obs"], env.env.sim)
    ex.vision = scene
    return scene


ex.refresh_vision = refresh
ex.last_obs = lambda: last["obs"]
scene = refresh()
for d in scene.summary():
    print("det:", d)
skipped = None
try:
    for item in mission:
        obj, box = item["object"], item["bin"]
        print(f"\n== {obj} -> {box}")
        def gt(n):
            try:
                return np.round(ex.u.sim.data.body_xpos[ex.u.obj_body_id[n]], 3)
            except Exception:
                return "?"
        refresh()
        print("   [gt] before grasp:", {k: list(gt(k)) for k in ("bolt_small_1", "parts_bin_blue_1")})
        ok, glog = ex.grasp(obj, verbose=True)
        print("   [gt] after grasp:", {k: list(gt(k)) for k in ("bolt_small_1", "parts_bin_blue_1")})
        print("   grasp_ok:", ok)
        if not ok:
            skipped = obj
            break
        ok2, tlog = ex.transfer(box, verbose=True)
        print("   [gt] after transfer:", {k: list(gt(k)) for k in ("bolt_small_1", "parts_bin_blue_1")})
        print("   transfer_ok:", ok2, "predicate:", env.env._check_success())
except EpisodeDone:
    print("!! env terminated")
print("\nsuccess predicate:", env.env._check_success(), "steps:", env.env.timestep)

print("\n[oracle] final truth positions:")
for n in ("bolt_small_1", "bolt_large_1", "parts_bin_blue_1", "parts_bin_red_1"):
    try:
        print("  ", n, np.round(ex.u.sim.data.body_xpos[ex.u.obj_body_id[n]], 4))
    except Exception as e:
        print("  ", n, "?", e)
for bn in ("parts_bin_blue_1", "parts_bin_red_1"):
    sid = env.env.sim.model.site_name2id(f"{bn}_contain_region")
    print("   region", bn, np.round(env.env.sim.data.site_xpos[sid], 4),
          "size", np.round(env.env.sim.model.site_size[sid], 4))
