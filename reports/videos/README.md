# 演示视频

每条 episode 都是独立子进程执行，逐原语写 `trace.jsonl`；视频为 agentview 俯视视角（每 2 个控制步取一帧，20 Hz）。

| 文件 | 套件 | 任务 | 结果 | 说明 |
|---|---|---|---|---|
| `libero_bolt_v2_t0_s1000_ok.mp4` | v2 | t0 大螺栓→红盒 | 成功 | 主任务典型回合（特权位姿口径） |
| `libero_bolt_v2_t1_s1000_ok.mp4` | v2 | t1 小螺栓→蓝盒 | 成功 | 小件搬运（速度降到 0.010 m/step） |
| `libero_bolt_v2_t5_s1000_ok.mp4` | v2 | t5 大螺栓→红盒 | 成功 | 最短回合（643 步） |
| `libero_bolt_v2_t6_s1000_ok.mp4` | v2 | t6 大螺栓→红盒 | 成功 | 高弧线搬运路线 |
| `libero_bolt_v2_t6_s1006_ok.mp4` | v2 | t6 大螺栓→红盒 | 成功 | **曾是唯一失败 seed**（红盒靠可达域边缘），本轮修复后通过 |
| `libero_bolt_v2_t9_s1003_ok.mp4` | v2 | t9 小螺栓→蓝盒 | 成功 | 抓取—搬运—释放完整过程 |
| `libero_bolt_v2_t10_s1000_ok.mp4` | v2 | t10 两件全分拣 | 成功 | 双件任务：`R.todo()` 两条目标依次完成 |
| `libero_bolt_v2_t2_s1000_vision_ok.mp4` | v2 | t2 大螺栓→红盒 | 成功 | **视觉闭环**（`AGENT_PERCEPTION=vision`，位姿全部来自 RGB-D） |
| `libero_bolt_multi_t3_s1001_ok.mp4` | multi | t3 两件小螺栓→蓝盒 | 成功 | 多件任务：第二件抓取前先回安全位 |
| `libero_bolt_multi_t10_s1000_fail.mp4` | multi | t10 四件全分拣 | **失败** | 长程 4 件：步数预算 3600 耗尽（压力项，如实保留） |
