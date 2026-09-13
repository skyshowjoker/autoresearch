# AutoQuant 策略研究验证实验室执行手册

## 1. 使用方式

本文是施工顺序和交付门禁。每个阶段都有明确的输入、产物、测试和停止条件。未经阶段门禁通过，不进入下一阶段；尤其不在控制台完成前引入复杂 Agent 编排，也不在数据协议未冻结前做大规模策略搜索。

### 1.1 工作区边界

主工程：`/Users/mac/PycharmProjects/autoresearch`

回测引擎：`/Users/mac/PycharmProjects/backtrader`

规则：

- 主工程只新增和修改 AutoQuant 代码及文档。
- Backtrader 仓库默认只读。
- Backtrader 当前存在用户未提交改动时，不执行 reset、checkout、clean 或批量格式化。
- 每个阶段开工前记录两个仓库的 `git status`、HEAD 和依赖环境。
- 不在自动实验循环中创建分支、提交、回滚或覆盖用户 `train.py`。

## 2. 目标目录

```text
autoresearch/
├── train.py                         # 当前候选策略入口
├── prepare.py                       # 固定数据准备入口
├── program.md                       # Agent 研究纪律
├── autoquant/
│   ├── cli.py                       # CLI
│   ├── config.py                    # 配置加载与校验
│   ├── contract.py                  # 策略契约/静态检查
│   ├── backtrader_loader.py         # 引擎路径隔离
│   ├── data.py / prepare.py         # 快照读写
│   ├── engine.py                    # 固定执行器
│   ├── metrics.py / scoring.py      # 指标和评分
│   ├── evaluate.py                  # worker、artifact、协议指纹
│   └── experiment.py                # 当前自主实验循环
├── configs/
│   ├── research.json                # 固定研究协议
│   ├── datasets/                    # 数据集描述
│   └── profiles/                    # dev/final/stress profile
├── laboratory/
│   ├── domain/                      # task/strategy/experiment 模型
│   ├── orchestration/               # 状态机、队列、重试、预算
│   ├── agents/                      # brief、生成、优化、审阅
│   ├── storage/                     # SQL、artifact、lineage
│   ├── api/                         # 控制台后端接口
│   └── workers/                     # 隔离 worker 启动器
├── console/
│   ├── web/                         # 控制台前端
│   └── README.md
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── protocol/
│   └── fixtures/
├── artifacts/                       # 忽略的实验产物
└── docs/
```

当前代码可继续运行，`laboratory/` 和 `console/` 在前期不要空壳接入生产 API；先完成域模型和协议测试。

## 3. 阶段计划总览

| 阶段 | 目标 | 主要交付 | 门禁 |
|---|---|---|---|
| P0 | 工作区和协议基线 | snapshot、protocol、依赖记录 | 可重跑基线 |
| P1 | 研究核心稳定化 | domain、状态机、artifact、lineage | 失败不晋级 |
| P2 | 策略生成 | brief、模板、Agent gateway | 生成候选可回测 |
| P3 | 策略优化 | diff、假设、比较和晋级 | parent-child 可追溯 |
| P4 | 数据/执行真实性 | L1/L2 执行模型和质量报告 | 成本/停牌测试通过 |
| P5 | 控制台 | API、前端、实时状态、审批 | 全链路可视化 |
| P6 | 发布验证 | final、paper trading、导出 | 人工批准后发布 |

## 4. P0：工作区与协议基线

### 4.1 步骤

1. 记录 `autoresearch` 和 `backtrader` 的分支、HEAD、dirty 状态。
2. 固定 `BACKTRADER_ROOT` 和 Python 解释器。
3. 检查 `uv sync`、`compileall`、单元测试和基线回测。
4. 复核 `configs/research.json`，确认执行、验证、评分字段完整。
5. 为一个正式数据集发布唯一 dataset ID。
6. 生成 manifest、校验和、切分和数据质量报告。
7. 运行同一基线两次，比较 summary 和 fold 结果。

### 4.2 产物

```text
artifacts/baseline/<experiment_id>/
├── strategy.py
├── request.json
├── provenance.json
├── folds.json
├── summary.json
├── run.log
└── *.parquet / *.json
```

### 4.3 门禁

- 两次基线的 protocol_id、metrics、orders 和 score 相同。
- 数据 manifest 校验成功。
- final profile 不会被 dev 命令调用。
- Backtrader 工作区没有被修改。
- 所有测试通过。

