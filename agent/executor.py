#!/usr/bin/env python3
"""Stage 3 — execution: run generated code in the simulator, capture everything.

Each episode is a fresh subprocess: a crash, an OOM or an infinite loop in
generated code can never take the pipeline down with it, and the trace is
reproducible from the command line alone.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import time
from dataclasses import dataclass, field, asdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config" / "agent.json").read_text())
RT = CFG["runtime"]


@dataclass
class EpisodeResult:
    task_idx: int
    seed: int
    success: bool
    steps: int = 0
    confirmations: int = 0
    duration_s: float = 0.0
    exit_code: int = -1
    video: str | None = None
    error: str | None = None
    log: str | None = None
    events: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _env(task_idx: int, seed: int, run_dir: pathlib.Path, render: bool) -> dict:
    env = os.environ.copy()
    env.update({
        "MUJOCO_GL": "egl",
        "PYOPENGL_PLATFORM": "egl",
        "OMP_NUM_THREADS": env.get("OMP_NUM_THREADS", "2"),
        "MKL_NUM_THREADS": env.get("MKL_NUM_THREADS", "2"),
        "OPENBLAS_NUM_THREADS": env.get("OPENBLAS_NUM_THREADS", "2"),
        "NUMEXPR_NUM_THREADS": env.get("NUMEXPR_NUM_THREADS", "2"),
        "PYTHONPATH": f"{ROOT}:{RT['libero_root']}:{env.get('PYTHONPATH', '')}",
        "AGENT_LIBERO_ROOT": RT["libero_root"],
        "AGENT_SUITE": os.environ.get("AGENT_SUITE") or RT["suite"],
        "AGENT_TASK_IDX": str(task_idx),
        "AGENT_SEED": str(seed),
        "AGENT_RUN_DIR": str(run_dir),
        "AGENT_RENDER": "1" if render else "0",
        "AGENT_CONFIRM_MODE": env.get("AGENT_CONFIRM_MODE", CFG["safety"]["mode"]),
    })
    return env


NOISE = ("Gym has been unmaintained", "upgrade to Gymnasium", "migration guide",
         "pynvml", "robosuite WARNING", "FutureWarning", "warnings.warn")


def _salient(stderr: str, limit: int = 260) -> str:
    """Pick the meaningful error line(s) out of simulator stderr noise."""
    lines = [l.strip() for l in stderr.splitlines() if l.strip()]
    keep = []
    for l in lines:
        if any(n in l for n in NOISE):
            continue
        if "Error" in l or "error:" in l or "Exception" in l:
            keep.append(l)
    if not keep:
        keep = [l for l in lines if not any(n in l for n in NOISE)][-2:]
    return " | ".join(keep[-2:])[:limit]


def run_episode(code_path: pathlib.Path, *, task_idx: int, seed: int,
                run_dir: pathlib.Path, render: bool = False,
                timeout_s: int | None = None) -> EpisodeResult:
    run_dir.mkdir(parents=True, exist_ok=True)
    timeout_s = timeout_s or RT["task_timeout_s"]
    t0 = time.time()
    try:
        proc = subprocess.run(
            [RT["python"], str(code_path)],
            cwd=str(ROOT), env=_env(task_idx, seed, run_dir, render),
            capture_output=True, text=True, timeout=timeout_s,
        )
        stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        stdout = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = f"TIMEOUT after {timeout_s}s"
        code = -9
    dur = time.time() - t0

    (run_dir / "stdout.log").write_text(stdout)
    (run_dir / "stderr.log").write_text(stderr)

    events, video = [], None
    for line in stdout.splitlines():
        if line.startswith("@@EV@@ "):
            try:
                ev = json.loads(line[7:])
            except json.JSONDecodeError:
                continue
            events.append(ev)
            if ev.get("event") == "video":
                video = ev.get("path")
    # strip trace lines from the human-facing log
    clean = "\n".join(l for l in stdout.splitlines() if not l.startswith("@@EV@@ "))
    (run_dir / "run.log").write_text(clean + ("\n[stderr]\n" + stderr if stderr.strip() else ""))

    end = next((e for e in reversed(events) if e.get("event") == "episode_end"), {})
    res_file = run_dir / "result.json"
    if not end and res_file.exists():
        try:
            end = json.loads(res_file.read_text())
        except json.JSONDecodeError:
            end = {}
    checks = [e for e in events if e.get("event") == "check"]
    success = bool(code == 0)
    if checks:
        success = bool(checks[-1].get("success"))
    elif end.get("success") is not None:
        success = bool(end["success"])
    elif not end:
        success = False   # never even booted the env

    err = None
    if code != 0:
        err = f"exit={code}: " + _salient(stderr)

    return EpisodeResult(
        task_idx=task_idx, seed=seed, success=success,
        steps=int(end.get("steps", 0)), confirmations=int(end.get("confirmations", 0)),
        duration_s=round(dur, 2), exit_code=code, video=video, error=err,
        log=str(run_dir / "run.log"), events=events,
    )


def run_once(code_path: pathlib.Path, task_idx: int, seed: int,
             run_dir: pathlib.Path | None = None, render: bool = False) -> EpisodeResult:
    run_dir = run_dir or (ROOT / "runs" / f"adhoc_t{task_idx}_s{seed}")
    return run_episode(code_path, task_idx=task_idx, seed=seed,
                       run_dir=run_dir, render=render)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("code")
    ap.add_argument("--task", type=int, default=5)
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--out", default="runs/adhoc")
    args = ap.parse_args()
    res = run_once(pathlib.Path(args.code), args.task, args.seed,
                   pathlib.Path(args.out), args.render)
    print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2)[:1200])
