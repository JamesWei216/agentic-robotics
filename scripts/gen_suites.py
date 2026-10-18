#!/usr/bin/env python3
"""Generate the two competition task suites.

  libero_bolt_v2     main task  : 2 bolts + 2 bins, workcell designed so every
                                  target stays inside the arm's vertical-grasp
                                  reachable set (that is what fixes the t0/t4
                                  unreachable-corner failures)
  libero_bolt_multi  variant    : same workcell, 4 bolts (2 small + 2 large),
                                  same classification rule, re-arranged positions
                                  -> the agent needs ZERO code changes

Outputs .bddl files into <LIBERO>/bddl_files/<suite>/ and registers the suites in
LIBERO's benchmark registry (append-only, marker guarded).

Run with the GalaxeaVLA venv python, from the project root:
    MUJOCO_GL=egl PYTHONPATH=<proj>:<LIBERO> python scripts/gen_suites.py
"""
import pathlib
import re
import shutil
import sys

import numpy as np

LIBERO = "/home/wei/work/g05/LIBERO-master"
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

# ------------------------------------------------------------------ region jitter
# LIBERO's TableRegionSampler shrinks the region by the object's horizontal
# radius before sampling (base_region_sampler._sample_x: minimum += r,
# maximum -= r). The *effective* jitter is therefore |half_len - r|: if the region
# is narrower than the object, the bounds invert and the object scatters over
# +-(r - half_len) -- silently, far outside the designed workcell. Measured
# consequence (2026-10-18): bins with half_len 8 mm and r 65-95 mm scattered
# +-57-87 mm, landing outside the reachable band and taking whole episodes down.
# So regions are now built as  half_len = radius + wanted jitter.
OBJ_RADIUS = {
    "bolt_small": 0.0310,
    "bolt_large": 0.0515,
    "parts_bin_blue": 0.0650,
    "parts_bin_red": 0.0950,
}
JITTER = {                      # v2 (single-object tasks)
    "bolt_small": 0.030,
    "bolt_large": 0.030,
    "parts_bin_blue": 0.010,
    "parts_bin_red": 0.010,
}
JITTER_MULTI = {                # variant suite: 6 objects on one table, tighter
    "bolt_small": 0.012,
    "bolt_large": 0.012,
    "parts_bin_blue": 0.008,
    "parts_bin_red": 0.008,
}


def region_half(kind: str, multi: bool = False) -> float:
    jitter = (JITTER_MULTI if multi else JITTER)[kind]
    return OBJ_RADIUS[kind] + jitter


# ---------------------------------------------------------------- reachability
# Measured on the real controller (see agent/skills/expert.py transfer()):
#   * a vertical (z-down) grasp can serve bins with |x| <= 0.17, y <= 0.20
#   * targets beyond that leave the arm saturated against a joint limit and the
#     release point is never reached, which is exactly the old t0/t4 failures.
# So the workcell below is *designed*: bins on a y=0.16..0.19 arc, bolts in the
# near half of the table.
V2_SCENES = [
    dict(name="bolt_v2_scene1", blue=(-0.15, 0.18), red=(0.15, 0.18),
         bolts={"bolt_small": [(-0.10, -0.03)], "bolt_large": [(0.10, -0.03)]}),
    # large bolt moved from (-0.10, 0.02) to (-0.10, -0.03) on 2026-10-18: at the
    # old spot seed 1005 sampled a pose that overlapped the red bin's placement
    # radius (RandomizationError in t2/t3). Verified with scripts/check_feasibility.
    dict(name="bolt_v2_scene2", blue=(0.15, 0.18), red=(-0.15, 0.18),
         bolts={"bolt_small": [(0.10, -0.05)], "bolt_large": [(-0.10, -0.03)]}),
    dict(name="bolt_v2_scene3", blue=(-0.15, 0.18), red=(0.15, 0.18),
         bolts={"bolt_small": [(-0.08, 0.03)], "bolt_large": [(-0.16, -0.10)]}),
    dict(name="bolt_v2_scene4", blue=(0.15, 0.18), red=(-0.15, 0.18),
         bolts={"bolt_small": [(0.05, -0.12)], "bolt_large": [(0.16, 0.00)]}),
    dict(name="bolt_v2_scene5", blue=(-0.14, 0.19), red=(0.14, 0.19),
         bolts={"bolt_small": [(-0.14, -0.06)], "bolt_large": [(0.14, -0.06)]}),
    dict(name="bolt_v2_scene6", blue=(0.15, 0.18), red=(-0.15, 0.18),
         bolts={"bolt_small": [(-0.06, -0.08)], "bolt_large": [(0.08, 0.04)]}),
    dict(name="bolt_v2_scene7", blue=(-0.15, 0.19), red=(0.15, 0.19),
         bolts={"bolt_small": [(0.02, -0.10)], "bolt_large": [(-0.12, -0.02)]}),
]

