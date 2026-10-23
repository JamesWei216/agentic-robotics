#!/usr/bin/env bash
# make_submission.sh — 按官方命名规则打提交包
#
#   bash scripts/make_submission.sh "单位简称" "作品名称" "队长姓名" "手机号" [PDF路径]
#
# 产出：
#   ~/Desktop/提交包-<日期>/                                     ← 人看的目录
#   ~/Desktop/提交包-<日期>/<单位简称>-<作品名称>-<队长姓名>-<手机号>-<YYYYMMDD>.zip   ← 上传这个
#
# 包内结构（官方要求：一个 zip，内含技术文档 PDF + 代码包）：
#   01_技术文档.pdf
#   02_代码/agentic-robotics/      ← git archive 出来的干净仓库（无 .git，无 runs/logs）
#   02_代码/runs/                  ← 关键运行（metrics.json / trace.jsonl / 逐 episode 日志）
#   02_代码/运行方式.md
#   03_视频链接.txt                ← 网盘链接与提取码（若已填）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 默认从 config/submission_meta.txt 读（不入库），命令行参数优先
META="$ROOT/config/submission_meta.txt"
if [ -f "$META" ]; then set -a; . "$META"; set +a; fi
ORG="${1:-${ORG:-}}"; WORK="${2:-${WORK:-}}"; LEADER="${3:-${LEADER:-}}"; PHONE="${4:-${PHONE:-}}"
PDF="${5:-$ROOT/reports/Agentic-Robotics-赛题总结报告.pdf}"
DATE="$(date +%Y%m%d)"
STAMP="$(date +%Y-%m-%d)"

# 视频链接（官方要求 PDF 里必须含 ≤5min / ≥720P 视频链接）
VIDEO_FILE="$ROOT/reports/videos/AG-VLA-demo-720p.mp4"
VIDEO_LINK_FILE="$ROOT/config/video_link.txt"
VIDEO_URL=""
if [ -f "$VIDEO_LINK_FILE" ]; then
  VIDEO_URL="$(grep -Eo 'https?://[^[:space:]]+' "$VIDEO_LINK_FILE" | head -1 || true)"
fi

if [ -z "$ORG" ] || [ -z "$WORK" ] || [ -z "$LEADER" ] || [ -z "$PHONE" ]; then
  cat >&2 <<'EOF'
用法: bash scripts/make_submission.sh "单位简称" "作品名称" "队长姓名" "队长手机号" [PDF路径]

例:  bash scripts/make_submission.sh "XX学院" "Agent驱动的机械臂分拣流水线" "张三" "13800000000"
EOF
  exit 2
fi

NAME="$ORG-$WORK-$LEADER-$PHONE-$DATE"
OUT="$HOME/Desktop/提交包-$DATE"
rm -rf "$OUT"; mkdir -p "$OUT/02_代码"

# 找得到 weasyprint 的解释器（venv/conda 均可能）
if [ -z "${PDF_PYTHON:-}" ]; then
  for cand in "$(command -v python3)" /home/wei/miniconda3/envs/smolvla/bin/python /home/wei/miniconda3/envs/vla/bin/python; do
    [ -x "$cand" ] || continue
    if "$cand" -c "import weasyprint" >/dev/null 2>&1; then PDF_PYTHON="$cand"; break; fi
  done
fi
PDF_PYTHON="${PDF_PYTHON:-python3}"

echo "== 1. 技术文档（注入视频链接后重新生成） =="
if [ -z "$VIDEO_URL" ]; then
  echo "   !! config/video_link.txt 里没找到 http(s) 链接：PDF 会写成“见 03_视频链接.txt”" >&2
fi
SUB_ORG="$ORG" SUB_WORK="$WORK" SUB_LEADER="$LEADER" VIDEO_URL="$VIDEO_URL" \
  "$PDF_PYTHON" "$ROOT/scripts/make_report_pdf.py" >/dev/null
if [ -f "$PDF" ]; then
  cp "$PDF" "$OUT/01_技术文档.pdf"
  echo "   重新生成并复制 -> 01_技术文档.pdf（video_url=${VIDEO_URL:-<空>}）"
else
  echo "   !! 找不到 PDF: $PDF" >&2; exit 1
fi

echo "== 2. 代码（git archive HEAD） =="
git -C "$ROOT" archive --format=tar HEAD | tar -xf - -C "$OUT/02_代码" --one-top-level=agentic-robotics
# 若工作区有未提交改动，提示（避免提交包与本地不一致）
if [ -n "$(git -C "$ROOT" status --porcelain)" ]; then
  echo "   !! 工作区有未提交改动，提交包只含 HEAD —— 建议先 commit" >&2
fi
rm -rf "$OUT/02_代码/agentic-robotics/third_party"   # LIBERO 由 bootstrap 下载，不进包

echo "== 3. 关键运行 =="
RUNS_MANIFEST="$ROOT/config/submission_runs.txt"
[ -f "$RUNS_MANIFEST" ] || { echo "   !! 缺 $RUNS_MANIFEST" >&2; exit 1; }
mkdir -p "$OUT/02_代码/runs"
while read -r rid; do
  [ -z "$rid" ] && continue
  case "$rid" in \#*) continue ;; esac
  if [ -d "$ROOT/runs/$rid" ]; then
    rsync -a --exclude '*.mp4' --exclude '__pycache__' "$ROOT/runs/$rid" "$OUT/02_代码/runs/"
    echo "   + runs/$rid"
  else
    echo "   !! 缺 runs/$rid" >&2
  fi
done < "$RUNS_MANIFEST"

echo "== 4. 运行方式 =="
cp "$ROOT/docs/运行方式.md" "$OUT/02_代码/运行方式.md" 2>/dev/null \
  || cp "$ROOT/docs/setup.md" "$OUT/02_代码/运行方式.md"

echo "== 5. 视频链接 =="
if [ -f "$VIDEO_LINK_FILE" ]; then
  cp "$VIDEO_LINK_FILE" "$OUT/03_视频链接.txt"
  echo "   已带上视频链接（$VIDEO_URL）"
else
  {
    echo "作品介绍视频：待上传后填入"
    echo
    echo "成片文件：$(basename "$VIDEO_FILE")"
    echo "规格：4 分 39 秒 / 1280×720 / 25 fps / H.264（满足 ≤5 分钟、≥720P）"
    echo "建议渠道：百度网盘（附提取码）或 B 站（公开视频 URL）"
    echo
    echo "上传后把链接写进 $VIDEO_LINK_FILE（一行 URL，可附提取码），重跑本脚本即自动注入 PDF。"
  } > "$OUT/03_视频链接.txt"
  echo "   (待补：$VIDEO_LINK_FILE)"
fi
# 视频成片放桌面包旁边（不进 zip，便于直接上传）
if [ -f "$VIDEO_FILE" ]; then
  cp "$VIDEO_FILE" "$OUT/AG-VLA-demo-720p.mp4"
  echo "   成片已复制到包旁：AG-VLA-demo-720p.mp4（$(du -h "$VIDEO_FILE" | cut -f1)）"
fi

echo "== 6. 打包 =="
( cd "$OUT" && zip -qr "$NAME.zip" 01_技术文档.pdf 02_代码 03_视频链接.txt )
ls -lh "$OUT/$NAME.zip"
echo
echo "上传文件: $OUT/$NAME.zip"
echo "自检: unzip -l \"$OUT/$NAME.zip\" | head"
