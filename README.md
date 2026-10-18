# Agentic Robotics — Agent 驱动的机械臂分拣流水线

赛题：**Agent 驱动的机械臂应用开发与评测流水线**（主任务：分拣 → 变体任务：批量分拣）
平台：LIBERO / MuJoCo + Franka Panda 单臂 + 平行二指夹爪 · **纯仿真，无真机依赖**

一句话：**自然语言任务书进去，可执行的抓放代码、仿真评测数字、失败诊断、自动修复和报告出来**，每一步都留可复现的产物。

---

## 0. 现在跑到什么程度（2026-10-18 收官）

| 口径 | 命令 | 结果 | 产物 |
|---|---|---|---|
| **主任务** `libero_bolt_v2`（10 单件任务 × 10 固定初始状态 = 100 episodes） | `--repairs 0` | **100.0%（100/100）**，587 步/回合，29.4 s | `runs/20261018-122903_v2_final_seeded/` |
| **变体任务** `libero_bolt_multi`（11 任务 × 10 seed = 110 episodes，每类 2 件） | `--suite libero_bolt_multi` | **64.5%（71/110）**（另一次独立生成 63.6%） | `runs/20261018-123707_multi_final/` |
| **视觉闭环**（加分 b，5 任务 × 4 seed） | `AGENT_PERCEPTION=vision` | **85.0%（17/20）** | `runs/20261018-122911_vision_final/` |
| **人机确认**（manual + 网页面板，含急停） | `--confirm-mode manual` | 3 次门控经面板批准，审计留痕 | `runs/confirm_demo_panel/` |
| 自动修复 A/B | `--repairs 1` | 配对子集 97%→100% 被采纳，**全量复测 98%（未泛化）** | `runs/20261018-104215_v2_final2/` |

> 失败集 12 例、感知精度表、评测协议、工位几何都在 `docs/`；数字出处在 `runs/*/metrics.json`，
> 报告 PDF 直接从这些 JSON 读，不会与运行结果脱节。

---

## 1. 流水线

```
taskbooks/sort_main.md           ← 自然语言任务书（工位/物料/目标/约束/确认要求/风险）
        │
        ├─[1] 任务理解  agent/planner.py     LLM → plan.json（步骤 / 约束 / 风险点 / 确认点）
        ├─[2] 代码生成  agent/codegen.py     LLM → task.py（只允许调用原语 API，AST 白名单校验）
        ├─[3] 仿真执行  agent/executor.py    每条 episode 独立子进程；trace.jsonl + run.log (+mp4)
        ├─[4] 达标评测  agent/verifier.py    固定 seed 协议；成功率 / 节拍 / 人确认次数
        ├─[5] 失败诊断  agent/diagnose.py    规则分类 + LLM 根因（root_cause / evidence / fix_hint）
        └─[6] 自动修复  agent/codegen.repair  改代码 → 配对子集复测 → 采纳或回退 → 全量复测
                                  │
                                  └→ runs/<id>/{plan.json, task.py, metrics.json, report.md, manifest.json}
```

**为什么不让 LLM 裸写控制代码**：LLM 只生成"编排 + 参数"，实际动作走一层已验证的原语
（抓取点从工件几何算、搬运路线有回退、释放高度按内腔底面算）。这样既保留 Agent 在产品链路里的
真实参与，又不会把 90%+ 的成功率交给随机性。

### 技能原语（Agent 只能用这些，`agent/skills/api.py`）

| 原语 | 作用 |
|---|---|
| `settle(steps)` | 场景静置（平躺螺栓前 30 步会下沉 ~13 mm，必须先静置再取抓取点） |
| `scan(category)` | 感知，返回 `[{"id","label","pose","source"}]`；`AGENT_PERCEPTION=vision` 时走 RGB-D |
| `todo()` | 本 episode 必须完成的分拣对（由 bddl goal 自动生成的 `config/missions.json`） |
| `pick(object)` | 自上而下抓杆身；未夹到 → `RuntimeError`（失败后自动重抓一次，带预算守门） |
| `place(object, box)` | 搬运 → 低空释放 → 撤回 → 返回**本件是否进本盒** |
| `pick_and_place(object, box)` | 上面两步的合成 |
| `home()` / `check()` / `log()` / `confirm(action)` | 回安全位 / 判定成功 / 打点 / 人确认 |

### 人机确认（赛题硬性要求）

