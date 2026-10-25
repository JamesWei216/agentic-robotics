# Agentic Robotics 赛题 · 结果汇总（RESULT_SUMMARY）

**日期**：2026-10-18（收官口径：采样器种子化 + 区域语义修正 + 全部修复）
**项目**：`/home/wei/work/g05/agentic-robotics/`
**平台**：LIBERO / MuJoCo · Franka Panda 单臂 + 平行二指夹爪（纯仿真，无真机依赖）

---

## 1. 三组数字（与 `runs/*/metrics.json` 一一对应）

| 口径 | 命令要点 | 成功 | 平均步数 | 产物 |
|---|---|---|---|---|
| **主任务**（10 单件任务 × 10 固定 seed，无自动修复 = 主口径） | `--suite libero_bolt_v2 --seeds 10 --repairs 0` | **100.0%（100/100）** | 685.6（34.3 s/回合） | `runs/20261018-134900_v2_carry/` |
| **变体任务**（批量分拣，11 任务 × 10 seed） | `--suite libero_bolt_multi --seeds 10` | **71.8%（79/110）** | 1517 | `runs/20261018-134855_multi_carry/` |
| **视觉闭环**（加分 b，5 任务 × 4 seed） | `AGENT_PERCEPTION=vision` | **90.0%（18/20）** | 697 | `runs/20261018-135739_vision_regionfix/` |

主任务**逐任务全清**：t0–t9 各 10/10；0 次超步、0 次 reset 失败、0 次 OOM。

### 变体套件逐任务（11 任务 × 10 seed）

| 任务 | t0 | t1 | t2 | t3 | t4 | t5 | t6 | t7 | t8 | t9 | t10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 通过 | 10/10 | 6/10 | 10/10 | 6/10 | 10/10 | 2/10 | 10/10 | 9/10 | 9/10 | 3/10 | 4/10 |

大螺栓类任务（t0/t2/t4/t6）**40/40 全清**；短板集中在小螺栓→蓝盒（t1/t5/t9）与 4 件任务（t10）。

## 2. 一天的收敛过程（同一任务书，逐步修 bug）

| 阶段 | 主任务 | 关键改动 |
|---|---|---|
| 10-17 深夜基线 | 98.0%（98/100） | — |
| + 搬运高弧线 + 失速早退 + 判据分离 | 99.0%（99/100） | A6、A7 |
| + 采样器种子化（"固定 seed"真的可复现） | 97.0%（97/100） | A11：暴露出 t3 有两个 seed 本来就不可行 |
| + 螺栓区域 70→55 mm + scene2 微调 | **100.0%（100/100）** | A12，`check_feasibility` 110/110 全通过 |
| + **区域语义修正**（半长 = 物体半径 + 目标抖动） | **100.0%（100/100）**，686 步 | A13：料盒原被"散布" ±57–87 mm 到可达域外；变体 64.5→71.8、视觉 85→90 |

> 中间那次"下降"不是退步：把随机性关掉之后，原本被运气掩盖的**不可行初始状态**才暴露出来；
> 修的是套件几何，不是分数。

## 3. 变体任务为什么只有 ~64%

失败分类（110 episodes，按 trace 统计）：**39 例失败中 30 例含"抓取失败"**，其中多数是
"第 2 件及以后"的抓取（第 1 件成功率 87%，第 2 件起明显下降）。已做的缓解：
① 释放后先 `home()` 回安全位再接近（t3 单任务 4/10 → 7/10）；
② 失败后一次"重抓 + 再搬运"（带剩余步数守门）；
③ 变体套件区域半长 70/25 → 20/8 mm（消除 reset 阶段的布局碰撞）。

仍失败的根因（如实标注）：上一动作残留姿态 + 目标被其他工件/料盒部分遮挡时，预抓取位姿在
OSC 关节限位处饱和，夹爪在工件上方闭合。下一步：改为**分层子目标编排**（每次只对一件做完整闭环 +
回安全位），而不是一个脚本顺序跑四件。

## 3b. 改动成本（加分 c 的量化证据，git 可复算）

仓库已初始化并分段提交，三个 tag 对应三个交付状态：

