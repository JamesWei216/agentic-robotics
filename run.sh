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
LIBERO_ROOT="${AGENT_LIBERO_ROOT:-/home/wei/work/g05/LIBERO-master}"

export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export MKL_NUM_THREADS="$OMP_NUM_THREADS"
export OPENBLAS_NUM_THREADS="$OMP_NUM_THREADS"
export NUMEXPR_NUM_THREADS="$OMP_NUM_THREADS"
export PYTHONPATH="$ROOT:$LIBERO_ROOT:${PYTHONPATH:-}"
export AGENT_LIBERO_ROOT="$LIBERO_ROOT"

cd "$ROOT"
exec "$PY" -m agent.run "$@"
