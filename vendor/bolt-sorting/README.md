# LIBERO「螺栓分拣」任务（G0.5 仿真复现扩展）

在已复现的 **星海图 G0.5 + LIBERO** 仿真栈上新增一套自定义任务 `libero_bolt`：
桌面上的两个**不同尺寸的六角头螺栓**要被分拣进**对应尺寸的料盒**。

- 复现基线（2026-09-24）：LIBERO 四套件 2000 episodes **98.4%**（官方 98.9%）
- 本扩展：新增 4 个物体 + 11 条任务，**不修改任何原有任务行为**（只做叠加式的注册）

---

## 1. 场景

| 物体 | 类型 | 尺寸 | 外观 | 说明 |
|---|---|---|---|---|
| `bolt_small` | 可动，自由关节 | 总长 62 mm，对边 22 mm，杆径 13 mm | 亮钢色 | 小螺栓 |
| `bolt_large` | 可动，自由关节 | 总长 103 mm，对边 38 mm，杆径 24 mm | 深灰发黑 | 大螺栓 |
| `parts_bin_small` | 可动，自由关节 | 外径 130 mm，壁厚 8 mm，高 45 mm | 蓝色 | 内腔带 `contain_region` 位点 |
| `parts_bin_large` | 可动，自由关节 | 外径 190 mm，壁厚 9 mm，高 65 mm | 橙色 | 内腔带 `contain_region` 位点 |

- 螺栓**平躺**在桌面上（长轴沿 X，六角头的一个平面朝下 → 静置稳定），生成时绕 Z 轴随机偏航。
- 料盒由 5 个 box 组成（底板 + 4 壁）；**碰撞体在 geom group 0，可见体在 group 1**
  —— robosuite 离屏渲染只画 `vgeomgroup[1]`，这是必须遵守的约定（否则物体"隐形"）。
- 螺栓的可见体是程序生成的 OBJ（六棱柱头 + 圆柱杆），碰撞体是 box（头）+ cylinder（杆），
  与可见网格对齐（`gen_assets.py` 里有 bbox 断言）。

## 2. 任务（11 条）

| # | 任务语言 | 目标谓词 |
|---|---|---|
| 0-9 | 5 种布局 × {小螺栓→小盒, 大螺栓→大盒}，各用一种自然语言表述 | `(In bolt_*_1 parts_bin_*_1_contain_region)` |
| 10 | `sort the bolts by size into the matching bins` | 两个 `In` 同时成立（长程） |

每个场景里**两个螺栓和两个料盒同时在场**，所以策略必须按尺寸选对螺栓、放对盒子（不能靠"只有一个可抓物体"取巧）。
5 种布局里料盒的左右位置会互换，避免空间捷径。

`max_steps = 300`（见 `experiments/libero/libero_eval_utils.py`）。

## 3. 文件

```
bolt-sorting/
├── gen_assets.py            # 生成螺栓网格 + 4 个物体的 MJCF XML  -> assets/custom_bolt/
├── libero_bolt_objects.py   # LIBERO 物体类（BoltSmall/BoltLarge/PartsBinSmall/PartsBinLarge）
├── create_bolt_tasks.py     # 场景模板 + 任务注册 -> 生成 11 个 .bddl
├── install.py               # 拷贝资产/模块进 LIBERO 树，并叠加式打补丁（自动备份 *.bak_bolt）
├── gen_init_states.py       # 每个任务采样 50 个初始状态 -> .pruned_init
├── smoke_test.py            # 逐任务验证：位置合理性 + 把螺栓瞬移进盒子后 check_success() 应为 True
├── verify_render2.py        # 分割渲染校验（每个物体的可见像素数）+ 生成任务对照图
└── assets/custom_bolt/      # 生成物（网格 + XML）
```

## 4. 安装 / 复现步骤

```bash
V=/home/wei/work/g05/GalaxeaVLA-main/.venv/bin/python
cd /home/wei/work/g05/bolt-sorting

$V gen_assets.py          # 1. 生成网格 + XML
$V install.py             # 2. 装进 LIBERO（先装物体，bddl 那步会提示稍后再跑）
$V create_bolt_tasks.py   # 3. 生成 11 个 bddl 到 LIBERO/bddl_files/libero_bolt/
$V install.py             # 4. 再跑一次：把任务清单 + LIBERO_BOLT benchmark 注册进去
$V gen_init_states.py     # 5. 每任务 50 个初始状态
$V smoke_test.py          # 6. 验证（应打印 goal predicate validated on 11/11 tasks）
$V verify_render2.py      # 7. 渲染对照图
```

### 对 LIBERO 的改动（全部叠加式，原文件已备份为 `*.bak_bolt`）

| 文件 | 改动 |
|---|---|
| `envs/objects/__init__.py` | +1 行 `from .custom_bolt_objects import *` |
| `envs/objects/custom_bolt_objects.py` | 新文件（4 个物体类） |
| `assets/custom_bolt/` | 新目录（网格 + XML） |
| `bddl_files/libero_bolt/` | 新目录（11 个 bddl） |
| `init_files/libero_bolt/` | 新目录（11 × 50 初始状态） |
| `benchmark/libero_suite_task_map.py` | 末尾追加 `libero_task_map["libero_bolt"] = [...]` |
| `benchmark/__init__.py` | `libero_suites` 加 `"libero_bolt"`；末尾追加 `LIBERO_BOLT` benchmark 类 |
| `GalaxeaVLA-main/experiments/libero/libero_eval_utils.py` | `get_max_steps` 加 `"libero_bolt": 300` |

## 5. 评测

```bash
cd /home/wei/work/g05/GalaxeaVLA-main
bash scripts/run/eval_libero.sh checkpoints/g05-libero \
     --suites libero_bolt --num_trials 10 --save_videos
```

（G0.5 的 LIBERO 权重只在 LIBERO-4 四套件上微调过，本套件是**零样本泛化**测试。）

## 6. 踩坑记录

1. **物体不可见** → robosuite 离屏渲染只开 `geomgroup[1]`，所有可见几何必须在 group 1
   （`robosuite/environments/base.py`：`render_collision_mesh=False`、`render_visual_mesh=True`）。
2. **物体下沉 1-2 cm** → 碰撞体与视觉网格不同坐标系：碰撞体位置要用**最终物体坐标系**
   （原点在包围盒底面中心），不要叠加 z 平移。（已加断言防回归）
3. **`contain_region` 位点必须有 `quat`** → `SiteObject.__init__` 会 `string_to_array(site_quat)`，
   缺 `quat` 属性直接 `AttributeError: 'NoneType'`。
4. **`save_to_file` 会加场景名前缀并大写** → 文件名首字母必须小写，否则 benchmark 的
   `grab_language_from_filename` 走 LIBERO-100 分支解析错误语言。
5. **`In` 谓词 = `in_box`（区域位点盒）+ 接触**：区域名 = `对象名 + "_" + 位点名`，
   `positions ± site_size`（`SiteObject.in_box`），z 下界额外放宽 1 cm。
6. **每条任务的 bddl 文件名必须唯一**（= 任务名）→ 5 个布局用 5 种不同句式，否则任务字典互相覆盖。
7. 区域采样器的 `ensure_object_boundary_in_range` 用 `half_len - horizontal_radius` 收缩采样区间：
   当 `half_len < radius` 时会得到**反向区间**（numpy 仍能均匀采样，但抖动幅度 = |half_len − radius|）。