MULTI_SCENES = [
    dict(name="bolt_multi_scene1", blue=(-0.15, 0.18), red=(0.15, 0.18),
         bolts={"bolt_small": [(-0.12, -0.04), (0.03, -0.11)],
                "bolt_large": [(0.12, -0.03), (-0.04, 0.03)]}),
    dict(name="bolt_multi_scene2", blue=(0.15, 0.18), red=(-0.15, 0.18),
         bolts={"bolt_small": [(0.12, -0.05), (-0.05, 0.02)],
                "bolt_large": [(-0.12, -0.04), (0.04, -0.11)]}),
    dict(name="bolt_multi_scene3", blue=(-0.15, 0.18), red=(0.15, 0.18),
         bolts={"bolt_small": [(-0.10, 0.02), (0.10, -0.12)],
                "bolt_large": [(0.14, 0.00), (-0.02, -0.06)]}),
    dict(name="bolt_multi_scene4", blue=(0.15, 0.18), red=(-0.15, 0.18),
         bolts={"bolt_small": [(0.06, -0.09), (-0.14, -0.02)],
                "bolt_large": [(-0.14, -0.12), (0.13, -0.05)]}),
    dict(name="bolt_multi_scene5", blue=(-0.14, 0.19), red=(0.14, 0.19),
         bolts={"bolt_small": [(-0.13, -0.05), (0.13, -0.13)],
                "bolt_large": [(0.13, -0.04), (-0.13, -0.13)]}),
    # 4-bolt scene (t10): one large bolt moved 0.09,-0.12 -> 0.12,-0.145 so that
    # seed 1004 stops colliding with the small bolt at -0.07,-0.08 (2026-10-18).
    dict(name="bolt_multi_scene6", blue=(0.15, 0.18), red=(-0.15, 0.18),
         bolts={"bolt_small": [(-0.07, -0.08), (0.09, 0.03)],
                "bolt_large": [(0.12, -0.145), (-0.10, -0.01)]}),
    dict(name="bolt_multi_scene7", blue=(-0.15, 0.19), red=(0.15, 0.19),
         bolts={"bolt_small": [(0.04, -0.12), (-0.10, 0.01)],
                "bolt_large": [(-0.12, -0.07), (0.12, -0.09)]}),
]


def make_scene(spec, scene_type):
    """Dynamically build (and register) one InitialSceneTemplates subclass."""

    class _Scene(InitialSceneTemplates):
        def __init__(self):
            object_num_info = {
                "bolt_small": len(spec["bolts"]["bolt_small"]),
                "bolt_large": len(spec["bolts"]["bolt_large"]),
                "parts_bin_blue": 1,
                "parts_bin_red": 1,
            }
            super().__init__(workspace_name="main_table",
                             fixture_num_info={"table": 1},
                             object_num_info=object_num_info)

        def define_regions(self):
            multi = scene_type == "bolt_sorting_multi"
            regions = [
                ("parts_bin_blue", spec["blue"], region_half("parts_bin_blue", multi)),
                ("parts_bin_red", spec["red"], region_half("parts_bin_red", multi)),
            ]
            for cat in ("bolt_small", "bolt_large"):
                for i, xy in enumerate(spec["bolts"][cat], start=1):
                    regions.append((f"{cat}_{i}", xy, region_half(cat, multi)))
            for tag, xy, half in regions:
                self.regions.update(self.get_region_dict(
                    region_centroid_xy=list(xy),
                    region_name=f"{tag}_init_region",
                    target_name=self.workspace_name,
                    region_half_len=half,
                    yaw_rotation=(0.0, 0.0),
                ))
            self.xy_region_kwargs_list = get_xy_region_kwargs_list_from_regions_info(
                self.regions)

        @property
        def init_states(self):
            # bins first: the placement sampler avoids what is already placed
            states = [
                ("On", "parts_bin_blue_1", "main_table_parts_bin_blue_init_region"),
                ("On", "parts_bin_red_1", "main_table_parts_bin_red_init_region"),
            ]
            for cat in ("bolt_small", "bolt_large"):
                for i in range(1, len(spec["bolts"][cat]) + 1):
                    states.append(("On", f"{cat}_{i}",
                                   f"main_table_{cat}_{i}_init_region"))
            return states

    _Scene.__name__ = spec["name"].title().replace("_", "")
    _Scene.__qualname__ = _Scene.__name__
    register_mu(scene_type=scene_type)(_Scene)
    return _Scene


