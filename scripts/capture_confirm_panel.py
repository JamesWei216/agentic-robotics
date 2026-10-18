#!/usr/bin/env python3
"""把正在运行的「人机确认」网页面板存成 PNG（给报告用）。

为什么不用浏览器截图：本机 firefox --headless 在 SWGL 上拿不到 framebuffer
（`RenderCompositorSWGL failed mapping default framebuffer`），截不出图；
但面板是纯 HTML+CSS，用 weasyprint 渲染成 PDF 再转 PNG 是等价的分辨率无关路径。

    python scripts/capture_confirm_panel.py --url http://127.0.0.1:8078/ \
        --out reports/screenshots/panel_pending.png

依赖：weasyprint（conda env smolvla 里有）+ poppler 的 pdftoppm。
"""
import argparse
import pathlib
import subprocess
import sys
import tempfile
import urllib.request

WRAP = """<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: {w}px {h}px; margin: 0; }}
html, body {{ margin: 0; padding: 0; }}
</style></head><body>{body}</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8078/")
    ap.add_argument("--out", default="reports/screenshots/panel.png")
    ap.add_argument("--size", default="1280x900")
    ap.add_argument("--dpi", type=int, default=96)
    ap.add_argument("--html-in", help="render this file instead of fetching --url")
    args = ap.parse_args()

    if args.html_in:
        raw = pathlib.Path(args.html_in).read_text()
    else:
        with urllib.request.urlopen(args.url, timeout=10) as r:
            raw = r.read().decode("utf-8", "replace")

    # strip the page's own <head>/<style> wrapper? keep it, only swap the @page rule
    body = raw.split("<body>", 1)[-1].rsplit("</body>", 1)[0]
    head_style = ""
    if "<style>" in raw:
        head_style = raw.split("<style>", 1)[1].split("</style>", 1)[0]
    w, h = (int(x) for x in args.size.lower().split("x"))
    html = (f'<!doctype html><html><head><meta charset="utf-8"><style>{head_style}</style>'
            f"<style>@page {{ size: {w}px {h}px; margin: 0; }} "
            f"html, body {{ margin:0; padding:0; }}</style></head><body>{body}</body></html>")

    import weasyprint
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        pdf = pathlib.Path(td) / "panel.pdf"
        weasyprint.HTML(string=html).write_pdf(str(pdf))
        subprocess.run(["pdftoppm", "-r", str(args.dpi), "-png", "-singlefile",
                        str(pdf), str(out.with_suffix(""))], check=True)
    png = out if out.exists() else out.with_suffix(".png")
    from PIL import Image
    im = Image.open(png)
    print(f"{png}  {im.size[0]}x{im.size[1]}  {png.stat().st_size // 1024} KB")


if __name__ == "__main__":
    sys.exit(main())
