# 验证记录（仪器校准与合并分布）

日期 2026-11-18，本机 Python 3.11（SQLite + FakeRedis 替代 PostgreSQL/Redis，逻辑路径一致；Docker 环境变量切回真实服务）。运行方式：`cd backend && python3 -m pytest tests/ -v`。

## 结果：22 passed

### 区间失效（要求核对点）
- `test_interval_invalidated_direct`：读数落在唯一条目适用区间外 → 无可用路径，单列排除。
- `test_interval_invalidated_mid_path`：第一步可行但中间换算值落在第二步区间外 → 整条路径不可用；区间内对照样本正常换算。
- `test_interval_boundary_inclusive`：区间端点视为落在区间内（闭区间）。

### 最短路径分歧（要求核对点）
- `test_divergence_over_tolerance_excluded`：两条并列最短路径结果相差 0.05 > 0.01 个百分点 → 排除并留档两条候选路径。
- `test_divergence_within_tolerance_included`：相差恰 0.01（未超过）→ 不排除，按仪器编号序列字典序取首条。
- `test_divergence_only_checked_among_shortest`：更长路径的结果不参与分歧判定。
- `test_tie_break_by_instrument_sequence`、`test_fewest_steps_wins`、`test_no_repeated_instruments`：步数最少优先、字典序并列取舍、含环图不重复经过仪器且搜索终止。

### 发布撞上排队（要求核对点）
- `test_publish_collides_with_queue`：研究排队冻结 v1（截距+1）后发布 v2（截距+10），worker 执行仍按 v1 换算，均值与版本号断言通过。
- `test_rerun_matches_original`：旧研究重跑复用同一冻结快照，checksum、结果与换算/排除明细完全一致，产物卷 JSON 一致。

### 留档与分母
- `test_exclusions_archived_and_denominator_consistent`：无路径与分歧排除同时出现，排除单列留档；`样本量=纳入数=len(换算明细)`，`总样本数=纳入+排除`。
- `test_multi_batch_merge_to_designated_instrument`：三批（含目标仪器批零步路径）合并换算正确。
- `test_too_few_included_fails`：纳入不足3份任务失败并保留错误。

### API 与回归
- `test_full_flow_and_roles`：登录、观察员 403（发布/发起）、分析师发布校准表→发起合并研究→排队冻结→详情查看换算依据→重跑同 checksum；审计含 `calibration.publish`/`merged.queue`/`merged.rerun`。
- `test_merged_run_validation_errors`：未知批次 404、区间倒置 422。
- `test_distribution_run_flow_unchanged`：原有批次分布研究链路（录入→排队→计算→复核）回归通过。

## 其他验证
- `scripts/seed_demo.py` 连跑两次幂等：users 3 / studies 3 / observations 360，校准表 1 版 4 条，不重复插入。
- 种子数据端到端模拟：三批（M1/M2/M3）→M0 合并研究排队后发布 v2，worker 按冻结 v1 执行，360 份纳入、分母一致、逐样本路径留档。
- 前端 22 个 ES module 全部经 `node --check` 与 import 图解析通过；`src/main.js` 导航含「校准合并」，`#merged/{id}` 页展示换算/排除明细。
