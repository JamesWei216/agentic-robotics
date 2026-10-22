# G0.5 仿真复现扩展：LIBERO「螺栓分拣」任务（红/蓝料盒版）

**日期**：2026-10-08（当日第二版：料盒改为**一红一蓝**）
**基线**：星海图 G0.5 + LIBERO 复现（2026-09-24，四套件 2000 episodes **98.4%**，官方 98.9%）
**本次目标**：仿真场景 = 桌面上 **两个料盒（蓝色 / 红色）**，**两种不同尺寸的螺栓**分别分拣到对应颜色的盒子里

---

## 1. 结论摘要

- 场景已按要求改为 **一红一蓝两个料盒**：**蓝色盒（小，130 mm）** 放 **小螺栓**，**红色盒（大，190 mm）** 放 **大螺栓**。
- 套件 `libero_bolt` 共 **11 个任务**，全部通过功能验证：**11/11 任务的目标谓词可被正确触发**。
- G0.5-LIBERO 权重（只在 LIBERO 四套件上微调过）**零样本**评测：**21/110 = 19.1%**。
  - 小螺栓 → 蓝盒：**32.0%**（16/50）
  - 大螺栓 → 红盒：**10.0%**（5/50）
  - 长程「两个螺栓都放对」：**0%**
  - 单任务最高 **70%**（place the small bolt inside the blue box）
- 对照：同权重在域内 LIBERO 四套件是 **98.4%** —— 14.5%→19.1% 的零样本水平说明
  **模型能把螺栓抓起来并放进盒子，但"按尺寸选对螺栓 / 放进对应颜色的盒子"远未稳定形成**。

## 2. 场景与物体

| 物体 | 类型 | 尺寸 | 外观 |
|---|---|---|---|
| `bolt_small` | 可动（自由关节） | 总长 **62 mm**，六角对边 22 mm，杆径 13 mm | 亮钢色 |
| `bolt_large` | 可动（自由关节） | 总长 **103 mm**，六角对边 38 mm，杆径 24 mm | 深灰（发黑） |
| `parts_bin_blue` | 可动（自由关节） | 外 130 mm，壁厚 8 mm，高 45 mm | **蓝色** ← 小螺栓 |
| `parts_bin_red` | 可动（自由关节） | 外 190 mm，壁厚 9 mm，高 65 mm | **红色** ← 大螺栓 |

- 螺栓**平躺**在桌面上（长轴沿 X，六角头一个平面朝下 → 静置稳定），生成时绕 Z 轴随机偏航。
- 螺栓外形程序生成（`trimesh` 六棱柱头 + 圆柱杆 → OBJ 视觉体；box + cylinder 碰撞体，与网格严格对齐，含 bbox 断言）。
- 料盒 = 5 个 box（底板 + 四壁），内腔带 `contain_region` 位点 → LIBERO `In` 谓词的判据。
- 每个料盒都做了**成对几何**：碰撞体在 geom group 0、可见体在 group 1
  （robosuite 离屏渲染只画 group 1，否则物体会"隐形"）。

## 3. 任务与结果（零样本）

| # | 任务语言 | 目标谓词 | 成功 | 成功率 |
|---|---|---|---|---|
| 0 | move the large bolt into the red box | `In(bolt_large_1, red_box)` | 0/10 | 0% |
| 1 | move the small bolt into the blue box | `In(bolt_small_1, blue_box)` | 2/10 | 20% |
| 2 | pick up the large bolt and place it in the red box | 同上 | 1/10 | 10% |
| 3 | pick up the small bolt and place it in the blue box | 同上 | 3/10 | 30% |
| 4 | place the large bolt inside the red box | 同上 | 0/10 | 0% |
| 5 | place the small bolt inside the blue box | 同上 | **7/10** | **70%** |
| 6 | put the large bolt in the red box | 同上 | 4/10 | 40% |
| 7 | put the small bolt in the blue box | 同上 | 1/10 | 10% |
| 8 | put the small bolt in the blue box and the large bolt in the red box | 两个 `In` 同时成立 | 0/10 | 0% |
| 9 | take the large bolt and drop it into the red box | 同上 | 0/10 | 0% |
| 10 | take the small bolt and drop it into the blue box | 同上 | 3/10 | 30% |

