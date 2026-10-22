#!/usr/bin/env python3
"""Lighting-independent check that the bolt-sorting assets really render.

Uses the segmentation renderer: every pixel carries the geom id, so we can
count exactly how many pixels each of our geoms occupies in the agentview
camera.  Also writes the task contact-sheet (preview_tasks_grid.png).
"""
import pathlib
import sys

import numpy as np

sys.path.insert(0, "/home/wei/work/g05/LIBERO-master")
from libero.libero import get_libero_path  # noqa: E402
from libero.libero.benchmark import get_benchmark_dict  # noqa: E402
from libero.libero.envs import OffScreenRenderEnv  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent


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
        seg = np.asarray(env.sim.render(camera_name="agentview", height=256,
                                        width=256, segmentation=True))[::-1]
        names = {gid: env.sim.model.geom_id2name(gid) or ""
                 for gid in np.unique(seg)}
        counts = {}
        for gid, nm in names.items():
            for tag in ("parts_bin_blue_1", "parts_bin_red_1",
                        "bolt_small_1", "bolt_large_1"):
                if nm.startswith(tag):
                    counts[tag] = counts.get(tag, 0) + int((seg == gid).sum())
        av = env.sim.render(camera_name="agentview", height=256, width=256)[::-1]
        tiles.append(av)
        print(f"[{i:2d}] {task.language[:48]:48s} " +
              "  ".join(f"{k}={counts.get(k, 0):5d}"
                        for k in ("parts_bin_blue_1", "parts_bin_red_1",
                                  "bolt_small_1", "bolt_large_1")))
        env.close()

    try:
        import imageio
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
        print("\ngrid ->", OUT / "preview_tasks_grid.png", grid.shape)
    except Exception as exc:                                # noqa: BLE001
        print("grid failed:", exc)


if __name__ == "__main__":
    main()
