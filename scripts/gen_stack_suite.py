#!/usr/bin/env python3
"""Generate the stacking (码垛) task suite `libero_wood_stack`.

Why this suite exists: 赛题加分 c asks for the *same* Agent framework to switch
between 码垛 and 分拣 with a **quantifiable** change cost.  So the stacking suite
deliberately reuses everything it can (workcell = main_table, assets pipeline,
init-state sampler, missions protocol, safety layer, the whole plan→code→run→
diagnose loop) and only adds:

    * one asset (40 mm wooden cube) + its object registration,
    * this suite generator,
    * one new primitive branch (`place_on_top`) in the skill layer.

Success is judged by LIBERO's native `On(top, base)` predicate (base z <= top z,
geometric contact, xy distance < 30 mm) — nothing is hand-scored.

垛型 (stack patterns) covered:
    t0-t4   3-block single tower   : On(b2,b1) + On(b3,b2)
    t5-t9   2-block tower          : On(b2,b1)
    t10     4-block double column  : On(b2,b1) + On(b4,b3)   (long horizon)

Run (from the project root, with the pipeline env):
    MUJOCO_GL=egl PYTHONPATH=<proj>:<LIBERO> python scripts/gen_stack_suite.py
"""
import pathlib
import re
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _paths import libero_root  # noqa: E402

LIBERO = str(libero_root())
sys.path.insert(0, LIBERO)

from libero.libero import get_libero_path  # noqa: E402
from libero.libero.utils.bddl_generation_utils import (  # noqa: E402
    get_xy_region_kwargs_list_from_regions_info,
)
from libero.libero.utils.mu_utils import register_mu, InitialSceneTemplates  # noqa: E402
from libero.libero.utils.task_generation_utils import (  # noqa: E402
    register_task_info, generate_bddl_from_task_info, TASK_INFO,
)
import libero.libero.envs  # noqa: E402,F401  (registers object categories)

BLOCK_EDGE = 0.040
BLOCK_R = BLOCK_EDGE / 2 ** 0.5          # 0.0283 m, the half-diagonal (conservative)

# Effective region jitter = |half_len - r| (see the note in gen_suites.py): the
# sampler shrinks the range by the object's horizontal radius, so the half length
# is built as  radius + wanted jitter.  Narrow jitter here because a stack must
# stay inside the arm's vertical-grasp reachable set at two block heights.
JITTER_BASE = 0.020       # the block that will be stacked on: keep it central
JITTER_PICK = 0.020       # blocks waiting to be picked up

# Reachable "comfort band" (measured 2026-10-23 on this arm/controller): a cube
# grasped at x = +0.13 leaves joint 4 at its -0.07 rad limit (elbow straight) and
# from there the Cartesian controller cannot retract the arm at all — q4 after the
# grasp was -0.115 and every placement then stalled ~145 mm short.  The same grasp
# at x <= +0.10 gives q4 = -1.2..-1.6 (bent elbow) and places within 2-4 mm.  The
# left side is more forgiving (robot base sits at x ~ -0.21), so pick cells stay in
# -0.15 <= x <= +0.09 and the stack zone in |x| <= 0.07, y ~ 0.10-0.13.


def half(jitter: float) -> float:
    return BLOCK_R + jitter


