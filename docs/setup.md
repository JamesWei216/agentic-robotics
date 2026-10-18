# 从零复现（Clean-install 验证记录）

> 2026-10-18 在一个**全新的 conda 环境**里，只按 `requirements.txt` 从零安装，
> 跑通 `scripts/preflight.py`（7 项）与一条真实 episode（t6 2/2 通过）。
> 这一步暴露了 6 个"开发机 venv 里恰好有、但 requirements 里没写"的隐式依赖。

## 1. 已验证的安装步骤（照抄即可）

```bash
# ① 干净环境（系统 python3 没有 pip/ensurepip，用 conda 最省事）
conda create -n rb_clean python=3.10 -y
conda activate rb_clean

# ② 运行时依赖（CPU-only 机器可先装 CPU 版 torch，省 ~2 GB 下载）
pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# ③ LIBERO 必须 editable 安装，且 --no-deps（它自己会拉 mujoco/robosuite 的错版本）
pip install -e /path/to/LIBERO --no-deps

# ④ 自定义套件（螺栓分拣）已经写进 LIBERO 的 bddl_files + benchmark 注册表；
#    如果拿到的是干净 LIBERO，先跑一遍：
#    MUJOCO_GL=egl python /path/to/bolt-sorting/install.py     # assets + 对象注册
#    MUJOCO_GL=egl python scripts/gen_suites.py                # 两个套件的 bddl + 注册

# ⑤ 自检
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export PYTHONPATH=$PWD:/path/to/LIBERO
python scripts/preflight.py            # 7 项必须全 ok
python scripts/check_feasibility.py libero_bolt_v2 10   # 110/110 初始状态可 reset

# ⑥ 跑一条真的
AGENT_PYTHON=$(which python) ./run.sh --suite libero_bolt_v2 --no-llm \
    --tasks 6 --seeds 2 --repairs 0 --tag smoke
```

## 2. 新环境里补出来的隐式依赖

| 包 | 谁需要 | 症状 |
|---|---|---|
| `pyyaml` | LIBERO 读 bddl / benchmark | `ModuleNotFoundError: yaml` |
| `termcolor` | robosuite 控制台输出 | `ModuleNotFoundError: termcolor` |
| `bddl` | LIBERO 任务定义解析 | `ModuleNotFoundError: bddl` |
| `easydict` | LIBERO env 配置对象 | `ModuleNotFoundError: easydict` |
| `matplotlib` | LIBERO utils 导入链 | `ModuleNotFoundError: matplotlib` |
| `gym==0.22.0` | LIBERO env 基类（robosuite 1.4 要 `gym`，不是 `gymnasium`） | `ModuleNotFoundError: gym` |

根因：**LIBERO 的 `setup.py` 里 `install_requires=[]`**（空的），所以 `pip install -e LIBERO --no-deps`
不会带任何依赖；这 6 个包在开发机 venv 里是别的项目装的，一直被"继承"着。
现在它们全部写进 `requirements.txt` 并注明用途。

## 3. 环境备注

- 开发机主用 `GalaxeaVLA-main/.venv`（python 3.10.16 + torch 2.7.1+cu128 + robosuite 1.4.0），
  本次验证用的干净环境是 `conda create -n rb_clean python=3.10`（python 3.10.22 + CPU 版 torch 2.7.1）。
  **两个环境跑同一任务结果一致**（t6 s1000/s1001 均通过）。
- `run.sh` 支持用 `AGENT_PYTHON` 指定解释器，方便在任意环境里复现。
- 渲染必须走 EGL（`MUJOCO_GL=egl PYOPENGL_PLATFORM=egl`）；没有 GPU 可用 `MUJOCO_GL=osmesa`，但未验证。
- 单进程连续 reset 很多次偶发 EGL 上下文泄漏（`EGLError: <exception str() failed>`）：v2 的 110 次能跑完，
  multi 的 110 次挂过。大批量检查建议按 task 分批（`scripts/check_resets.py` 或每 task 一个进程）。