- 三模式：`auto`（纯仿真，仍写审计）/ `manual`（真机式阻塞）/ `deny`（回归测试用）。
- 四条门控：`first_motion`（解除使能）、`grasp_close`（夹爪闭合）、`release`（释放物料）、`long_travel`（长距离移动）。
- 网页面板 `python -m agent.confirm_server --port 8077`，带**急停**按钮（写 `runtime/ESTOP`，所有原语每步检查）；
  决定走 `runtime/confirm/*.json`，审计落 `runtime/audit.jsonl`。

---

## 2. 快速开始

```bash
cd /home/wei/work/g05/agentic-robotics
PY=/home/wei/work/g05/GalaxeaVLA-main/.venv/bin/python
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export PYTHONPATH=$PWD:/home/wei/work/g05/LIBERO-master

$PY scripts/preflight.py                      # ① 环境自检（7 项：包/套件/注册/资产/渲染/missions/LLM）
$PY scripts/check_feasibility.py libero_bolt_v2 10   # ② 110/110 初始状态可行才算环境可用

# 主任务全量（主口径，100 episodes，无自动修复）
./run.sh --suite libero_bolt_v2    --taskbook taskbooks/sort_main.md \
         --tasks 0,1,2,3,4,5,6,7,8,9 --seeds 10 --repairs 0 --tag main

# 变体任务全量（110 episodes）
./run.sh --suite libero_bolt_multi --taskbook taskbooks/sort_variant.md \
         --tasks 0,1,2,3,4,5,6,7,8,9,10 --seeds 10 --repairs 0 --tag variant

# 视觉闭环（RGB-D 感知，不读仿真真值）
AGENT_PERCEPTION=vision ./run.sh --suite libero_bolt_v2 --no-llm \
         --tasks 0,1,2,3,4 --seeds 4 --repairs 0 --tag vision

# 单任务快速验证 / 完全离线（不调 LLM）
./run.sh --tasks 5 --seeds 3 --tag quick
./run.sh --no-llm --tasks 5 --seeds 3 --tag offline

# 人机确认演示（另开一个终端打开 http://localhost:8077/）
python -m agent.confirm_server --port 8077 &
./run.sh --confirm-mode manual --tasks 5 --seeds 1 --tag hitl

# 演示视频 / 总结报告
$PY scripts/make_videos.py                    # → reports/videos/*.mp4
/home/wei/miniconda3/envs/smolvla/bin/python scripts/make_report_pdf.py   # 需 weasyprint
```

依赖：见 `requirements.txt`；LIBERO 需 `pip install -e /home/wei/work/g05/LIBERO-master --no-deps`，
自定义套件用 `scripts/gen_suites.py` 生成并注册。LLM：DeepSeek（key 取 `$DEEPSEEK_API_KEY`，
否则读 OpenClaw auth store；`--no-llm` 可完全离线）。

---

## 3. 产物

```
runs/<run_id>/
├── plan.json          结构化计划（步骤/约束/风险/确认点）      ← 赛题 2.b
├── plan_meta.json     计划来源（llm/fallback）、尝试次数
├── task.py            生成的控制逻辑（AST 白名单校验通过）      ← 赛题 2.d
├── code_meta.json     生成方式与校验结果
├── smoke/             单 episode 冒烟
├── verify/ (verify_final/)  每 episode 一个目录：trace.jsonl / run.log / stderr.log / result.json
├── metrics.json       成功率、分任务明细、平均步数、确认次数     ← 赛题 2.e
├── diagnosis_r*.json  失败根因分析                            ← 赛题 2.f
├── repair_r*/         修复前后代码 + 配对子集复测 + 全量复测
├── report.md          人读报告
└── manifest.json      全链路溯源（模型/协议/指标/产物清单）
```

---

## 4. 与赛题要求的对应