# --------------------------------------------------------------- scene table
# positions are table coordinates in metres: x lateral, +y away from the robot
TOWER3_SCENES = [
    dict(name="wood_stack_scene1", blocks=[((-0.02, 0.12), JITTER_BASE),
                                           ((-0.13, -0.06), JITTER_PICK),
                                           ((0.08, -0.06), JITTER_PICK)]),
    dict(name="wood_stack_scene2", blocks=[((0.02, 0.10), JITTER_BASE),
                                           ((-0.11, -0.12), JITTER_PICK),
                                           ((0.09, -0.02), JITTER_PICK)]),
    dict(name="wood_stack_scene3", blocks=[((-0.06, 0.13), JITTER_BASE),
                                           ((0.07, -0.10), JITTER_PICK),
                                           ((-0.15, -0.02), JITTER_PICK)]),
    dict(name="wood_stack_scene4", blocks=[((0.05, 0.12), JITTER_BASE),
                                           ((-0.14, -0.08), JITTER_PICK),
                                           ((0.08, -0.13), JITTER_PICK)]),
    dict(name="wood_stack_scene5", blocks=[((0.00, 0.13), JITTER_BASE),
                                           ((-0.12, -0.02), JITTER_PICK),
                                           ((0.09, -0.09), JITTER_PICK)]),
]
TOWER2_SCENES = [
    dict(name="wood_stack_scene6", blocks=[((-0.03, 0.12), JITTER_BASE),
                                           ((0.08, -0.08), JITTER_PICK)]),
    dict(name="wood_stack_scene7", blocks=[((0.03, 0.11), JITTER_BASE),
                                           ((-0.12, -0.10), JITTER_PICK)]),
    dict(name="wood_stack_scene8", blocks=[((-0.05, 0.13), JITTER_BASE),
                                           ((0.09, -0.03), JITTER_PICK)]),
    dict(name="wood_stack_scene9", blocks=[((0.04, 0.12), JITTER_BASE),
                                           ((-0.08, -0.12), JITTER_PICK)]),
    dict(name="wood_stack_scene10", blocks=[((0.00, 0.10), JITTER_BASE),
                                            ((0.09, -0.11), JITTER_PICK)]),
]
FOUR_SCENE = dict(name="wood_stack_scene11",
                  blocks=[((-0.07, 0.11), JITTER_BASE),          # base, left column
                          ((-0.11, -0.09), JITTER_PICK),         # -> on block 1
                          ((0.04, 0.11), JITTER_BASE),           # base, right column
                          ((0.08, -0.11), JITTER_PICK)])         # -> on block 3

SCENES = TOWER3_SCENES + TOWER2_SCENES + [FOUR_SCENE]
SCENE_TYPE = "wood_stacking"


def make_scene(spec):
    """Dynamically build (and register) one InitialSceneTemplates subclass."""

    class _Scene(InitialSceneTemplates):
        def __init__(self):
            super().__init__(workspace_name="main_table",
                             fixture_num_info={"table": 1},
                             object_num_info={"wood_block": len(spec["blocks"])})

        def define_regions(self):
            for i, (xy, jit) in enumerate(spec["blocks"], start=1):
                self.regions.update(self.get_region_dict(
                    region_centroid_xy=list(xy),
                    region_name=f"wood_block_{i}_init_region",
                    target_name=self.workspace_name,
                    region_half_len=half(jit),
                    yaw_rotation=(0.0, 0.0),
                ))
            self.xy_region_kwargs_list = get_xy_region_kwargs_list_from_regions_info(
                self.regions)

        @property
        def init_states(self):
            return [("On", f"wood_block_{i}", f"main_table_wood_block_{i}_init_region")
                    for i in range(1, len(spec["blocks"]) + 1)]

    _Scene.__name__ = spec["name"].title().replace("_", "")
    _Scene.__qualname__ = _Scene.__name__
    register_mu(scene_type=SCENE_TYPE)(_Scene)
    return _Scene


# ------------------------------------------------------------------- tasks
# (language, scene, objects of interest, goal states)
TOWER3_LANG = [
    "stack the three wooden blocks into a single tower",
    "build a three block tower with the wooden blocks",
    "place the two loose wooden blocks on top of the base block",
    "make a tower of three wooden blocks",
    "put every wooden block on top of the one below it",
]
TOWER2_LANG = [
    "stack the wooden block on top of the other wooden block",
    "put one wooden block on top of the other one",
    "build a two block tower with the wooden blocks",
    "place the loose wooden block on top of the base block",
    "stack one wooden block onto the other wooden block",
]


def tasks():
    out = []
    for spec, lang in zip(TOWER3_SCENES, TOWER3_LANG):
        out.append((lang, spec["name"],
                    ["wood_block_1", "wood_block_2", "wood_block_3"],
                    [("On", "wood_block_2", "wood_block_1"),
                     ("On", "wood_block_3", "wood_block_2")]))
    for spec, lang in zip(TOWER2_SCENES, TOWER2_LANG):
        out.append((lang, spec["name"],
                    ["wood_block_1", "wood_block_2"],
                    [("On", "wood_block_2", "wood_block_1")]))
    out.append(("build two towers of two wooden blocks each", FOUR_SCENE["name"],
                ["wood_block_1", "wood_block_2", "wood_block_3", "wood_block_4"],
                [("On", "wood_block_2", "wood_block_1"),
                 ("On", "wood_block_4", "wood_block_3")]))
    return out


