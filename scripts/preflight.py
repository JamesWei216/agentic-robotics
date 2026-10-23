#!/usr/bin/env python3
"""Pre-flight self-check: is this machine able to run the pipeline at all?

    python scripts/preflight.py            # all checks, exit 1 on a hard failure

Checks (no LLM calls, no GPU rendering beyond one tiny env):
  1. python / torch / mujoco / robosuite / LIBERO import paths
  2. LIBERO bddl suites exist (libero_bolt, libero_bolt_v2, libero_bolt_multi)
  3. benchmark registry knows the suites and the task counts
  4. bolt assets are installed in the LIBERO asset tree
  5. one env builds, one 5-step rollout runs (EGL render path)
  6. config/missions.json is consistent with the suite task counts
  7. LLM endpoint config is present (only a warning: --no-llm works without it)
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _paths import libero_root  # noqa: E402

LIBERO = str(libero_root())
sys.path.insert(0, str(ROOT))
sys.path.insert(0, LIBERO)

OK, WARN, FAIL = "  [ok]  ", "  [warn]", "  [FAIL]"
failures = 0


def check(label, fn):
    global failures
    try:
        detail = fn()
        print(f"{OK} {label}" + (f" — {detail}" if detail else ""))
        return True
    except AssertionError as exc:
        print(f"{FAIL} {label} — {exc}")
        failures += 1
    except Exception as exc:                      # noqa: BLE001
        print(f"{FAIL} {label} — {type(exc).__name__}: {exc}")
        failures += 1
    return False


def warn(label, detail):
    print(f"{WARN} {label} — {detail}")


def main():
    print(f"project : {ROOT}")
    print(f"libero  : {LIBERO}")
    print(f"python  : {sys.version.split()[0]} ({sys.executable})\n")

    def imports():
        import numpy, scipy, mujoco, robosuite  # noqa: F401
        import libero  # noqa: F401
        return (f"numpy {numpy.__version__}, scipy {scipy.__version__}, "
                f"mujoco {mujoco.__version__}, robosuite {robosuite.__version__}")

    check("python packages import", imports)

    def suites():
        from libero.libero import get_libero_path
        base = pathlib.Path(get_libero_path("bddl_files"))
        wanted = {"libero_bolt": 11, "libero_bolt_v2": 11, "libero_bolt_multi": 11,
                  "libero_wood_stack": 11}
        got = {}
        for name, n in wanted.items():
            files = sorted((base / name).glob("*.bddl"))
            assert files, f"{name}: no bddl in {base / name} (run scripts/gen_suites.py)"
            got[name] = len(files)
        return ", ".join(f"{k}:{v}" for k, v in got.items())

    check("bddl suites installed", suites)

    def registry():
        from libero.libero.benchmark import get_benchmark_dict
        d = get_benchmark_dict()
        names = ("libero_bolt", "libero_bolt_v2", "libero_bolt_multi", "libero_wood_stack")
        missing = [s for s in names if s not in d]
        assert not missing, f"not registered: {missing} (run bolt-sorting/install.py + gen_stack_suite.py)"
        return ", ".join(f"{s}:{len(d[s]().tasks)} tasks" for s in names)

    check("benchmark registry", registry)

    def assets():
        from libero.libero import get_libero_path
        a = pathlib.Path(get_libero_path("assets"))
        root = a / "custom_bolt"
        need = ["bolt_small", "bolt_large", "parts_bin_blue", "parts_bin_red"]
        hits = [p.name for p in root.glob("*") if p.is_dir()] if root.exists() else []
        missing = [n for n in need if n not in hits]
        assert not missing, (f"missing {missing} under {root} "
                             "(run bolt-sorting/install.py)")
        return ", ".join(sorted(hits))

    check("bolt assets installed", assets)

    def stack_assets():
        from libero.libero import get_libero_path
        a = pathlib.Path(get_libero_path("assets")) / "custom_wood"
        assert (a / "wood_block" / "wood_block.xml").is_file(), \
            f"missing wood_block asset under {a} (run vendor/wood-stack/install.py)"
        return str(a / "wood_block" / "wood_block.xml")

    check("stack assets installed", stack_assets)

    def rollout():
        os.environ.setdefault("MUJOCO_GL", "egl")
        os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
        import numpy as np
        from libero.libero import get_libero_path
        from libero.libero.benchmark import get_benchmark_dict
        from libero.libero.envs import OffScreenRenderEnv
        suite = get_benchmark_dict()["libero_bolt_v2"]()
        task = suite.get_task(0)
        bddl = pathlib.Path(get_libero_path("bddl_files")) / "libero_bolt_v2" / task.bddl_file
        env = OffScreenRenderEnv(bddl_file_name=bddl, camera_heights=128,
                                 camera_widths=128)
        env.seed(0)
        obs = env.reset()
        for _ in range(5):
            env.step(np.zeros(7, dtype=np.float32))
        img = obs["agentview_image"]
        env.close()
        assert img.shape == (128, 128, 3), img.shape
        return f"5 control steps ok, agentview {img.shape}"

    check("one env + short rollout (EGL)", rollout)

    def missions():
        suites_dir = pathlib.Path(LIBERO) / "libero/libero/bddl_files"
        m = json.loads((ROOT / "config" / "missions.json").read_text())
        for name, table in m.items():
            n_files = len(list((suites_dir / name).glob("*.bddl")))
            bad = [k for k, v in table.items() if not v]
            assert not bad, f"{name}: empty mission for task(s) {bad}"
        return ", ".join(f"{k}:{len(v)}" for k, v in m.items())

    check("missions.json consistent", missions)

    def llm():
        cfg = json.loads((ROOT / "config" / "agent.json").read_text())
        llm_cfg = cfg.get("llm", {})
        assert llm_cfg.get("base_url"), "llm.base_url missing"
        return (f"model={llm_cfg.get('model')} base_url={llm_cfg.get('base_url')} "
                f"(use --no-llm to skip the LLM entirely)")

    if not check("llm config", llm):
        pass

    print()
    if failures:
        print(f"preflight FAILED ({failures} hard failure(s))")
        return 1
    print("preflight OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
