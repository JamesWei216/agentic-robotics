#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 10 条 episode 视频剪成一条 60–90 秒的演示片（标题卡 + 每段说明卡 + 片段 + 结尾卡）。

    /home/wei/miniconda3/envs/smolvla/bin/python scripts/make_demo_video.py
    → reports/videos/agentic-robotics-demo.mp4

素材：reports/videos/*.mp4（256×256 / 10 fps）。输出统一放大到 512×512、10 fps、yuv420p。
用 imageio-ffmpeg 自带的 ffmpeg 二进制，不依赖系统安装。
"""
import pathlib
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT = pathlib.Path(__file__).resolve().parent.parent
VID = ROOT / "reports" / "videos"
OUT = VID / "agentic-robotics-demo.mp4"
FF = imageio_ffmpeg.get_ffmpeg_exe()
SIZE = 512
FPS = 10
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

INK = (20, 53, 95)
GREY = (110, 118, 128)
BG = (247, 249, 252)

# (文件, 说明标题, 说明副标题, 截取起点秒数, 时长秒数)
CLIPS = [
    ("libero_bolt_v2_t0_s1000_ok.mp4",
     "主任务 · 大螺栓 → 红盒", "自上而下抓杆身，高弧线搬运，低空释放", 6, 8),
    ("libero_bolt_v2_t1_s1000_ok.mp4",
     "主任务 · 小螺栓 → 蓝盒", "小件搬运速度降到 0.010 m/step 防滑脱", 4, 7),
    ("libero_bolt_v2_t6_s1006_ok.mp4",
     "主任务 · 曾经的唯一失败 seed", "红盒贴可达域边缘；区域语义修正后通过", 2, 7),
    ("libero_bolt_v2_t10_s1000_ok.mp4",
     "主任务 · 双件全分拣", "R.todo() 两条目标依次完成", 5, 8),
    ("libero_bolt_v2_t2_s1000_vision_ok.mp4",
     "视觉闭环（加分 b）", "位姿全部来自 RGB-D：分割 + 反投影 + PCA", 3, 7),
    ("libero_bolt_multi_t3_s1001_ok.mp4",
     "变体任务 · 两件小螺栓", "第 2 件抓取前先回安全位", 8, 8),
    ("libero_bolt_multi_t10_s1000_fail.mp4",
     "变体任务 · 四件长程（失败，如实保留）", "3600 步预算耗尽；第 2 件后的抓取是瓶颈", 20, 8),
]


def font(path, size):
    return ImageFont.truetype(path, size)


def card(path, title, sub, footer=""):
    im = Image.new("RGB", (SIZE, SIZE), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, SIZE, 8], fill=INK)
    d.text((36, 120), title, font=font(FONT_BOLD, 34 if len(title) < 16 else 27), fill=INK)
    y = 210
    for line in sub.split("\n"):
        d.text((36, y), line, font=font(FONT_REG, 19), fill=GREY)
        y += 34
    if footer:
        d.text((36, SIZE - 60), footer, font=font(FONT_REG, 17), fill=(150, 156, 164))
    im.save(path)
    return path


def seg_from_image(png, dur, out):
    subprocess.run([FF, "-y", "-loop", "1", "-t", str(dur), "-i", str(png),
                    "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "20", str(out)],
                   check=True, capture_output=True)


def seg_from_clip(src, start, dur, out):
    subprocess.run([FF, "-y", "-ss", str(start), "-t", str(dur), "-i", str(src),
                    "-vf", f"scale={SIZE}:{SIZE}:flags=lanczos,fps={FPS},format=yuv420p",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-an", str(out)], check=True, capture_output=True)


def main():
    segs = []
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        title = card(td / "t.png", "Agentic Robotics",
                     "机械臂分拣流水线 · 纯仿真\nLIBERO / MuJoCo · Franka Panda",
                     "2026-10-18")
        seg = td / "s000.mp4"
        seg_from_image(title, 3.0, seg)
        segs.append(seg)

        for i, (name, t, s, start, dur) in enumerate(CLIPS, start=1):
            src = VID / name
            if not src.exists():
                print(f"  skip missing {name}")
                continue
            cap = card(td / f"c{i}.png", t, s, f"{i}/{len(CLIPS)}")
            seg_a = td / f"s{i:03d}a.mp4"
            seg_from_image(cap, 1.4, seg_a)
            seg_b = td / f"s{i:03d}b.mp4"
            seg_from_clip(src, start, dur, seg_b)
            segs += [seg_a, seg_b]

        end = card(td / "e.png", "结果",
                   "主任务 100/100（100%）\n变体 79/110（71.8%）\n视觉闭环 18/20（90%）",
                   "固定 seed 协议 · 0 超步 / 0 OOM")
        seg = td / "s999.mp4"
        seg_from_image(end, 3.5, seg)
        segs.append(seg)

        lst = td / "list.txt"
        lst.write_text("".join(f"file '{s}'\n" for s in segs))
        subprocess.run([FF, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-c", "copy", str(OUT)], check=True, capture_output=True)

    size_mb = OUT.stat().st_size / 1024 / 1024
    dur = subprocess.run([FF, "-i", str(OUT)], capture_output=True, text=True).stderr
    line = [l for l in dur.splitlines() if "Duration" in l]
    print(f"{OUT.relative_to(ROOT)}  {size_mb:.1f} MB  {line[0].strip() if line else ''}")


if __name__ == "__main__":
    main()
