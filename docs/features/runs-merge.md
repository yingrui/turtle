# 把「任务」和「分析运行」合并成一张表

现在有两张表做同一件事：`jobs`（回测、因子计算、筛选）和 `analysis_runs`（评分模型、导出训练集）。
两者都是一次后台执行：有状态、有结果、会失败、会因重启中断。分成两套的代价是：两处看进度、两套线程、
中断收尾写两遍。

界面已经先合并了（`/api/tasks` 读取两张表合成一个列表）。这份文档是**存储层**合并的方案。

## 一、新表

```sql
runs (
  id            varchar(36) primary key,
  kind          varchar(32) not null,   -- simulation | factor_compute | screen | score_table | model | dataset_build
  title         varchar(160),           -- 人看的一行："回测：短窗口验证"、"导出训练集"
  status        varchar(16) not null,   -- pending | running | completed | failed | cancelled
  params        jsonb not null default '{}',
  result        jsonb not null default '{}',
  error         text,
  artifact_key  varchar(512),           -- 产物位置（评分模型的目录、导出描述文件）
  artifact_sha256 varchar(64),
  created_by    varchar(64),
  started_at    timestamptz not null default now(),
  finished_at   timestamptz
);
```

两张旧表都有的字段（id、status、params/payload、result、error、起止时间）能直接对上；差异字段各留一列，
不做多态外键 —— 谁需要谁的明细，用 `kind` 去查各自的业务表（`simulation_runs` 仍然存在，它记录的是**回测结果**，
不是"一次执行"）。

## 二、四步迁移（每步都能停下来）

**第 1 步：建表 + 双写**

- 建 `runs`，加迁移 `021`；
- `JobService.create_job` 与 `analysis_service.run_analysis` 在建旧记录的同时写一条 `runs`；
- 读路径暂不改。**这一步失败可以直接回滚，旧路径不受影响。**

**第 2 步：切读**

- `/api/tasks` 改读 `runs`；
- `/-/reload`、启动中断收尾（`mark_interrupted`）只处理 `runs`；
- 两张旧表仍在写，作为保险。

**第 3 步：回填历史**

- 一次性脚本把 `jobs` + `analysis_runs` 的历史行插入 `runs`（按 `created_at` 去重）；
- 校验：`runs` 行数 = 两张旧表之和，抽查 20 条状态与时间一致。

**第 4 步：删旧路径**

- 调用方只写 `runs`；
- 迁移 `022` 删 `jobs`、`analysis_runs`（或先改名保留一个版本周期）。

## 三、验收标准

| 检查 | 通过条件 |
|---|---|
| 无重复 | 同一次执行在新旧表里只有一条，且 id 相同 |
| 中断收尾 | 重启后 `running` 全部变 `failed`，界面不再显示假进度 |
| 界面一致 | 运行记录页的行数与两张旧表之和相等 |
| 回测可查 | 从运行记录点进回测详情，能跳到 `simulation_runs` 对应的那条 |

## 四、风险

- **回测的明细**（成交、净值、股票池）在 `simulation_runs` 及其子表里，`runs` 只存"这次执行"。迁移时不要把两者混为一谈；
- 有外部调用方在读 `/api/jobs`（openKMS 的 Action 回调也用它），第 4 步之前要保留这个路由做兼容转发。