SMALL_LANG = [
    "pick up the small bolt and place it in the blue box",
    "put the small bolt in the blue box",
    "take the small bolt and drop it into the blue box",
    "move the small bolt into the blue box",
    "place the small bolt inside the blue box",
]
LARGE_LANG = [
    "pick up the large bolt and place it in the red box",
    "put the large bolt in the red box",
    "take the large bolt and drop it into the red box",
    "move the large bolt into the red box",
    "place the large bolt inside the red box",
]

MULTI_SMALL_LANG = [
    "put both small bolts in the blue box",
    "take the two small bolts and drop them into the blue box",
    "move both small bolts into the blue box",
    "place both small bolts inside the blue box",
    "sort both small bolts into the blue box",
]
MULTI_LARGE_LANG = [
    "put both large bolts in the red box",
    "take the two large bolts and drop them into the red box",
    "move both large bolts into the red box",
    "place both large bolts inside the red box",
    "sort both large bolts into the red box",
]


def single_tasks():
    tasks = []
    for i, spec in enumerate(V2_SCENES[:5]):
        tasks.append((SMALL_LANG[i], spec["name"], ["bolt_small_1", "parts_bin_blue_1"],
                      [("In", "bolt_small_1", "parts_bin_blue_1_contain_region")]))
        tasks.append((LARGE_LANG[i], spec["name"], ["bolt_large_1", "parts_bin_red_1"],
                      [("In", "bolt_large_1", "parts_bin_red_1_contain_region")]))
    tasks.append((
        "put the small bolt in the blue box and the large bolt in the red box",
        V2_SCENES[5]["name"],
        ["bolt_small_1", "bolt_large_1", "parts_bin_blue_1", "parts_bin_red_1"],
        [("In", "bolt_small_1", "parts_bin_blue_1_contain_region"),
         ("In", "bolt_large_1", "parts_bin_red_1_contain_region")],
    ))
    return tasks


def multi_tasks():
    tasks = []
    for i, spec in enumerate(MULTI_SCENES[:5]):
        tasks.append((MULTI_SMALL_LANG[i], spec["name"],
                      ["bolt_small_1", "bolt_small_2", "parts_bin_blue_1"],
                      [("In", "bolt_small_1", "parts_bin_blue_1_contain_region"),
                       ("In", "bolt_small_2", "parts_bin_blue_1_contain_region")]))
        tasks.append((MULTI_LARGE_LANG[i], spec["name"],
                      ["bolt_large_1", "bolt_large_2", "parts_bin_red_1"],
                      [("In", "bolt_large_1", "parts_bin_red_1_contain_region"),
                       ("In", "bolt_large_2", "parts_bin_red_1_contain_region")]))
    tasks.append((
        "put both small bolts in the blue box and both large bolts in the red box",
        MULTI_SCENES[5]["name"],
        ["bolt_small_1", "bolt_small_2", "bolt_large_1", "bolt_large_2",
         "parts_bin_blue_1", "parts_bin_red_1"],
        [("In", "bolt_small_1", "parts_bin_blue_1_contain_region"),
         ("In", "bolt_small_2", "parts_bin_blue_1_contain_region"),
         ("In", "bolt_large_1", "parts_bin_red_1_contain_region"),
         ("In", "bolt_large_2", "parts_bin_red_1_contain_region")],
    ))
    return tasks


