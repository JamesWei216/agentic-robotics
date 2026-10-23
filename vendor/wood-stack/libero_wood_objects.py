"""LIBERO objects for the "wood stacking" (码垛) suite.

Installed into: <LIBERO>/libero/libero/envs/objects/custom_wood_objects.py
Assets live in: <LIBERO>/libero/libero/assets/custom_wood/<obj_name>/<obj_name>.xml

A wooden cube spawned upright on the table. The stacking goal is judged by
LIBERO's native `On` predicate (base z <= top z, geometric contact, xy distance
< 30 mm) — no hand-written success script anywhere in the loop.
"""
import os
import pathlib
import re

import numpy as np

from robosuite.models.objects import MujocoXMLObject

from libero.libero.envs.base_object import register_object

absolute_path = pathlib.Path(__file__).parent.parent.parent.absolute()


class WoodBlockBaseObject(MujocoXMLObject):
    """40 mm wooden cube."""

    def __init__(self, name, obj_name):
        super().__init__(
            os.path.join(
                str(absolute_path),
                f"assets/custom_wood/{obj_name}/{obj_name}.xml",
            ),
            name=name,
            joints=[dict(type="free", damping="0.0005")],
            obj_type="all",
            duplicate_collision_geoms=False,
        )
        self.category_name = "_".join(
            re.sub(r"([A-Z])", r" \1", self.__class__.__name__).split()
        ).lower()
        # Same convention as the stock LIBERO objects and custom_bolt_objects:
        # a fixed 90-deg "yaw" (see the long note in libero_bolt_objects.py).
        # A cube is invariant to it in the table plane, so no region collapse.
        self.rotation = (np.pi / 2, np.pi / 2)
        self.rotation_axis = "x"
        self.object_properties = {"vis_site_names": {}}


@register_object
class WoodBlock(WoodBlockBaseObject):
    def __init__(self, name="wood_block", obj_name="wood_block"):
        super().__init__(name, obj_name)