## 5. P1：研究核心稳定化

### 5.1 领域模型

新增不可变 dataclass 或 Pydantic-equivalent schema：

- `ResearchTask`
- `StrategyRecord`
- `StrategyVersion`
- `ExperimentRequest`
- `ExperimentResult`
- `FoldResult`
- `DecisionEvent`
- `ApprovalRequest`

每个 schema 必须具有：

- 明确版本号。
- JSON 可序列化。
- 字段校验。
- 稳定的 ID。
- 从旧 artifacts 读取的兼容策略。

### 5.2 状态机

```text
DRAFT
  → QUEUED
  → GENERATING
  → VALIDATING
  → EVALUATING
  → REVIEW_PENDING
  → PROMOTED / DISCARDED / INVALID / CRASH / TIMEOUT
```

final 审批状态独立于开发实验状态：

```text
DEV_CHAMPION
  → FINAL_REQUESTED
  → FINAL_APPROVED
  → FINAL_RUNNING
  → FINAL_REVIEW
  → PAPER_TRADING / REJECTED
```

状态迁移必须检查前置状态，重复请求必须幂等。

### 5.3 Artifact store

实现：

- 按内容哈希保存策略源文件。
- 运行目录使用 experiment ID。
- JSON 使用临时文件 + 原子 rename。
- Parquet 先写临时路径，再发布。
- 每次结果保存 `artifact_manifest.json`。
- 删除策略只做逻辑归档，不删除审计产物。

### 5.4 Lineage store

第一版可以使用 SQLite，表建议：

```text
research_tasks
strategies
strategy_versions
datasets
protocols
experiments
fold_runs
stress_runs
decision_events
approvals
agent_runs
artifact_refs
```

每个表都保存 created_at、updated_at、schema_version。实验结果文件不直接塞进 SQLite 大字段，只保存引用和摘要。

### 5.5 P1 测试

- 状态迁移合法性。
- 重复请求幂等。
- artifact 原子发布。
- 数据/策略/配置哈希变更会生成新 protocol_id。
- champion 文件篡改会阻止恢复。
- crash/timeout/invalid 不能变成 keep。
- 旧 JSON 可以迁移到当前 schema。

## 6. P2：自然语言生成新策略

### 6.1 Research Brief

定义结构化输入，不直接把长文本传给 worker：

```json
{
  "objective": "降低趋势策略的最大回撤",
  "market": "cn_etf",
  "universe": ["510300", "510500", "159915"],
  "frequency": "1d",
  "allowed_features": ["sma", "ema", "atr", "drawdown"],
  "risk_limits": {"max_drawdown": 0.25, "max_turnover": 8},
  "complexity_budget": {"max_indicators": 5, "max_lines_changed": 120},
  "validation_profile": "dev"
}
```

### 6.2 Agent Gateway

Gateway 负责：

- 选择模型/Agent provider。
- 版本化 system prompt 和 task prompt。
- 提供只读上下文和可写 candidate 目录。
- 限制工具集合。
- 校验结构化输出。
- 保存模型、提示、响应摘要和耗时。

Gateway 不负责评估分数，也不能访问 final 数据。

### 6.3 生成输出

生成器必须输出：

```text
candidate/train.py
hypothesis.json
design.json
dependencies.json
```

`hypothesis.json` 至少包含：

```json
{
  "hypothesis": "使用波动率过滤可减少震荡期的无效交易",
  "expected_effect": "降低最大回撤和换手",
  "failure_condition": "成本翻倍后 score 下降超过门槛",
  "changed_components": ["signal_filter"]
}
```

### 6.4 生成门禁

- 候选只能写入临时目录。
- 静态检查、导入检查、契约检查全部通过。
- 代码 diff 不超过预算。
- 只允许导入白名单库。
- 禁止网络和任意文件访问。
- 必须先 smoke test，再进入完整评估。

## 7. P3：自动优化已有策略

### 7.1 优化动作类型

按风险从低到高：

1. 参数默认值调整。
2. 指标周期或阈值调整。
3. 单个信号条件替换。
4. 仓位和风险预算调整。
5. 退出逻辑调整。
6. 一个新指标或过滤器。
7. 策略结构重写。

先完成 1–5，再开放 6–7。每个任务锁定一种动作类型。

### 7.2 Diff 审核

自动优化前保存 parent source。检查：