| 维度 | 成功率 |
|---|---|
| **整体** | **19.1%**（21/110） |
| 小螺栓 → 蓝盒（5 条） | **32.0%**（16/50） |
| 大螺栓 → 红盒（5 条） | **10.0%**（5/50） |
| 长程「两个都放对」（1 条） | **0.0%**（0/10） |
| 对照：同权重域内 LIBERO 4 套件 | 98.4% |

**观察**
1. 不是全 0 也不是瞎抓：19.1% 说明零样本策略已能把螺栓抓起来并放进盒子，最高单任务 70%。
2. **小螺栓（→蓝盒）明显比大螺栓（→红盒）容易**：32% vs 10%。大螺栓总长 103 mm、对边 38 mm，
   对 Franka 二指夹爪的抓取位姿更苛刻；小螺栓（62 mm/22 mm）更接近 LIBERO 原有小物体尺度。
3. 长程任务（两个 `In` 同时成立）为 0%：连单个都还不稳定，属预期。
4. 评测口径与 09-24 基线一致：256×256 双相机、`--action_steps 10`、LIBERO 原生 reward、
   每任务 50 个初始状态取前 10、bf16 权重 + SDPA、8 路并行。唯一差别是**域外零样本**。

> **为什么这个数字有意义**：每个场景里两个螺栓、两个料盒同时在场，目标谓词只接受
> "小螺栓在蓝盒 / 大螺栓在红盒"。任何成功都必须同时选对**物体**和**盒子**，
> 不存在"场上只有一个可抓物体"或"只有一个容器"的取巧路径；
> 5 种布局里两个盒子左右位置互换，进一步排除了纯空间记忆。

## 4. 功能验证

| 验证项 | 方法 | 结果 |
|---|---|---|
| 目标谓词可被触发 | 把目标螺栓瞬移进对应料盒后 `env.check_success()` | **11/11 True**，初始 False |
| 物体真的可见 | 分割渲染统计每物体在 agentview 的像素数 | 蓝盒 1380 / 红盒 6883 / 小螺栓 / 大螺栓 全部非 0 |
| 物理合理 | 40–60 步自由静置 | 落回桌面 0.90 m，无穿模、无飞出 |
| 初始状态 | 每任务 50 个随机合法布局 | 11 × 50 = 550 个 `.pruned_init` |
| benchmark 识别 | `benchmark_dict["libero_bolt"]()` | 11 个任务，语言自动从文件名还原 |

## 5. 对原仓库的改动（全部叠加式，原文件已备份 `*.bak_bolt`）

| 文件 | 改动 |
|---|---|
| `LIBERO .../envs/objects/__init__.py` | +1 行 `from .custom_bolt_objects import *` |
| `.../envs/objects/custom_bolt_objects.py` | 新文件：`BoltSmall/BoltLarge/PartsBinBlue/PartsBinRed` |
| `.../assets/custom_bolt/` | 新目录：OBJ 网格 + 4 个 MJCF XML |
| `.../bddl_files/libero_bolt/` | 新目录：11 个 bddl |
| `.../init_files/libero_bolt/` | 新目录：11 × 50 初始状态 |
| `.../benchmark/libero_suite_task_map.py` | 末尾追加任务清单（不改原有键） |
| `.../benchmark/__init__.py` | 注册 `libero_bolt` + 末尾追加 `LIBERO_BOLT` 类 |
| `GalaxeaVLA .../libero_eval_utils.py` | `get_max_steps` +`"libero_bolt": 300` |

原有 4 套件行为零改动；diff 见附件 `patches/`。

## 6. 复现命令

