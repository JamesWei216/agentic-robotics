"""Plan schema, primitive registry and validation.

The plan is the *structured output of Agent task understanding*: it must contain
steps, constraints and risks (赛题 2.b).  Everything downstream (codegen,
safety, execution, verification) consumes this one artifact, so it is validated
strictly and rejected loudly.
"""
from __future__ import annotations

ALLOWED_OPS = {
    "settle":       {"steps": "int"},
    "scan":         {"category": "str"},
    "pick":         {"object": "str"},
    "place":        {"object": "str", "bin": "str"},
    "pick_and_place": {"object": "str", "bin": "str"},
    # 码垛 (stacking): the second argument is another object, not a container
    "stack":        {"object": "str", "on": "str"},
    "pick_and_stack": {"object": "str", "on": "str"},
    "home":         {},
    "check":        {},
    "log":          {"message": "str"},
    "confirm":      {"action": "str"},
}

# Ops that place an object ON TOP OF another object instead of into a container.
STACK_OPS = {"stack", "pick_and_stack"}

# Objects that exist in the two workcells.
SCENE_OBJECTS = {
    "bolt_small_1": {"label": "bolt_small", "target": "parts_bin_blue_1"},
    "bolt_large_1": {"label": "bolt_large", "target": "parts_bin_red_1"},
    "parts_bin_blue_1": {"label": "parts_bin_blue", "target": None},
    "parts_bin_red_1": {"label": "parts_bin_red", "target": None},
    # libero_wood_stack: cube -> cube, stacking order is enforced by the mission
    "wood_block_1": {"label": "wood_block", "on": None},
    "wood_block_2": {"label": "wood_block", "on": "wood_block_1"},
    "wood_block_3": {"label": "wood_block", "on": "wood_block_2"},
    "wood_block_4": {"label": "wood_block", "on": "wood_block_3"},
}

REQUIRED_TOP = ("task", "scene", "steps", "constraints", "risks", "confirmations")


class PlanError(ValueError):
    pass


# LLMs rename arguments constantly; normalise before rejecting, otherwise every
# attempt dies on a synonym instead of a real modelling mistake.
ARG_ALIASES = {
    "obj": "object", "object_id": "object", "obj_id": "object", "object_name": "object",
    "target": "bin", "box": "bin", "bin_id": "bin", "target_bin": "bin", "target_box": "bin",
    "destination": "bin", "container": "bin",
    "n": "steps", "count": "steps", "num_steps": "steps", "settle_steps": "steps",
    "category_name": "category", "label": "category", "object_category": "category",
    "msg": "message", "text": "message",
    "action_name": "action", "name": "action",
}

OP_ALIASES = {
    "settle_scene": "settle", "wait": "settle", "detect": "scan", "perceive": "scan",
    "grasp": "pick", "pick_up": "pick", "grasp_object": "pick",
    "drop": "place", "release": "place", "place_into": "place", "put": "place",
    "sort": "pick_and_place", "transfer": "pick_and_place", "pick_place": "pick_and_place",
    "go_home": "home", "return_home": "home", "reset": "home",
    "verify": "check", "check_success": "check",
    "print": "log", "confirm_action": "confirm",
    # stacking aliases (码垛)
    "stack_up": "pick_and_stack", "pile": "pick_and_stack", "build_tower": "pick_and_stack",
    "place_on": "stack", "place_on_top": "stack", "put_on": "stack",
    "stack_block": "stack", "stack_blocks": "pick_and_stack",
}

# The second stack argument is called `on`; models love to spell it differently and
# the generic aliases would otherwise turn it into `bin`.
STACK_ARG_ALIASES = {
    "target": "on", "onto": "on", "on_top_of": "on", "on_object": "on",
    "base": "on", "below": "on", "support": "on", "target_object": "on",
    "bin": "on", "box": "on",
}


