#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成报告用图：流水线架构 / 一天收敛曲线 / 失败分类。

    /home/wei/miniconda3/envs/smolvla/bin/python scripts/make_figures.py
    → reports/figures/{pipeline_architecture,convergence,failure_taxonomy}.png

数据来源：convergence 用的是今天各次 `--repairs 0` 运行的 overall（与 runs/*/metrics.json 一致），
failure_taxonomy 由最新变体运行的 trace.jsonl 统计得出。
"""
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.family"] = ["Noto Sans CJK HK", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

INK = "#14355f"
GREY = "#5b6470"
LIGHT = "#e8eef7"
ACC = "#238636"
WARN = "#c0392b"


# ----------------------------------------------------------------- 1. 架构图
def pipeline():
    fig, ax = plt.subplots(figsize=(11.2, 6.4), dpi=200)
    ax.set_xlim(0, 11.2)
    ax.set_ylim(0, 6.4)
    ax.axis("off")

    def box(x, y, w, h, title, sub, fc=LIGHT, ec=INK, tc=INK, fs=11, sfs=8.4):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06,rounding_size=0.12",
                                    linewidth=1.3, edgecolor=ec, facecolor=fc))
        ax.text(x + w / 2, y + h - 0.20, title, ha="center", va="top", fontsize=fs,
                color=tc, fontweight="bold")
        if sub:
            ax.text(x + w / 2, y + h - 0.52, sub, ha="center", va="top", fontsize=sfs,
                    color=GREY, linespacing=1.45)

    def arrow(x1, y1, x2, y2, color=INK, style="-|>", lw=1.5, ls="-", rad=0.0):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                                     mutation_scale=13, linewidth=lw, color=color,
                                     linestyle=ls, connectionstyle=f"arc3,rad={rad}"))

    ax.text(0.15, 6.20, "Agentic Robotics 流水线：自然语言任务书 → 可执行代码 → 评测 → 诊断 → 修复",
            fontsize=12.5, fontweight="bold", color=INK)

    x, w = 0.35, 2.55
    ys = [5.05, 4.05, 3.05, 2.05, 1.05, 0.10]
    h = 0.78
    stages = [
        ("① 任务理解", "agent/planner.py\nLLM → plan.json\n步骤 / 约束 / 风险 / 确认点"),
        ("② 代码生成", "agent/codegen.py\nLLM → task.py\nAST 白名单：只能调原语"),
        ("③ 仿真执行", "agent/executor.py\n每条 episode 独立子进程\ntrace.jsonl / run.log / mp4"),
        ("④ 达标评测", "agent/verifier.py\n固定 seed 协议\n成功率 / 节拍 / 确认次数"),
        ("⑤ 失败诊断", "agent/diagnose.py\n规则分类 + LLM 根因\nroot_cause / evidence"),
        ("⑥ 自动修复", "codegen.repair\n配对子集复测\n采纳 or 回退 → 全量"),
    ]
    for (t, s), y in zip(stages, ys):
        box(x, y, w, h, t, s)

    for i in range(len(ys) - 1):
        arrow(x + w / 2, ys[i], x + w / 2, ys[i + 1] + h)

    # 修复回环
    arrow(x + w, ys[5] + h / 2, x + w + 0.55, ys[5] + h / 2, color=ACC)
    ax.plot([x + w + 0.55, x + w + 0.55], [ys[5] + h / 2, ys[1] + h / 2], color=ACC, lw=1.5)
    arrow(x + w + 0.55, ys[1] + h / 2, x + w, ys[1] + h / 2, color=ACC)
    ax.text(x + w + 0.62, (ys[5] + ys[1]) / 2 + h / 2 + 0.05, "改代码\n重测", fontsize=8.2,
            color=ACC, ha="left", va="center", linespacing=1.4)

    # 中间产物列
    xa, wa = 3.55, 2.35
    arts = [
        ("taskbooks/*.md", "自然语言任务书\n工位 / 物料 / 目标 / 约束", 5.05),
        ("plan.json", "结构化计划\n+ plan_meta.json", 4.05),
        ("task.py", "生成的控制逻辑\n+ code_meta.json（校验）", 3.05),
        ("runs/<id>/", "verify/*/trace.jsonl\nmetrics.json", 2.05),
        ("diagnosis_r1.json", "失败根因 + 证据\n+ 修复建议", 1.05),
        ("repair_r1/", "before / after / full\n+ manifest.json", 0.10),
    ]
    for t, s, y in arts:
        box(xa, y, wa, h, t, s, fc="#fbfcfe", ec="#b9c2cf", tc=GREY, fs=9.6, sfs=8.0)
    for y in ys:
        arrow(x + w, y + h / 2, xa, y + h / 2, color="#8a929e", style="-|>", lw=1.2)

    # 右侧：安全 / 确认 / 感知
    xb, wb = 6.55, 4.25
    ax.add_patch(FancyBboxPatch((xb, 3.55), wb, 2.28, boxstyle="round,pad=0.06,rounding_size=0.12",
                                linewidth=1.3, edgecolor="#8e44ad", facecolor="#f7f2fb"))
    ax.text(xb + wb / 2, 5.62, "横切关注点（每个原语都过一遍）", ha="center", fontsize=10.5,
            color="#5b2c6f", fontweight="bold")
    bullets = [
        "人确认门控 agent/confirm.py：auto / manual / deny，四条门控\n"
        "（解除使能 / 夹爪闭合 / 释放 / 长距离移动），网页面板 + 急停",
        "安全层 agent/safety.py：工作空间 AABB、单步位移上限、e-stop 文件\n"
        "（每一步都检查）",
        "感知 agent/skills/perception.py：RGB-D 分割 + 深度反投影 + PCA；\n"
        "AGENT_PERCEPTION=vision 时位姿全部来自相机",
    ]
    y = 5.28
    for b in bullets:
        ax.text(xb + 0.18, y, "·", fontsize=11, color="#8e44ad", va="top")
        ax.text(xb + 0.38, y, b, fontsize=8.2, color="#3d3d3d", va="top", linespacing=1.5)
        y -= 0.62

    # 右下：评测协议
    ax.add_patch(FancyBboxPatch((xb, 0.10), wb, 3.20, boxstyle="round,pad=0.06,rounding_size=0.12",
                                linewidth=1.3, edgecolor="#2c7a7b", facecolor="#eef7f7"))
    ax.text(xb + wb / 2, 3.10, "评测口径（写死在 docs/protocol.md）", ha="center", fontsize=10.5,
            color="#1f5f60", fontweight="bold")
    lines = [
        "主任务：10 单件任务 × 10 固定初始状态 = 100 episodes",
        "变体任务：11 任务 × 10 seed = 110 episodes（每类 2 件）",
        "步数预算：400 + 800 × 本回合件数（单件 1200 / 四件 3600）",
        "初始状态：seed 1000..1009；采样器也必须种子化（A11）",
        "区域半长 = 物体半径 + 目标抖动（A13，否则物体被散布到场外）",
        "可行性先验：check_feasibility.py 必须 110/110 可 reset",
    ]
    y = 2.72
    for ln in lines:
        ax.text(xb + 0.22, y, "·", fontsize=11, color="#2c7a7b", va="top")
        ax.text(xb + 0.40, y, ln, fontsize=8.1, color="#333", va="top")
        y -= 0.40

    fig.savefig(OUT / "pipeline_architecture.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


# --------------------------------------------------------------- 2. 收敛曲线
def convergence():
    main = [(0, 98.0, "10-17 基线"), (1, 99.0, "搬运路线\n失速早退"), (2, 98.0, "本地判据\n重抓一次"),
            (3, 97.0, "采样器\n种子化"), (4, 100.0, "布局\n可行化"), (5, 100.0, "区域语义\n修正")]
    var = [(0, 58.2, "初始"), (1, 74.5, ""), (2, 75.4, "区域/搬运"), (3, 66.4, ""),
           (4, 63.6, "种子化后\n变难"), (5, 64.5, ""), (6, 70.0, "区域语义"), (7, 71.8, "+小件搬运")]

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 3.9), dpi=200)
    for ax, data, title, color, ylim in (
            (axes[0], main, "主任务 libero_bolt_v2（10 任务 × 10 seed = 100）", INK, (94, 101.5)),
            (axes[1], var, "变体任务 libero_bolt_multi（11 任务 × 10 seed = 110）", "#b9770e", (55, 80))):
        xs = [d[0] for d in data]
        ys = [d[1] for d in data]
        ax.plot(xs, ys, "-o", color=color, lw=2.0, ms=5.5, zorder=3)
        ax.fill_between(xs, ylim[0], ys, color=color, alpha=0.07)
        for x, y, note in data:
            ax.annotate(f"{y:.1f}%", (x, y), textcoords="offset points", xytext=(0, 9),
                        ha="center", fontsize=8.4, color=color, fontweight="bold")
            if note:
                ax.annotate(note, (x, y), textcoords="offset points", xytext=(0, -22),
                            ha="center", fontsize=7.2, color=GREY, linespacing=1.3)
        ax.set_title(title, fontsize=10.5, color=INK, pad=10)
        ax.set_ylim(*ylim)
        ax.set_xlabel("迭代（同一天，按修复顺序）", fontsize=8.6, color=GREY)
        ax.set_ylabel("成功率 %", fontsize=8.6, color=GREY)
        ax.grid(alpha=0.25, ls=":")
        ax.tick_params(labelsize=8, colors=GREY)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)

    fig.suptitle("一天的收敛：每次只改一处，数字随之变化（变体套件每轮会重新生成任务脚本，故有涨落）",
                 fontsize=10.8, color=INK, y=1.02)
    fig.tight_layout()
    fig.savefig(OUT / "convergence.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


# --------------------------------------------------------------- 3. 失败分类
def taxonomy():
    labels = ["含抓取失败", "步数预算耗尽", "含放置失败", "总共失败"]
    var_vals = [28, 24, 3, 28]
    main_vals = [0, 0, 0, 0]
    fig, ax = plt.subplots(figsize=(7.4, 3.4), dpi=200)
    y = range(len(labels))
    h = 0.36
    b1 = ax.barh([i + h / 2 for i in y], var_vals, height=h, color="#b9770e", label="变体任务（110 episodes）")
    b2 = ax.barh([i - h / 2 for i in y], main_vals, height=h, color=INK, label="主任务（100 episodes）")
    for bars in (b1, b2):
        for r in bars:
            w = r.get_width()
            ax.text(w + 0.4, r.get_y() + r.get_height() / 2, f"{int(w)}", va="center",
                    fontsize=8.6, color=GREY)
    ax.set_yticks(list(y), labels, fontsize=9)
    ax.set_xlabel("episode 数（同一 episode 可能同时计入多项）", fontsize=8.4, color=GREY)
    ax.set_title("失败分类：变体任务的瓶颈是抓取（28/28 失败都含抓取失败）", fontsize=10.5, color=INK)
    ax.legend(fontsize=8.2, frameon=False, loc="lower right")
    ax.grid(axis="x", alpha=0.25, ls=":")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=8, colors=GREY)
    fig.tight_layout()
    fig.savefig(OUT / "failure_taxonomy.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    pipeline()
    convergence()
    taxonomy()
    for f in sorted(OUT.glob("*.png")):
        print(f"{f.relative_to(ROOT)}  {f.stat().st_size // 1024} KB")
