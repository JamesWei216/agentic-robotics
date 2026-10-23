#!/usr/bin/env python3
"""Generate assets for the LIBERO "wood stacking" (码垛) task.

Creates, under ./assets/custom_wood/:
    wood_block/wood_block.xml   : 40 mm wooden cube

Geometry convention (identical to vendor/bolt-sorting so the rest of the stack
needs no new code):
  * object frame origin = centre of the bottom face (z = 0 on the table),
  * collision geom in group 0, visual twin in group 1 (robosuite's offscreen
    renderer only draws geomgroup[1] — a group-0-only body is invisible on camera),
  * bottom_site / top_site / horizontal_radius_site present because robosuite's
    placement sampler reads all three.

Robosuite only uses `horizontal_radius_site`'s **x** component as the bounding
radius, so it is set to the half-diagonal (0.0283 m) — the conservative value
that keeps a square block inside its sampling region.

No trimesh needed (a cube is a single box geom). Run with any env that has numpy:
    python vendor/wood-stack/gen_assets.py
"""
import pathlib

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "assets" / "custom_wood"

BLOCK = dict(
    edge=0.040,          # 40 mm cube
    density=800,         # ~0.051 kg per block (hardwood-ish), stable when stacked
    rgba=(0.72, 0.51, 0.30, 1.0),
    friction="1.0 0.005 0.0001",
)

GEOM = ('density="{density}" friction="{friction}" solimp="0.998 0.998 0.001" '
        'solref="0.001 1"')


def fmt(v):
    return " ".join(f"{x:.6f}" for x in np.atleast_1d(v))


def write_block(name: str, p: dict) -> None:
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    e = p["edge"]
    half = e / 2.0
    r = e / np.sqrt(2.0)                      # circumscribed radius of the footprint

    xml = f"""<mujoco model="{name}">
  <worldbody>
    <body>
      <body name="object">
        <!-- collision: origin at bottom centre, so the geom sits +edge/2 up -->
        <geom type="box" pos="{fmt([0, 0, half])}" size="{fmt([half, half, half])}" group="0" {GEOM.format(**p)}/>
        <!-- visual twin (group 1 is what the offscreen renderer draws) -->
        <geom type="box" pos="{fmt([0, 0, half])}" size="{fmt([half, half, half])}" group="1"
              contype="0" conaffinity="0" rgba="{fmt(p['rgba'])}"/>
      </body>
      <site rgba="0 0 0 0" size="0.005" pos="0 0 0" name="bottom_site"/>
      <site rgba="0 0 0 0" size="0.005" pos="0 0 {e:.6f}" name="top_site"/>
      <site rgba="0 0 0 0" size="0.005" pos="{r:.6f} 0 0" name="horizontal_radius_site"/>
    </body>
  </worldbody>
</mujoco>
"""
    (d / f"{name}.xml").write_text(xml)
    print(f"[block] {name}: edge={e * 1000:.1f}mm, height={e * 1000:.1f}mm, "
          f"radius={r * 1000:.1f}mm, mass~{p['density'] * e ** 3 * 1000:.1f}g")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_block("wood_block", BLOCK)
    print("assets written to", OUT)


if __name__ == "__main__":
    main()
