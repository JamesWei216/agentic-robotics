# 交接状态（Handoff）· Agentic Robotics 赛题

**最后更新**：2026-10-18（收官口径）
**截止**：2026-11-03（报名/初赛提交）
**工程根目录**：`/home/wei/work/g05/agentic-robotics/`（一键入口 `./run.sh`）
**归档**：`~/Desktop/Agentic-Robotics-赛题/`（PDF + RESULT_SUMMARY + 四组关键运行）

---

## 1. 现在能跑到什么程度

| 口径 | 结果 | 产物 |
|---|---|---|
| **主任务** `libero_bolt_v2`（10 单件任务 × 10 固定 seed = 100 episodes，Agent 全链路，无自动修复） | **100.0%（100/100）**，平均 686 步 | `20261018-134900_v2_carry/` |
| 同任务开启自动修复（A/B） | 子集 97%→100% 采纳，**全量 98%**（未泛化；当时未修复版是 99%） | `runs/20261018-104215_v2_final2/` |
| **变体套件** `libero_bolt_multi`（11 任务 × 10 seed = 110 episodes） | **71.8%（79/110）**，平均 1517 步（大螺栓类 40/40，短板在小螺栓→蓝盒） | `20261018-134855_multi_carry/` |
| **视觉闭环**（加分 b，`AGENT_PERCEPTION=vision`，5 任务 × 4 seed） | **90.0%（18/20）**，平均 697 步 | `20261018-135739_vision_regionfix/` |
| 人确认（manual + 网页面板） | 面板批准 12 次、episode 通过；**4 张实测截图**（待确认/空闲/急停/夹爪闭合） | `reports/screenshots/` + `runs/confirm_demo_panel/` |

Agent 全链路 = 任务书 → LLM 计划（步骤/约束/风险/确认点）→ LLM 生成代码（AST 白名单）→ 仿真执行 → 固定 seed 评测 → 失败诊断 → 自动修复（配对复测，采纳/回退）→ 报告。

---

## 2. 今天（10-18）改了什么

1. **`agent/skills/expert.py`｜搬运路线 + 失速早退**（失败集 A6）
   - `move_to(stall_patience=…)`：位置误差 30–40 步无实质改善即退出，失败段不再烧满 `max_steps`。
   - `transfer()` 路线改为 `high_arc → over_table → split → retreat → via_base`，且**只以"离料盒中心的 xy 距离 ≤ 60 mm"为够用判据**（内腔 172 mm，不必毫米级收敛）。
   - 效果：v2 t6 80% → 90%，平均步数 678 → 631，主口径 98% → 99%。
2. **`scripts/gen_suites.py`｜变体套件区域半长**（失败集 D4）
   - `BOLT_HALF_MULTI=0.030`、`BIN_HALF_MULTI=0.020`（主套件保持 0.070 不变），重新生成 `libero_bolt_multi` 的 11 个 bddl。
   - 效果：`RandomizationError` 从 13% → 0，变体 58.2% → 74.5%。
3. **`agent/skills/perception.py`（新增）+ `api.py` 接线**｜视觉闭环（加分 b）
   - RGB-D 分割 + 深度反投影 + PCA；`AGENT_PERCEPTION=vision` 切换；`docs/perception.md` 有精度表与三个坑。
4. **`scripts/`｜新增诊断与验证脚本**：`diag_t6.py`、`probe_t6_joints.py`、`probe_t6_recover.py`、`validate_perception.py`、`calib_colors.py`、`check_cam_convention.py`、`calib_depth.py`、`confirm_bot.py`。
4b. **`agent/skills/api.py`｜采样器种子化（A11）**：`np.random.seed(seed)` 必须在**构造 env 之前**——
   LIBERO 的 `env.seed()` 只种仿真器，物品布局用全局 `np.random`，否则同一 seed 每次布局都不同。
   配套 `scripts/check_feasibility.py`（110/110 才算环境可用）。
4c. **`scripts/gen_suites.py`｜布局可行化（A12）**：主套件螺栓区域半长 70 → 55 mm，scene2 大螺栓 y 0.02 → −0.03。
5. **文档/交付**：`docs/perception.md` 新增；`docs/failures.md` 追加 A6/A7/D2 改写/D4；`RESULT_SUMMARY.md`、`requirements.txt`、`reports/Agentic-Robotics-赛题总结报告.pdf`。

---

## 3. 接下来该做什么（按优先级）

1. **变体套件的"第 2 件及以后"抓取**（当前主要瓶颈，39 例失败中 30 例含抓取失败）：
   ① 分层子目标编排（每次一件 + 单件预算 + 回安全位），而不是一个脚本顺序跑四件；
   ② 抓取前做"遮挡/邻件检查"——目标被其他工件或料盒挡住时先挪开或换抓取姿态。
