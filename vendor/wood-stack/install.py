#!/usr/bin/env python3
"""Install the wood-stacking assets/objects into the local LIBERO package.

Additive only: new files + one appended import line in LIBERO's object registry
(the original is backed up to *.bak_wood the first time).

The suite itself (bddl + benchmark registration) is generated separately by
scripts/gen_stack_suite.py.

Usage:  python install.py [--libero /path/to/LIBERO]
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

MARK_OBJ = "from .custom_wood_objects import *"


def backup(p: pathlib.Path, tag=".bak_wood"):
    b = p.with_name(p.name + tag)
    if not b.exists():
        shutil.copyfile(p, b)
        print(f"    backup -> {b.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--libero", default=str(DEFAULT_LIBERO))
    args = ap.parse_args()

    root = pathlib.Path(args.libero)
    pkg = root / "libero" / "libero"
    if not (pkg / "envs" / "objects").is_dir():
        sys.exit(f"cannot find LIBERO package under {pkg}")

    # 1. assets ------------------------------------------------------------
    src_assets = HERE / "assets" / "custom_wood"
    if not src_assets.is_dir():
        sys.exit("run gen_assets.py first (assets/custom_wood missing)")
    dst_assets = pkg / "assets" / "custom_wood"
    if dst_assets.exists():
        shutil.rmtree(dst_assets)
    shutil.copytree(src_assets, dst_assets)
    print(f"[1] assets  -> {dst_assets}")

    # 2. object module -----------------------------------------------------
    dst_mod = pkg / "envs" / "objects" / "custom_wood_objects.py"
    shutil.copyfile(HERE / "libero_wood_objects.py", dst_mod)
    print(f"[2] module  -> {dst_mod}")

    init_py = pkg / "envs" / "objects" / "__init__.py"
    txt = init_py.read_text()
    if MARK_OBJ not in txt:
        backup(init_py)
        if "from .custom_bolt_objects import *" in txt:
            anchor = "from .custom_bolt_objects import *"
        else:
            anchor = "from .turbosquid_objects import *"
        txt = txt.replace(anchor, f"{anchor}\n{MARK_OBJ}")
        init_py.write_text(txt)
        print(f"[2] registry patched -> {init_py.name}")
    else:
        print("[2] registry already patched")

    print("\ninstall done.")


if __name__ == "__main__":
    main()
