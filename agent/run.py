#!/usr/bin/env python3
"""Agentic robotics pipeline — one command, full loop.

    NL task book
      -> [1] plan (LLM, validated)              agent/planner.py
      -> [2] generated control code (LLM)       agent/codegen.py
      -> [3] simulation execution               agent/executor.py
      -> [4] verification over fixed seeds      agent/verifier.py
      -> [5] failure diagnosis (LLM + rules)    agent/diagnose.py
      -> [6] repair & re-verify (loop)          agent/codegen.py + verifier
      -> [7] report + manifest                  this file

    python -m agent.run --taskbook taskbooks/sort_main.md --tasks 5 --seeds 10
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import time

from agent import codegen, diagnose, executor, planner, verifier
from agent.schemas import plan_summary

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config" / "agent.json").read_text())


def _now_tag(tag: str) -> str:
    return f"{time.strftime('%Y%m%d-%H%M%S')}_{tag}"


def _progress(res: executor.EpisodeResult) -> None:
    print(f"  [t{res.task_idx} s{res.seed}] "
          f"{'OK ' if res.success else 'FAIL'} {res.steps:4d} steps "
          f"{res.duration_s:5.1f}s {res.error or ''}", flush=True)


def write_report(run_dir: pathlib.Path, ctx: dict) -> pathlib.Path:
    plan, prov, metrics = ctx["plan"], ctx["provenance"], ctx["metrics"]
    lines = [
        f"# Agentic Robotics 运行报告 · {ctx['run_id']}",
        "",
        f"- 任务书：`{ctx['taskbook']}`",
        f"- 套件 / 任务：`{CFG['runtime']['suite']}` / {ctx['tasks']}",
        f"- 初始状态协议：seed {ctx['seed0']}..{ctx['seed0'] + ctx['seeds'] - 1} × {len(ctx['tasks'])} 任务 "
        f"（{ctx['seeds'] * len(ctx['tasks'])} episodes）",
        f"- 人确认模式：`{os.environ.get('AGENT_CONFIRM_MODE', CFG['safety']['mode'])}`",
        "",
        "## 1. Agent 任务理解（结构化计划）",
        "",
        f"- 生成方式：**{prov['plan']['source']}**（{prov['plan']['attempts']} 次尝试）",
        f"- 目标：{plan['task'].get('goal')}",
        f"- 步骤数：{len(plan['steps'])}；约束 {len(plan['constraints'])} 条；风险 {len(plan['risks'])} 条；"
        f"确认点 {len(plan['confirmations'])} 个",
        "",
        "| # | 原语 | 参数 | 目的 | 失败处理 |",
        "|---|---|---|---|---|",
    ]
    for s in plan["steps"]:
        args = ", ".join(f"{k}={v}" for k, v in (s.get("args") or {}).items()) or "-"
        lines.append(f"| {s['id']} | `{s['op']}` | {args} | {s.get('purpose', '')} | {s.get('on_failure', '')} |")

    lines += ["", "### 约束", ""]
    lines += [f"- **{c.get('id')}** {c['text']}" + (f"（{c['enforced_by']}）" if c.get("enforced_by") else "")
              for c in plan["constraints"]]
    lines += ["", "### 风险点", ""]
    lines += [f"- **{r.get('id')}** {r['text']} → 缓解：{r.get('mitigation', '-')}；检测：{r.get('detect', '-')}"
              for r in plan["risks"]]

    lines += ["", "## 2. 代码生成", "",
              f"- 生成方式：**{prov['code']['generator']}**"
              + (f"（{prov['code']['reason']}）" if prov["code"].get("reason") else ""),
              f"- 静态校验：白名单 import + 禁止 eval/exec/open/网络/文件；结果 `{prov['code'].get('validation')}`",
              f"- 代码文件：`task.py`（{ctx['code_lines']} 行）", ""]

    lines += ["## 3. 仿真达标", "",
              f"**成功率 {metrics['ok']}/{metrics['n']} = {100 * metrics['overall']:.1f}%**"
              f"；平均 {metrics['mean_steps']:.0f} 步 / {metrics['mean_duration_s']:.1f}s per episode",
              "", "| 任务 | 成功 | 成功率 | 平均步数 |", "|---|---|---|---|"]
    for t, v in sorted(metrics["per_task"].items(), key=lambda kv: int(kv[0])):
        lines.append(f"| {t} | {v['ok']}/{v['n']} | {v['success_rate']}% | {v['mean_steps']} |")

    if ctx.get("diagnosis"):
        d = ctx["diagnosis"]
        lines += ["", "## 4. 失败分析", "",
                  f"- 归类：`{d.get('taxonomy') or d.get('failure_stage')}`",
                  f"- 根因：{d.get('root_cause')}",
                  f"- 证据：{d.get('evidence')}",
                  f"- 修复建议：{d.get('fix_hint')}"]
    else:
        lines += ["", "## 4. 失败分析", "", "- 本轮无失败样本，未触发诊断。"]

    if ctx.get("repairs"):
        lines += ["", "## 5. 自动修复迭代", "",
                  "| 轮次 | 生效 | 子集成功率（修复前→后） | 结论 |", "|---|---|---|---|"]
        for r in ctx["repairs"]:
            lines.append(f"| {r['round']} | {r['applied']} | {r['before']} → {r['after']} | {r['decision']} |")
    lines += ["", "## 6. 复现命令", "", "```bash", ctx["repro"], "```", "",
              "## 7. 产物", ""]
    for p in sorted(run_dir.rglob("*")):
        if p.is_file() and p.suffix in (".json", ".md", ".py", ".log", ".mp4"):
            lines.append(f"- `{p.relative_to(run_dir)}`")
    path = run_dir / "report.md"
    path.write_text("\n".join(lines) + "\n")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--taskbook", default="taskbooks/sort_main.md")
    ap.add_argument("--suite", default=None, help="benchmark suite override")
    ap.add_argument("--tasks", default="5", help="comma separated task indices")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--seed0", type=int, default=1000)
    ap.add_argument("--repairs", type=int, default=2)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--target", type=float, default=0.0,
                    help="stop repairing once overall success rate reaches this (0-1)")
    ap.add_argument("--tag", default="sort")
    ap.add_argument("--no-llm", action="store_true", help="template plan + template code")
    ap.add_argument("--confirm-mode", default=None, help="auto | manual | deny")
    ap.add_argument("--render", action="store_true", help="record one mp4")
    args = ap.parse_args()

    if args.confirm_mode:
        os.environ["AGENT_CONFIRM_MODE"] = args.confirm_mode
    if args.suite:
        CFG["runtime"]["suite"] = args.suite
        os.environ["AGENT_SUITE"] = args.suite

    tasks = [int(t) for t in args.tasks.split(",") if t.strip()]
    run_id = _now_tag(args.tag)
    run_dir = ROOT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"=== run {run_id} ===")

    # 1. task understanding -------------------------------------------------
    print("[1/6] planning from", args.taskbook)
    if args.no_llm:
        pres = planner.PlanResult(planner._fallback_plan(
            pathlib.Path(args.taskbook).read_text()), "fallback", 0, "no-llm")
    else:
        pres = planner.make_plan(args.taskbook, suite=CFG["runtime"]["suite"], retries=1)
    (run_dir / "plan.json").write_text(json.dumps(pres.plan, ensure_ascii=False, indent=2) + "\n")
    (run_dir / "plan_meta.json").write_text(json.dumps(
        {"source": pres.source, "attempts": pres.attempts, "error": pres.error},
        ensure_ascii=False, indent=2) + "\n")
    print("     ", "plan source:", pres.source, "|", plan_summary(pres.plan).splitlines()[1][:150])

    # 2. code generation ----------------------------------------------------
    print("[2/6] generating control code")
    code, cprov = codegen.generate(pres.plan, use_llm=not args.no_llm)
    code_path = codegen.write(code, run_dir / "task.py")
    (run_dir / "code_meta.json").write_text(json.dumps(cprov, ensure_ascii=False, indent=2) + "\n")
    print("     ", "generator:", cprov["generator"], cprov.get("reason") or "")

    # 3. smoke episode ------------------------------------------------------
    print("[3/6] smoke episode (task %d, seed %d)" % (tasks[0], args.seed0))
    smoke = executor.run_once(code_path, tasks[0], args.seed0,
                              run_dir / "smoke", render=args.render)
    _progress(smoke)
    (run_dir / "smoke" / "result.json").write_text(
        json.dumps(smoke.to_dict(), ensure_ascii=False, indent=2)[:20000] + "\n")

    # 4. verification -------------------------------------------------------
    # If the smoke episode already failed, screen on a small paired subset first:
    # the repair loop only needs a signal, and a broken script must not burn the
    # full protocol budget.
    first_seeds = args.seeds if smoke.success else min(3, args.seeds)
    print(f"[4/6] verification: {len(tasks)} tasks x {first_seeds} seeds"
          + ("" if first_seeds == args.seeds else " (screening subset: smoke failed)"))
    metrics = verifier.verify(code_path, tasks, seeds=first_seeds, seed0=args.seed0,
                              run_dir=run_dir / "verify", workers=args.workers,
                              progress=_progress)
    verifier.save(metrics, run_dir / "metrics.json")
    print("     ", verifier.brief(metrics))

    # 5/6. diagnose + repair loop ------------------------------------------
    repairs = []
    diag = None
    for rnd in range(1, args.repairs + 1):
        if metrics.overall >= args.target > 0:
            print(f"[5/6] target {args.target:.0%} reached, stop repairing")
            break
        failed = [e.to_dict() for e in metrics.episodes if not e.success]
        if not failed:
            print("[5/6] no failures, nothing to diagnose")
            break
        print(f"[5/6] diagnosing {len(failed)} failed episodes (round {rnd})")
        diag = diagnose.diagnose(failed, plan_summary(pres.plan),
                                 json.dumps({"overall": metrics.overall,
                                             "per_task": metrics.per_task}, ensure_ascii=False))
        diagnose.save(diag, run_dir / f"diagnosis_r{rnd}.json")
        print("      root cause:", str(diag.get("root_cause"))[:160])

        print(f"[6/6] repair round {rnd}")
        fixed, rprov = codegen.repair(code_path.read_text(), diag)
        if not rprov["applied"]:
            print("      repair not applicable:", rprov["reason"])
            repairs.append({"round": rnd, "applied": False, "before": "-", "after": "-",
                            "decision": f"skipped: {rprov['reason']}"})
            break

        # evaluate the candidate on a small paired subset, adopt only if better
        sub_tasks, sub_seeds = tasks, min(3, args.seeds)
        cand_path = codegen.write(fixed, run_dir / f"repair_r{rnd}" / "task.py")
        base_sub = verifier.verify(code_path, sub_tasks, seeds=sub_seeds,
                                   run_dir=run_dir / f"repair_r{rnd}" / "before",
                                   workers=args.workers)
        cand_sub = verifier.verify(cand_path, sub_tasks, seeds=sub_seeds,
                                   run_dir=run_dir / f"repair_r{rnd}" / "after",
                                   workers=args.workers)
        better = cand_sub.overall > base_sub.overall
        repairs.append({
            "round": rnd, "applied": True,
            "before": f"{100 * base_sub.overall:.0f}%", "after": f"{100 * cand_sub.overall:.0f}%",
            "decision": "adopted" if better else "rejected (no improvement)",
        })
        print(f"      subset {100 * base_sub.overall:.0f}% -> {100 * cand_sub.overall:.0f}% : "
              f"{'adopted' if better else 'rejected'}")
        if not better:
            break
        code_path = cand_path
        metrics = verifier.verify(code_path, tasks, seeds=args.seeds, seed0=args.seed0,
                                  run_dir=run_dir / f"repair_r{rnd}" / "full",
                                  workers=args.workers, progress=_progress)
        verifier.save(metrics, run_dir / "metrics.json")
        print("     ", verifier.brief(metrics))

    # final full-protocol verification (only if the loop screened on a subset)
    if first_seeds != args.seeds:
        print(f"[6/6] final verification: {len(tasks)} tasks x {args.seeds} seeds")
        metrics = verifier.verify(code_path, tasks, seeds=args.seeds, seed0=args.seed0,
                                  run_dir=run_dir / "verify_final", workers=args.workers,
                                  progress=_progress)
        verifier.save(metrics, run_dir / "metrics.json")
        print("     ", verifier.brief(metrics))

    # 7. report -------------------------------------------------------------
    recon = ("python -m agent.run "
             f"--taskbook {args.taskbook} --suite {CFG['runtime']['suite']} "
             f"--tasks {args.tasks} --seeds {args.seeds} "
             f"--seed0 {args.seed0} --tag {args.tag}"
             + (" --no-llm" if args.no_llm else "")
             + (f" --confirm-mode {args.confirm_mode}" if args.confirm_mode else ""))
    metric_d = json.loads((run_dir / "metrics.json").read_text())
    report = write_report(run_dir, {
        "run_id": run_id, "taskbook": args.taskbook, "tasks": tasks,
        "seeds": args.seeds, "seed0": args.seed0, "plan": pres.plan,
        "provenance": {"plan": {"source": pres.source, "attempts": pres.attempts},
                       "code": cprov},
        "metrics": metric_d, "diagnosis": diag, "repairs": repairs,
        "code_lines": len(code_path.read_text().splitlines()), "repro": recon,
    })
    manifest = {
        "run_id": run_id, "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "taskbook": args.taskbook, "suite": CFG["runtime"]["suite"], "tasks": tasks,
        "seeds": [args.seed0, args.seed0 + args.seeds - 1],
        "confirm_mode": os.environ.get("AGENT_CONFIRM_MODE", CFG["safety"]["mode"]),
        "llm": {"model": CFG["llm"]["model"] if not args.no_llm else None},
        "plan": json.loads((run_dir / "plan_meta.json").read_text()),
        "code": cprov, "repairs": repairs,
        "metrics": {k: metric_d[k] for k in ("overall", "n", "ok", "per_task",
                                            "mean_steps", "mean_duration_s", "confirmations")},
        "artifacts": {"plan": "plan.json", "code": "task.py", "metrics": "metrics.json",
                      "report": "report.md"},
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"\n=== done: {100 * metric_d['overall']:.1f}% success "
          f"({metric_d['ok']}/{metric_d['n']}) ===")
    print("report:", report)
    return 0 if metric_d["overall"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
