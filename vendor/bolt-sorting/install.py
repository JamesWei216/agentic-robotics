#!/usr/bin/env python3
"""Install the bolt-sorting assets/objects into the local LIBERO package.

Additive only: new files + three appended/inserted lines in LIBERO's registry
files (originals are backed up to *.bak_bolt the first time).

Usage:  python install.py [--libero /path/to/LIBERO-master]
"""
import argparse
import os
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_LIBERO = pathlib.Path(
    os.environ.get("AGENT_LIBERO_ROOT")
    or HERE.parents[1] / "third_party" / "LIBERO"
)
DEFAULT_GALAXEA = pathlib.Path(os.environ.get("AGENT_GALAXEA_ROOT", "/nonexistent"))

MARK_OBJ = "from .custom_bolt_objects import *"
MARK_SUITE = '# --- libero_bolt suite (installed by bolt-sorting/install.py) ---'
MARK_BENCH = '# --- LIBERO_BOLT benchmark (installed by bolt-sorting/install.py) ---'


def backup(p: pathlib.Path, tag=".bak_bolt"):
    b = p.with_name(p.name + tag)
    if not b.exists():
        shutil.copyfile(p, b)
        print(f"    backup -> {b.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--libero", default=str(DEFAULT_LIBERO))
    ap.add_argument("--galaxea", default=str(DEFAULT_GALAXEA))
    ap.add_argument("--skip-assets", action="store_true")
    ap.add_argument("--skip-galaxea", action="store_true",
                    help="skip patching GalaxeaVLA's eval utils (not needed for this project)")
    args = ap.parse_args()

    root = pathlib.Path(args.libero)
    pkg = root / "libero" / "libero"
    if not (pkg / "envs" / "objects").is_dir():
        sys.exit(f"cannot find LIBERO package under {pkg}")

    # 1. assets ------------------------------------------------------------
    src_assets = HERE / "assets" / "custom_bolt"
    if not src_assets.is_dir():
        sys.exit("run gen_assets.py first (assets/custom_bolt missing)")
    dst_assets = pkg / "assets" / "custom_bolt"
    if not args.skip_assets:
        if dst_assets.exists():
            shutil.rmtree(dst_assets)
        shutil.copytree(src_assets, dst_assets)
        print(f"[1] assets  -> {dst_assets}")

    # 2. object module -----------------------------------------------------
    dst_mod = pkg / "envs" / "objects" / "custom_bolt_objects.py"
    shutil.copyfile(HERE / "libero_bolt_objects.py", dst_mod)
    print(f"[2] module  -> {dst_mod}")

    init_py = pkg / "envs" / "objects" / "__init__.py"
    txt = init_py.read_text()
    if MARK_OBJ not in txt:
        backup(init_py)
        txt = txt.replace(
            "from .turbosquid_objects import *",
            f"from .turbosquid_objects import *\n{MARK_OBJ}",
        )
        init_py.write_text(txt)
        print(f"[2] registry patched -> {init_py.name}")
    else:
        print("[2] registry already patched")

    # 3. bddl task list in libero_suite_task_map.py ------------------------
    bddl_dir = pkg / "bddl_files" / "libero_bolt"
    if bddl_dir.is_dir():
        names = sorted(p.stem for p in bddl_dir.glob("*.bddl"))
        map_py = pkg / "benchmark" / "libero_suite_task_map.py"
        txt = map_py.read_text()
        if MARK_SUITE not in txt:
            backup(map_py)
            txt = txt.rstrip() + "\n"
        else:
            # regenerate the block (task list may have changed)
            txt = txt.split(MARK_SUITE)[0].rstrip() + "\n"
        block = [f"\n{MARK_SUITE}", 'libero_task_map["libero_bolt"] = [']
        block += [f'    "{n}",' for n in names]
        block.append("]")
        map_py.write_text(txt + "\n".join(block) + "\n")
        print(f"[3] task map patched with {len(names)} tasks")
    else:
        print("[3] no bddl yet -> run create_bolt_tasks.py, then re-run install.py")

    # 4. benchmark class ---------------------------------------------------
    bench = pkg / "benchmark" / "__init__.py"
    txt = bench.read_text()
    if MARK_BENCH not in txt:
        backup(bench)
        if '"libero_bolt"' not in txt.split("libero_suites = [")[1].split("]")[0]:
            txt = txt.replace(
                '    "libero_10",\n]',
                '    "libero_10",\n    "libero_bolt",\n]',
            )
        txt = txt.rstrip() + f'''


{MARK_BENCH}
@register_benchmark
class LIBERO_BOLT(Benchmark):
    """Custom bolt-sorting suite (all tasks, no fixed task order)."""

    def __init__(self, task_order_index=0):
        super().__init__(task_order_index=task_order_index)
        self.name = "libero_bolt"
        self.tasks = list(task_maps[self.name].values())
        self.n_tasks = len(self.tasks)
'''
        bench.write_text(txt)
        print(f"[4] benchmark patched -> {bench.name}")
    else:
        print("[4] benchmark already patched")

    # 4b. 兜底：libero_suites 里出现 "libero_bolt" 但 task map 没键会让 benchmark 导入直接 KeyError
    #     （发生在“先装对象注册、后生成 bddl”的中间态）→ 补一个空列表占位。
    map_py = pkg / "benchmark" / "libero_suite_task_map.py"
    mtxt = map_py.read_text()
    if 'libero_task_map["libero_bolt"]' not in mtxt:
        map_py.write_text(mtxt.rstrip() + '\n\nlibero_task_map["libero_bolt"] = []\n')
        print("[4b] task map placeholder added (libero_bolt = [])")

    # 5. eval client: max_steps for the new suite --------------------------
    utils = pathlib.Path(args.galaxea) / "experiments" / "libero" / "libero_eval_utils.py"
    if args.skip_galaxea:
        print("[5] skipped (galaxea)")
    elif utils.is_file():
        txt = utils.read_text()
        if '"libero_bolt"' not in txt:
            backup(utils)
            txt = txt.replace('        "libero_90": 400,\n',
                              '        "libero_90": 400,\n        "libero_bolt": 300,\n')
            utils.write_text(txt)
            print(f"[5] max_steps patched -> {utils.name}")
        else:
            print("[5] max_steps already patched")
    else:
        print(f"[5] eval utils not found at {utils}")

    print("\ninstall done.")


if __name__ == "__main__":
    main()