| 赛题要求 | 实现位置 | 状态 |
|---|---|---|
| a 主任务（分拣）+ 变体任务 | `taskbooks/sort_main.md`（按尺寸）/ `taskbooks/sort_variant.md`（批量，每类 2 件）；套件 `scripts/gen_suites.py` | ✅ 100/100、64.5% |
| b Agent 任务理解：NL → 结构化计划 | `agent/planner.py` + `agent/prompts.py` + `agent/schemas.py` | ✅ |
| c 场景/流程构建（可复现工作单元） | 两个套件 + 550 初始状态；采样器种子化 + `scripts/check_feasibility.py` | ✅ 110/110 可行 |
| d 代码生成与调试 + 关键动作人确认 | `agent/codegen.py`（LLM + 模板双路 + AST 白名单）、`agent/run.py` 修复循环、`agent/confirm*.py` | ✅ |
| e 仿真达标 | `agent/verifier.py`（固定 seed 协议）+ `docs/protocol.md` | ✅ 100 episodes |
| f 工程交付 | `run.sh` / `requirements.txt` / `runs/*/report.md` / `docs/failures.md`（12 例）/ `reports/videos/` | ✅ |
| 加分 a 虚实迁移（真机） | — | ❌ 未做（SO-101 在手，3–5 天，风险最高） |
| 加分 b 感知闭环 | `agent/skills/perception.py`（RGB-D 分割 + 反投影 + PCA），`AGENT_PERCEPTION=vision` | ✅ 85% |
| 加分 c 多任务泛化 | 变体任务书 + 同一 Agent 框架；`agent/` 侧零改动（换任务书 + 套件参数） | 🟡 数量/布局维度已验证，跨任务类型（码垛）未做 |
| 加分 d 安全与协同 | `agent/safety.py`（工作空间 AABB / 位移上限 / e-stop）+ 确认面板 + 审计 | ✅ |

---

## 5. 目录结构

```
agentic-robotics/
├── run.sh                 一键入口
├── requirements.txt       运行时依赖
├── RESULT_SUMMARY.md      结果汇总（数字 + 收敛过程 + 诚实边界）
├── STATUS.md              交接状态与下一步
├── PLAN.md                10-17 的盘点与补齐计划（含 10-18 收官对照）
├── config/agent.json      LLM / 运行 / 安全参数
├── config/missions.json   任务协议（suite+task → 哪件入哪个盒）
├── taskbooks/             自然语言任务书（主任务 / 变体任务）
├── agent/                 planner / codegen / executor / verifier / diagnose /
│                          confirm(+server) / safety / run + skills/{api,expert,perception}
├── scripts/               套件生成、可行性检查、感知标定、诊断、视频、报告 PDF
├── docs/                  workcell（工位几何）/ protocol（评测协议）/
│                          failures（12 例失败案例分析）/ perception（视觉闭环）
├── reports/               PDF 报告 + videos/
└── runs/<run_id>/         每次运行的全链路产物
```

---

## 6. 已验证 / 已知限制（如实标注）

**已验证**
- `scripts/preflight.py` 7 项自检全过；`scripts/check_feasibility.py` 110/110 初始状态可 reset。
- 归档目录内（`~/Desktop/Agentic-Robotics-赛题/`）可直接 `./run.sh --no-llm` 跑通，不依赖开发机的临时文件。
- 主任务 100 episodes 全部通过，0 次超步、0 次 OOM、0 次 reset 失败。

**已知限制**
- 变体任务 64.5%：失败 39 例中 30 例含"抓取失败"，集中在第 2 件及以后（第 1 件 87%）。根因是
  上一动作残留姿态 + 邻件遮挡下预抓取位姿在关节限位饱和；下一步是分层子目标编排，不是一个脚本顺序跑四件。
- 视觉闭环 85%：小螺栓柄径仅 13 mm，柄夹持接触面小偶有滑脱；蓝盒内腔底面被近侧盒壁遮挡，估计偏高 12 mm。
- 主任务的主口径感知是**特权位姿**；视觉闭环单列，不混进主口径。
- 自动修复（r1）根因判断正确、子集 97%→100%，但全量复测 98%（未泛化）——"子集提升不等于修复有效"已在报告单列。
- 本管线不做策略学习：控制逻辑是解析式原语组合；VLA 微调结果（14.5% / 10.2%）作为对照基线，不参与达标口径。

---

## 7. 文档索引

| 文档 | 内容 |
|---|---|
| `docs/protocol.md` | 评测协议：任务集 / 初始状态 / 步数预算 / 指标定义（写死，不可事后调整） |
| `docs/workcell.md` | 工位几何、物料参数、可达域设计、`contain_region` 约定 |
| `docs/failures.md` | 12 个真实失败案例：现象 → 根因 → 修复 → 影响（A1–A12、D1–D4） |
| `docs/perception.md` | RGB-D 感知：运行时不用真值、精度表、三个必须踩的坑 |
| `RESULT_SUMMARY.md` | 三组数字 + 一天的收敛过程 + 诚实边界 |
| `STATUS.md` | 交接状态、下一步优先级、结构速查、踩坑速查 |
