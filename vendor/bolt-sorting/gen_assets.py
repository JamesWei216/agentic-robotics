#!/usr/bin/env python3
"""Generate assets for the LIBERO "bolt sorting" task (G0.5 sim reproduction).

Creates, under ./assets/custom_bolt/:
  - bolt_small/ , bolt_large/      : hex-head bolt (visual mesh + primitive collision)
  - parts_bin_small/ , parts_bin_large/ : open-top parts bin (pure box geoms)

Bolts lie flat on the table (axis along X, hex flat facing down) so they are
stable when spawned by LIBERO's region sampler.

Run with the GalaxeaVLA venv python (needs trimesh + numpy).
"""
import pathlib
import numpy as np
import trimesh

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "assets" / "custom_bolt"

# ---------------------------------------------------------------- parameters
BOLTS = {
    # name            across-flats  head_h   shank_d  shank_L   rgba
    "bolt_small": dict(AF=0.022, head_h=0.010, shank_d=0.013, shank_L=0.052,
                       rgba=(0.78, 0.79, 0.82, 1.0), specular="1.0", shininess="1.0",
                       reflectance="0.6"),
    "bolt_large": dict(AF=0.038, head_h=0.018, shank_d=0.024, shank_L=0.085,
                       rgba=(0.16, 0.16, 0.18, 1.0), specular="0.8", shininess="0.8",
                       reflectance="0.3"),
}

BINS = {
    # name                outer   wall    height  rgba
    # 蓝色盒子放小螺栓，红色盒子放大螺栓（尺寸沿用原设计，只改颜色/命名）
    "parts_bin_blue": dict(outer=0.130, wall=0.008, height=0.045,
                           rgba=(0.15, 0.35, 0.90, 1.0)),
    "parts_bin_red": dict(outer=0.190, wall=0.009, height=0.065,
                          rgba=(0.88, 0.16, 0.16, 1.0)),
}

GEOM_COMMON = ('solimp="0.998 0.998 0.001" solref="0.001 1" density="100" '
               'friction="0.95 0.3 0.1"')

SITES = """      <site rgba="0 0 0 0" size="0.005" pos="0 0 0" name="bottom_site"/>
      <site rgba="0 0 0 0" size="0.005" pos="0 0 {top}" name="top_site"/>
      <site rgba="0 0 0 0" size="0.005" pos="{hr} 0 0" name="horizontal_radius_site"/>"""


def fmt(v):
    return " ".join(f"{x:.6f}" for x in np.atleast_1d(v))


# ---------------------------------------------------------------- bolt mesh
def hex_prism(R, h, phase=np.pi / 6):
    """Regular hexagonal prism, circumradius R, height h, base at z=0."""
    ang = phase + np.arange(6) * np.pi / 3.0
    c, s = np.cos(ang) * R, np.sin(ang) * R
    verts = np.vstack([
        np.stack([c, s, np.zeros(6)], 1),
        np.stack([c, s, np.full(6, h)], 1),
    ])
    faces = []
    for i in range(1, 5):                     # bottom cap (fan)
        faces.append([0, i + 1, i])
    for i in range(1, 5):                     # top cap (fan)
        faces.append([6, 6 + i, 6 + i + 1])
    for i in range(6):                        # side quads
        j = (i + 1) % 6
        faces.append([i, j, 6 + j])
        faces.append([i, 6 + j, 6 + i])
    m = trimesh.Trimesh(vertices=verts, faces=np.array(faces))
    m.fix_normals()
    return m


def bolt_mesh(AF, head_h, shank_d, shank_L):
    """Bolt lying flat: axis along X, head at -X, bottom face at z=0, centred in x/y."""
    R = AF / np.sqrt(3.0)                      # circumradius from across-flats
    head = hex_prism(R, head_h, phase=np.pi / 6)
    head.apply_translation([0, 0, shank_L])    # head sits above the shank
    shank = trimesh.creation.cylinder(radius=shank_d / 2.0, height=shank_L, sections=64)
    shank.apply_translation([0, 0, shank_L / 2.0])
    m = trimesh.util.concatenate([head, shank])

    # +Z axis -> -X axis  (head ends up at -X)
    m.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [0, 1, 0]))
    b = m.bounds
    T = head_h + shank_L
    m.apply_translation([-(b[0, 0] + b[1, 0]) / 2.0,      # centre x
                         -(b[0, 1] + b[1, 1]) / 2.0,      # centre y
                         -b[0, 2]])                       # bottom -> z = 0
    m.fix_normals()

    # sanity: mesh frame must be x in [-T/2, T/2], y in +-AF/sqrt(3), z in [0, AF]
    eb = m.bounds
    exp = np.array([[-T / 2, -AF / np.sqrt(3), 0.0],
                    [T / 2, AF / np.sqrt(3), AF]])
    assert np.allclose(eb, exp, atol=1e-6), f"bolt bbox {eb} != expected {exp}"
    return m, dict(T=T)