```bash
V=/home/wei/work/g05/GalaxeaVLA-main/.venv/bin/python
cd /home/wei/work/g05/bolt-sorting
$V gen_assets.py          # 生成螺栓网格 + 4 个物体 XML（含红/蓝料盒）
$V install.py             # 装进 LIBERO（bddl 那一步会提示稍后再跑）
$V create_bolt_tasks.py   # 生成 11 个 bddl
$V install.py             # 再跑一次：注册任务清单 + LIBERO_BOLT benchmark
$V gen_init_states.py     # 每任务 50 个初始状态
$V smoke_test.py          # 期望: goal predicate validated on 11/11 tasks
$V make_previews.py       # 预览图 + 任务对照图
```

评测（必须带 bf16 + SDPA 两个 override，否则 fp32 → 12.3 GB → OOM）：

```bash
cd /home/wei/work/g05/GalaxeaVLA-main
export PATH="$PWD/.venv/bin:$PATH"
bash scripts/run/eval_libero.sh checkpoints/g05-libero/model.pt \
  --suites libero_bolt --num_trials 10 --num_parallel 8 \
  --max_batch_size 8 --max_wait_ms 300 --save_videos \
  --output_dir outputs/libero_bolt_zeroshot \
  model.model_weights_to_bf16=true model.model_arch.attn_implementation=sdpa
```

## 7. 踩坑记录

1. **物体渲染不出来** —— robosuite 离屏渲染只开 `geomgroup[1]`（`render_collision_mesh=False`）。
   所有可见几何必须放 group 1；只放 group 0（碰撞体）的物体在视频里是隐形的。
2. **物体下沉 1–2 cm** —— 碰撞体与视觉网格坐标系不一致：碰撞体位置必须写在最终物体坐标系
   （原点 = 包围盒底面中心），不要叠加网格的 z 平移。
3. **`contain_region` 位点必须带 `quat`** —— `SiteObject.__init__` 会 `string_to_array(site_quat)`，
   缺属性直接 `AttributeError: 'NoneType'`。
4. **bddl 文件名必须以小写字母开头** —— `save_to_file` 会加 `<SCENE_NAME>_` 前缀并大写，
   benchmark 会对大写名走 LIBERO-100 分支解析出错误语言。
5. **任务名（= bddl 文件名）必须唯一** —— 5 种布局需 5 种不同句式。
6. **`In` → `in_box`**：判据是 `位置 ± site_size`，z 下界额外放宽 1 cm；区域名 = `对象名 + "_" + 位点名`。
7. **区域采样器抖动幅度 = `|half_len − horizontal_radius|`**（`ensure_object_boundary_in_range` 收缩区间）。
8. **评测显存**：`serve_policy_batched.py` 没有 `serve_policy.py` 里的 bf16 + `empty_cache` 补丁，
   必须显式传 `model.model_weights_to_bf16=true`；否则 12.3 GB + 8 路并行离屏上下文 → CUDA OOM。

## 8. 附件

- `previews/preview_tasks_grid.png` —— 11 个任务初始状态对照图（agentview）
- `previews/preview_task*.png` —— 每个任务的 agentview + 腕部相机
- `videos/` —— 103 条 rollout 视频（其中 **14 条 success**，文件名带 `_success`）
- `bddl/`、`init_files/` —— 11 个任务定义 + 4 个物体 XML + 550 个初始状态
- `patches/` —— 对 LIBERO / GalaxeaVLA 的改动 diff
- `results/summary.json` —— 评测原始结果
- `scripts/` —— 全部生成/验证脚本 + README

## 9. 下一步（待拍板）

1. **采示教数据**：IK 脚本化专家自动采 100–200 集成功轨迹 → HDF5 数据集。
2. **微调小模型验证可学性**：SmolVLA-0.45B / Diffusion Policy（本机 16 GB 够用，约 1 h/套件），
   预期成功率显著高于 19.1% 零样本。
3. G0.5 2B 全参微调在 16 GB 上不现实（需换机器或作为挑战赛后续）。
4. SO-101 真机部署那条线仍未开工。