2. ✅ **报告配图（2026-10-18 完成）**：`reports/figures/` 三张（流水线架构 1835×1071 / 收敛曲线 2211×805 /
   失败分类 1460×660），由 `scripts/make_figures.py` 用 matplotlib 生成并嵌入报告。
3. 视觉模式收口（18/20 → 目标 20/20）：
   - 蓝盒内腔底面被近侧盒壁遮挡，估计偏高 12 mm → 用"盒口高度 − 已知盒高"替代内腔底面 5 分位；
   - 小螺栓柄夹持偶滑脱 → 抓六角头 + 高度闭环（需更稳的 z：现在 OSC 偏差 3–8 mm）。
3. ✅ **面板截图（2026-10-18 完成）**：`reports/screenshots/` 四张 PNG（待确认 / 空闲 / 急停 / 夹爪闭合），
   由 `scripts/capture_confirm_panel.py` 从 live 面板渲染；已嵌进报告 PDF 第六节。
4. ✅ **打包自检（2026-10-18 完成）**：新建 conda 环境按 `requirements.txt` 从零装好 → preflight 7/7 → t6 2/2 通过；
   过程中补出 6 个隐式依赖（pyyaml / termcolor / bddl / easydict / matplotlib / gym==0.22），已写进 `requirements.txt` 与 `docs/setup.md`。

---

## 3b. 提交状态（2026-10-18 17:45）

| 项 | 状态 |
|---|---|
| 代码仓库 | ✅ <https://github.com/<你的GitHub用户名>/agentic-robotics>（public，16 提交 / 8 tag / 79 文件，SSH 推送） |
| 认证 | ✅ SSH（`~/.ssh/id_ed25519`，无口令，公钥已加到 GitHub）；一次性 token 已删除 |
| 提交包 | ✅ `~/Desktop/Agentic-Robotics-提交包-20261018/`（11 MB：repo bundle / 两个 zip / 演示片 + 10 片段 / 12 页 PPT / 5 页 PDF） |
| PR 合入方式 | 后续修改直接 `git push origin master`（SSH 免 token）；大改动建议开分支 + tag |
| 待办 | ① 官方《任务说明书》/最低指标数值 → 据它校报告措辞 ② 可选：在 GitHub 打 Release 挂 PDF/PPT/演示片 |

## 4. 关键路径与命令

```bash
PY=/home/wei/work/g05/GalaxeaVLA-main/.venv/bin/python
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export PYTHONPATH=/home/wei/work/g05/agentic-robotics:/home/wei/work/g05/LIBERO-master

./run.sh --suite libero_bolt_v2    --taskbook taskbooks/sort_main.md    --tasks 0,1,2,3,4,5,6,7,8,9 --seeds 10
./run.sh --suite libero_bolt_multi --taskbook taskbooks/sort_variant.md --tasks 0,1,2,3,4,5,6,7,8,9,10 --seeds 10
AGENT_PERCEPTION=vision ./run.sh --suite libero_bolt_v2 --no-llm --tasks 0,1,2,3,4 --seeds 4
./run.sh --no-llm --tasks 5 --seeds 3          # 无 LLM 回归
python -m agent.confirm_server --port 8077     # 人确认面板（另开一个 manual 运行）
python scripts/make_report_pdf.py              # 需 smolvla 环境的 weasyprint
```

---

## 5. 结构速查（新增部分标 +）

```
agentic-robotics/
├── run.sh                 # 一键入口
├── requirements.txt       # +
├── RESULT_SUMMARY.md      # +
├── config/agent.json      # LLM / 运行 / 安全参数
├── config/missions.json   # 任务协议（suite+task → 哪件入哪个盒）
├── taskbooks/             # 主任务 / 变体任务任务书
├── agent/
│   ├── planner.py  codegen.py  executor.py  verifier.py
│   ├── diagnose.py confirm.py confirm_server.py safety.py
│   └── skills/
│       ├── api.py         # 原语（含 PERCEPTION_MODE 分支）
│       ├── expert.py      # 抓放实现（路线 / 失速早退 / 视觉分支）
│       └── perception.py  # + RGB-D 感知
├── scripts/               # 套件生成 + 诊断/验证 + 报告 PDF（+ 今日 8 个脚本）
├── docs/                  # workcell / protocol / failures / perception(+)
└── runs/<run_id>/         # plan/task.py/metrics/report + 每 episode 日志
```

---

## 6. 今天踩过/复查过的坑

1. **区域半长过大**会让多物体套件在 reset 阶段就不可行（表现为 `RandomizationError`，不是策略问题）。
2. **"收敛"不等于"可达"**：料盒内腔宽度才是释放可行性的尺度。
3. **关节限位饱和**：OSC 卡在 `j4` 下限时 EE 冻结但误差不降 → 必须靠失速早退，不然每段烧满预算。
4. **深度相机约定**：图像缓冲自下而上、内外参自上而下；"缓冲行取深度 + 翻转行算 y"才对（错配 81 mm，正确 9 mm）。
5. **深度看到的是最高面**（六角头），不是要夹的柄 → 抓取高度用"台面标定 + 工件几何"。
6. **腕部像素数≠在手机检**（工件在指下方也算），抓取判定用"撤臂后原位是否已空"。
7. `run.sh` 不带 `-u`，后台日志会缓冲；看进度请看 `runs/<id>/verify/` 而不是日志文件。

