#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成汇报 PPT（16:9，12 页）。

    /home/wei/miniconda3/envs/rb_clean/bin/python scripts/make_ppt.py
    → reports/Agentic-Robotics-赛题汇报.pptx

数字与 runs/*/metrics.json 一致：主任务 100/100、变体 79/110、视觉 18/20。
"""
import pathlib

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt, Emu

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "Agentic-Robotics-赛题汇报.pptx"
FIG = ROOT / "reports" / "figures"
SHOT = ROOT / "reports" / "screenshots"

INK = RGBColor(0x14, 0x35, 0x5F)
GREY = RGBColor(0x5B, 0x64, 0x70)
ACC = RGBColor(0x23, 0x86, 0x36)
WARN = RGBColor(0xC0, 0x39, 0x2B)
LIGHT = RGBColor(0xE8, 0xEE, 0xF7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Microsoft YaHei"

W, H = Inches(13.333), Inches(7.5)


def new_deck():
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    return prs


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def text(slide, x, y, w, h, lines, size=16, color=INK, bold=False, align=PP_ALIGN.LEFT,
         spacing=1.25, anchor=MSO_ANCHOR.TOP):
    """lines: str 或 [(text, size, color, bold), ...]"""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    if isinstance(lines, str):
        lines = [(lines, size, color, bold)]
    for i, item in enumerate(lines):
        t, s, c, b = (item + (color, bold))[:4] if isinstance(item, tuple) else (item, size, color, bold)
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        r = p.add_run()
        r.text = t
        r.font.size = Pt(s)
        r.font.bold = b
        r.font.color.rgb = c
        r.font.name = FONT
    return tb


def header(slide, title, sub=""):
    bar = slide.shapes.add_shape(1, 0, 0, W, Inches(0.09))
    bar.fill.solid(); bar.fill.fore_color.rgb = INK; bar.line.fill.background()
    text(slide, Inches(0.55), Inches(0.28), W - Inches(1.1), Inches(0.7),
         [(title, 26, INK, True)])
    if sub:
        text(slide, Inches(0.55), Inches(0.95), W - Inches(1.1), Inches(0.4),
             [(sub, 13, GREY, False)])


def kpi(slide, x, y, w, h, value, label, sub="", color=INK):
    box = slide.shapes.add_shape(1, x, y, w, h)
    box.fill.solid(); box.fill.fore_color.rgb = RGBColor(0xFB, 0xFC, 0xFE)
    box.line.color.rgb = RGBColor(0xCF, 0xD8, 0xE3)
    text(slide, x, y + Inches(0.12), w, Inches(0.7), [(value, 30, color, True)], align=PP_ALIGN.CENTER)
    text(slide, x, y + Inches(0.82), w, Inches(0.36), [(label, 12.5, GREY, False)], align=PP_ALIGN.CENTER)
    if sub:
        text(slide, x, y + Inches(1.15), w, Inches(0.4), [(sub, 10.5, RGBColor(0x8A, 0x8F, 0x98), False)],
             align=PP_ALIGN.CENTER)


def bullets(slide, x, y, w, h, items, size=14.5, color=INK, gap=6):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame; tf.word_wrap = True
    for i, it in enumerate(items):
        if isinstance(it, tuple):
            head, body = it
        else:
            head, body = it, ""
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        p.line_spacing = 1.3
        r = p.add_run(); r.text = "· "
        r.font.size = Pt(size); r.font.color.rgb = INK; r.font.name = FONT
        if head:
            r2 = p.add_run(); r2.text = head
            r2.font.size = Pt(size); r2.font.bold = True; r2.font.color.rgb = color; r2.font.name = FONT
        if body:
            r3 = p.add_run(); r3.text = body
            r3.font.size = Pt(size - 1.2); r3.font.color.rgb = GREY; r3.font.name = FONT
    return tb


def table(slide, x, y, w, rows, col_w=None, size=11, header_fill=INK):
    r, c = len(rows), len(rows[0])
    shape = slide.shapes.add_table(r, c, x, y, w, Inches(0.3 * r)).table
    if col_w:
        for i, cw in enumerate(col_w):
            shape.columns[i].width = Inches(cw)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = shape.cell(i, j)
            cell.text = str(val)
            cell.margin_left = cell.margin_right = Inches(0.06)
            cell.margin_top = cell.margin_bottom = Inches(0.02)
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
            r_ = p.runs[0] if p.runs else p.add_run()
            r_.font.size = Pt(size); r_.font.name = FONT
            r_.font.bold = (i == 0)
            r_.font.color.rgb = WHITE if i == 0 else INK
            cell.fill.solid()
            cell.fill.fore_color.rgb = header_fill if i == 0 else (
                RGBColor(0xF7, 0xF9, 0xFC) if i % 2 == 0 else WHITE)
    return shape


def picture(slide, path, x, y, max_w, max_h=None):
    if not pathlib.Path(path).exists():
        return None
    from PIL import Image
    iw, ih = Image.open(path).size
    ratio = iw / ih
    w = max_w
    h = int(w / ratio)
    if max_h and h > max_h:
        h = max_h
        w = int(h * ratio)
    return slide.shapes.add_picture(str(path), x, y, width=w, height=h)


# ------------------------------------------------------------------ slides
def build():
    prs = new_deck()

    # 1 封面
    s = blank(prs)
    bg = s.shapes.add_shape(1, 0, 0, W, H)
    bg.fill.solid(); bg.fill.fore_color.rgb = RGBColor(0x0F, 0x17, 0x21); bg.line.fill.background()
    text(s, Inches(0.9), Inches(2.1), Inches(11.5), Inches(1.2),
         [("Agentic Robotics", 40, WHITE, True)])
    text(s, Inches(0.9), Inches(3.05), Inches(11.5), Inches(1.0),
         [("Agent 驱动的机械臂应用开发与评测流水线", 24, RGBColor(0x7E, 0xE7, 0x87), False)])
    text(s, Inches(0.9), Inches(4.1), Inches(11.5), Inches(1.2),
         [("主任务：分拣（10 任务 × 10 初始状态 = 100 episodes，100/100）", 15,
           RGBColor(0xC9, 0xD1, 0xD9), False),
          ("平台：LIBERO / MuJoCo · Franka Panda + 平行二指夹爪 · 纯仿真", 15,
           RGBColor(0xC9, 0xD1, 0xD9), False)])
    text(s, Inches(0.9), Inches(6.3), Inches(11.5), Inches(0.5),
         [("2026-10-18", 13, RGBColor(0x8A, 0x8F, 0x98), False)])

    # 2 一页看懂
    s = blank(prs)
    header(s, "一页看懂", "自然语言任务书进去，可执行代码 / 评测数字 / 失败诊断 / 报告出来")
    kpi(s, Inches(0.55), Inches(1.5), Inches(2.9), Inches(1.6), "100%", "主任务成功率", "100/100 episodes")
    kpi(s, Inches(3.62), Inches(1.5), Inches(2.9), Inches(1.6), "71.8%", "变体任务成功率", "79/110 episodes",
        RGBColor(0xB9, 0x77, 0x0E))
    kpi(s, Inches(6.69), Inches(1.5), Inches(2.9), Inches(1.6), "90%", "视觉闭环（加分 b）", "18/20 episodes", ACC)
    kpi(s, Inches(9.76), Inches(1.5), Inches(2.9), Inches(1.6), "686", "主任务平均步数", "34.3 s / episode")
    bullets(s, Inches(0.55), Inches(3.45), Inches(12.2), Inches(3.4), [
        ("六个阶段全自动：", "任务书 → LLM 计划（步骤/约束/风险/确认点）→ LLM 生成代码（AST 白名单）→ 逐 episode 子进程执行 → 固定 seed 评测 → 失败诊断 → 自动修复"),
        ("不让 LLM 裸写控制代码：", "它只生成编排与参数，动作走一层已验证原语（抓取点按工件几何算、搬运有回退路线、释放高度按内腔底面算）"),
        ("人机确认是硬门控：", "auto / manual / deny 三模式，四条门控（解除使能 / 夹爪闭合 / 释放 / 长距离移动），网页面板带急停，全部写审计"),
        ("可复现：", "采样器种子化 + 区域半长 = 物体半径 + 抖动 + 可行性检查 110/110；干净环境按 requirements.txt 从零装通"),
    ], size=15)

    # 3 架构
    s = blank(prs)
    header(s, "流水线架构", "六阶段 + 修复回环；横切关注点：人确认 / 安全 / 感知")
    picture(s, FIG / "pipeline_architecture.png", Inches(0.45), Inches(1.35), Inches(12.4), Inches(5.7))

    # 4 原语契约
    s = blank(prs)
    header(s, "Agent 只能调用这些原语（API 契约）", "生成代码经 AST 白名单校验，越界直接判不通过")
    table(s, Inches(0.55), Inches(1.5), Inches(7.6), [
        ["原语", "作用", "失败时"],
        ["settle(n)", "场景静置（平躺螺栓前 30 步会下沉 ~13 mm）", "继续"],
        ["scan(cat)", "感知，返回 id / label / pose（vision 模式走 RGB-D）", "中止"],
        ["todo()", "本回合必须完成的分拣对（由 bddl goal 导出）", "—"],
        ["pick(obj)", "自上而下抓杆身；未夹到 → RuntimeError（自动重抓 1 次）", "重试"],
        ["place(obj, box)", "搬运 → 低空释放 → 撤回 → 返回本件是否进本盒", "重做一次"],
        ["home() / check()", "回安全位 / 判定成功（环境目标谓词）", "—"],
    ], col_w=[1.7, 4.7, 1.2], size=11.5)
    bullets(s, Inches(8.45), Inches(1.55), Inches(4.4), Inches(4.6), [
        ("为什么不让 LLM 直接写控制：", "解析式原语把 90%+ 的成功率固定住，LLM 只负责编排，避免随机性"),
        ("AST 白名单：", "只允许 import 原语 API、字面量、循环/条件；`os`/`subprocess`/文件访问一律拒绝"),
        ("失败可回退：", "生成不通过或 smoke 失败 → 模板路径（--no-llm 可完全离线）"),
    ], size=13)
    picture(s, FIG / "failure_taxonomy.png", Inches(8.35), Inches(4.15), Inches(4.5), Inches(2.9))

    # 5 主任务
    s = blank(prs)
    header(s, "主任务：10 个单件分拣任务 × 10 固定初始状态 = 100 episodes", "100/100，平均 686 步 / 34.3 s，0 次超步、0 次 OOM")
    table(s, Inches(0.55), Inches(1.55), Inches(12.2), [
        ["任务"] + [f"t{i}" for i in range(10)],
        ["通过"] + ["10/10"] * 10,
    ], col_w=[1.4] + [1.08] * 10, size=12)
    bullets(s, Inches(0.55), Inches(2.75), Inches(5.9), Inches(3.6), [
        ("上一轮的瓶颈：", "t6（大螺栓→红盒）只有 8–10/10，且平均 964 步 —— 搬运阶段被关节限位卡住"),
        ("根因两处：", "① 直线斜插把 elbow 顶到硬限位（j4 = −0.070）② 料盒被「区域语义」错散布到可达域外（A13）"),
        ("修法：", "高弧线路线 + 失速早退；区域半长 = 物体半径 + 抖动；小件搬运降速"),
    ], size=13.5)
    picture(s, FIG / "convergence.png", Inches(6.6), Inches(2.6), Inches(6.2), Inches(4.0))

    # 6 变体任务
    s = blank(prs)
    header(s, "变体任务：每类 2 件（11 任务 × 10 seed = 110 episodes）", "79/110 = 71.8%；大螺栓类任务 40/40 全清")
    table(s, Inches(0.55), Inches(1.6), Inches(12.2), [
        ["任务"] + [f"t{i}" for i in range(11)],
        ["通过"] + ["10/10", "6/10", "10/10", "6/10", "10/10", "2/10", "10/10", "9/10", "9/10", "3/10", "4/10"],
    ], col_w=[1.3] + [0.99] * 11, size=11.5)
    bullets(s, Inches(0.55), Inches(2.9), Inches(6.4), Inches(3.8), [
        ("换任务的改动成本：", "只加一份任务书（68 行）——`git diff v0.1-main v0.2-variant -- agent/` 为空（0 行）"),
        ("瓶颈：", "28 例失败里 28 例含抓取失败、24 例预算耗尽，集中在小螺栓（13 mm 柄）的第 2 件及以后"),
        ("已做：", "释放后先 home 再接近、失败重抓一次（带预算守门）、小件降速、区域语义修正"),
        ("下一步：", "分层子目标编排（一件一闭环 + 回安全位），而不是一个脚本顺序跑四件"),
    ], size=13.5)
    picture(s, FIG / "failure_taxonomy.png", Inches(7.15), Inches(2.95), Inches(5.6), Inches(3.6))

    # 7 视觉闭环
    s = blank(prs)
    header(s, "加分 b · 视觉闭环：位姿全部来自 RGB-D", "AGENT_PERCEPTION=vision · 18/20 = 90%（离线核对 24/24 检出）")
    bullets(s, Inches(0.55), Inches(1.6), Inches(6.4), Inches(5.0), [
        ("流程：", "HSV 分割（蓝/红盒 + 钢件，蓝通道 ≥ 红通道排除米色台面）→ 连通域与尺寸门限 → 深度反投影 → PCA 求长轴/长度分类 → 盒口与内腔几何"),
        ("精度（真值只作测试预言机）：", "盒中心 0.4–4.2 mm；螺栓横向 2–7 mm、沿轴 4–8 mm；大小分类 12/12；假目标 0（门限前每场景 4 个）"),
        ("运行时不用真值：", "body_pos / body_rot / site_state 三个查询全部由检测结果提供"),
        ("三个必须踩的坑：", "① 图像缓冲自下而上 vs 内外参自上而下（错配 81 mm，正确 9 mm）② 深度最先返回六角头顶面（比柄高 9–14 mm）③ 腕部像素数 ≠ 在手机检"),
    ], size=13)
    text(s, Inches(7.25), Inches(1.9), Inches(5.4), Inches(4.6),
         [("表：视觉 vs 特权位姿", 15, INK, True),
          ("", 8, GREY, False),
          ("特权位姿（主口径）  100/100", 14, GREY, False),
          ("视觉闭环（RGB-D）   18/20（90%）", 14, ACC, True),
          ("", 8, GREY, False),
          ("差距来源：xy 偏 5–7 mm 会把「恰好够得着」变成「差一点」；小螺栓柄夹持接触面小", 12, GREY, False)])

    # 8 人确认 + 安全
    s = blank(prs)
    header(s, "人机确认与安全（赛题硬性要求）", "三模式 + 四条门控 + 网页面板 + 急停 + 审计")
    picture(s, SHOT / "confirm_panel_1_pending.png", Inches(0.5), Inches(1.5), Inches(6.0), Inches(4.2))
    picture(s, SHOT / "confirm_panel_3_estop_engaged.png", Inches(6.75), Inches(1.5), Inches(6.0), Inches(4.2))
    text(s, Inches(0.55), Inches(5.85), Inches(6.0), Inches(0.9),
         [("左：待确认（first_motion）——门控动作、details、批准/拒绝、请求号与等待时长", 11, GREY, False)])
    text(s, Inches(6.8), Inches(5.85), Inches(6.0), Inches(0.9),
         [("右：急停按下——徽标变急停态；runtime/ESTOP 存在时每个原语每步检查并中止", 11, GREY, False)])

    # 9 失败案例
    s = blank(prs)
    header(s, "失败案例分析（docs/failures.md 共 16 例）", "每条都有：现象 → 根因 → 修复 → 影响 → 可复现证据")
    table(s, Inches(0.55), Inches(1.55), Inches(12.2), [
        ["编号", "现象", "根因 / 修法"],
        ["A6", "搬运中途停住、误差恒定 0.26 m 直到超步", "直线斜插使 joint4 顶硬限位（−0.070）→ 高弧线路线 + 失速早退"],
        ["A9", "第 2 件抓取连续失手（两次 418 步后放弃）", "释放后停在料盒上方就接着抓 → pick 前先 home；t3 4/10 → 7/10"],
        ["A11", "同一 seed 在不同进程给出不同布局", "env.seed() 只种仿真器，布局用全局 np.random → 构造 env 前种子化"],
        ["A13", "料盒常出现在设计位置外 40–90 mm", "有效抖动 = |区域半长 − 半径|，区间反转 → 半长 = 半径 + 抖动"],
    ], col_w=[0.9, 5.2, 6.1], size=12)
    text(s, Inches(0.55), Inches(4.35), Inches(12.2), Inches(2.2),
         [("这四个 bug 有一个共同点：它们都不抛异常，只是让成功率随机抖动 —— 最容易被误判成「策略不行」。", 14, WARN, True),
          ("所以评测协议里加了两条硬检查：check_feasibility（110/110 可 reset）与 preflight（7 项环境自检），任何一次跑分前先过这两道。", 13, GREY, False)])

    # 10 可复现
    s = blank(prs)
    header(s, "可复现性（初赛硬性要求）", "固定 seed 协议 + 干净环境 + 一键入口")
    bullets(s, Inches(0.55), Inches(1.55), Inches(6.3), Inches(4.8), [
        ("固定 seed：", "seed 1000..1009；采样器也种子化（A11），否则同一 seed 每次布局不同"),
        ("可行性先验：", "check_feasibility.py 要求 110/110 初始状态可 reset，否则先修套件几何"),
        ("干净环境：", "conda create python=3.10 + pip install -r requirements.txt + LIBERO editable → preflight 7/7 → t6 2/2 通过（docs/setup.md）"),
        ("一键入口：", "./run.sh --suite … --taskbook … --tasks … --seeds …；--no-llm 可完全离线"),
        ("补出的隐式依赖：", "pyyaml / termcolor / bddl / easydict / matplotlib / gym==0.22（LIBERO 的 setup.py 里 install_requires 为空）"),
    ], size=13.5)
    table(s, Inches(7.2), Inches(1.7), Inches(5.6), [
        ["git 证据", "结果"],
        ["diff v0.1→v0.2 的 agent/", "0 行（变体任务不改控制链路）"],
        ["diff v0.1→v0.2 全部", "1 文件 / +68 行（任务书）"],
        ["tags", "v0.1-main → v0.6-figures"],
    ], col_w=[2.6, 3.0], size=11.5)
    text(s, Inches(7.2), Inches(4.15), Inches(5.6), Inches(2.2),
         [("运行产物", 14, INK, True),
          ("runs/<id>/：plan.json、task.py、metrics.json、diagnosis_r1.json、repair_r1/、report.md、manifest.json；每个 episode 一个目录（trace.jsonl / run.log / result.json）", 11.5, GREY, False)])

    # 11 诚实边界
    s = blank(prs)
    header(s, "诚实边界（与数字一起看）", "哪些没做、哪些只是「能跑」、哪些结论还不能下")
    bullets(s, Inches(0.55), Inches(1.6), Inches(12.2), Inches(5.0), [
        ("没做：", "加分 a 虚实迁移（SO-101 真机）—— 3–5 天且风险最高，本轮不排；加分 c 只做了「换数量/布局」，没做跨任务类型（码垛）"),
        ("变体 71.8%：", "失败全部含抓取失败，集中在小螺栓的第 2 件及以后；根因是残留姿态 + 邻件遮挡下预抓取位姿触关节限位"),
        ("视觉 90%：", "小螺栓 13 mm 柄夹持偶有滑脱；蓝盒内腔底面被近侧盒壁遮挡，释放点估计偏高 12 mm"),
        ("自动修复：", "r1 根因判断正确、配对子集 97%→100% 被采纳，但全量复测 98%（未泛化）→ 单列为风险，主口径不用它"),
        ("主口径感知是特权位姿：", "视觉闭环单列一条，不混进主口径"),
        ("不做策略学习：", "控制逻辑是解析式原语组合；VLA 微调（14.5% / 10.2%）只作对照基线"),
    ], size=14)

    # 12 交付与下一步
    s = blank(prs)
    header(s, "交付物与下一步", "新文件夹：桌面 / Agentic-Robotics-提交包-20261018")
    table(s, Inches(0.55), Inches(1.55), Inches(6.4), [
        ["目录", "内容"],
        ["01_repo", "git bundle + push 说明（含 6 个 tag）"],
        ["02_zip", "源码包 + 关键运行包"],
        ["03_video", "演示片 69 s + 10 条原始 episode"],
        ["04_ppt", "本 PPT"],
        ["05_report", "PDF 报告（5 页）+ RESULT_SUMMARY + STATUS"],
    ], col_w=[1.5, 4.9], size=11.5)
    bullets(s, Inches(7.2), Inches(1.6), Inches(5.6), Inches(4.6), [
        ("下一步 1：", "变体套件分层子目标编排（目标 75%+）"),
        ("下一步 2：", "视觉模式小件夹持闭环（目标 95%）"),
        ("下一步 3：", "如果要真机加分：SO-101 零样本入口 + 同模块视觉"),
        ("提交前需确认：", "官方是否有《任务说明书》与最低指标数值；repo 远端地址"),
    ], size=13.5)

    prs.save(str(OUT))
    print(f"{OUT.relative_to(ROOT)}  {OUT.stat().st_size // 1024} KB  {len(prs.slides.__iter__.__self__._sldIdLst)} slides")


if __name__ == "__main__":
    build()
