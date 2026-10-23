#!/usr/bin/env python3
"""Compose the ≤5 min / 1280x720 submission video from the episode clips.

官方要求：技术文档 PDF 内必须含 **≤ 5 分钟、≥ 720P** 的作品介绍视频网盘链接。
源素材是 256x256 的仿真回合录像，所以这里合成到 1280x720 画布：
左侧放回合录像（放大到 600x600），右侧放该段的指标与要点；段落之间用信息卡。

    python scripts/make_demo_video_720p.py            # -> reports/videos/AG-VLA-demo-720p.mp4

只用 PIL + imageio（venv 内已有），不依赖系统 ffmpeg。
"""
import json
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "videos"
VID = ROOT / "reports" / "videos"
FIG = ROOT / "reports" / "figures"
SHOT = ROOT / "reports" / "screenshots"

W, H, FPS = 1280, 720, 25
FONT_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_M = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"

BG = (14, 18, 26)
PANEL = (22, 28, 38)
ACCENT = (86, 176, 255)
ACCENT2 = (120, 230, 190)
WARN = (255, 170, 90)
FG = (232, 238, 246)
DIM = (150, 163, 180)


def font(path, size):
    return ImageFont.truetype(path, size)


F = {
    "title": font(FONT_B, 64),
    "sub": font(FONT_R, 30),
    "h2": font(FONT_B, 42),
    "body": font(FONT_R, 26),
    "bul": font(FONT_R, 27),
    "small": font(FONT_R, 21),
    "metric": font(FONT_B, 40),
    "clip_tag": font(FONT_M, 20),
}


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if draw.textlength(cur + ch, font=fnt) > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def base_canvas():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # subtle vertical gradient
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(14 + 10 * t), int(18 + 12 * t), int(26 + 14 * t)))
    return img


def footer(d, label, pct):
    d.rectangle([0, H - 6, W, H], fill=(30, 36, 48))
    d.rectangle([0, H - 6, int(W * pct), H], fill=ACCENT)
    d.text((28, H - 40), "AG-VLA 智能机械臂 · <已按赛题要求隐去>", font=F["small"], fill=DIM)
    tw = d.textlength(label, font=F["small"])
    d.text((W - 28 - tw, H - 40), label, font=F["small"], fill=DIM)


def card_title(lines, kicker, pct):
    """Big centred title card."""
    img = base_canvas()
    d = ImageDraw.Draw(img)
    y = 180
    if kicker:
        d.text((90, y - 54), kicker, font=F["small"], fill=ACCENT)
    for text, size, color in lines:
        d.text((90, y), text, font=F[size], fill=color)
        y += int(size_px(size) * 1.45)
    d.rectangle([92, y + 10, 92 + 160, y + 16], fill=ACCENT2)
    footer(d, pct[0], pct[1])
    return img


def size_px(key):
    return {"title": 64, "h2": 42, "sub": 30, "body": 26, "bul": 27}.get(key, 26)


def bullets_card(title, items, pct, note=None):
    img = base_canvas()
    d = ImageDraw.Draw(img)
    d.text((80, 64), title, font=F["h2"], fill=FG)
    d.rectangle([80, 128, 250, 134], fill=ACCENT)
    y = 180
    for item in items:
        if isinstance(item, tuple):
            text, color = item
        else:
            text, color = item, FG
        d.ellipse([88, y + 12, 100, y + 24], fill=ACCENT if color is FG else color)
        for line in wrap(d, text, F["bul"], W - 220):
            d.text((122, y), line, font=F["bul"], fill=color)
            y += 38
        y += 14
    if note:
        d.text((80, H - 90), note, font=F["small"], fill=DIM)
    footer(d, pct[0], pct[1])
    return img


def clip_frame(img, clip_img, tag):
    """Paste the upscaled sim frame on the left, keep the right column for text."""
    cw = 600
    frame = clip_img.resize((cw, cw), Image.LANCZOS)
    img.paste(frame, (60, 60))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 60, 60 + cw, 60 + cw], outline=(60, 70, 88), width=2)
    d.text((60, 60 + cw + 14), tag, font=F["clip_tag"], fill=DIM)
    return img


def right_column(d, rows, x=710, y=96, width=520):
    for kind, text in rows:
        if kind == "h":
            for line in wrap(d, text, F["h2"], width):
                d.text((x, y), line, font=F["h2"], fill=FG)
                y += 56
            d.rectangle([x, y + 4, x + 90, y + 9], fill=ACCENT)
            y += 30
        elif kind == "m":
            d.text((x, y), text, font=F["metric"], fill=ACCENT2)
            y += 58
        elif kind == "b":
            d.ellipse([x + 2, y + 12, x + 12, y + 22], fill=ACCENT)
            for i, line in enumerate(wrap(d, text, F["body"], width - 30)):
                d.text((x + 26, y), line, font=F["body"], fill=FG)
                y += 34
            y += 10
        elif kind == "w":
            for line in wrap(d, text, F["small"], width):
                d.text((x, y), line, font=F["small"], fill=WARN)
                y += 28
            y += 8