```
v0.1-main      主任务达标（libero_bolt_v2 100/100）
v0.2-variant   变体任务接入（批量分拣）
v1.0-submit    初赛提交版本（含感知闭环 + 交付物）
```

| 对比 | 命令 | 结果 |
|---|---|---|
| 变体任务接入对**控制链路**的改动 | `git diff v0.1-main v0.2-variant --stat -- agent/` | **空（0 行）** |
| 变体任务接入的**全部**改动 | `git diff v0.1-main v0.2-variant --stat` | 1 file changed, 68 insertions（只有 `taskbooks/sort_variant.md`） |

也就是说：**换任务 = 换一份任务书**；套件由同一 `scripts/gen_suites.py` 生成，`config/missions.json`
由 bddl 的 goal 自动导出，控制链路与安全层完全复用。

## 4. 视觉闭环（加分项 b）

- `agent/skills/perception.py`：颜色分割 + 深度反投影 + PCA（长轴 / 长度分类 / 盒几何），
  运行时不读任何仿真真值；`AGENT_PERCEPTION=vision` 切换。
- 离线核对（真值仅作测试预言机）：24/24 检出，盒中心 0.4–4.2 mm，螺栓横向 2–7 mm / 沿轴 4–8 mm，
  大小分类 12/12，假目标 0（加尺寸门限前每场景 4 个，来自机械臂本体的大团块）。
- 在线：**90.0%（18/20）**（区域修复后复测）；两次失败：t3 s1003 抓取两试空夹（xy 偏 5–7 mm 把六角头误当柄）、
  t3 s1000 放置失败（盒腔底面被盒壁遮挡，深度估计偏高 12 mm）。
- 三个必须踩的坑：图像缓冲自下而上 vs 内外参自上而下（错配 81 mm → 正确 9 mm）；深度看到的是六角头顶面
  （比柄高 9–14 mm）；腕部像素数≠在手机检（工件在指下方也算）。

## 5. 自动修复 A/B（诚实结论）

| 轮次 | 配对子集（3 seeds/任务） | 全量 100 episodes | 结论 |
|---|---|---|---|
| r1 | 97% → 100% | 98%（比当时未修复版低 1 点） | harness 采纳，但**未泛化** |

根因判断正确（`pick` 吃掉 717/1200 步 → `place` 超步），子集也确实全过 —— 但全量复测没有提升。
说明"子集提升"不足以证明修复有效，报告里单列为风险；主口径采用未修复版。

## 6. 人机确认（真机口径；纯仿真 auto 不阻断）

- 三模式 `auto / manual / deny`；四条门控 `first_motion / grasp_close / release / long_travel`。
- 网页面板 `python -m agent.confirm_server --port 8077`（带**急停**），决定走 `runtime/confirm/`，审计落 `runtime/audit.jsonl`。
- 本轮用面板完成 manual 演示：3 次批准，快照见 `runs/confirm_demo_panel/`。

## 7. 交付清单

```
~/Desktop/Agentic-Robotics-赛题/
├── Agentic-Robotics-赛题总结报告.pdf   # 15 页 A4（weasyprint，2026-10-25 v2）
├── RESULT_SUMMARY.md                    # 本文件
├── STATUS.md                            # 交接状态 + 下一步
├── requirements.txt
├── README.md PLAN.md
├── agent/ config/ taskbooks/ scripts/ run.sh
├── docs/            # workcell / protocol / failures(32 例) / perception / stacking
├── reports/videos/  # 9 条演示视频（含 1 条失败）
├── runs/            # 主任务 / 变体 / 视觉 / 人确认 的关键运行
└── confirm_demo_panel/
```

## 8. 复现与自检

```bash
PY=/home/wei/work/g05/GalaxeaVLA-main/.venv/bin/python
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export PYTHONPATH=/home/wei/work/g05/agentic-robotics:/home/wei/work/g05/LIBERO-master

$PY scripts/preflight.py                    # 环境自检（7 项）
$PY scripts/check_feasibility.py libero_bolt_v2 10   # 110/110 布局可行
./run.sh --suite libero_bolt_v2 --taskbook taskbooks/sort_main.md --tasks 0,1,2,3,4,5,6,7,8,9 --seeds 10 --repairs 0
```