def _normalize_step(st: dict) -> dict:
    op = str(st.get("op", "")).strip().lower().replace(" ", "_")
    st["op"] = OP_ALIASES.get(op, op)
    args = st.get("args")
    if not isinstance(args, dict):
        # some models put the arguments at the top level of the step
        args = {k: v for k, v in st.items() if k not in
                ("op", "id", "purpose", "why", "on_failure", "description", "args")}
    stack = st["op"] in STACK_OPS
    norm = {}
    for k, v in args.items():
        key = str(k).strip().lower()
        if stack and key in STACK_ARG_ALIASES:
            norm[STACK_ARG_ALIASES[key]] = v
            continue
        norm[ARG_ALIASES.get(key, key)] = v
    st["args"] = norm
    return st


def validate_plan(plan: dict) -> dict:
    if not isinstance(plan, dict):
        raise PlanError("plan must be an object")
    missing = [k for k in REQUIRED_TOP if k not in plan]
    if missing:
        raise PlanError(f"missing top-level keys: {missing}")

    task = plan["task"]
    if not isinstance(task, dict) or not task.get("goal"):
        raise PlanError("task.goal is required")

    steps = plan["steps"]
    if not isinstance(steps, list) or not steps:
        raise PlanError("steps must be a non-empty list")
    for i, st in enumerate(steps):
        if not isinstance(st, dict):
            raise PlanError(f"step {i} must be an object")
        st = _normalize_step(st)
        steps[i] = st
        op = st.get("op")
        if op not in ALLOWED_OPS:
            raise PlanError(f"step {i}: unknown op {op!r}; allowed={sorted(ALLOWED_OPS)}")
        args = st.get("args") or {}
        if not isinstance(args, dict):
            raise PlanError(f"step {i}: args must be an object")
        for name, typ in ALLOWED_OPS[op].items():
            if name not in args:
                raise PlanError(f"step {i} ({op}): missing arg {name!r}; "
                                f"received args={sorted(args)}")
            if typ == "int":
                # LLMs love to send "30" instead of 30; coerce numeric strings, reject the rest
                try:
                    args[name] = int(args[name])
                except (TypeError, ValueError):
                    raise PlanError(f"step {i} ({op}): arg {name!r} must be int")
        extra = set(args) - set(ALLOWED_OPS[op])
        if extra:
            # drop harmless narration keys instead of failing the whole plan
            for k in list(extra):
                args.pop(k)
            extra = set()
        if op in ("pick", "place", "pick_and_place"):
            objs = [args.get("object"), args.get("bin")]
            for o in filter(None, objs):
                if o not in SCENE_OBJECTS:
                    raise PlanError(f"step {i}: unknown object {o!r}; scene has {sorted(SCENE_OBJECTS)}")
        if op in STACK_OPS:
            for o in filter(None, [args.get("object"), args.get("on")]):
                if o not in SCENE_OBJECTS:
                    raise PlanError(f"step {i}: unknown object {o!r}; scene has {sorted(SCENE_OBJECTS)}")
            if args.get("object") == args.get("on"):
                raise PlanError(f"step {i}: cannot stack {args.get('object')!r} onto itself")
        st["args"] = args
        st.setdefault("id", i + 1)

    for key, ref in (("constraints", "text"), ("risks", "text"), ("confirmations", "action")):
        items = plan[key]
        if not isinstance(items, list) or not items:
            raise PlanError(f"{key} must be a non-empty list")
        for i, it in enumerate(items):
            if isinstance(it, str):
                plan[key][i] = {ref: it}
            elif not isinstance(it, dict) or not it.get(ref):
                raise PlanError(f"{key}[{i}] must be an object with {ref!r}")
    return plan


def plan_summary(plan: dict) -> str:
    lines = [f"goal: {plan['task'].get('goal')}"]
    lines.append("steps: " + " -> ".join(
        f"{s['id']}.{s['op']}" + (f"({','.join(f'{k}={v}' for k, v in (s.get('args') or {}).items())})"
                                 if s.get("args") else "")
        for s in plan["steps"]))
    return "\n".join(lines)
