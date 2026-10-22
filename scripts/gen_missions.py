#!/usr/bin/env python3
"""Generate config/missions.json from the bddl goal of every task in a suite.

This is the "task protocol" binding: which object must end up in which bin for
each task index. Derived mechanically from the simulator's own goal spec so it
cannot drift from the scene definition.

    MUJOCO_GL=egl PYTHONPATH=<project>:<LIBERO>:... python scripts/gen_missions.py
"""
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _paths import libero_root  # noqa: E402

LIBERO = str(libero_root())
sys.path.insert(0, LIBERO)

from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parents[1] / "config" / "missions.json"
GOAL_RE = re.compile(r"\(In\s+(\S+)\s+(\S+?)_contain_region\)")


def main(suites):
    root = pathlib.Path(get_libero_path("bddl_files"))
    # merge: never drop suites that were generated earlier
    data = json.loads(OUT.read_text()) if OUT.exists() else {}
    for suite_name in suites:
        suite = get_benchmark_dict()[suite_name]()
        per_task = {}
        for i in range(suite.get_num_tasks()):
            task = suite.get_task(i)
            bddl = root / suite_name / task.bddl_file
            text = bddl.read_text()
            pairs = [{"object": obj, "bin": f"{bin_}"} for obj, bin_ in GOAL_RE.findall(text)]
            per_task[str(i)] = pairs
            print(f"{suite_name}[{i:2d}] {task.language[:52]:52s} {pairs}")
        data[suite_name] = per_task
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["libero_bolt"])
