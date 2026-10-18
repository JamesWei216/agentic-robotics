# 评测协议（Evaluation Protocol）

> 目的：让"成功率"这个数字**可复现、可对比、不可事后调整**。所有阈值在跑之前写死，
> 代码里对应 `config/agent.json`、`agent/verifier.py`、`agent/skills/api.py`。

## 1. 任务集

| 套件 | 用途 | 任务数 | 说明 |
|---|---|---|---|
| `libero_bolt_v2` | **主任务（分拣）** | 11 | 5 套布局 × {小螺栓→蓝盒, 大螺栓→红盒} = 10 个单件任务；1 个长程双件任务（压力项，单列） |
| `libero_bolt_multi` | **变体任务（批量分拣）** | 11 | 同工位、同布局，每类螺栓 2 枚；10 个双件任务 + 1 个四件任务 |

- 主任务口径：**10 个单件任务 × 10 个固定初始状态 = 100 episodes**（长程/四件任务单独报，不并入主口径）。
- 变体口径同上，但每 task 是 2 件：**10 × 10 = 100 episodes**。

## 2. 初始状态

- 每个任务 `scripts/gen_init_states.py` 采样 **50** 个物理合法状态（LIBERO 原生 `.pruned_init`）。
- 评测固定取前 **10** 个：`seed = 1000 + i`，i=0..9。
- 同一 seed 在不同代码版本下看到的是**完全相同**的初始状态 → 修复前后可配对比较。
- **采样器也必须种子化**（2026-10-18 修）：LIBERO 的 `env.seed()` 只种仿真器，
  物体布局用的是全局 `np.random`。`Robot.from_env()` 在**构造 env 之前**执行 `np.random.seed(seed)`，
  否则同一 seed 在不同进程里会拿到不同布局（实测 5 个进程里 1 个 `RandomizationError`）。
  回归检查：`python scripts/check_feasibility.py libero_bolt_v2 10` 必须 110/110 全部可 reset。

## 3. 回合预算

| 项 | 值 |
|---|---|
| 环境步数上限（horizon） | `400 + 800 × 本回合要求分拣的件数` → 单件 1200、双件 2000、四件 3600 |
| 单 episode 墙钟超时 | 1200 s（`runtime.task_timeout_s`） |
| 每件失败重试 | 生成代码内最多 1 次（提示词约束）；原语层抓取验证最多 2 次尝试 |

> 预算随件数线性放宽是**协议设计**，写死在此，避免"为了过线偷偷放宽"。

## 4. 成功判定

- 唯一判据：仿真原生 `env._check_success()`（即 bddl 目标谓词，全部 `In(bolt, bin)` 成立）。
- 生成代码可以自己 `R.check()`，但**评测以 verifier 读取的 episode 结果为准**，且只有 `check` 为真成功。
- 进程异常退出、超时、`check=False` 一律记为失败，不做人工剔除。

## 5. 指标

| 指标 | 定义 |
|---|---|
| 成功率 | 成功 episodes / 总 episodes |
| 分任务成功率 | 每个 task 的 10 个 episode |
| 平均节拍 | 平均步数 / episode（20 Hz 控制 → 步数/20 = 秒） |
| 人工介入次数 | 每次 `confirm` 计 1（仿真 auto 模式也留痕） |
| 自动修复轮次 | 采纳的修复轮数（拒绝的不计） |

## 6. 人确认模式

- 纯仿真评测：`AGENT_CONFIRM_MODE=auto`（赛题规定纯仿真不要求运动前确认，但**机制必须存在**）。
- 机制演示/真机：`manual`（TTY 或 `agent/confirm_server.py` 网页批准/拒绝）+ `runtime/audit.jsonl` 审计。
- 另有 `deny` 模式用于回归测试，证明确认门控真的会拦住动作。

## 7. 报告口径

- 主表：主任务 10 任务 × 10 状态。
- 附表：长程压力任务、变体任务（双件/四件）。
- 所有数字对应的 `runs/<run_id>/metrics.json` + `manifest.json` 必须一并提交，任何人可以用同一命令复现。
