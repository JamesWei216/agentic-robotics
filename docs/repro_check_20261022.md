# 从零复现实测记录 · 2026-10-22

> 目的：证明"评审拿到提交包，在一台干净机器上按文档能跑出与报告一致的结果"。
> 做法：**不是**在开发机上跑，而是把仓库拷到 `/tmp/rb_repro`（不带任何本机路径）、
> 新建 conda 环境 `rb_verify`（CPU torch）、只按 `scripts/bootstrap_env.sh` 走一遍。

## 1. 环境

| 项 | 值 |
|---|---|
| 代码位置 | `/tmp/rb_repro`（从仓库 rsync，排除 `.git` / `runs` / `logs` / `third_party`） |
| Python | 3.10.22（conda 新建 `rb_verify`） |
| torch | 2.7.1+cpu |
| LIBERO | 现场 `git clone`，pin `8f1084e3132a39270c3a13ebe37270a43ece2a01`（640 MB） |
| 渲染 | EGL（本机有 GPU，但依赖是 CPU 版 torch —— 说明不需要训练卡） |

## 2. 过程与耗时

| 阶段 | 耗时 | 结果 |
|---|---|---|
| conda 建环境 + CPU torch | ~3 min | ok |
| clone LIBERO（depth 1，640 MB） | ~7 min | ok |
| `pip install -r requirements.txt` | ~14 min | ok（`gym==0.22`、`bddl` 需源码构建，是全程最慢的一步） |
| `install.py`（资产/对象注册） | <10 s | ok |
| `create_bolt_tasks.py`（libero_bolt） | ~20 s | 11 个 bddl |
| `gen_suites.py`（v2 + multi） | ~40 s | 22 个 bddl，failures 0 |
| `gen_init_states.py` ×2（每任务 50 个） | ~18 min | 11 + 11 个 `.pruned_init` |
| `gen_missions.py` | <5 s | `config/missions.json`（22 条） |
| `preflight.py` | ~30 s | **7/7 ok** |

## 3. 结果

```
preflight:
  [ok] python packages import — numpy 1.26.4, scipy 1.15.3, mujoco 3.3.2, robosuite 1.4.0
  [ok] bddl suites installed — libero_bolt:11, libero_bolt_v2:11, libero_bolt_multi:11
  [ok] benchmark registry — libero_bolt:11 tasks, libero_bolt_v2:11 tasks, libero_bolt_multi:11 tasks
  [ok] bolt assets installed — bolt_large, bolt_small, parts_bin_blue, parts_bin_large, parts_bin_red, parts_bin_small
  [ok] one env + short rollout (EGL) — 5 control steps ok, agentview (128, 128, 3)
  [ok] missions.json consistent — libero_bolt_v2:11, libero_bolt:11, libero_bolt_multi:11
  [ok] llm config
preflight OK

run.sh --suite libero_bolt_v2 --no-llm --tasks 6 --seeds 1
  [t6 s1000] OK  1079 steps  8.7s
  overall 1/1 = 100.0%
```

产物：`/tmp/rb_repro/runs/20261022-215455_fresh_smoke/`（plan / task.py / metrics / report）。

## 4. 这次实测抓到的两个坑（都已修，且已写进 `docs/failures.md`）

### A14 `LIBERO_CONFIG_PATH` 是用户级全局配置

LIBERO 不按 `pip install -e` 的路径找 bddl/init/assets，而是读 `$LIBERO_CONFIG_PATH/config.yaml`
（默认 `~/.libero/config.yaml`），里面是**绝对路径**。所以：

- 机器上没装过 LIBERO → 首次会自动生成，正常；
- 机器上装过别的 LIBERO（评审很可能有）→ 静默写到/读到**那棵树**，表现是
  `RandomizationError`、任务表串台、或"明明生成了 bddl 但评测说找不到"。

本次实测就是这个症状：`/tmp/rb_repro` 里跑 `gen_suites.py`，bddl 却写进了
`/home/wei/work/g05/LIBERO-master`。

修法：`bootstrap_env.sh` 生成 `third_party/libero_config/config.yaml` 并 `export LIBERO_CONFIG_PATH`；
`run.sh`、`scripts/_paths.py`、`agent/skills/api.py` 三处都按"项目内配置优先"解析。

### A15 安装顺序会让 benchmark 导入炸

`install.py` 先把 `"libero_bolt"` 加进 `libero_suites`，但 task map 的键要等 bddl 生成后才有
→ 中间态下 `from libero.libero.benchmark import ...` 直接 `KeyError: 'libero_bolt'`。
修法：`install.py` 加 4b 步，缺键时先写 `libero_task_map["libero_bolt"] = []` 占位，任何时刻都可导入。

## 5. 对提交文档的影响

- `docs/setup.md` 与提交包内 `运行方式.md` 的"三条命令"已按实测更新；
- 文档里补了"首次安装 ~40 min（网络慢时更久），其中 pip 与初始状态采样是大头"，
  避免评审以为命令卡死；
- 纯 CPU 机器同样能跑（本次验证就是 CPU torch）。