- 触碰的文件只有 candidate `train.py`。
- 修改行数和函数数量在预算内。
- 没有修改 `get_strategy_spec()` 的 universe、frequency 或 warmup 以绕过协议。
- 没有修改协议、评分或 worker。
- 假设与改动组件一致。

### 7.3 比较规则

候选和 parent 必须在同一 protocol 下运行。输出 side-by-side：

- score delta。
- median/worst fold delta。
- drawdown delta。
- turnover/cost delta。
- 每个 fold 的胜负。
- 交易差异和持仓差异。

晋级使用固定门槛，不允许 Agent 自定义门槛。

### 7.4 优化停止条件

满足任一条件停止当前任务：

- 达到 max_trials。
- 达到 wall-clock 预算。
- 连续 N 次无改进。
- 连续 N 次 crash/invalid。
- protocol 或数据发生变化。
- 人工暂停/取消。

## 8. P4：数据和执行真实性

### 8.1 数据实施顺序

1. CSV → normalized Parquet。
2. 统一时区和交易日历。
3. 记录上市/停牌/退市。
4. 明确前复权、后复权和原始价格的使用场景。
5. 引入历史成分和点时因子数据。
6. 建立数据质量和可见性测试。

### 8.2 执行模型实施顺序

1. 佣金、最低费用、印花税。
2. 滑点和整手。
3. 停牌不可成交。
4. 涨停买入/跌停卖出限制。
5. T+1 和订单未成交。
6. 成交量容量和冲击成本。
7. 公司行为和历史费率。

每一步都要先写独立测试，再接入完整回测。不要通过修改策略来绕过执行约束。

### 8.3 P4 门禁

- 费用单位、税费方向和最低费用测试通过。
- 涨跌停 fixture 测试通过。
- 停牌/缺失数据 fixture 测试通过。
- T+1 fixture 测试通过。
- 同一数据 snapshot 的重复回测可复现。
- 数据质量报告可以在控制台查看。

## 9. P5：控制台实施

### 9.1 后端

建议优先复用 BackQuant 已存在的 Flask/SQLite 经验，但不要复用其全局 `_results_store` 作为研究状态源。新后端需要：

- 任务 API。
- 实验/策略/版本查询 API。
- artifact 下载 API。
- SSE 或 WebSocket 进度。
- final/promote 审批 API。
- 权限和审计中间件。

### 9.2 前端

先实现只读页面，再实现控制操作：

1. 实验列表和筛选。
2. 实验详情和指标卡。
3. 净值/回撤/交易图。
4. 版本 diff 和 lineage。
5. 任务状态和实时日志。
6. 审批和发布按钮。

图表数据直接读取结构化 artifacts/API，不让前端解析原始 stdout。

### 9.3 控制台门禁

- 运行中的任务刷新后状态不丢失。
- 任务取消后 worker 最终退出。
- final 按钮有明确确认和审计事件。
- 用户不能通过 API 直接改变评分。
- 失败实验仍可打开日志和错误产物。

## 10. P6：发布和纸面交易

### 10.1 发布包

发布包必须包含：

```text
strategy.py
strategy_metadata.json
dataset_manifest.json
protocol.json
backtest_summary.json
fold_results.parquet
stress_results.parquet
trades.parquet
approval.json
```

### 10.2 Paper trading

- 使用与回测相同的信号代码。
- 订单模拟器独立于回测结果。
- 记录信号时间、报价、理论成交和实际可成交条件。
- 至少覆盖一个完整市场阶段。
- paper trading 失败时不能自动进入实盘。

### 10.3 实盘前清单

- 数据源可用性和断线恢复。
- 订单幂等和重复下单保护。
- 风控限额。
- kill switch。
- 资金和持仓对账。
- 日志、告警和审计。
- 人工批准记录。

## 11. 测试矩阵

### 单元测试

- manifest 校验。
- split 不重叠。
- 未来索引检查。
- contract schema。
- commission/slippage/lot/T+1。
- metrics/scoring。
- promotion gate。
- 状态机和幂等。

### 集成测试

- prepare → evaluate → artifact。
- worker 超时和进程组清理。
- candidate 生成 → smoke → full evaluation。
- parent/child lineage。
- 结果写入 SQLite 和文件 store。
- 控制台查询和实时进度。

### 回归测试

- 固定 baseline summary golden file。
- Backtrader 引擎升级前后差异报告。
- 数据快照升级差异报告。
- 旧 artifact schema 迁移。

### 对抗测试