# ------------------------------------------------------------- registration
SUITE = "libero_wood_stack"
CLS = "LIBERO_WOOD_STACK"
BENCH_PY = pathlib.Path(LIBERO) / "libero/libero/benchmark/__init__.py"
TASKMAP_PY = pathlib.Path(LIBERO) / "libero/libero/benchmark/libero_suite_task_map.py"


def install_registration(task_names):
    mark_suite = f'    "{SUITE}",'
    txt = BENCH_PY.read_text()
    # Insert into the `libero_suites = [...]` literal (task_maps is built from it at
    # import time, so a suite that is missing there raises KeyError later).
    if mark_suite not in txt:
        head, sep, tail = txt.partition("libero_suites = [")
        assert sep, "cannot find libero_suites in benchmark/__init__.py"
        block, sep2, rest = tail.partition("]")
        block = block.rstrip("\n") + f'\n{mark_suite}\n'
        txt = head + sep + block + sep2 + rest
        BENCH_PY.write_text(txt)
        print(f"  registered suite name in {BENCH_PY.name}")
        assert mark_suite in BENCH_PY.read_text(), "suite name insert failed"

    mark_cls = f"class {CLS}(Benchmark):"
    txt = BENCH_PY.read_text()
    if mark_cls not in txt:
        txt += f'''

# --- {SUITE} benchmark (generated by agentic-robotics/scripts/gen_stack_suite.py) ---
@register_benchmark
class {CLS}(Benchmark):
    def __init__(self, task_order_index=0):
        super().__init__(task_order_index=task_order_index)
        self.name = "{SUITE}"
        self.tasks = list(task_maps[self.name].values())
        self.n_tasks = len(self.tasks)
'''
        BENCH_PY.write_text(txt)

    tmap = TASKMAP_PY.read_text()
    marker = f'libero_task_map["{SUITE}"]'
    if marker in tmap:
        pre, rest = tmap.split(f'# --- {SUITE} (generated', 1)
        _, post = rest.split("]\n", 1)
        tmap = pre.rstrip() + "\n" + post.lstrip("\n")
    block = [f'# --- {SUITE} (generated by agentic-robotics/scripts/gen_stack_suite.py) ---',
             f'libero_task_map["{SUITE}"] = [']
    block += [f'    "{n}",' for n in task_names]
    block.append("]")
    TASKMAP_PY.write_text(tmap.rstrip() + "\n\n" + "\n".join(block) + "\n")
    print(f"  registered {SUITE} -> {CLS} ({len(task_names)} tasks)")


def main():
    TASK_INFO.clear()
    for spec in SCENES:
        make_scene(spec)
    for language, scene_name, ooi, goals in tasks():
        register_task_info(language, scene_name=scene_name,
                           objects_of_interest=ooi, goal_states=goals)

    tmp = pathlib.Path(f"/tmp/{SUITE}_bddl")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    files, failures = generate_bddl_from_task_info(folder=str(tmp))
    print(f"generated {len(files)} bddl, failures {failures}")
    if failures:
        print("FAILURES:", failures)

    out_dir = pathlib.Path(get_libero_path("bddl_files")) / SUITE
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("*.bddl"):
        f.unlink()
    names = []
    # natural scene order (plain string sort puts SCENE10 before SCENE2, which makes
    # the task indices random with respect to the designed pattern order)
    def _scene_key(p):
        m = re.search(r"SCENE(\d+)_", p.stem)
        return (int(m.group(1)) if m else 999, p.stem)

    for f in sorted(tmp.glob("*.bddl"), key=_scene_key):
        stem = re.sub(r"^WOOD_[A-Z0-9_]*SCENE\d+_", "", f.stem)
        target = out_dir / f"{stem.lower()}.bddl"
        shutil.copyfile(f, target)
        names.append(target.stem)
    print(f"wrote {len(names)} bddl -> {out_dir}")
    install_registration(names)


if __name__ == "__main__":
    main()