def figure_scene(path, rows, pct, scale=0.72):
    img = base_canvas()
    d = ImageDraw.Draw(img)
    fig = Image.open(path).convert("RGB")
    bw = int(W * scale)
    bh = int(fig.height * bw / fig.width)
    if bh > 560:
        bh = 560
        bw = int(fig.width * bh / fig.height)
    fig = fig.resize((bw, bh), Image.LANCZOS)
    img.paste(fig, (60, 90))
    right_column(d, rows, x=60 + bw + 30 if 60 + bw + 30 < 700 else 700, width=W - (60 + bw + 30) - 40)
    footer(d, pct[0], pct[1])
    return img


def main():
    import imageio.v2 as iio

    metrics_v2 = json.loads((ROOT / "runs/20261018-134900_v2_carry/metrics.json").read_text())
    metrics_multi = json.loads((ROOT / "runs/20261023-212018_multi_recheck_stackwork/metrics.json").read_text())
    metrics_stack = json.loads((ROOT / "runs/20261023-211446_stack_full/metrics.json").read_text())
    metrics_vision = json.loads((ROOT / "runs/20261018-135739_vision_regionfix/metrics.json").read_text())

    def pct_of(m):
        return f"{m['ok']}/{m['n']} = {m['overall'] * 100:.1f}%"

    # total duration for the progress bar
    scenes = [
        ("title", 17),
        ("overview", 20),
        ("arch", 20),
        ("clip", 34, "libero_bolt_v2_t0_s1000_ok.mp4", "主任务 · t0 小螺栓 → 蓝盒"),
        ("clip", 38, "libero_bolt_multi_t3_s1001_ok.mp4", "变体任务 · t3 批量分拣"),
        ("clip", 33, "libero_wood_stack_t0_s1000_ok.mp4", "码垛 · t0 三层直塔"),
        ("clip", 24, "libero_wood_stack_t10_s1000_ok.mp4", "码垛 · t10 双层双列 4 块"),
        ("clip", 20, "libero_bolt_v2_t2_s1000_vision_ok.mp4", "视觉闭环 · RGB-D 分割 + 反投影"),
        ("shot", 17),
        ("clip", 24, "libero_bolt_multi_t10_s1000_fail.mp4", "失败案例 · 邻件遮挡下的后续抓取"),
        ("repro", 20),
        ("outro", 12),
    ]
    total = sum(s[1] for s in scenes)

    rows_main = [
        ("h", "主任务：螺栓按尺寸分拣"),
        ("m", pct_of(metrics_v2)),
        ("b", "10 个单件任务 × 10 个固定初始状态，全部 10/10"),
        ("b", "平均 686 步 / 34 秒一回合，0 次超步、0 次 OOM"),
        ("w", "成功判据：LIBERO 原生 In(bolt, bin) 谓词"),
    ]
    rows_multi = [
        ("h", "变体：批量分拣"),
        ("m", pct_of(metrics_multi)),
        ("b", "11 任务 × 10 seed，每回合 3–4 件连续分拣"),
        ("b", "失败集中在“第 2 件及以后”：邻件遮挡 + 残留姿态"),
        ("w", "已定位到预抓取位姿触关节限位，下一步做分层子目标编排"),
    ]
    rows_stack = [
        ("h", "码垛：木块堆叠（本次新增）"),
        ("m", pct_of(metrics_stack)),
        ("b", "11 任务 × 10 seed：三层直塔 / 两层塔 / 双层双列"),
        ("b", "成功判据改为原生 On(top, base)：接触 + 高度序 + xy < 30 mm"),
        ("b", "同一 Agent 框架，控制逻辑只新增 292 行"),
    ]
    rows_stack2 = [
        ("h", "垛型由任务协议下发"),
        ("b", "3 层直塔：On(b2,b1) ∧ On(b3,b2)"),
        ("b", "双层双列：两列各 2 块，4 次放置 / 回合"),
        ("b", "放置精度 0.5–8.4 mm，落点高度恒为 40.0 mm"),
        ("m", "100.0%"),
    ]
    rows_vision = [
        ("h", "加分 b：视觉闭环"),
        ("m", pct_of(metrics_vision)),
        ("b", "RGB-D 分割 + 反投影 + PCA，不用特权位姿"),
        ("b", "盒中心误差 0.4–4.2 mm，螺栓横向 2–7 mm"),
        ("w", "在线 90%（18/20），离线检出 24/24"),
    ]
    rows_fail = [
        ("h", "失败案例也交底"),
        ("b", "变体 t10 s1000：第 2 件起预抓取位姿触关节限位，超步失败"),
        ("b", "根因写进 docs/failures.md（A6–A21 共 21 例）"),
        ("w", "自动修复在子集上 97%→100%，但全量复测 98% —— 如实标注，不进主口径"),
    ]

    writer = iio.get_writer(OUT / "AG-VLA-demo-720p.mp4", fps=FPS, codec="libx264",
                            quality=8, macro_block_size=1, ffmpeg_log_level="error",
                            ffmpeg_params=["-pix_fmt", "yuv420p"])
    done = 0

    def pct_label():
        return (f"{int(done)}s / {total}s", done / total)

    for scene in scenes:
        kind, dur = scene[0], scene[1]
        n = dur * FPS
        tag = None
        rows = None
        if kind == "title":
            frames = [card_title(
                [("AG-VLA 智能机械臂", "title", FG),
                 ("Agent 驱动的机械臂应用开发与评测流水线", "sub", ACCENT),
                 ("分拣 100% · 变体 72.7% · 码垛 100% · 视觉闭环 90%", "body", FG)],
                "2026 年 Agentic Robotics 赛题 · 参赛作品", pct_label()) for _ in range(n)]
        elif kind == "overview":
            frames = [bullets_card("三个可复现的交付口径", [
                ("主任务：螺栓按尺寸分拣入对应颜色料盒 —— 100%（100/100）", FG),
                ("变体：同工位 4 件批量分拣 —— 72.7%（80/110）", FG),
                ("码垛：木块按约定垛型建塔 —— 100%（110/110）", ACCENT2),
                ("加分 b 视觉闭环 90% ／ 加分 d 人确认 + 急停已演示", FG),
            ], pct_label(),
                note="全部数字来自固定 seed 的公开初始状态，无隐藏测试集、无人工挑选样例") for _ in range(n)]
        elif kind == "arch":
            frames = [figure_scene(FIG / "pipeline_architecture.png", [
                ("h", "流水线（Agent 在链路里）"),
                ("b", "任务书 → LLM 计划 → LLM 生成代码"),
                ("b", "AST 白名单沙箱 → 逐回合执行 → trace"),
                ("b", "诊断 → 自动修复 → 复测 → 报告"),
                ("w", "人确认门控 auto/manual/deny + 急停全链路生效"),
            ], pct_label(), scale=0.52) for _ in range(n)]
        elif kind == "shot":
            frames = [figure_scene(SHOT / "confirm_panel_4_grasp.png", [
                ("h", "加分 d：人机确认 + 急停"),
                ("b", "抓取 / 释放 / 首次运动 / 长距离移动 四道门控"),
                ("b", "网页面板实时批准，决定写 runtime/audit.jsonl"),
                ("w", "manual 模式已演示：3 次批准、1 次急停"),
            ], pct_label(), scale=0.52) for _ in range(n)]
        elif kind == "repro":
            frames = [bullets_card("复现：三条命令 + 自检", [
                "bash scripts/bootstrap_env.sh  → 装依赖、装资产、生成四套任务与固定初始状态",
                "python scripts/preflight.py  → 8 项自检全绿（含码垛资产与套件注册）",
                "./run.sh --suite <套件> --taskbook <任务书> --seeds 10  → 复跑本视频里的数字",
                ("代码与运行日志：github.com/<你的GitHub用户名>/agentic-robotics", ACCENT2),
            ], pct_label(), note="干净环境（新建 conda + requirements 从零装）已验证 preflight 全绿") for _ in range(n)]
        elif kind == "outro":
            frames = [card_title(
                [("谢谢", "title", FG),
                 ("AG-VLA 智能机械臂 · <已按赛题要求隐去>", "body", ACCENT),
                 ("队长：魏凤辰", "body", DIM)],
                "2026-10-23", pct_label()) for _ in range(n)]
        else:  # clip scenes
            clip_name = scene[2]
            tag = scene[3]
            rows = {"主任务": rows_main, "变体": rows_multi, "码垛": rows_stack,
                    "双层": rows_stack2, "视觉": rows_vision, "失败": rows_fail}
            key = next(k for k in rows if clip_name.find(k) >= 0 or tag.startswith(k))
            rows = rows[key]
            reader = iio.get_reader(str(VID / clip_name))
            clip_frames = [f for f in reader]
            fps_clip = reader.get_meta_data().get("fps") or 10
            reader.close()
            # the source clip is real-time (10 fps recording of a 20 Hz controller was
            # sampled every 2nd step); squeezing it into this scene's duration speeds
            # it up, so the on-screen label states the actual factor
            speed = max(1.0, len(clip_frames) / fps_clip / dur)
            tag = f"{tag} · 约 {speed:.1f}× 加速" if speed > 1.15 else f"{tag} · 实时回放"
            frames = []
            for i in range(n):
                src = clip_frames[int(i * len(clip_frames) / n) % len(clip_frames)]
                img = base_canvas()
                clip_frame(img, Image.fromarray(src), tag)
                right_column(ImageDraw.Draw(img), rows)
                footer(ImageDraw.Draw(img), pct_label()[0], pct_label()[1])
                frames.append(img)
        for img in frames:
            writer.append_data(_as_array(img))
        done += dur
        print(f"  {kind:8s} {dur:>3}s  done {done}/{total}s")

    writer.close()
    out = OUT / "AG-VLA-demo-720p.mp4"
    print(f"\nwrote {out}  ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


def _as_array(img):
    import numpy as np
    return np.asarray(img.convert("RGB"))


if __name__ == "__main__":
    sys.exit(main())
