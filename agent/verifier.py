#!/usr/bin/env python3
"""Stage 4 — verification: success rate over a fixed initial-state protocol.

赛题 2.e: 在公开评测协议下达到最低指标.
Protocol: task set × seeds (default 10 seeds/task, seeds 1000..1009), each seed
is a fixed LIBERO initial state, so runs are paired and comparable across code
versions (repair iterations are measured on the *same* states).
"""
from __future__ import annotations

import json
import pathlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from agent.executor import EpisodeResult, run_episode

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config" / "agent.json").read_text())


@dataclass
class VerifyResult:
    episodes: list
    per_task: dict
    overall: float
    n: int
    ok: int
    mean_steps: float
    mean_duration_s: float
    confirmations: int

    def to_dict(self) -> dict:
        return {
            "overall": round(self.overall, 4), "n": self.n, "ok": self.ok,
            "per_task": self.per_task,
            "mean_steps": round(self.mean_steps, 1),
            "mean_duration_s": round(self.mean_duration_s, 2),
            "confirmations": self.confirmations,
            "episodes": [e.to_dict() for e in self.episodes],
        }


def verify(code_path: pathlib.Path, tasks: list[int], *, seeds: int = 10,
           seed0: int = 1000, run_dir: pathlib.Path,
           workers: int = 4, render_first: bool = False,
           progress=None) -> VerifyResult:
    jobs = [(t, seed0 + i) for t in tasks for i in range(seeds)]

    def one(job):
        task_idx, seed = job
        ep_dir = run_dir / f"t{task_idx}_s{seed}"
        render = render_first and seed == seed0 and task_idx == tasks[0]
        return run_episode(code_path, task_idx=task_idx, seed=seed,
                           run_dir=ep_dir, render=render)

    results: list[EpisodeResult] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for res in ex.map(one, jobs):
            results.append(res)
            if progress:
                progress(res)

    per_task: dict[str, dict] = {}
    for t in tasks:
        rs = [r for r in results if r.task_idx == t]
        ok = sum(r.success for r in rs)
        per_task[str(t)] = {
            "ok": ok, "n": len(rs),
            "success_rate": round(100.0 * ok / max(1, len(rs)), 1),
            "mean_steps": round(sum(r.steps for r in rs) / max(1, len(rs)), 1),
            "errors": [r.error for r in rs if r.error][:3],
            "videos": [r.video for r in rs if r.video],
        }
    ok_all = sum(r.success for r in results)
    return VerifyResult(
        episodes=results, per_task=per_task,
        overall=ok_all / max(1, len(results)), n=len(results), ok=ok_all,
        mean_steps=sum(r.steps for r in results) / max(1, len(results)),
        mean_duration_s=sum(r.duration_s for r in results) / max(1, len(results)),
        confirmations=sum(r.confirmations for r in results),
    )


def save(result: VerifyResult, path: pathlib.Path) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n")
    return path


def brief(result: VerifyResult) -> str:
    parts = [f"{k}: {v['ok']}/{v['n']} ({v['success_rate']}%)"
             for k, v in sorted(result.per_task.items(), key=lambda kv: int(kv[0]))]
    return (f"overall {result.ok}/{result.n} = {100 * result.overall:.1f}%  |  "
            + "  ".join(parts)
            + f"  |  mean {result.mean_steps:.0f} steps, {result.mean_duration_s:.1f}s/ep")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("code")
    ap.add_argument("--tasks", default="5")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="runs/verify")
    args = ap.parse_args()
    tasks = [int(t) for t in args.tasks.split(",") if t.strip()]
    res = verify(pathlib.Path(args.code), tasks, seeds=args.seeds,
                 run_dir=pathlib.Path(args.out), workers=args.workers)
    save(res, pathlib.Path(args.out) / "metrics.json")
    print(brief(res))
