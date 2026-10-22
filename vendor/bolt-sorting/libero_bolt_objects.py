"""LIBERO objects for the "bolt sorting" task (G0.5 sim reproduction).

Installed into: <LIBERO>/libero/libero/envs/objects/custom_bolt_objects.py
Assets live in: <LIBERO>/libero/libero/assets/custom_bolt/<obj_name>/<obj_name>.xml

Two bolts lie flat on the table (long axis along X, hex flat down); two
open-top parts bins provide the `contain_region` affordance used by the
`In` predicate.
"""
import os
import re
import numpy as np

from robosuite.models.objects import MujocoXMLObject

import pathlib

absolute_path = pathlib.Path(__file__).parent.parent.parent.absolute()

from libero.libero.envs.base_object import register_object


class BoltBaseObject(MujocoXMLObject):
    """Hex-head bolt, spawned lying flat with a random yaw."""

    def __init__(self, name, obj_name):
        super().__init__(
            os.path.join(
                str(absolute_path),
                f"assets/custom_bolt/{obj_name}/{obj_name}.xml",
            ),
            name=name,
            joints=[dict(type="free", damping="0.0005")],
            obj_type="all",
            duplicate_collision_geoms=False,
        )
        self.category_name = "_".join(
            re.sub(r"([A-Z])", r" \1", self.__class__.__name__).split()
        ).lower()
        # random yaw in the table plane -> bolt keeps lying flat, orientation varies
        # NOTE: LIBERO's TableRegionSampler._sample_quat returns quaternions in
        # (x,y,z,w) order while MuJoCo qpos is (w,x,y,z).  Net effect: axis="x"
        # with a uniform angle yields a *uniform yaw* (angle = pi - theta), so
        # this is how you get a clean random yaw for objects on `main_table`.
        # (axis="z" would make objects spawn flipped ~180 deg about a tilted axis.)
        # Fixed 90-deg yaw, same convention as the stock LIBERO objects.
        # (Random yaw would be nice, but SiteObject.in_box computes
        #  |R @ size| instead of |R| @ size, so a *square* contain region
        #  yawed near 45 deg collapses to a zero-width box and the `In` goal
        #  becomes impossible.  At 90 deg the two formulas agree.)
        self.rotation = (np.pi / 2, np.pi / 2)
        self.rotation_axis = "x"
        self.object_properties = {"vis_site_names": {}}


class PartsBinBaseObject(MujocoXMLObject):
    """Open-top rectangular parts bin; exposes `contain_region`."""

    def __init__(self, name, obj_name):
        super().__init__(
            os.path.join(
                str(absolute_path),
                f"assets/custom_bolt/{obj_name}/{obj_name}.xml",
            ),
            name=name,
            joints=[dict(type="free", damping="0.0005")],
            obj_type="all",
            duplicate_collision_geoms=False,
        )
        self.category_name = "_".join(
            re.sub(r"([A-Z])", r" \1", self.__class__.__name__).split()
        ).lower()
        # Fixed 90-deg yaw, same convention as the stock LIBERO objects.
        # (Random yaw would be nice, but SiteObject.in_box computes
        #  |R @ size| instead of |R| @ size, so a *square* contain region
        #  yawed near 45 deg collapses to a zero-width box and the `In` goal
        #  becomes impossible.  At 90 deg the two formulas agree.)
        self.rotation = (np.pi / 2, np.pi / 2)
        self.rotation_axis = "x"
        self.object_properties = {"vis_site_names": {}}


@register_object
class BoltSmall(BoltBaseObject):
    def __init__(self, name="bolt_small", obj_name="bolt_small"):
        super().__init__(name, obj_name)


@register_object
class BoltLarge(BoltBaseObject):
    def __init__(self, name="bolt_large", obj_name="bolt_large"):
        super().__init__(name, obj_name)


@register_object
class PartsBinBlue(PartsBinBaseObject):
    def __init__(self, name="parts_bin_blue", obj_name="parts_bin_blue"):
        super().__init__(name, obj_name)


@register_object
class PartsBinRed(PartsBinBaseObject):
    def __init__(self, name="parts_bin_red", obj_name="parts_bin_red"):
        super().__init__(name, obj_name)