---

## 7. 2026-10-22 夜 · 官方赛题要求到手后的状态（明天从这里继续）

**官方要求差距清单**：`docs/SPEC_GAP.md`（逐条对齐 + P0/P1/P2 + 排期到 11-03）

### ✅ 已完成：P0-1 可复现打包（commit `9ce9ad5`，本地未 push）

- `vendor/bolt-sorting/` 入仓；`scripts/bootstrap_env.sh`（8 步幂等，LIBERO pin `8f1084e`）
- `scripts/_paths.py` 路径解析；`run.sh` / `agent/skills/api.py` 同步
- `scripts/make_submission.sh` 官方命名一键打包（实测 5.3 MB / 3161 文件）
- `docs/运行方式.md`（提交包内）、`docs/repro_check_20261022.md`（干净环境实测）
- **实测**：`/tmp` 全新副本 + 新 conda（CPU torch）→ preflight 7/7 → t6 s1000 100%（1079 步 / 8.7 s）
- 实测抓到并修复 **A14 `LIBERO_CONFIG_PATH` 用户级全局配置串台**、**A15 安装顺序 KeyError**（见 `docs/failures.md`）
- 开发机 LIBERO 的 bddl/init 已恢复（11+11），preflight 复查 7/7

### ⏭️ 明天待做（按顺序）

1. **P1-1 码垛 suite**（`libero_wood_stack`）+ 改动成本表 → 补官方加分 c「码垛↔分拣切换、改动成本可量化」
2. **P1-2 变体 71.8% → ≥85%**（分层子目标编排 + 遮挡检查）
3. **P1-3 报告口径**：人确认按官方口径改（仿真 auto 不阻断 / 真机 manual+急停）、补 Agent 证据链章节、无隐藏测试集声明
4. **P0-2 打包**：等 James 给 单位简称 / 作品名 / 队长姓名 / 手机号
5. **P0-3 视频**：≤5 min 成片 + 网盘链接（等网盘选定）

### 需要 James 提供
- 官方《任务说明包》（**分拣物料是否含螺母**最重要；还有最低指标数值、工位尺寸/垛型）
- 提交包命名 4 个字段；网盘账号

---

# 2026-10-23 · P1-1 码垛套件完成（加分 c）

**代码**：`scripts/gen_stack_suite.py` + `vendor/wood-stack/` + 技能层 `place_on_top`（详见 `docs/stacking.md`）
**结果**：`libero_wood_stack` 11 任务 × 10 seed = **100.0%（110/110）**，均 564 步；LLM 全链路 8/8 = 100%
**回归**：`libero_bolt_v2` 98.0%（模板口径，t6 8/10）、`libero_bolt_multi` 72.7%（对照 LLM 口径 100% / 71.8%）

### 新增文件
- `scripts/gen_stack_suite.py`、`scripts/probe_stack.py`、`taskbooks/stack_main.md`
- `vendor/wood-stack/{gen_assets,libero_wood_objects,install}.py`
- `docs/stacking.md`（设计 + 改动成本表 + A16–A21）

### 改动文件
`agent/skills/expert.py`(+208) `agent/skills/api.py`(+84/−6) `agent/schemas.py` `agent/codegen.py`
`agent/planner.py` `agent/prompts.py` `agent/run.py` `scripts/gen_missions.py` `scripts/preflight.py`
`scripts/bootstrap_env.sh` `config/missions.json`

### 明天/接下来（按优先级）
1. **P0-2 提交包**：需要 James 给 单位简称 / 作品名称 / 队长姓名 / 队长手机号（命名规则硬性）
2. **P0-3 视频成片（≤5 min，≥720P）+ 网盘链接**：素材齐（演示片 + 逐 episode 日志），缺叙事剪辑与上传
3. **P1-3 报告口径与证据链**：人确认措辞改官方口径、Agent 证据链章节、无隐藏测试集声明、失败案例章节（A6/A11–A21）
   → PDF 目标 12–15 页（现 5 页），把 `docs/stacking.md` 的改动成本表整段搬进去
4. **P1-2 变体 72.7% → ≥85%**（分层子目标编排 + 邻件遮挡检查），对冲未知最低指标
5. 可选：`libero_wood_stack` 也做一次视觉闭环？**不做**——感知模块只分割钢色螺栓，木块没有检测器（已在代码里显式报错）

### 复现命令（码垛）
```bash
./run.sh --suite libero_wood_stack --taskbook taskbooks/stack_main.md \
         --tasks 0,1,2,3,4,5,6,7,8,9,10 --seeds 10 --repairs 0
```