def write_bolt(name, p):
    d = OUT / name
    (d / "visual").mkdir(parents=True, exist_ok=True)
    mesh, info = bolt_mesh(p["AF"], p["head_h"], p["shank_d"], p["shank_L"])

    obj = d / "visual" / f"{name}_vis.obj"
    mesh.export(obj, include_texture=False)
    assert obj.exists()

    T = info["T"]
    H_h, L, AF, sd = p["head_h"], p["shank_L"], p["AF"], p["shank_d"]

    # collision geoms expressed in the final object frame (origin = bottom centre,
    # bolt lying along X with the hex head at -X, its lower flat at z = 0)
    head_pos = [-T / 2 + H_h / 2, 0.0, AF / 2]
    head_size = [H_h / 2, AF / 2, AF / 2]
    shank_pos = [H_h / 2, 0.0, AF / 2]
    shank_size = [sd / 2, L / 2]

    xml = f"""<mujoco model="{name}">
  <asset>
    <material name="{name}_mat" rgba="{fmt(p['rgba'])}" specular="{p['specular']}" shininess="{p['shininess']}" reflectance="{p['reflectance']}"/>
    <mesh file="visual/{name}_vis.obj" name="{name}_vis" scale="1.0 1.0 1.0"/>
  </asset>
  <worldbody>
    <body>
      <body name="object">
        <geom pos="{fmt(head_pos)}" size="{fmt(head_size)}" type="box" {GEOM_COMMON} group="0"/>
        <geom pos="{fmt(shank_pos)}" size="{fmt(shank_size)}" quat="0.70711 0.00000 0.70711 0.00000" type="cylinder" {GEOM_COMMON} group="0"/>
        <geom type="mesh" mesh="{name}_vis" conaffinity="0" contype="0" group="1" material="{name}_mat" rgba="{fmt(p['rgba'])}"/>
      </body>
{SITES.format(top=f"{AF:.6f}", hr=f"{T / 2.0:.6f}")}
    </body>
  </worldbody>
</mujoco>
"""
    (d / f"{name}.xml").write_text(xml)
    print(f"[bolt] {name}: T={T * 1000:.1f}mm AF={AF * 1000:.1f}mm "
          f"bbox={np.round(mesh.extents * 1000, 1)}mm verts={len(mesh.vertices)}")


# ---------------------------------------------------------------- bin
def write_bin(name, p):
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    L, th, H = p["outer"], p["wall"], p["height"]
    rgba = fmt(p["rgba"])

    geoms = []
    geoms.append(([0, 0, th / 2.0], [L / 2.0, L / 2.0, th / 2.0]))              # floor
    geoms.append(([L / 2.0 - th / 2.0, 0, H / 2.0], [th / 2.0, L / 2.0, H / 2.0]))
    geoms.append(([-(L / 2.0 - th / 2.0), 0, H / 2.0], [th / 2.0, L / 2.0, H / 2.0]))
    geoms.append(([0, L / 2.0 - th / 2.0, H / 2.0], [L / 2.0, th / 2.0, H / 2.0]))
    geoms.append(([0, -(L / 2.0 - th / 2.0), H / 2.0], [L / 2.0, th / 2.0, H / 2.0]))

    # robosuite only renders geomgroup[1] (visual mesh) offscreen, so every
    # visible surface needs a group=1 twin of the group=0 collision geom.
    lines = []
    for pos, size in geoms:
        lines.append(
            f'        <geom pos="{fmt(pos)}" size="{fmt(size)}" type="box" '
            f'{GEOM_COMMON} group="0"/>'
        )
    for pos, size in geoms:
        lines.append(
            f'        <geom pos="{fmt(pos)}" size="{fmt(size)}" type="box" '
            f'contype="0" conaffinity="0" group="1" rgba="{rgba}"/>'
        )
    lines = "\n".join(lines)

    inner = L / 2.0 - th
    site_pos = [0, 0, (th + H) / 2.0]
    site_size = [inner, inner, (H - th) / 2.0]

    xml = f"""<mujoco model="{name}">
  <worldbody>
    <body>
      <body name="object">
        <site type="box" pos="{fmt(site_pos)}" quat="0.00000 0.00000 0.00000 1.00000" size="{fmt(site_size)}" group="0" rgba="1 0 0 0" name="contain_region"/>
{lines}
      </body>
      <site rgba="0 0 0 0" size="0.005" pos="0 0 0" name="bottom_site"/>
      <site rgba="0 0 0 0" size="0.005" pos="0 0 {H:.6f}" name="top_site"/>
      <site rgba="0 0 0 0" size="0.005" pos="{L / 2.0:.6f} 0 0" name="horizontal_radius_site"/>
    </body>
  </worldbody>
</mujoco>
"""
    (d / f"{name}.xml").write_text(xml)
    print(f"[bin]  {name}: outer={L * 1000:.1f}mm wall={th * 1000:.1f}mm "
          f"h={H * 1000:.1f}mm cavity={2 * inner * 1000:.1f}mm")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for k, v in BOLTS.items():
        write_bolt(k, v)
    for k, v in BINS.items():
        write_bin(k, v)
    print("assets written to", OUT)


if __name__ == "__main__":
    main()
