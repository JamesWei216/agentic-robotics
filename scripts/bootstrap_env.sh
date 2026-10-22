#!/usr/bin/env bash
# bootstrap_env.sh — 从零把"螺栓分拣"仿真环境搭起来（可复现性入口）
#
#   bash scripts/bootstrap_env.sh            # 默认 third_party/LIBERO
#   AGENT_LIBERO_ROOT=/path/to/LIBERO bash scripts/bootstrap_env.sh   # 用已有 LIBERO
#   AGENT_PYTHON=/path/to/python bash scripts/bootstrap_env.sh        # 指定解释器
#
# 做的事（全部幂等，可重复执行）：
#   1. 取 LIBERO 源码（默认 pin 到 VERIFIED_COMMIT，本地无网络时用已有目录）
#   2. pip install -e LIBERO --no-deps
#   3. 装自定义资产/对象/套件注册（vendor/bolt-sorting/install.py）
#   4. 生成三套任务（libero_bolt / libero_bolt_v2 / libero_bolt_multi）
#   5. 采样固定初始状态、生成任务协议 config/missions.json
#   6. 跑 preflight 自检
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${AGENT_PYTHON:-python3}"
LIBERO_ROOT="${AGENT_LIBERO_ROOT:-$ROOT/third_party/LIBERO}"

# LIBERO 上游 master 的已验证提交（2026-10-22 记录；本作品的全部结果都基于它）
LIBERO_REPO="${AGENT_LIBERO_REPO:-https://github.com/Lifelong-Robot-Learning/LIBERO}"
LIBERO_COMMIT="${AGENT_LIBERO_COMMIT:-8f1084e3132a39270c3a13ebe37270a43ece2a01}"

export AGENT_LIBERO_ROOT="$LIBERO_ROOT"
export MUJOCO_GL="${MUJOCO_GL:-egl}"
export PYOPENGL_PLATFORM="${PYOPENGL_PLATFORM:-egl}"

# LIBERO 用 $LIBERO_CONFIG_PATH/config.yaml 解析 bddl/init/assets 路径，默认落在 ~/.libero（用户级、全局）。
# 这会导致“换了机器却写到以前那个 LIBERO 目录里”——把配置钉在本仓库内，保证目录隔离。
export LIBERO_CONFIG_PATH="$ROOT/third_party/libero_config"

export PYTHONPATH="$ROOT:$LIBERO_ROOT:${PYTHONPATH:-}"

step() { printf '\n\033[1m== [%s] %s\033[0m\n' "$1" "$2"; }

step 0 "环境信息"
echo "  repo      : $ROOT"
echo "  python    : $($PY -c 'import sys; print(sys.executable, sys.version.split()[0])')"
echo "  LIBERO    : $LIBERO_ROOT"
echo "  commit    : $LIBERO_COMMIT"

# ---------------------------------------------------------------- 1. LIBERO 源码
step 1 "LIBERO 源码"
if [ -d "$LIBERO_ROOT/libero/libero" ]; then
  echo "  已存在，跳过下载"
else
  mkdir -p "$(dirname "$LIBERO_ROOT")"
  if [ -n "${AGENT_LIBERO_TARBALL:-}" ] && [ -f "$AGENT_LIBERO_TARBALL" ]; then
    echo "  从本地压缩包解压：$AGENT_LIBERO_TARBALL"
    mkdir -p "$LIBERO_ROOT"
    tar -xf "$AGENT_LIBERO_TARBALL" -C "$LIBERO_ROOT" --strip-components=1
  else
    echo "  clone $LIBERO_REPO（depth 1）"
    git clone --depth 1 "$LIBERO_REPO" "$LIBERO_ROOT"
    head_commit="$(git -C "$LIBERO_ROOT" rev-parse HEAD)"
    if [ "$head_commit" != "$LIBERO_COMMIT" ]; then
      echo "  当前 HEAD=$head_commit，切到已验证提交 $LIBERO_COMMIT"
      git -C "$LIBERO_ROOT" fetch --depth 1 origin "$LIBERO_COMMIT"
      git -C "$LIBERO_ROOT" checkout -q "$LIBERO_COMMIT"
    fi
  fi
fi

# 官方 zip 包缺 libero/libero/__init__.py，pip -e 会失败 → 补空文件
if [ ! -f "$LIBERO_ROOT/libero/libero/__init__.py" ]; then
  echo "  补齐缺失的 libero/libero/__init__.py（官方 zip 包的已知缺口）"
  : > "$LIBERO_ROOT/libero/libero/__init__.py"
fi

# ---------------------------------------------------------------- 1.5 LIBERO 路径配置
step 1.5 "写 LIBERO 路径配置（$LIBERO_CONFIG_PATH/config.yaml）"
mkdir -p "$LIBERO_CONFIG_PATH"
cat > "$LIBERO_CONFIG_PATH/config.yaml" <<YAML
benchmark_root: $LIBERO_ROOT/libero/libero
bddl_files: $LIBERO_ROOT/libero/libero/bddl_files
init_states: $LIBERO_ROOT/libero/libero/init_files
datasets: $LIBERO_ROOT/datasets
assets: $LIBERO_ROOT/libero/libero/assets
YAML
echo "  -> $LIBERO_CONFIG_PATH/config.yaml"

# ---------------------------------------------------------------- 2. 依赖
step 2 "安装依赖（requirements.txt）"
if [ -f requirements.txt ]; then
  $PY -m pip install -q -r requirements.txt
else
  echo "  !! 缺 requirements.txt" >&2; exit 1
fi
echo "  pip install -e LIBERO --no-deps（LIBERO 的 setup.py 里 install_requires 为空，依赖已在上一步装好）"
$PY -m pip install -q -e "$LIBERO_ROOT" --no-deps

# ---------------------------------------------------------------- 3. 自定义资产/注册
step 3 "安装螺栓资产 + 对象注册（vendor/bolt-sorting/install.py）"
$PY vendor/bolt-sorting/install.py --libero "$LIBERO_ROOT" --skip-galaxea

step 4 "生成 libero_bolt（第一版单件任务套件）"
$PY vendor/bolt-sorting/create_bolt_tasks.py
$PY vendor/bolt-sorting/install.py --libero "$LIBERO_ROOT" --skip-assets --skip-galaxea

step 5 "生成比赛套件 libero_bolt_v2 + libero_bolt_multi"
$PY scripts/gen_suites.py

step 6 "采样固定初始状态（每个任务 50 个，seed 公开）"
$PY scripts/gen_init_states.py --suite libero_bolt_v2 --num 50
$PY scripts/gen_init_states.py --suite libero_bolt_multi --num 50

step 7 "生成任务协议 config/missions.json"
$PY scripts/gen_missions.py libero_bolt_v2 libero_bolt_multi

# ---------------------------------------------------------------- 8. 自检
step 8 "preflight 自检（7 项）"
$PY scripts/preflight.py

cat <<'EOF'

--------------------------------------------------------------------
环境就绪。跑一条主任务 episode：

  AGENT_PYTHON=$PY MUJOCO_GL=egl ./run.sh --suite libero_bolt_v2 \
      --no-llm --tasks 6 --seeds 1 --repairs 0 --tag smoke

完整主任务（10 任务 × 10 固定初始状态）：

  AGENT_PYTHON=$PY ./run.sh --suite libero_bolt_v2 \
      --taskbook taskbooks/sort_main.md --tasks 0,1,2,3,4,5,6,7,8,9 --seeds 10

注意：AGENT_LIBERO_ROOT 需指向本次安装的 LIBERO（默认 third_party/LIBERO，run.sh 已按此取默认值）。
--------------------------------------------------------------------
EOF
