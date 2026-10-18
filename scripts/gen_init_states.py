#!/usr/bin/env python3
"""Sample `.pruned_init` initial states for a suite (LIBERO's native format).

    python scripts/gen_init_states.py --suite libero_bolt_v2 --num 50

Every state is a physically valid, non-overlapping placement sampled by LIBERO's
own region sampler, so the evaluation protocol (seed -> initial state) is
reproducible and identical across code versions.
"""
import argparse
import gc
import pathlib
import sys

import numpy as np
import torch

LIBERO = "/home/wei/work/g05/LIBERO-master"
sys.path.insert(0, LIBERO)

from libero.libero import get_libero_path  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="libero_bolt_v2")
    ap.add_argument("--num", type=int, default=50)
    args = ap.parse_args()

    bddl_dir = pathlib.Path(get_libero_path("bddl_files")) / args.suite
    init_dir = pathlib.Path(get_libero_path("init_states")) / args.suite
    init_dir.mkdir(parents=True, exist_ok=True)
    for old in init_dir.glob("*.pruned_init"):
        old.unlink()
    bddls = sorted(bddl_dir.glob("*.bddl"))
    if not bddls:
        sys.exit(f"no bddl in {bddl_dir}")

    for k, bddl in enumerate(bddls):
        out = init_dir / f"{bddl.stem}.pruned_init"
        if out.exists():
            print(f"  {bddl.stem[:58]:58s} skip (exists)")
            continue
        # EGL contexts leak across iterations; build each env behind a retry and
        # collect garbage between tasks.
        env = None
        for retry in range(3):
            try:
                env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=64,
                                         camera_widths=64)
                break
            except Exception as exc:  # noqa: BLE001
                print(f"    construct failed ({type(exc).__name__}), retry {retry + 1}")
                gc.collect()
        if env is None:
            print(f"  {bddl.stem[:58]:58s} SKIPPED (cannot construct env)")
            continue
        states, attempts, seed = [], 0, 1000 * k
        while len(states) < args.num and attempts < args.num * 10:
            seed += 1
            attempts += 1
            try:
                env.seed(seed)
                env.reset()
            except Exception as exc:  # noqa: BLE001 - sampler can reject a draw
                print(f"    reset failed ({type(exc).__name__}), retry")
                continue
            states.append(np.asarray(env.get_sim_state()).copy())
        env.close()
        del env
        gc.collect()
        torch.save(np.array(states), out)
        print(f"  {bddl.stem[:58]:58s} {len(states):3d} states")
    print(f"wrote {init_dir}")


if __name__ == "__main__":
    main()
