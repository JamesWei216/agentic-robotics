#!/usr/bin/env python3
"""Generate .pruned_init initial states for the libero_bolt suite.

For every bddl in bddl_files/libero_bolt -> sample N randomized, physically
valid object placements and store `sim.get_state().flatten()` (the same format
the stock LIBERO init files use: torch-pickled numpy array, shape (N, D)).
"""
import argparse
import pathlib
import sys

import numpy as np
import torch

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

SUITE = "libero_bolt"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--num_states", type=int, default=50)
    args = ap.parse_args()

    bddl_dir = pathlib.Path(get_libero_path("bddl_files")) / SUITE
    init_dir = pathlib.Path(get_libero_path("init_states")) / SUITE
    init_dir.mkdir(parents=True, exist_ok=True)
    # drop stale init files from previous task iterations (task names may change)
    for old in init_dir.glob("*.pruned_init"):
        old.unlink()
    bddls = sorted(bddl_dir.glob("*.bddl"))
    if not bddls:
        sys.exit(f"no bddl files in {bddl_dir}")

    for k, bddl in enumerate(bddls):
        env = OffScreenRenderEnv(bddl_file_name=bddl,
                                 camera_heights=64, camera_widths=64)
        states = []
        attempts = 0
        seed = 1000 * k
        while len(states) < args.num_states and attempts < args.num_states * 10:
            seed += 1
            attempts += 1
            try:
                env.seed(seed)
                env.reset()
            except Exception as exc:                      # noqa: BLE001
                print(f"    reset failed ({type(exc).__name__}) - retry")
                continue
            states.append(np.asarray(env.get_sim_state()).copy())
        env.close()
        outp = init_dir / f"{bddl.stem}.pruned_init"
        torch.save(np.array(states), outp)
        print(f"  {bddl.stem[:60]:60s} {len(states):3d} states -> {outp.name}")
    print(f"\nwrote init states to {init_dir}")


if __name__ == "__main__":
    main()
