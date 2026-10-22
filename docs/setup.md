# 从零复现（Clean-install 验证记录）

> 一条命令入口：`AGENT_PYTHON=$(which python) bash scripts/bootstrap_env.sh`
> 它把下面所有步骤串起来（幂等，可重复执行），并在最后跑 `scripts/preflight.py` 自检。

## 0. 已验证的结论

| 验证 | 时间 | 结果 |
|---|---|---|
| 干净 conda 环境（python 3.10.22 + CPU torch），只按 `requirements.txt` 装 | 2026-10-18 | preflight 7/7，t6 2/2 通过 |
| **干净 clone + 干净 conda 环境 + `bootstrap_env.sh` 一条命令** | 2026-10-22 | 见 `docs/repro_check_20261022.md`（本次补做的验证） |

## 1. bootstrap 做了什么（8 步）

```bash
bash scripts/bootstrap_env.sh              # 默认把 LIBERO 装到 third_party/LIBERO
AGENT_LIBERO_ROOT=/path/to/LIBERO bash scripts/bootstrap_env.sh   # 用已有 LIBERO
AGENT_PYTHON=/path/to/python bash scripts/bootstrap_env.sh        # 指定解释器
```

1. **拉 LIBERO 源码**：`github.com/Lifelong-Robot-Learning/LIBERO`，默认 pin 到
   `8f1084e3132a39270c3a13ebe37270a43ece2a01`（本作品全部结果都基于它）。
   离线时用 `AGENT_LIBERO_TARBALL=/path/to/LIBERO.tar.gz`。
2. 补 `libero/libero/__init__.py`（官方 zip 包缺这个文件，`pip -e` 会失败）。
3. `pip install -r requirements.txt`。
4. `pip install -e LIBERO --no-deps`（它自己的 `install_requires` 是空的）。
5. `vendor/bolt-sorting/install.py`：拷资产 + 对象模块 + 注册表（marker 守卫，可重跑）。
6. `create_bolt_tasks.py` + `gen_suites.py`：生成 `libero_bolt` / `libero_bolt_v2` / `libero_bolt_multi`。
7. `gen_init_states.py`（每任务 50 个固定初始状态）+ `gen_missions.py`（任务协议）。
8. `scripts/preflight.py`：7 项自检（导入、套件、注册表、资产、一次 EGL rollout、协议一致性、LLM 配置）。

## 2. 路径解析（不再有绝对路径）

`scripts/_paths.py` 统一解析 LIBERO 位置：

1. `$AGENT_LIBERO_ROOT`
2. `<repo>/third_party/LIBERO`（bootstrap 默认）
3. `/home/wei/work/g05/LIBERO-master`（开发机历史路径，仅向后兼容）

`run.sh` 用同样的顺序。

## 3. 新环境里补出来的隐式依赖

| 包 | 谁需要 | 症状 |
|---|---|---|
| `pyyaml` | LIBERO 读 bddl / benchmark | `ModuleNotFoundError: yaml` |
| `termcolor` | robosuite 控制台输出 | `ModuleNotFoundError: termcolor` |
| `bddl` | LIBERO 任务定义解析 | `ModuleNotFoundError: bddl` |
| `easydict` | LIBERO env 配置对象 | `ModuleNotFoundError: easydict` |
| `matplotlib` | LIBERO utils 导入链 | `ModuleNotFoundError: matplotlib` |
| `gym==0.22.0` | LIBERO env 基类（robosuite 1.4 要 `gym`，不是 `gymnasium`） | `ModuleNotFoundError: gym` |

根因：**LIBERO 的 `setup.py` 里 `install_requires=[]`**，所以 `pip install -e --no-deps` 不带任何依赖，
这 6 个包在开发机上是别的项目装的、一直被"继承"着。现在全部写进 `requirements.txt` 并注明用途。

## 4. 环境备注

- 开发机主用 `GalaxeaVLA-main/.venv`（python 3.10.16 + torch 2.7.1+cu128 + robosuite 1.4.0），
  `bootstrap_env.sh` 的干净环境是 `conda create -n rb_verify python=3.10`（CPU torch 2.7.1）。
  **两个环境跑同一任务结果一致**（t6 s1000/s1001 均通过）。
- `run.sh` 支持 `AGENT_PYTHON` 指定解释器，方便在任意环境复现。
- 渲染必须走 EGL（`MUJOCO_GL=egl PYOPENGL_PLATFORM=egl`）；没有 GPU 可用 `MUJOCO_GL=osmesa`（未大规模验证）。
- 单进程连续 reset 很多次偶发 EGL 上下文泄漏（`EGLError: <exception str() failed>`）：v2 的 110 次能跑完，
  multi 的 110 次挂过。大批量检查建议按 task 分批（`scripts/check_resets.py`）。