- candidate 试图读其他目录。
- candidate 试图联网。
- candidate 修改配置/协议。
- candidate 注入未来 bar。
- candidate 生成 NaN/Inf/负资产。
- candidate 无限循环和内存膨胀。
- generator 写入额外文件。

## 12. 运行手册

### 12.1 开发环境

```bash
cd /Users/mac/PycharmProjects/autoresearch
export BACKTRADER_ROOT=/Users/mac/PycharmProjects/backtrader
uv sync --extra dev
uv run pytest
uv run prepare.py --dataset <dataset_id>
uv run autoquant evaluate --strategy train.py --dataset <dataset_id>
```

### 12.2 运行一个有界优化批次

```bash
uv run autoquant experiment \
  --session artifacts/session-<date> \
  --iterations 10 \
  --strategy train.py \
  --generator '<trusted-agent-command> --candidate {candidate} --context {context}'
```

所有任务使用有界 `iterations`。需要继续时复用同一个 session；需要切换数据、协议或引擎时新建 session。

### 12.3 final 测试

```bash
uv run autoquant evaluate \
  --strategy artifacts/<champion>/strategy.py \
  --dataset <dataset_id> \
  --profile final \
  --allow-final
```

该命令只能由人工审批流程调用，结果不能喂回自动优化器。

## 13. 迁移和兼容策略

### 13.1 当前原型到实验室核心

- 保留现有 CLI 行为。
- 将现有 `evaluate.py` 拆成 `worker.py`、`artifact_store.py`、`protocol.py`。
- 将 `experiment.py` 的 session 状态迁移到数据库，同时保留 state.json 兼容读取。
- 将 `results.tsv` 保留为导出索引，不再作为唯一数据库。
- 旧 artifacts 自动标记 `legacy=true`。

### 13.2 BackQuant UI 对接

采用单向发布：

```text
AutoQuant Lab → approved strategy package → BackQuant registry/UI
```

不把控制台实验状态写回 BackQuant 的旧全局状态。若复用 `ui/engines/result_extractor.py`，先抽出无 UI 依赖的适配层并写契约测试。

## 14. 交付节奏

### Sprint 1：协议和核心模型

- 完成 P0/P1。
- 交付 schema、状态机、artifact manifest 和 lineage 表。
- 通过 baseline golden tests。

### Sprint 2：生成闭环

- 完成 brief、候选模板、Agent gateway 接口。
- 用离线 deterministic generator 做端到端测试。
- 通过生成候选、失败候选和超时测试。

### Sprint 3：优化闭环

- 完成 parent-child、diff 限制、晋级门槛和预算。
- 通过 10 轮有界优化测试。

### Sprint 4：数据和执行

- 完成目标市场 snapshot、费用和执行 fixture。
- 输出数据质量报告。

### Sprint 5：控制台

- 先只读，再控制，再审批。
- 通过刷新、取消、实时状态和 artifact 访问测试。

### Sprint 6：发布前验证

- final 审批、paper trading 和发布包。
- 完成独立复核和风险清单。

## 15. 评审问题清单

在开始 P1 之前，需要审视并确认：

1. 首期目标市场是中国 ETF、股票，还是先保留多市场抽象？
2. 首期数据源和数据授权是什么？
3. 首期执行模型目标是 L1 还是 L2？
4. 是否允许外部 Agent/模型访问研究提示和代码？
5. 使用本机隔离、Docker，还是独立 worker 主机？
6. 首期控制台沿用 BackQuant 前端，还是独立 React 页面？
7. champion 晋级是否需要人工确认，还是 dev 阶段可自动晋级？
8. final 测试的审批人和审批记录存储在哪里？
9. 研究预算的最大试验次数、运行时和磁盘配额是多少？
10. 何种条件下允许进入 paper trading？

## 16. 完成定义

只有同时满足以下条件，才称为“自动策略研究验证实验室第一版完成”：

- 用户可以从 prompt 创建一个有界研究任务。
- 系统可以生成一个策略候选并在固定协议下回测。
- 系统可以基于 parent 自动提出和评估修改。
- 所有实验有可追溯版本、数据、配置、指标和决策。
- 崩溃、超时、未来函数和协议篡改会被拒绝。
- 控制台可以查询和比较实验，显示实时状态。
- final 测试需要审批并且不会泄漏回开发循环。
- 至少有一个 paper trading 前置门禁。
- 文档明确当前模型的局限，不把回测结果包装成投资结论。

