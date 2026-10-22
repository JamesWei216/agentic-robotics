#!/usr/bin/env bash
# One-command entry point for the agentic robotics pipeline.
#
#   ./run.sh                                  # plan -> code -> sim -> verify -> repair -> report
#   ./run.sh --tasks 5 --seeds 10             # single task protocol
#   ./run.sh --no-llm                         # template plan+code (no API calls)
#   ./run.sh --confirm-mode manual            # human-in-the-loop (TTY or web UI)
#
# Environment knobs: AGENT_CONFIRM_MODE (auto|manual|deny), OMP_NUM_THREADS,
# AGENT_RENDER=1 to record video.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${AGENT_PYTHON:-/home/wei/work/g05/GalaxeaVLA-main/.venv/bin/python}"
# LIBERO 解析顺序：AGENT_LIBERO_ROOT → 仓库内 third_party/LIBERO → 开发机历史路径
if [ -n "${AGENT_LIBERO_ROOT:-}" ]; then
  LIBERO_ROOT="$AGENT_LIBERO_ROOT"
elif [ -d "$ROOT/third_party/LIBERO/libero/libero" ]; then
  LIBERO_ROOT="$ROOT/third_party/LIBERO"
elif [ -d /home/wei/work/g05/LIBERO-master/libero/libero ]; then
  LIBERO_ROOT=/home/wei/work/g05/LIBERO-master
else
  LIBERO_ROOT="$ROOT/third_party/LIBERO"
fi

export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export NUMEXPR_NUM_THREADS="$OMP_NUM_THREADS"
export PYTHONPATH="$ROOT:$LIBERO_ROOT:${PYTHONPATH:-}"
export AGENT_LIBERO_ROOT="$LIBERO_ROOT"

# LIBERO 的 bddl/init/assets 目录由 $LIBERO_CONFIG_PATH/config.yaml 决定（默认 ~/.libero 是用户级的）。
# 仓库内有 bootstrap 生成的配置时用它，保证用到的就是我们装的那棵树。
if [ -f "$ROOT/third_party/libero_config/config.yaml" ]; then
  export LIBERO_CONFIG_PATH="$ROOT/third_party/libero_config"
fi

cd "$ROOT"
exec "$PY" -m agent.run "$@"
