#!/usr/bin/env python3
"""Where exactly are the fingers when the grasp closes? Compare the ground-truth
grasp point with the vision one, and print finger/pad world positions."""
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

from agent.skills.expert import Expert  # noqa: E402
from agent.skills.perception import perceive  # noqa: E402

SUITE, TASK, SEED = "libero_bolt_v2", 0, 1000
suite = get_benchmark_dict()[SUITE]()
task = suite.get_task(TASK)
bddl = pathlib.Path(get_libero_path("bddl_files")) / SUITE / task.bddl_file
env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=256, camera_widths=256,
                         horizon=1200, camera_depths=True)
env.seed(SEED)
obs = env.reset()
ex = Expert(env)
last = {"obs": obs}
ex.recorder = lambda o, a: last.__setitem__("obs", o)
sim = env.env.sim
m = sim.model

finger_bodies = [m.body_id2name(i) for i in range(m.nbody) if "finger" in m.body_id2name(i)]
pad_geoms = [m.geom_id2name(i) for i in range(m.ngeom)
             if m.geom_id2name(i) and ("finger" in m.geom_id2name(i) or "pad" in m.geom_id2name(i))]
print("finger bodies:", finger_bodies)
print("pad geoms:", pad_geoms)
for i in range(m.ngeom):
    nm = m.geom_id2name(i)
    if nm in pad_geoms:
        print(f"  {nm} size={np.round(m.geom_size[i], 4)} pos={np.round(m.geom_pos[i], 4)}")

scene = perceive(last["obs"], sim)
ex.vision = scene
name = "bolt_large_1"
gp_v = scene.grasp_point(name)
ex.vision = None
gp_gt = ex.grasp_point(name)
print(f"grasp point  vision={np.round(gp_v, 4)}  truth={np.round(gp_gt, 4)}")
print(f"bolt truth pos={np.round(ex.body_pos(name), 4)}")
ex.vision = scene

axis = ex.bolt_axis(name)
Rg = ex.grasp_orientation(axis, R_cur=ex.ee()[1])
print("vision axis", np.round(axis, 3), "R_grasp cols", np.round(Rg, 3).tolist())
ex.vision = None
axis_gt = ex.bolt_axis(name)
print("truth  axis", np.round(axis_gt, 3))
ex.vision = scene

target = gp_v
ex.move_to(target + np.array([0, 0, 0.10]), Rg, grip=-1.0, max_steps=120)
print("after pre-grasp ee", np.round(ex.ee()[0], 4))
err = ex.move_to(target, Rg, grip=-1.0, tol_p=0.006, max_steps=80)
print("after descend ee", np.round(ex.ee()[0], 4), "err", np.round(err, 4))
for nm in finger_bodies:
    print(f"  {nm} pos={np.round(sim.data.body_xpos[m.body_name2id(nm)], 4)}")
for i in range(m.ngeom):
    nm = m.geom_id2name(i)
    if nm in pad_geoms:
        print(f"  geom {nm} xpos={np.round(sim.data.geom_xpos[i], 4)}")
print("EE site:", np.round(ex.r.eef_site_id and sim.data.site_xpos[ex.r.eef_site_id], 4))
