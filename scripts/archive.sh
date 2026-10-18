#!/usr/bin/env bash
# 归档到桌面：代码 + 文档 + 四组关键运行 + PDF + 汇总
set -euo pipefail
SRC=/home/wei/work/g05/agentic-robotics
DST="$HOME/Desktop/Agentic-Robotics-赛题"
mkdir -p "$DST"

# 代码与文档（不含 runs / __pycache__）
rsync -a --delete \
  --exclude 'runs/' --exclude '__pycache__/' --exclude '*.pyc' \
  --exclude '.venv' --exclude 'runtime/confirm' \
  "$SRC/" "$DST/"

# 关键运行
mkdir -p "$DST/runs"
for r in "$@"; do
  [ -d "$SRC/runs/$r" ] || { echo "skip $r"; continue; }
  rsync -a --delete "$SRC/runs/$r" "$DST/runs/"
done
rsync -a --delete "$SRC/runs/confirm_demo_panel" "$DST/confirm_demo_panel/"

# PDF 报告
[ -f "$SRC/reports/Agentic-Robotics-赛题总结报告.pdf" ] && \
  cp "$SRC/reports/Agentic-Robotics-赛题总结报告.pdf" "$DST/"

du -sh "$DST"
find "$DST" -maxdepth 1 -mindepth 1 | sort