---

# 2026-10-23 追加：码垛套件（加分 c「码垛 ↔ 分拣切换 + 改动成本可量化」）

详见 `docs/stacking.md`。要点：

| 口径 | 套件 | 结果 | 平均步数 |
|---|---|---|---|
| 模板代码（`--no-llm`，确定性） | `libero_wood_stack` 11 任务 × 10 seed = 110 | **100.0%（110/110）** | 564 |
| LLM 全链路（DeepSeek 出计划 + 出代码） | 4 任务 × 2 seed = 8 | **100.0%（8/8）** | 618 |

- 垛型 3 种：3 层直塔（t0–t4）、2 层塔（t5–t9）、双层双列 4 块（t10）；成功判定用 LIBERO 原生 `On(top, base)`（接触 + z 序 + xy < 30 mm），**无自写判定脚本**。
- 放置精度 0.5–8.4 mm xy、落点高度恒为一个块高（40.0 mm）。
- **改动成本**：新增/修改代码 ≈1,224 行（tracked +601/−59 + 新文件 623），其中真正控制逻辑 **292 行**（`expert.py` 208 + `api.py` 84）；新增 1 个对象资产、1 个配置字段（mission 的 `on`）+ 11 条任务协议；编排/执行/评测/安全/人确认/报告层**零改动**。
- 分拣回归（no-LLM 模板口径）：`libero_bolt_v2` 98.0%（t6 大螺栓 8/10）、`libero_bolt_multi` 72.7%（对照 10-18 LLM 口径 100% / 71.8%）→ 无明显回退。
- 新增 6 个坑（A16–A21，见 `docs/failures.md`）：抓取高度导致肘关节奇异、工作空间舒适带 x ≤ +0.10、释放间隙要按指尖算、运输高度按垛顶算、限位后不可恢复、mission 解析要区分 init/goal。

---

# 2026-10-25 追加：P1-3 报告定稿（失败案例章 + 评测声明）

**报告 PDF 从 7 页扩到 15 页**（`reports/Agentic-Robotics-赛题总结报告.pdf`，生成器 `scripts/make_report_pdf.py`）。

新增内容：
1. **第四章 失败案例分析（运行日志实证）**：失败清单/失败原语/失败件序/失败坐标**全部由生成脚本现场扫描**
   `runs/*/verify/*/result.json` + `trace.jsonl` 统计（`_fail_detail()`），并给出一条失败 episode 的完整日志回放
   （multi t5 s1000）、失败位置指纹、A6–A13 摘要表、32 条完整失败索引。
2. **第五章 自动修复 A/B**：机制四步 + 本次 r1 真实结果（子集 97%→100% 采纳、全量 98%）+ `diagnosis_r1.json` 原文摘录 + 诚实结论。
3. **第八章 评测协议与「无隐藏测试集」声明**：协议表、三条声明（无隐藏测试集 / 无伪造日志 / 数字与运行结果强绑定）、
   产物清单、干净环境实测（preflight 7/7，CPU-only，~40 min）。
4. **三·A 工位与物料**：毫米级工位/物料/5 套布局表 + 可达域设计（加分 c 的"可复现工作单元"）。
5. **附录 A 套件与任务清单**：33 条任务的语言指令（取自 episode_start）。
6. 口径修正：人确认改为官方口径（仅约束真机；仿真 auto 不阻断）；修正 §二 与实跑数字不一致的旧表述。

### 关键失败统计（本报告新增的硬数字）

| 套件 | episodes | 失败 | 构成 |
|---|---|---|---|
| 主任务 bolt_v2 | 100 | 0 | — |
| 变体 bolt_multi | 110 | 31 | **28 抓取失败（全部第 2 件及以后；其中 3 例伴随 1 次放置失败）** + 3 初始布局不可行 |
| 码垛 wood_stack | 110 | 0 | — |
| 视觉闭环 | 20 | 2 | 1 抓取失败 + 1 放置失败 |

失败 pick 的 EE x 分布 −0.133…+0.141 m、中位 +0.102 m，31/56 落在 x > +0.09 → 与码垛阶段独立测到的舒适带（A17）互证，
下一版按件编排（P1-2）。