# ---------------------------------------------------------------- registration
BENCH_PY = pathlib.Path(LIBERO) / "libero/libero/benchmark/__init__.py"
TASKMAP_PY = pathlib.Path(LIBERO) / "libero/libero/benchmark/libero_suite_task_map.py"

SUITE_SPECS = {
    "libero_bolt_v2": dict(scenes=V2_SCENES, scene_type="bolt_sorting_v2",
                           tasks=single_tasks, cls="LIBERO_BOLT_V2"),
    "libero_bolt_multi": dict(scenes=MULTI_SCENES, scene_type="bolt_sorting_multi",
                              tasks=multi_tasks, cls="LIBERO_BOLT_MULTI"),
}


def install_registration(suite, cls_name, task_names):
    mark_suite = f'    "{suite}",'
    txt = BENCH_PY.read_text()
    if mark_suite not in txt:
        txt = txt.replace('    "libero_bolt",\n', f'    "libero_bolt",\n{mark_suite}\n')
    mark_cls = f"class {cls_name}(Benchmark):"
    if mark_cls not in txt:
        txt += f'''

# --- {suite} benchmark (generated by agentic-robotics/scripts/gen_suites.py) ---
@register_benchmark
class {cls_name}(Benchmark):
    def __init__(self, task_order_index=0):
        super().__init__(task_order_index=task_order_index)
        self.name = "{suite}"
        self.tasks = list(task_maps[self.name].values())
        self.n_tasks = len(self.tasks)
'''
    BENCH_PY.write_text(txt)

    tmap = TASKMAP_PY.read_text()
    marker = f'libero_task_map["{suite}"]'
    if marker in tmap:
        # drop the previous block (marker comment .. closing bracket)
        pre, rest = tmap.split(f'# --- {suite} (generated', 1)
        _, post = rest.split("]\n", 1)
        tmap = pre.rstrip() + "\n" + post.lstrip("\n")
    block = [f'# --- {suite} (generated by agentic-robotics/scripts/gen_suites.py) ---',
             f'libero_task_map["{suite}"] = [']
    block += [f'    "{n}",' for n in task_names]
    block.append("]")
    TASKMAP_PY.write_text(tmap.rstrip() + "\n\n" + "\n".join(block) + "\n")
    print(f"  registered {suite} -> {cls_name} ({len(task_names)} tasks)")


def main():
    only = sys.argv[1:] or list(SUITE_SPECS)
    for suite, spec in SUITE_SPECS.items():
        if suite not in only:
            continue
        print(f"\n=== {suite} ===")
        # TASK_INFO is a module-level registry: without clearing it every suite
        # would re-emit the previous suite's tasks as well.
        TASK_INFO.clear()
        for scene in spec["scenes"]:
            make_scene(scene, spec["scene_type"])
        tasks = spec["tasks"]()
        for language, scene_name, ooi, goals in tasks:
            register_task_info(language, scene_name=scene_name,
                               objects_of_interest=ooi, goal_states=goals)

        tmp = pathlib.Path(f"/tmp/{suite}_bddl")
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        files, failures = generate_bddl_from_task_info(folder=str(tmp))
        print(f"  generated {len(files)} bddl, failures {len(failures)}")
        if failures:
            print("  FAILURES:", failures)

        out_dir = pathlib.Path(get_libero_path("bddl_files")) / suite
        out_dir.mkdir(parents=True, exist_ok=True)
        for f in out_dir.glob("*.bddl"):
            f.unlink()
        names = []
        for f in sorted(tmp.glob("*.bddl")):
            stem = re.sub(r"^BOLT_[A-Z0-9_]*SCENE\d+_", "", f.stem)
            stem = re.sub(r"^MULTI_[A-Z0-9_]*SCENE\d+_", "", stem)
            target = out_dir / f"{stem.lower()}.bddl"
            shutil.copyfile(f, target)
            names.append(target.stem)
        print(f"  wrote {len(names)} bddl -> {out_dir}")
        install_registration(suite, spec["cls"], names)


if __name__ == "__main__":
    main()
