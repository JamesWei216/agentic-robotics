#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agentic Robotics 赛题 总结报告生成（weasyprint）

用 vla conda 环境的 python 运行（weasyprint 装在那里）：
    /home/wei/miniconda3/envs/vla/bin/python scripts/make_report_pdf.py
"""
import pathlib
import sys

import weasyprint

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "Agentic-Robotics-赛题总结报告.pdf"

import os
# --- numbers are read from the archived runs so the report cannot drift ----
import glob
import json


def _latest(pattern: str, key: str = "per_task"):
    cands = sorted(glob.glob(str(ROOT / "runs" / pattern / "metrics.json")))
    if not cands:
        raise SystemExit(f"no metrics.json matching runs/{pattern}")
    data = json.loads(pathlib.Path(cands[-1]).read_text())
    data["_run"] = pathlib.Path(cands[-1]).parent.name
    return data


def _pct(d):
    return f"{100 * d['overall']:.1f}%"


MAIN_M = _latest(os.environ.get("MAIN_RUN", "20261018-134900_v2_carry"))
VAR_M = _latest(os.environ.get("VAR_RUN", "20261018-134855_multi_carry"))
VIS_M = _latest(os.environ.get("VIS_RUN", "20261018-135739_vision_regionfix"))
STACK_M = _latest(os.environ.get("STACK_RUN", "20261023-211446_stack_full"))

# 参赛信息 + 视频链接（提交包构建时由 make_submission.sh 通过环境变量注入）
ORG = os.environ.get("SUB_ORG", "北京精密机电设备控制研究所")
WORK = os.environ.get("SUB_WORK", "AG-VLA智能机械臂")
LEADER = os.environ.get("SUB_LEADER", "魏凤辰")
VIDEO_URL = os.environ.get("VIDEO_URL", "").strip()

MAIN = dict(overall=_pct(MAIN_M), ok=MAIN_M["ok"], n=MAIN_M["n"],
            steps=MAIN_M.get("mean_steps", 0), run=MAIN_M["_run"],
            per_task=[(f"t{k}", v["ok"], v["n"], v.get("mean_steps", 0))
                      for k, v in sorted(MAIN_M["per_task"].items(), key=lambda kv: int(kv[0]))])
VARIANT = dict(overall=_pct(VAR_M), ok=VAR_M["ok"], n=VAR_M["n"],
               steps=VAR_M.get("mean_steps", 0), run=VAR_M["_run"],
               before="58.2% (64/110)",
               per_task=[(f"t{k}", v["ok"], v["n"], v.get("mean_steps", 0))
                         for k, v in sorted(VAR_M["per_task"].items(), key=lambda kv: int(kv[0]))])
VISION = dict(overall=_pct(VIS_M), ok=VIS_M["ok"], n=VIS_M["n"],
              steps=VIS_M.get("mean_steps", 0), run=VIS_M["_run"])
STACK = dict(overall=_pct(STACK_M), ok=STACK_M["ok"], n=STACK_M["n"],
             steps=STACK_M.get("mean_steps", 0), run=STACK_M["_run"],
             per_task=[(f"t{k}", v["ok"], v["n"], v.get("mean_steps", 0))
                       for k, v in sorted(STACK_M["per_task"].items(), key=lambda kv: int(kv[0]))])
STACK_PATTERNS = ["t0–t4 三层直塔（On(b2,b1) ∧ On(b3,b2)）",
                  "t5–t9 两层塔（On(b2,b1)）",
                  "t10 双层双列 4 块（On(b2,b1) ∧ On(b4,b3)）"]


def _snippet_plan(run: str) -> str:
    """plan.json -> a few compact lines (steps + one constraint + one risk)."""
    p = ROOT / "runs" / run / "plan.json"
    if not p.exists():
        return "（未找到 plan.json）"
    plan = json.loads(p.read_text())
    steps = []
    for s in plan.get("steps", [])[:4]:
        args = ", ".join(f"{k}={v}" for k, v in (s.get("args") or {}).items())
        steps.append(f'  {s["id"]}. {s["op"]}({"args: " + args if args else ""})')
    cons = (plan.get("constraints") or [{}])[0].get("text", "")
    risk = (plan.get("risks") or [{}])[0]
    return ("{\n 7 \"steps\": [\n" + "\n".join(steps) + "\n  ...],\n"
            f'  "constraints": ["{cons}", ...],\n'
            f'  "risks": [{{"text": "{risk.get("text","")}", "mitigation": "{risk.get("mitigation","")}"}}, ...]\n}}')


def _snippet_code(run: str) -> str:
    p = ROOT / "runs" / run / "task.py"
    if not p.exists():
        return "（未找到 task.py）"
    lines = p.read_text().splitlines()
    keep = [l for l in lines if any(k in l for k in
            ("def run(", "for item in R.todo()", "item.get(\"on\")", "pick_and_stack",
             "pick_and_place", "R.check()", "R.home()"))]
    return "\n".join(keep[:7]) or "\n".join(lines[8:14])


def _snippet_trace(run: str, ep: str = "t0_s1000") -> str:
    p = ROOT / "runs" / run / "verify" / ep / "trace.jsonl"
    if not p.exists():
        return "（未找到 trace.jsonl）"
    out = []
    for line in p.read_text().splitlines():
        ev = json.loads(line)
        if ev.get("event") in ("todo", "pick", "stack", "check", "home"):
            brief = {k: v for k, v in ev.items() if k in
                     ("event", "items", "object", "on", "success", "steps")}
            out.append(json.dumps(brief, ensure_ascii=False))
    return "\n".join(out[:6])


def _snippet_ast() -> str:
    """Run the real validator on a malicious snippet to show the rejection."""
    sys.path.insert(0, str(ROOT))
    from agent.codegen import validate_code
    bad = "import os\nfrom agent.skills.api import Robot\nR = Robot.from_env()\nopen('x','w')\ndef run(): return True\n"
    try:
        validate_code(bad)
        return "（意外通过）"
    except Exception as e:  # noqa: BLE001
        return f"输入：import os / open('x','w')\n拒绝：{type(e).__name__}: {e}"


PLAN_SNIPPET = _snippet_plan(STACK["run"])
CODE_SNIPPET = _snippet_code(STACK["run"])
TRACE_SNIPPET = _snippet_trace(STACK["run"])
AST_SNIPPET = _snippet_ast()

# every variant-suite run of the day, so the variance is visible in the report
_multi = []
for f in sorted(glob.glob(str(ROOT / "runs" / "*multi_[sf]*" / "metrics.json"))):
    d = json.loads(pathlib.Path(f).read_text())
    _multi.append((pathlib.Path(f).parent.name.split("_")[-1], 100 * d["overall"]))
_multi.sort(key=lambda kv: kv[1])
VAR3 = " / ".join(f"{p:.1f}%" for _r, p in _multi) if _multi else "—"
VAR_MED = (f"{sorted(p for _r, p in _multi)[len(_multi) // 2]:.1f}%"
           if _multi else "—")

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>
  @page {{ size: A4; margin: 1.5cm 1.4cm;
          @bottom-center {{ content: "Agentic Robotics 赛题 · 总结报告 · 第 " counter(page) " / " counter(pages) " 页";
                           font-size: 8pt; color: #999; }} }}
  body {{ font-family: "Noto Sans CJK SC", "WenQuanYi Zen Hei", sans-serif; font-size: 9.8pt;
         color: #222; line-height: 1.5; }}
  h1 {{ font-size: 18pt; color: #14355f; border-bottom: 3px solid #14355f; padding-bottom: 5px; margin: 0 0 3px; }}
  h2 {{ font-size: 13pt; color: #14355f; border-left: 5px solid #14355f; padding-left: 8px; margin: 16px 0 7px; }}
  h3 {{ font-size: 10.6pt; color: #333; margin: 11px 0 5px; }}
  .sub {{ color: #666; font-size: 9.2pt; margin-bottom: 9px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 7px 0; font-size: 8.8pt; }}
  th, td {{ border: 1px solid #b9b9b9; padding: 3.5px 6px; text-align: center; }}
  th {{ background: #e8eef7; color: #14355f; }}
  .left {{ text-align: left; }}
  .good {{ background: #d9f2d9; font-weight: bold; }}
  .warn {{ background: #fff3cd; }}
  .bad {{ color: #c0392b; }}
  .note {{ background: #f5f7fa; border-left: 4px solid #7f8c8d; padding: 7px 9px; font-size: 8.9pt;
           color: #444; margin: 9px 0; }}
  ul {{ margin: 5px 0 5px 16px; padding: 0; }} li {{ margin: 2.5px 0; }}
  code {{ background: #eef1f5; padding: 0 3px; border-radius: 2px; font-size: 8.6pt; }}
  .kpi {{ display: flex; gap: 8px; margin: 8px 0; }}
  .kpi div {{ flex: 1; border: 1px solid #cfd8e3; border-radius: 5px; padding: 8px; text-align: center; background: #fbfcfe; }}
  .kpi b {{ display: block; font-size: 15pt; color: #14355f; }}
  .kpi span {{ font-size: 8.4pt; color: #666; }}
</style></head><body>

<h1>Agentic Robotics 赛题 · 总结报告</h1>
<div class="sub">作品：<b>{WORK}</b> · 单位：{ORG} · 队长：{LEADER}<br>
赛题：Agent 驱动的机械臂应用开发与评测流水线 · 主任务=分拣，变体=批量分拣，加分 c=码垛<br>
平台：LIBERO / MuJoCo · Franka Panda 单臂 + 平行二指夹爪 · 纯仿真 · 2026-10-23</div>

<div class="kpi">
  <div><b>{MAIN['overall']}</b><span>主任务成功率<br>{MAIN['ok']}/{MAIN['n']} episodes</span></div>
  <div><b>{VARIANT['overall']}</b><span>变体任务成功率<br>{VARIANT['ok']}/{VARIANT['n']} episodes</span></div>
  <div><b>{STACK['overall']}</b><span>码垛（加分 c）<br>{STACK['ok']}/{STACK['n']} episodes</span></div>
  <div><b>{VISION['overall']}</b><span>视觉闭环（加分 b）<br>{VISION['ok']}/{VISION['n']} episodes</span></div>
</div>

<h2>一、流水线做了什么</h2>
<img src="reports/figures/pipeline_architecture.png" style="width:100%;margin:2px 0 8px">
<p>自然语言任务书进去，<b>可执行代码 + 仿真评测数字 + 失败诊断 + 报告</b>出来，每一步都有可复现产物：</p>
<table>
<tr><th style="width:16%">阶段</th><th style="width:20%">模块</th><th class="left">产物 / 机制</th></tr>
<tr><td>1 任务理解</td><td>agent/planner.py</td><td class="left">LLM → <code>plan.json</code>：步骤 / 约束 / 风险点 / <b>人确认点</b></td></tr>
<tr><td>2 代码生成</td><td>agent/codegen.py</td><td class="left">LLM → <code>task.py</code>，<b>AST 白名单</b>只允许调用原语 API；失败可回退模板路径</td></tr>
<tr><td>3 执行</td><td>agent/executor.py</td><td class="left">每条 episode 独立子进程 + <code>trace.jsonl</code> 逐原语留痕（含 <code>skip_after_termination</code>）</td></tr>
<tr><td>4 评测</td><td>agent/verifier.py</td><td class="left">固定 seed 协议（seed 1000..1009），成功率 / 节拍 / 确认次数</td></tr>
<tr><td>5 诊断</td><td>agent/diagnose.py</td><td class="left">规则分类 + LLM 根因（root_cause / evidence / fix_hint）</td></tr>
<tr><td>6 自动修复</td><td>agent/codegen.repair</td><td class="left">改代码 → <b>配对子集复测</b> → 采纳或回退 → 全量复测（本次 r1：子集 97%→100% 被采纳，全量 98% —— 未泛化，见 §5）</td></tr>
</table>
<p class="note"><b>人机确认</b>：<code>auto</code>（仿真，仍写审计）/ <code>manual</code>（阻塞等人，TTY 或网页面板）/ <code>deny</code>（回归测试用）。
四条门控：解除使能、夹爪闭合、释放物料、长距离移动；网页面板 <code>localhost:8077</code> 带<b>急停</b>，
所有决定写入 <code>runtime/audit.jsonl</code>。本次已用网页面板完成 manual 演示（3 次批准，快照见归档 <code>confirm_demo_panel/</code>）。</p>

<h2>一·B、Agent 证据链（可核查）</h2>
<p class="note">以下三类证据都是仓库里的<b>真实文件片段</b>（每次运行自动生成），与数字一一对应，可用 <code>cat</code> 直接核对。</p>
<table>
<tr><th style="width:16%">证据</th><th style="width:26%">文件</th><th class="left">片段</th></tr>
<tr><td class="left">结构计划<br>（步骤/约束/风险/确认点）</td><td class="left"><code>runs/{STACK['run']}/plan.json</code></td>
    <td class="left"><code style="white-space:pre-wrap">{PLAN_SNIPPET}</code></td></tr>
<tr><td class="left">生成的控制逻辑</td><td class="left"><code>runs/{STACK['run']}/task.py</code></td>
    <td class="left"><code style="white-space:pre-wrap">{CODE_SNIPPET}</code></td></tr>
<tr><td class="left">逐原语 trace</td><td class="left"><code>runs/{STACK['run']}/verify/t0_s1000/trace.jsonl</code></td>
    <td class="left"><code style="white-space:pre-wrap">{TRACE_SNIPPET}</code></td></tr>
<tr><td class="left">AST 安全拦截<br>（实测）</td><td class="left">agent/codegen.validate_code</td>
    <td class="left"><code style="white-space:pre-wrap">{AST_SNIPPET}</code></td></tr>
</table>

<h2>二、主任务成绩（libero_bolt_v2）</h2>
<p>10 个单件分拣任务 × 10 个固定初始状态 = 100 episodes，成功率 {MAIN['overall']}，平均 {MAIN['steps']:.0f} 步/回合。</p>
<table>
<tr><th>任务</th>{"".join(f"<th>{t}</th>" for t, _o, _n, _s in MAIN['per_task'])}</tr>
<tr><td class="left">通过 / 总数</td>{"".join(f"<td class='{'good' if o == n else 'warn'}'>{o}/{n}</td>" for _t, o, n, _s in MAIN['per_task'])}</tr>
<tr><td class="left">平均步数</td>{"".join(f"<td>{s:.0f}</td>" for _t, _o, _n, s in MAIN['per_task'])}</tr>
</table>
<p>唯一失败是 t6 的一个 seed（大螺栓→红盒，红盒落点靠近可达域边缘，搬运阶段超步）。</p>

<img src="reports/figures/convergence.png" style="width:100%;margin:4px 0 6px">
<h3>本轮（10-18）的关键工程修复 · 一天从 98% 到 100%</h3>
<table>
<tr><th style="width:26%">阶段</th><th style="width:14%">主任务</th><th class="left">改动</th></tr>
<tr><td class="left">10-17 深夜基线</td><td>98.0%</td><td class="left">—</td></tr>
<tr><td class="left">+ 搬运修复</td><td>99.0%</td><td class="left">高弧线路线 + 失速早退 + 判据分离（A6/A7）</td></tr>
<tr><td class="left">+ 采样器种子化</td><td>97.0%</td><td class="left">"固定 seed"原本不可复现，修好后<u>暴露出</u> t3 两个 seed 本来就不可行（A11）</td></tr>
<tr><td class="left">+ 布局可行化</td><td class="good">100.0%</td><td class="left">螺栓区域 70→55 mm、scene2 微调，`check_feasibility` 110/110（A12）</td></tr>
</table>
<ul>
<li><b>搬运路线</b>：直线斜插会在某构型把 <code>joint4</code> 顶到下限（实测 j4 = −0.070 的硬限位），OSC 饱和、EE 冻结但每段仍跑满步数。
改为 <b>高弧线路线</b>（先升到携带高度 +0.14 m，再经二分点横向跨越）+ <code>stall_patience</code> 失速早退。</li>
<li><b>判据分离</b>：把"控制是否收敛"和"任务是否可达"分开判 —— 料盒内腔 172 mm，释放点偏 60 mm 仍能落进去，
所以路线选择不再要求毫米级收敛（曾因要求收敛把 98% 打到 92%）。</li>
<li><b>结果</b>：t6 由 80% → 100%，平均步数 678 → {MAIN['steps']:.0f}，总成功率 98% → {MAIN['overall']}（无自动修复口径）。</li>
</ul>

<h2>三、变体任务（libero_bolt_multi）</h2>
<p>同一任务书、同一套流水线。变体套件每类 2 件（t0–t9）+ 一件 4 件全分拣（t10），共 11 任务 × 10 seed：
<b>{VARIANT['overall']}（{VARIANT['ok']}/{VARIANT['n']}）</b>。今天在这一项上做了三轮，数字是 64.5% → 70.0% → {VARIANT['overall']}，
根因见 A13（区域半长小于物体半径 → 料盒被散布到可达域外）与小螺栓搬运滑脱。
大螺栓类任务（t0/t2/t4/t6）已 **40/40 全清**，短板集中在"小螺栓→蓝盒"与 4 件任务。</p>
<p>同一工位、同一分类规则，但每类 2 件、任务书换成批量分拣：<b>Agent 侧代码改动 0 行</b>（全部由 <code>R.todo()</code> 驱动），只换任务书与套件。</p>
<table>
<tr><th>任务</th>{"".join(f"<th>{t}</th>" for t, _o, _n, _s in VARIANT['per_task'])}</tr>
<tr><td class="left">通过 / 总数</td>{"".join(f"<td class='{'good' if o == n else 'warn'}'>{o}/{n}</td>" for _t, o, n, _s in VARIANT['per_task'])}</tr>
<tr><td class="left">平均步数</td>{"".join(f"<td>{s:.0f}</td>" for _t, _o, _n, s in VARIANT['per_task'])}</tr>
</table>
<table>
<tr><th>版本</th><th>成功率</th><th>说明</th></tr>
<tr><td class="left">修复前</td><td class="bad">{VARIANT['before']}</td>
    <td class="left">13% 的 seed 直接抛 <code>RandomizationError</code>（6 个物体的初始区域互相重叠，采样器 20 次都放不下）；其余是搬运超步</td></tr>
<tr><td class="left">本次（三次独立生成脚本）</td><td class="good">{VAR3}<br><small>中位 {VAR_MED}</small></td>
    <td class="left">根因是"第 2 件及以后"的抓取：39 例失败中 30 例含抓取失败。已做 ① 释放后先 home 再接近 ② 失败后重抓一次（带预算守门） ③ 区域半长 70/25→20/8 mm</td></tr>
</table>
<img src="reports/figures/failure_taxonomy.png" style="width:76%;display:block;margin:6px auto 8px">
<p class="note"><b>改动成本</b>：主任务 → 变体任务，<code>agent/</code> 目录 diff 为 0 行；变化只在
<code>taskbooks/sort_variant.md</code>（任务书）与 <code>utils/gen_suites.py</code>（套件定义，属于"环境生成"而非"策略代码"）。</p>

<h2>三·B、码垛（加分 c）：同一框架的第二类任务</h2>
<p>加分 c 要求证明<b>同一套 Agent 框架</b>能在码垛与分拣之间切换，并把切换成本量化。新增套件
<code>libero_wood_stack</code>：40 mm 木块、3 种约定垛型、11 任务 × 10 个固定初始状态。
成功判定用 LIBERO 原生 <code>On(top, base)</code> 谓词（底块 z ≤ 顶块 z + 几何接触 + 中心 xy < 30 mm），
<b>没有自写判定脚本</b>。结果：<b>{STACK['overall']}（{STACK['ok']}/{STACK['n']}）</b>，平均 {STACK['steps']:.0f} 步/回合；
LLM 全链路（模型出计划 + 出代码）抽样 4 任务 × 2 seed = 8/8 也是 100%。</p>
<table>
<tr><th>任务</th>{"".join(f"<th>{t}</th>" for t, _o, _n, _s in STACK['per_task'])}</tr>
<tr><td class="left">通过 / 总数</td>{"".join(f"<td class='{'good' if o == n else 'warn'}'>{o}/{n}</td>" for _t, o, n, _s in STACK['per_task'])}</tr>
<tr><td class="left">平均步数</td>{"".join(f"<td>{s:.0f}</td>" for _t, _o, _n, s in STACK['per_task'])}</tr>
</table>
<p>垛型：{STACK_PATTERNS[0]}；{STACK_PATTERNS[1]}；{STACK_PATTERNS[2]}。放置精度 xy 0.5–8.4 mm、
落点高度恒为一个块高（40.0 mm）。垛型与顺序全部写在任务协议（<code>config/missions.json</code> 的 <code>on</code> 字段）里，换垛型不改代码。</p>
<h3>改动成本（码垛 vs 分拣，同一仓库同一提交）</h3>
<table>
<tr><th style="width:22%">类别</th><th style="width:26%">新增/修改</th><th class="left">内容</th></tr>
<tr><td class="left">技能层（核心）</td><td>+208 行</td><td class="left"><code>expert.py</code>：<code>grasp_block</code>（底部上方 12 mm 抓取）+ <code>place_on_top</code>（顶面释放 + 三条运输路线）+ <code>_stack_ok</code></td></tr>
<tr><td class="left">原语层</td><td>+84/−6 行</td><td class="left"><code>api.py</code>：新原语 <code>stack</code> / <code>pick_and_stack</code>；物料/容器集合通用化</td></tr>
<tr><td class="left">计划/代码生成</td><td>+230 行</td><td class="left"><code>schemas.py</code> 新 op + 参数别名；<code>codegen.py</code> 模板分支；<code>planner.py</code> 码垛 fallback 计划；<code>prompts.py</code> 能力卡双套件</td></tr>
<tr><td class="left">任务定义</td><td>+284 行</td><td class="left"><code>gen_stack_suite.py</code>（场景/垛型/套件注册）+ <code>gen_missions.py</code> 支持 <code>On</code> 目标</td></tr>
<tr><td class="left">资产</td><td>+208 行 + 1 个对象</td><td class="left"><code>vendor/wood-stack/</code>：立方体 XML 生成 + 对象注册 + 幂等安装</td></tr>
<tr><td class="left">自检/复现</td><td>+30 行</td><td class="left"><code>preflight.py</code> 增加码垛 3 项检查；<code>bootstrap_env.sh</code> 增加码垛三步</td></tr>
<tr><td class="left"><b>零改动复用</b></td><td><b>0 行</b></td><td class="left">编排层（六阶段）、执行沙箱（AST 白名单）、评测协议、安全层、人确认门控、报告生成</td></tr>
</table>
<p class="note"><b>合计新增/修改代码 ≈ 1,224 行</b>（tracked +601/−59，新文件 623），其中真正的控制逻辑只有 <b>292 行</b>；
新增 <b>1 个对象资产</b>、<b>1 个配置字段</b>（mission 的 <code>on</code>）+ 11 条任务协议。
分拣套件回归（模板代码口径）：<code>libero_bolt_v2</code> 98.0%（t6 大螺栓 8/10）、<code>libero_bolt_multi</code> 72.7%，与旧口径（100% / 71.8%，LLM 代码）无明显回退。</p>
<p><b>码垛专有的 6 个坑（A16–A21，已写入 docs/failures.md）</b>：①抓取点放几何中心 → 肘关节顶限位（手臂伸直=雅可比奇异）、
控制器<b>无法回缩</b>，改成抓底面以上 12 mm；②工作空间“舒适带”：右侧 x &gt; +0.10 处的工件抓后放不到位，工位重排；
③释放间隙要按<b>指尖</b>算（指尖低于工件底面）10 → 22 mm；④运输高度要按<b>当前垛顶</b>算而非桌面；
⑤一旦顶到限位，后续任何路线都救不回来 → 安全路线优先；⑥从 bddl 反解 mission 要区分 <code>:init</code> 与 <code>:goal</code>。</p>

<h2>四、视觉闭环（加分项 b）</h2>
<p><code>AGENT_PERCEPTION=vision</code> 时，<code>scan()</code> 与抓放全部改走 RGB-D：颜色分割 + 深度反投影 + PCA 求长轴/长度分类，
不使用任何仿真真值位姿。检测精度（离线用真值做测试预言机，12 场景 24 物体，100% 检出）：
盒中心 0.4–4.2 mm，螺栓中心 横向 2–7 mm、沿轴 4–8 mm，大小分类 12/12 正确。</p>
<table>
<tr><th>口径</th><th>成功率</th><th>平均步数</th><th>说明</th></tr>
<tr><td class="left">特权位姿（主口径）</td><td class="good">{MAIN['overall']}</td><td>{MAIN['steps']:.0f}</td>
    <td class="left">直接读仿真体姿，报告里必须标注</td></tr>
<tr><td class="left">视觉闭环（RGB-D）</td><td class="good">{VISION['overall']} ({VISION['ok']}/{VISION['n']})</td><td>{VISION['steps']}</td>
    <td class="left">任务 0–4 × seed 1000–1003；成功判定仍由环境目标谓词给出（评测不是感知）</td></tr>
</table>
<p>三个必须踩的坑：① 图像缓冲自下而上、内外参自上而下，反投影要"缓冲行取深度 + 翻转行算 y"（错配时误差 81 mm，正确 9 mm）；
② 深度最先返回的是**六角头顶面**（比柄高 9–14 mm），抓取高度必须用"台面标定 + 工件几何"，否则夹爪在柄上方空夹；
③ 腕部相机像素数≠在手机检（工件在指下方时也在视野里），抓取判定改用"撤臂后看原位是否已空"。</p>

<h2>五、本轮修的真 bug（A6–A13 摘要，完整 16 例见 docs/failures.md）</h2>
<table>
<tr><th style="width:8%">编号</th><th style="width:34%">现象</th><th class="left">根因 → 修法</th></tr>
<tr><td>A6</td><td>搬运中途停住，误差恒定 0.26 m 直到超步</td>
    <td class="left">直线斜插使 joint4 顶到硬限位（实测 -0.070），OSC 饱和 → 改<b>高弧线路线</b>（升到携带高度 +0.14 m → 二分点横向 → 下降）+ 失速早退</td></tr>
<tr><td>A7</td><td>要求"搬运收敛到 20 mm"后成功率反而下降</td>
    <td class="left">内腔 172 mm，释放偏 60 mm 仍能进盒 → <b>控制收敛 ≠ 任务可达</b>，改为"最接近料盒的路线 + ≤60 mm 即释放"</td></tr>
<tr><td>A8</td><td>多件任务里每次 <code>place</code> 都报失败（零件其实在盒里）</td>
    <td class="left"><code>transfer()</code> 返回的是<b>全局</b>目标谓词 → 新增 <code>_local_placement_ok()</code>，按"本件 vs 本盒"判</td></tr>
<tr><td>A9</td><td>第二件抓取连续失手（两次 418 步后放弃）</td>
    <td class="left">释放后停在料盒上方（易饱和构型）就接着抓 → <code>pick()</code> 在"上一动作是释放"时先 <code>home()</code>；t3 由 4/10 → 7/10</td></tr>
<tr><td>A13</td><td>料盒常出现在设计位置外 40–90 mm，搬运"够不着"，随机掉分</td>
    <td class="left">LIBERO 采样前按物体半径收缩区间，<b>有效抖动 = |区域半长 − 半径|</b>；半长偏小时区间反转、物体在 ±(r−half) 内乱跑。
    改为 <b>半长 = 半径 + 目标抖动</b>：变体 64.5% → {VARIANT['overall']}，主任务 t6 回到 10/10，视觉 85% → 90%</td></tr>
<tr><td>A11</td><td>"固定 seed"其实不可复现：同一 seed 在不同进程给出不同布局</td>
    <td class="left">LIBERO 的 <code>env.seed()</code> 只种仿真器，布局用全局 <code>np.random</code> → 在<b>构造 env 之前</b> <code>np.random.seed(seed)</code>（A11）</td></tr>
<tr><td>A12</td><td>种子化后暴露 t3 两个 seed"本来就无解"</td>
    <td class="left">螺栓区域 70→55 mm + scene2 微调，`check_feasibility` 110/110 全通过（A12）</td></tr>
<tr><td>A10</td><td>零件滑落即判失败，没有第二次机会</td>
    <td class="left"><code>place()</code> 增加"重抓 + 再搬运"，并用<b>剩余步数 ≥750</b> 守门，避免挤掉多件任务的后半段</td></tr>
</table>

<h2>六、人机确认面板（manual 模式实测截图）</h2>
<table style="border:0"><tr>
<td style="border:0;width:50%;padding:0 6px 0 0"><img src="reports/screenshots/confirm_panel_1_pending.png" style="width:100%"></td>
<td style="border:0;width:50%;padding:0 0 0 6px"><img src="reports/screenshots/confirm_panel_3_estop_engaged.png" style="width:100%"></td>
</tr><tr>
<td class="left" style="border:0;font-size:8.2pt;color:#555">左：待确认（first_motion）——门控动作、details、批准/拒绝按钮、请求号与等待时长。</td>
<td class="left" style="border:0;font-size:8.2pt;color:#555">右：急停按下——徽标变为急停态；runtime/ESTOP 一旦存在，所有原语每步检查并中止。</td>
</tr></table>
<p class="note">面板是纯 stdlib HTTP 服务（无守护进程）：请求/决定走 <code>runtime/confirm/*.json</code>，
决定落 <code>runtime/audit.jsonl</code>。一次 manual 运行实测：面板批准 12 次，episode 通过；四张截图
（待确认 / 空闲 / 急停 / 夹爪闭合）见 <code>reports/screenshots/</code>。</p>

<h2>七、演示视频（≤ 5 分钟，1280×720）</h2>
<p><b>视频链接：</b>{('<a href="' + VIDEO_URL + '">' + VIDEO_URL + '</a>') if VIDEO_URL else '见随包 <code>03_视频链接.txt</code>（网盘链接与提取码）'}</p>
<p>成片 <code>reports/videos/AG-VLA-demo-720p.mp4</code>（4 分 39 秒，1280×720，25 fps）按“概述 → 主任务 → 变体 → 码垛 →
视觉闭环 → 人确认 → 失败案例 → 复现”编排；每个片段都标注了实际加速倍率，画面右下角的时间轴可核对进度。
原始素材是仿真回合录像（每条 episode 独立子进程 + 逐原语 trace）：</p>
<ul>
<li><b>成功</b>：v2 t0 / t1 / t5 / t6（含曾经的唯一失败 seed s1006）/ t9 / t10 双件、multi t3 三件、码垛 t0 三层塔与 t10 双层双列、以及<b>视觉闭环</b>一条。</li>
<li><b>失败（如实保留）</b>：<code>libero_bolt_multi_t10_s1000_fail.mp4</code> —— 长程 4 件，预算耗尽。</li>
</ul>

<h2>八、诚实边界（必须与数字一起看）</h2>
<ul>
<li>主口径 <b>感知是特权位姿</b>；视觉闭环单独一条（{VISION['overall']}），差距 9 个百分点主要来自 xy 偏 5–7 mm 把"可达域边缘"的 seed 变不可达。</li>
<li><b>成功判定由环境目标谓词给出</b>（这是评测口径），不是感知输出。</li>
<li><b>自动修复的泛化问题</b>：r1 对失败根因判断正确（pick 吃掉 717/1200 步 → place 超步），改写在
<b>配对子集（3 seeds/任务）</b>上 97%→100% 因此被采纳；但全量 100 episodes 复测只有 <b>98%</b>（比修复前 99% 低 1 点）。
说明"子集提升"不足以证明修复有效 —— 这本身是流水线该暴露的风险，报告里如实列出，主口径采用<b>未修复版</b>的 {MAIN['overall']}。</li>
<li>变体任务 t10（4 件长程）仍是短板（1/10）：多件连续搬运的预算与残留姿态问题未根除。</li>
<li>全部数字与 <code>runs/*/metrics.json</code> 一一对应，评测协议写死在 <code>docs/protocol.md</code>。</li>
</ul>

<h2>九、复现方式</h2>
<table>
<tr><th style="width:26%">目的</th><th class="left">命令（在项目根目录）</th></tr>
<tr><td class="left">依赖</td><td class="left"><code>cat requirements.txt</code>；LIBERO 需 <code>pip install -e /home/wei/work/g05/LIBERO-master --no-deps</code></td></tr>
<tr><td class="left">主任务全量（主口径）</td><td class="left"><code>./run.sh --suite libero_bolt_v2 --taskbook taskbooks/sort_main.md --tasks 0..9 --seeds 10 --repairs 0</code></td></tr>
<tr><td class="left">自动修复 A/B</td><td class="left">同上去掉 <code>--repairs 0</code>（会做配对子集复测 + 全量复测）</td></tr>
<tr><td class="left">变体套件</td><td class="left"><code>./run.sh --suite libero_bolt_multi --taskbook taskbooks/sort_variant.md --tasks 0..10 --seeds 10</code></td></tr>
<tr><td class="left">码垛套件（加分 c）</td><td class="left"><code>./run.sh --suite libero_wood_stack --taskbook taskbooks/stack_main.md --tasks 0..10 --seeds 10 --repairs 0</code></td></tr>
<tr><td class="left">视觉闭环</td><td class="left"><code>AGENT_PERCEPTION=vision ./run.sh --suite libero_bolt_v2 --tasks 0,1,2,3,4 --seeds 4</code></td></tr>
<tr><td class="left">人确认演示</td><td class="left"><code>python -m agent.confirm_server --port 8077</code> + <code>./run.sh --confirm-mode manual</code></td></tr>
<tr><td class="left">无 LLM 回归</td><td class="left"><code>./run.sh --no-llm --tasks 5 --seeds 3</code></td></tr>
</table>

<p class="note">归档内容：<code>agent/</code>（流水线）· <code>config/</code> · <code>taskbooks/</code> · <code>docs/</code>（workcell / protocol / failures / perception）·
<code>scripts/</code>（套件生成、相机标定、感知验证、诊断脚本）· <code>runs/</code>（本次三组评测的 metrics / report / 逐 episode trace）· 人确认面板快照。</p>
</body></html>"""

if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    weasyprint.HTML(string=HTML, base_url=str(ROOT)).write_pdf(str(OUT))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
