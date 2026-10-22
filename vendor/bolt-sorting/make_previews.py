#!/usr/bin/env python3
"""Render the task contact sheet + per-task previews (agentview | wrist)."""
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent


def main():
    import imageio
    for old in OUT.glob("preview_*.png"):
        old.unlink()
    suite = get_benchmark_dict()["libero_bolt"]()
    bd = pathlib.Path(get_libero_path("bddl_files")) / "libero_bolt"
    tiles = []
    for i in range(suite.get_num_tasks()):
        task = suite.get_task(i)
        env = OffScreenRenderEnv(bddl_file_name=bd / task.bddl_file,
                                 camera_heights=256, camera_widths=256)
        env.seed(3)
        env.reset()
        av = env.sim.render(camera_name="agentview", height=256, width=256)[::-1]
        wv = env.sim.render(camera_name="robot0_eye_in_hand", height=256,
                            width=256)[::-1]
        imageio.imwrite(OUT / f"preview_task{i:02d}.png",
                        np.concatenate([av, wv], axis=1))
        tiles.append(av)
        env.close()
    rows = []
    for r in range(0, len(tiles), 4):
        row = list(tiles[r:r + 4])
        while len(row) < 4:
            row.append(np.zeros_like(tiles[0]))
        rows.append(np.concatenate(row, axis=1))
    grid = np.concatenate(rows, axis=0)
    imageio.imwrite(OUT / "preview_tasks_grid.png", grid)
    imageio.imwrite(OUT / "preview_task00_pair.png",
                    np.concatenate(tiles[:2], axis=1))
    print("wrote", len(tiles) + 2, "previews;", grid.shape)


if __name__ == "__main__":
    main()
