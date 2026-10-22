#!/usr/bin/env python3
"""Render one preview per libero_bolt task and sanity-check the pixels.

Produces:
  preview_tasks_grid.png  -- contact sheet of all tasks (agentview, at reset)
  preview_<task>.png      -- per task agentview + wrist view
and prints colour statistics so we can tell the bins/bolts are really visible.
"""
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent

# approximate sRGB colours of our assets (after lighting they get darker)
REF = {
    "bin_small(blue)":   np.array([0.20, 0.42, 0.88]),
    "bin_large(orange)": np.array([0.95, 0.55, 0.10]),
    "bolt_small(steel)": np.array([0.78, 0.79, 0.82]),
    "bolt_large(dark)":  np.array([0.16, 0.16, 0.18]),
}


def count(img, ref, tol=0.22):
    d = np.linalg.norm(img.astype(np.float32) / 255.0 - ref, axis=-1)
    return int((d < tol).sum())


def main():
    suite = get_benchmark_dict()["libero_bolt"]()
    bddl_dir = pathlib.Path(get_libero_path("bddl_files")) / "libero_bolt"
    tiles = []
    for i in range(suite.get_num_tasks()):
        task = suite.get_task(i)
        env = OffScreenRenderEnv(bddl_file_name=bddl_dir / task.bddl_file,
                                 camera_heights=256, camera_widths=256)
        env.seed(3)
        env.reset()
        av = env.sim.render(camera_name="agentview", height=256, width=256)[::-1]
        wv = env.sim.render(camera_name="robot0_eye_in_hand", height=256,
                            width=256)[::-1]
        stats = {k: count(av, v) for k, v in REF.items()}
        print(f"[{i:2d}] {task.language[:52]:52s} px: "
              + "  ".join(f"{k.split('(')[0]}={v}" for k, v in stats.items()))
        tiles.append(av)
        try:
            import imageio
            imageio.imwrite(OUT / f"preview_task{i:02d}.png",
                            np.concatenate([av, wv], axis=1))
        except Exception as exc:                            # noqa: BLE001
            print("   imageio failed:", exc)
        env.close()

    try:
        import imageio
        rows = [np.concatenate(tiles[r * 4:(r + 1) * 4], axis=1) for r in range(3)]
        gap = np.zeros((256, 256 * 4 - len(tiles) * 256, 3), dtype=np.uint8) \
            if len(tiles) % 4 else None
        rows = []
        for r in range(0, len(tiles), 4):
            row = tiles[r:r + 4]
            while len(row) < 4:
                row.append(np.zeros_like(tiles[0]))
            rows.append(np.concatenate(row, axis=1))
        grid = np.concatenate(rows, axis=0)
        imageio.imwrite(OUT / "preview_tasks_grid.png", grid)
        print("\ngrid ->", OUT / "preview_tasks_grid.png", grid.shape)
    except Exception as exc:                               # noqa: BLE001
        print("grid failed:", exc)


if __name__ == "__main__":
    main()
