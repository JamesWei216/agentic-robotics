#!/usr/bin/env python3
"""Build the LIBERO "libero_bolt" task suite: scene templates + task registry.

Run with the GalaxeaVLA venv python, after install.py has copied
`libero_bolt_objects.py` into the LIBERO package (the scene templates need the
new object categories to be registered).

Writes .bddl files into  <LIBERO>/libero/libero/bddl_files/libero_bolt/
"""
import os
import pathlib
import re
import shutil
import sys
import numpy as np

# --- make sure the installed LIBERO package (with our objects) is importable
LIBERO = os.environ.get("AGENT_LIBERO_ROOT") or str(
    pathlib.Path(__file__).resolve().parents[2] / "third_party" / "LIBERO"
)
sys.path.insert(0, LIBERO)

from libero.libero.utils.mu_utils import register_mu, InitialSceneTemplates  # noqa: E402
from libero.libero.utils.bddl_generation_utils import (  # noqa: E402
    get_xy_region_kwargs_list_from_regions_info,
)
from libero.libero.utils.task_generation_utils import (  # noqa: E402
    register_task_info,
    generate_bddl_from_task_info,
)
import libero.libero.envs  # noqa: E402,F401  (registers objects)
from libero.libero import get_libero_path  # noqa: E402

SUITE = "libero_bolt"

# ---------------------------------------------------------------------------
# Layouts.  Each scene keeps BOTH bolts and BOTH bins on the table; the task
# decides which bolt has to end up in which bin.
#   small_bin / large_bin : (x, y) centroid on the table, +y is away from the robot
#   bolt_small / bolt_large : (x, y) centroid of the bolt's spawn region
# ---------------------------------------------------------------------------
SCENES = [
    dict(name="bolt_scene1", blue_bin=(-0.15, 0.22), red_bin=(0.15, 0.22),
         bolt_small=(-0.10, -0.03), bolt_large=(0.10, -0.03)),
    dict(name="bolt_scene2", blue_bin=(0.15, 0.22), red_bin=(-0.15, 0.22),
         bolt_small=(0.10, -0.05), bolt_large=(-0.10, 0.02)),
    dict(name="bolt_scene3", blue_bin=(-0.15, 0.22), red_bin=(0.15, 0.22),
         bolt_small=(-0.08, 0.03), bolt_large=(-0.16, -0.12)),
    dict(name="bolt_scene4", blue_bin=(0.15, 0.22), red_bin=(-0.15, 0.22),
         bolt_small=(0.05, -0.12), bolt_large=(0.16, 0.00)),
    dict(name="bolt_scene5", blue_bin=(-0.16, 0.20), red_bin=(0.16, 0.20),
         bolt_small=(-0.14, -0.06), bolt_large=(0.14, -0.06)),
    dict(name="bolt_scene6", blue_bin=(0.15, 0.22), red_bin=(-0.15, 0.22),
         bolt_small=(-0.06, -0.08), bolt_large=(0.08, 0.04)),
]

BIN_HALF = 0.06    # placement jitter +-0.035 m
BOLT_HALF = 0.08


def make_scene(spec):
    """Dynamically build (and register) one InitialSceneTemplates subclass."""

    class _BoltScene(InitialSceneTemplates):
        def __init__(self):
            fixture_num_info = {"table": 1}
            object_num_info = {
                "bolt_small": 1,
                "bolt_large": 1,
                "parts_bin_blue": 1,
                "parts_bin_red": 1,
            }
            super().__init__(
                workspace_name="main_table",
                fixture_num_info=fixture_num_info,
                object_num_info=object_num_info,
            )

        def define_regions(self):
            for tag, xy, half in (
                ("parts_bin_blue", spec["blue_bin"], BIN_HALF),
                ("parts_bin_red", spec["red_bin"], BIN_HALF),
                ("bolt_small", spec["bolt_small"], BOLT_HALF),
                ("bolt_large", spec["bolt_large"], BOLT_HALF),
            ):
                self.regions.update(
                    self.get_region_dict(
                        region_centroid_xy=list(xy),
                        region_name=f"{tag}_init_region",
                        target_name=self.workspace_name,
                        region_half_len=half,
                        yaw_rotation=(0.0, 0.0),
                    )
                )
            self.xy_region_kwargs_list = get_xy_region_kwargs_list_from_regions_info(
                self.regions
            )

        @property
        def init_states(self):
            # bins first: the placement sampler checks overlaps against what is
            # already placed, so the bolts avoid the bins.
            return [
                ("On", "parts_bin_blue_1", "main_table_parts_bin_blue_init_region"),
                ("On", "parts_bin_red_1", "main_table_parts_bin_red_init_region"),
                ("On", "bolt_small_1", "main_table_bolt_small_init_region"),
                ("On", "bolt_large_1", "main_table_bolt_large_init_region"),
            ]

    _BoltScene.__name__ = spec["name"].title().replace("_", "")
    _BoltScene.__qualname__ = _BoltScene.__name__
    register_mu(scene_type="bolt_sorting")(_BoltScene)
    return _BoltScene


# distinct phrasing per layout keeps every task name (== bddl filename) unique
# 小螺栓 -> 蓝盒；大螺栓 -> 红盒
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

TASKS = []   # (language, scene_name, objects_of_interest, goal_states)

for i, spec in enumerate(SCENES[:5]):
    TASKS.append((
        SMALL_LANG[i], spec["name"],
        ["bolt_small_1", "parts_bin_blue_1"],
        [("In", "bolt_small_1", "parts_bin_blue_1_contain_region")],
    ))
    TASKS.append((
        LARGE_LANG[i], spec["name"],
        ["bolt_large_1", "parts_bin_red_1"],
        [("In", "bolt_large_1", "parts_bin_red_1_contain_region")],
    ))

# one long-horizon task: sort BOTH bolts into their matching boxes
TASKS.append((
    "put the small bolt in the blue box and the large bolt in the red box",
    SCENES[5]["name"],
    ["bolt_small_1", "bolt_large_1", "parts_bin_blue_1", "parts_bin_red_1"],
    [
        ("In", "bolt_small_1", "parts_bin_blue_1_contain_region"),
        ("In", "bolt_large_1", "parts_bin_red_1_contain_region"),
    ],
))


def main():
    for spec in SCENES:
        make_scene(spec)

    for language, scene_name, ooi, goals in TASKS:
        register_task_info(language, scene_name=scene_name,
                           objects_of_interest=ooi, goal_states=goals)

    tmp = pathlib.Path("/tmp/bolt_bddl_gen")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    files, failures = generate_bddl_from_task_info(folder=str(tmp))
    print(f"generated: {len(files)}  failures: {len(failures)}")
    if failures:
        print("FAILURES:", failures)

    out_dir = pathlib.Path(get_libero_path("bddl_files")) / SUITE
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in sorted(out_dir.glob("*.bddl")):
        f.unlink()
    for f in sorted(tmp.glob("*.bddl")):
        # LIBERO-1 style naming: lowercase language, no scene prefix
        stem = re.sub(r"^BOLT_SCENE\d+_", "", f.stem)
        target = out_dir / f"{stem.lower()}.bddl"
        shutil.copyfile(f, target)
        print("  ->", target.name)
    print(f"\nwrote {len(list(out_dir.glob('*.bddl')))} bddl files to {out_dir}")


if __name__ == "__main__":
    main()
