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
ORG="${1:-}"; WORK="${2:-}"; LEADER="${3:-}"; PHONE="${4:-}"
PDF="${5:-$ROOT/reports/Agentic-Robotics-赛题总结报告.pdf}"
DATE="$(date +%Y%m%d)"
STAMP="$(date +%Y-%m-%d)"

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

echo "== 1. 技术文档 =="
if [ -f "$PDF" ]; then
  cp "$PDF" "$OUT/01_技术文档.pdf"
  echo "   $PDF -> 01_技术文档.pdf"
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
if [ -f "$ROOT/config/video_link.txt" ]; then
  cp "$ROOT/config/video_link.txt" "$OUT/03_视频链接.txt"
  echo "   已带上视频链接"
else
  echo "   (待补：config/video_link.txt)" > "$OUT/03_视频链接.txt"
fi

echo "== 6. 打包 =="
( cd "$OUT" && zip -qr "$NAME.zip" . -x '*.zip' )
ls -lh "$OUT/$NAME.zip"
echo
echo "上传文件: $OUT/$NAME.zip"
echo "自检: unzip -l \"$OUT/$NAME.zip\" | head"
