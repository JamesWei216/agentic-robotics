# 人机确认面板截图

面板：`python -m agent.confirm_server --port 8078` → 浏览器打开 `http://localhost:8078/`。
截图来自一次 `--confirm-mode manual` 的真实运行（t5，1 seed，面板共批准 12 次，episode 通过）。

| 文件 | 场景 | 关键信息 |
|---|---|---|
| `confirm_panel_1_pending.png` | **待确认**（`first_motion`：解除使能 / 首次运动） | 顶部红色急停区 + 卡片显示门控动作与 details、批准/拒绝按钮、请求号与已等待秒数 |
| `confirm_panel_2_idle.png` | **空闲**（无待确认） | 只有急停区与"等待中"提示：门控是阻塞式的，放行后条目自动消失 |
| `confirm_panel_3_estop_engaged.png` | **急停按下** | 徽标由"正常"变为急停态；`runtime/ESTOP` 存在时所有原语每步检查并中止 |
| `confirm_panel_4_grasp.png` | **待确认**（`grasp_close`：夹爪闭合） | 与 1 同结构，details 里是具体工件名（如 `bolt_small_1`） |

生成方式：`scripts/capture_confirm_panel.py` —— 面板是纯 HTML+CSS，用 weasyprint 渲成 PDF 再转 PNG。
（本机 `firefox --headless` 在 SWGL 上取不到 framebuffer，截不出图，原因见脚本注释。）

审计：每次批准/拒绝都写入 `runtime/audit.jsonl`（`{"event":"confirm","decision":"approved",...}`），
可与本目录截图一一对应、交叉核对。
