#!/usr/bin/env python3
"""Check that specific (task, seed) pairs still reset without a placement error.

    python scripts/check_resets.py libero_bolt_multi 10:1003 2:1000 2:1006 ...
"""
import pathlib
import sys

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

suite_name = sys.argv[1] if len(sys.argv) > 1 else "libero_bolt_multi"
pairs = sys.argv[2:] or ["10:1003", "2:1000", "2:1006", "3:1000", "3:1007",
                         "4:1003", "4:1009", "5:1002", "5:1006"]
suite = get_benchmark_dict()[suite_name]()
bad = 0
for pair in pairs:
    t, s = (int(x) for x in pair.split(":"))
    task = suite.get_task(t)
    bddl = pathlib.Path(get_libero_path("bddl_files")) / suite_name / task.bddl_file
    try:
        env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=64,
                                 camera_widths=64)
        env.seed(s)
        env.reset()
        env.close()
        print(f"  {pair}: ok")
    except Exception as exc:                      # noqa: BLE001
        bad += 1
        print(f"  {pair}: {type(exc).__name__}: {exc}")
print(f"\n{len(pairs) - bad}/{len(pairs)} reset cleanly")
sys.exit(1 if bad else 0)
