# AutoQuant 策略研究验证实验室

## 1. 文档目的

本文定义将 `/Users/mac/PycharmProjects/autoresearch` 演进为一套自动策略研究验证实验室的目标架构、职责边界、数据协议、研究流程、控制台能力和验收标准。

目标能力：

1. 根据自然语言研究提示自动生成可回测策略。
2. 在固定研究协议下自动修改、优化和比较策略。
3. 完整记录实验假设、代码版本、数据版本、参数、回测结果和晋级决策。
4. 提供可视化控制台，管理研究任务、实验轨迹、策略版本、回测结果和人工审批。

本文是方案设计，不授权直接修改 `/Users/mac/PycharmProjects/backtrader`。实施阶段应把该仓库作为受控回测引擎依赖，默认只读；任何对它的修改都必须单独审查、测试并固定版本。

## 2. 现状与资料分级

### 2.1 必须遵守的仓库指令

`/Users/mac/PycharmProjects/backtrader/AGENTS.md` 是该仓库目录范围内的操作和开发约束。它说明了 Backtrader 的核心模块、策略/数据/分析器扩展方式、测试命令以及安装方式。施工时把它视为 instruction，而不是业务需求。

### 2.2 参考资料

- `/Users/mac/PycharmProjects/backtrader/ARCHITECTURE.md`：当前 BackQuant UI、API、Runner、结果抽取、策略注册表、沙箱和 SQLite 的现状分析。
- `/Users/mac/PycharmProjects/backtrader/README_STRATEGY.md`：策略编写和回测使用参考。
- `/Users/mac/PycharmProjects/backtrader/doc/`：Backtrader 项目结构与开发说明。
- `/Users/mac/PycharmProjects/autoresearch/README.md`：当前 AutoQuant 原型的使用说明。
- `/Users/mac/PycharmProjects/autoresearch/ARCHITECTURE.md`：当前固定评估器和自主循环的实现边界。
- `/Users/mac/PycharmProjects/autoresearch/VALIDATION.md`：当前原型的验证记录，不应被误认为生产级量化验证证据。

### 2.3 当前已具备能力

`autoresearch` 当前已经具备：

- `train.py` 策略契约和 `get_strategy_spec()` 入口。
- 离线数据快照、manifest、源文件哈希和 Parquet 数据。
- Backtrader 显式路径加载。
- 独立进程回测和超时清理。
- 开发区间与最终留出区间。
- 基础费用、滑点、预热和下一期开盘撮合。
- 多 fold、双倍成本压力测试和综合评分。
- artifacts、`results.tsv`、session 状态和候选晋级/丢弃。
- 有限 AST 检查及 13 项原型测试。

### 2.4 当前不足

- 没有真正的研究任务模型，只有文件级候选循环。
- 生成器接口可以连接外部 Agent，但缺少提示模板、工具权限、结构化输出和多轮研究状态。
- 当前 `train.py` 只有单一固定策略，没有策略模板、特征注册和策略族概念。
- 还没有明确的“生成新策略”和“优化现有策略”两条工作流。
- 实验记录以 TSV/JSON 为主，没有关系型实验图谱和可查询的 lineage。
- 没有可视化控制台。
- 当前默认数据是 ORCL 示例 CSV，不是经过认证的中国市场数据集。
- 基础执行模型没有完整模拟 T+1、涨跌停、成交量容量、停牌成交限制、公司行为和历史费率。
- AST 检查不是安全沙箱，未提供容器/用户/网络隔离。
- 当前回测是固定策略的 walk-forward 评估，没有独立 `fit()` / `predict()` 学习协议。

## 3. 设计原则

### 3.1 研究和评价分离

研究 Agent 可以提出假设、修改候选和读取开发集反馈，但不能修改数据、撮合、切分、评分和隐藏测试协议。评价器是唯一可信的结果生产者。

### 3.2 可复现优先于吞吐

每次运行必须能通过策略快照、数据快照、引擎版本、配置、依赖和随机种子重放。自动实验数量不能以牺牲审计性为代价。

### 3.3 OOS 优先于单次最优

晋级依据必须来自多个时间段、成本场景和压力测试，而不是单一回测区间的最高收益。

### 3.4 失败也要成为资产

崩溃、超时、数据不足、未来函数、交易数量不足和回撤越界都要形成结构化事件，不能只打印一行错误后丢失。

### 3.5 引擎隔离

AutoQuant 负责研究编排与评价协议；Backtrader 负责回测执行。研究框架不依赖 BackQuant UI 的全局线程状态，也不由实验 Agent 修改回测引擎源码。

### 3.6 人工审批关键状态

自动生成和开发集迭代可以无人值守；进入最终测试、候选发布、纸面交易和实盘前必须人工审批。

## 4. 目标系统架构

```text
┌─────────────────────────────────────────────────────────────┐
│                    Research Console                         │
│  任务 / 策略 / 实验 / 版本 / 曲线 / 交易 / 审批 / 审计       │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST/WebSocket
┌──────────────────────────▼──────────────────────────────────┐
│                   Research Control Plane                    │
│ Task API · Scheduler · Agent Gateway · Approval · RBAC       │
└──────────────┬───────────────────┬───────────────────────────┘
               │                   │
               ▼                   ▼
┌─────────────────────┐  ┌────────────────────────────────────┐
│ Experiment Orchestrator│  │ Artifact / Lineage Store           │
│ generate · optimize  │  │ SQL metadata + Parquet + JSON       │
│ validate · evaluate   │  │ content-addressed snapshots         │
│ promote · stop        │  └────────────────────────────────────┘
└──────────┬──────────┘
           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Isolated Evaluation Plane                 │
│ candidate worker · fixed data · fixed engine · fixed scoring  │
└──────────┬──────────────────────────────────────────────────┘
           ▼
┌─────────────────────────────────────────────────────────────┐
│ /Users/mac/PycharmProjects/backtrader                        │
│ Cerebro · Strategy · Feeds · Broker · Analyzers               │
└─────────────────────────────────────────────────────────────┘
```

### 4.1 控制平面

控制平面管理任务生命周期，不执行策略代码。职责包括：

- 创建研究任务和研究主题。
- 选择数据集、策略基线和验证 profile。
- 调度生成、优化、评估、晋级和停止。
- 保存 Agent 输出和人工审批。
- 将工作分派给隔离的 evaluation worker。
- 向控制台提供实时状态。

### 4.2 评价平面

评价平面在新进程中运行候选策略，使用只读数据和固定配置。职责包括：

- 导入候选并校验策略契约。
- 加载指定 dataset snapshot。
- 创建 Backtrader Cerebro 和固定 broker。
- 运行 walk-forward、压力测试和硬门槛。
- 生成净值、交易、订单、日志、指标和评分。
- 返回不可变实验结果。

### 4.3 存储平面

建议采用“关系元数据 + 文件型时序结果”的混合模式：

- SQLite/PostgreSQL：任务、策略、版本、实验、fold、审批、事件和索引。
- Parquet：行情快照、净值、订单、交易、持仓和逐日指标。
- JSON：manifest、summary、provenance、错误和 Agent 结构化输出。
- 内容寻址目录：策略代码和配置快照。

## 5. 核心领域模型

### 5.1 ResearchTask

表示一次人工发起的研究目标。

```text
task_id
title
prompt
mode: generate | optimize | compare | validate
dataset_id
benchmark_id
base_strategy_version_id
dev_profile
budget: max_trials / max_runtime / max_cost
status
owner
created_at / updated_at
```

### 5.2 Strategy

表示策略逻辑的长期实体。

```text
strategy_id
name
family
description
asset_class
frequency
universe_policy
status: draft | candidate | champion | archived | rejected
```

### 5.3 StrategyVersion

表示一次不可变代码版本。

```text
strategy_version_id
strategy_id
source_sha256
parent_version_id
commit_sha
code_path
contract_version
metadata_json
created_by
created_at
```

策略代码不应通过数据库字段拼接恢复。必须保存完整源文件副本和 SHA-256。

### 5.4 DatasetSnapshot

表示不可变的数据集版本。

```text
dataset_id
manifest_sha256
source_provider
symbols
calendar_id
adjustment_policy
point_in_time_policy
start_date / end_date
created_at
```

### 5.5 Experiment

表示一个候选在一个固定协议下的一次完整运行。

```text
experiment_id
task_id
strategy_version_id
parent_experiment_id
protocol_id
status: queued | running | success | invalid | crash | timeout | cancelled
score
decision: baseline | keep | discard | rejected | pending_review
artifact_uri
started_at / finished_at
```

### 5.6 FoldRun / StressRun

保存每个时间段和成本压力场景的独立结果。不可只保留聚合分数。

### 5.7 DecisionEvent

记录为何晋级或拒绝：

```text
decision_id
experiment_id
decision
hypothesis
evidence_json
thresholds_json
actor: system | agent | human
created_at
```

## 6. 策略契约

### 6.1 `train.py` 唯一可变入口

策略文件继续保留在 `train.py`，但契约应扩展为：

```python
import backtrader as bt


STRATEGY_META = {
    "name": "example_strategy",
    "version": 1,
    "family": "trend_following",
    "universe": ["510300", "510500"],
    "frequency": "1d",
    "warmup_bars": 252,
    "execution_assumption": "next_open",
}


class Strategy(bt.Strategy):
    params = (("lookback", 60),)

    def __init__(self):
        ...

    def next(self):
        ...


def get_strategy_spec():
    return {
        "strategy_class": Strategy,
        "params": {},
        "meta": STRATEGY_META,
    }
```

### 6.2 策略可以做什么

- 构建指标和信号。
- 选择资产和排序。
- 设定目标仓位。
- 处理策略内部止盈、止损和退出。
- 在固定数据范围内读取当前及历史 bars。
- 使用固定的 Backtrader 订单接口。

### 6.3 策略不可以做什么

- 下载数据或访问网络。
- 修改数据集、配置、评分器、引擎或 artifacts。
- 读取隐藏测试区或其他候选的结果。
- 设置 broker、费用、滑点、初始资金或评估区间。
- 访问操作系统、子进程、环境机密或任意文件。
- 使用未来 bar、未来财务数据或未来成分股。
- 通过异常、退出、日志伪造结果。

AST 检查只是第一道门。可信执行需要只读挂载、无网络、低权限用户、CPU/内存/时间限制和独立容器或沙箱。

## 7. 数据治理方案

### 7.1 数据层次

```text
Raw Provider Data
        ↓ immutable ingestion
Normalized Market Data
        ↓ point-in-time validation
Dataset Snapshot
        ↓ fixed manifest
Evaluation Worker
```

### 7.2 数据快照要求

每个快照必须包含：

- OHLCV 和时间戳规范。
- 交易日历。
- 标的上市、退市、停牌和可交易状态。
- 复权/不复权政策。
- 公司行为处理方式。
- 历史标的池或 point-in-time 成分。
- 基准数据。
- 数据源、拉取时间、版本和校验和。
- 缺失、异常和重复行统计。

### 7.3 中国市场数据优先级

若目标是中国 ETF/股票，应按以下顺序施工：

1. 先实现离线 Parquet snapshot。
2. 选择一个明确的数据提供方并固定接口版本。
3. 明确 ETF 与股票的复权和费用差异。
4. 补齐上市日、停牌、涨跌停和成交量字段。
5. 对成分股策略引入点时成分快照。
6. 对财务因子引入公告发布时间和可见日期。

没有 point-in-time 数据时，不应宣称“无幸存者偏差”或“无前视偏差”。

## 8. 回测执行协议

### 8.1 默认协议

- 日线信号使用当日收盘信息。
- 订单在下一交易日开盘撮合。
- 只支持显式允许的订单类型。
- 默认禁用融券和负现金。
- 预热区只用于指标，不计入绩效。
- 每个 fold 重置资金、策略状态和 broker 状态。
- 回测结束不强制平仓，必须在结果中标记。
- 所有订单和成交都进入审计流。

### 8.2 真实执行模型分级

| 级别 | 能力 | 用途 |
|---|---|---|
| L0 | 收盘信号、下一开盘、市价、比例费用 | 软件闭环和单元测试 |
| L1 | 佣金、印花税、最低费用、滑点、整手、停牌 | 研究开发 |
| L2 | 涨跌停、成交量容量、T+1、订单未成交状态 | 可信历史回测 |
| L3 | 公司行为、点时成分、历史费率和执行冲击 | 高可信研究 |
| L4 | 纸面交易、实时行情、订单回报和独立实盘校验 | 发布前验证 |

自动晋级只能在配置要求的最低等级达到后启用。当前原型约为 L0/L1 之间。

## 9. 两类自动研究工作流

### 9.1 工作流 A：根据提示生成新策略

输入：

- 自然语言研究目标。
- 资产类别和标的池。
- 频率和数据集。
- 风险限制。
- 可用指标/特征白名单。
- 复杂度预算。

输出：

- 一个策略设计说明。
- 一份 `train.py` 候选。
- 一份 `hypothesis.json`。
- 参数和数据依赖说明。
- 静态检查报告。

流程：

```text
Prompt
  → Research Brief
  → Strategy Design
  → Code Candidate
  → Contract Check
  → Smoke Backtest
  → Walk-forward Evaluation
  → Human/System Decision
```

生成阶段不读取历史最佳结果之外的隐藏信息；若生成器使用外部模型，必须记录模型标识、提示版本和响应摘要。

### 9.2 工作流 B：自动优化已有策略

优化不是无限参数搜索。每个优化任务必须声明一个主假设，例如：

- 降低换手是否能改善成本后收益。
- 趋势过滤是否能降低回撤。
- 风险预算是否能改善最差 fold。
- 简化一个指标是否保持性能。

优化流程：

1. 读取 champion 版本和最近实验轨迹。
2. 生成一个最小修改候选。
3. 检查 diff 范围和修改文件白名单。
4. 运行 smoke test。
5. 运行固定开发 folds 和压力场景。
6. 与 champion 做统计和风险比较。
7. 满足晋级门槛后保存为新版本，否则丢弃。

每轮只允许一个主要假设，防止无法解释的多变量变更。

## 10. 验证、评分和晋级

### 10.1 时间切分

建议使用 anchored walk-forward：

```text
开发 folds：
2015–2018 → 2019
2015–2019 → 2020
2015–2020 → 2021
2015–2021 → 2022
2015–2022 → 2023

最终留出：
2024–2025
```

具体年份必须由数据集 manifest 决定，不能写死在策略文件中。

### 10.2 必须报告的指标

- 总收益、CAGR、年化波动率。
- Sharpe、Sortino、Calmar。
- 最大回撤、回撤持续时间。
- 相对基准收益、Beta、Alpha、信息比率。
- 交易次数、胜率、盈亏比、平均持仓时间。
- 换手、成本占毛收益比例、成交金额。
- 月度/年度分布和最差期间。
- 资产暴露、集中度和空仓时间。
- 基础成本、双倍成本和三倍成本结果。

### 10.3 晋级规则

候选必须同时满足：

- 所有要求 fold 完成。
- 无 NaN、Inf、负资产或异常订单。
- 最低交易数量和最低有效天数通过。
- 最大回撤不超过门槛。
- 双倍成本场景仍通过基本稳定性门槛。
- 分数相对 champion 提升超过最小改进值。
- 最差 fold 和最大回撤没有超过允许恶化幅度。
- 复杂度和换手没有无理由膨胀。

建议评分：

```text
fold_score =
    0.35 * clipped_sharpe
  + 0.25 * clipped_calmar
  + 0.20 * clipped_information_ratio
  + 0.20 * clipped_annual_excess_return
  - turnover_penalty

robust_score =
    median(fold_score)
  - 0.50 * std(fold_score)
  - 0.25 * worst_fold_gap
  - cost_sensitivity_penalty
```

分数只是排序工具，不是统计显著性证明。长期任务要记录试验次数和选择偏差。

### 10.4 最终测试规则

- 自动研究循环不能调用 final profile。
- final 运行需要人工审批或一次性 token。
- final 结果不能回写为开发集反馈。
- final 之后进入 paper trading，而不是直接实盘。
- 如果 final 失败，必须新建研究任务或回到开发集，不能偷偷修改结果。

## 11. 版本管理与实验轨迹

### 11.1 Git 角色

- Git 管理人类审阅的策略版本和框架代码。
- 每次候选保存 `source_sha256` 和可选 `commit_sha`。
- 自动循环不执行 `git reset --hard`，不覆盖用户工作区。
- champion 作为不可变 artifacts 复制保存。
- 进入发布候选前由人工创建正式 Git commit/tag。

### 11.2 实验 lineage

```text
ResearchTask
  └── Baseline Experiment
        ├── Candidate A
        │     ├── Fold Runs
        │     ├── Stress Runs
        │     └── Decision: discard
        └── Candidate B
              ├── Fold Runs
              ├── Stress Runs
              └── Decision: keep → Champion Version
```

必须能回答：

- 这个 champion 从哪个版本演化而来？
- 它尝试过哪些失败假设？
- 哪些数据、配置和引擎版本生成了它？
- 它是否看过 final？
- 晋级时的分数、最差 fold 和成本敏感度是多少？
- 研究 Agent 和人工分别做了什么？

## 12. 可视化管理控制台

### 12.1 页面

1. **总览**：运行中任务、冠军策略、最近实验、资源和异常。
2. **研究任务**：自然语言目标、预算、数据集、当前阶段、暂停/恢复/取消。
3. **策略库**：策略族、版本树、参数、代码 diff、标签和审批状态。
4. **实验轨迹**：按时间、分数、假设、父子关系、keep/discard/crash 过滤。
5. **回测详情**：净值、基准、超额、回撤、滚动 Sharpe、月度热力图。
6. **交易审计**：订单、成交、滑点、佣金、持仓和信号。
7. **数据集**：manifest、覆盖、缺失、数据版本和校验结果。
8. **审批中心**：final 测试、冠军发布、纸面交易和导出。
9. **系统设置**：引擎路径、 worker 并发、资源预算和权限。

### 12.2 关键交互

- 从任务页面查看 Agent 当前假设和下一步。
- 一键比较两个实验的 fold、成本和交易差异。
- 选择一个历史版本作为新优化基线。
- 暂停队列而不杀死正在运行的 worker。
- 对 final 运行执行显式审批。
- 导出可审计的实验包，而不是只导出一张收益图。

### 12.3 API 最小集合

```text
POST   /api/research/tasks
GET    /api/research/tasks
GET    /api/research/tasks/{id}
POST   /api/research/tasks/{id}/pause
POST   /api/research/tasks/{id}/resume
POST   /api/research/tasks/{id}/cancel

GET    /api/strategies
GET    /api/strategies/{id}/versions
GET    /api/strategies/versions/{version_id}

GET    /api/experiments
GET    /api/experiments/{id}
GET    /api/experiments/{id}/equity
GET    /api/experiments/{id}/trades
GET    /api/experiments/{id}/artifacts

POST   /api/experiments/{id}/approve-final
POST   /api/experiments/{id}/promote
```

API 不直接接受任意策略源码执行。上传、解析、运行必须经过策略契约和 worker 队列。

## 13. 安全与资源控制

自动生成代码视为不可信代码，即使来自已登录 Agent：

- 容器或独立低权限用户运行。
- 根文件系统只读，candidate 目录单独可写。
- 无网络或仅允许经过审计的数据服务。
- 禁止读取 SSH key、环境密钥和其他任务目录。
- CPU、内存、进程数和 wall-clock 超时限制。
- worker 完成后销毁。
- 限制日志和 artifacts 大小。
- 记录所有工具调用和文件 diff。
- UI、API、worker 使用不同身份和最小权限。

如果暂时只能使用本机子进程，必须在 UI 中明确标记为“可信代码模式”，不能称为安全沙箱。

## 14. 资源调度

每个任务需要预算：

```text
max_trials
max_runtime_seconds
max_parallel_workers
max_artifact_bytes
max_agent_turns
```

默认采用有界批次，不使用不可控的“永远运行”。队列应支持优先级、取消、重试上限和幂等键。相同策略版本、数据集和协议的重复实验应命中缓存或明确标记 duplicate。

## 15. 可观测性

每次运行至少记录：

- queue time、startup time、evaluation time。
- worker exit code、资源使用、超时原因。
- fold 进度和当前阶段。
- 日志、异常堆栈和数据加载警告。
- Agent 的提示版本、模型标识和输出摘要。
- 任务、实验、候选、父版本和 protocol_id。

控制台需要区分：

- 回测失败。
- 代码契约失败。
- 数据不可用。
- 资源超限。
- 评分无效。
- 正常丢弃。

## 16. 分阶段路线图

### Phase 0：协议冻结

- 冻结策略契约。
- 冻结 dataset manifest 格式。
- 冻结 execution/scoring/validation 配置。
- 确认 Backtrader 依赖方式和版本记录。

### Phase 1：研究核心

- 将当前 `autoquant` 模块整理为稳定 package。
- 增加策略版本、实验、fold 和 decision 元数据。
- 增加 hash-based artifact store。
- 增加真实的实验状态机和幂等重试。

### Phase 2：生成与优化

- 定义 Research Brief。
- 实现生成策略模板。
- 实现优化提示模板和 diff 限制。
- 接入外部 Agent Gateway。
- 支持人工确认后启动任务。

### Phase 3：数据和执行真实性

- 建立目标市场离线快照。
- 补齐停牌、涨跌停、T+1、容量和公司行为。
- 加入数据质量报告和 point-in-time 检查。

### Phase 4：控制台

- API 和数据库。
- 任务/实验/策略/数据页面。
- 曲线和交易可视化。
- WebSocket/SSE 实时进度。
- 审批与导出。

### Phase 5：发布链路

- final 测试审批。
- paper trading。
- 独立回放验证。
- 策略包导出。
- 实盘接入前风险委员会或人工审核。

## 17. 验收标准

### 功能验收

- 能通过 prompt 创建策略研究任务。
- 能生成至少一个符合契约的 `train.py`。
- 能自动优化已有策略并保留父子版本关系。
- 能暂停、恢复、取消和重试任务。
- 能查看每次实验的代码、假设、数据、配置、指标和决策。
- 能在控制台比较两个实验。
- 能显式审批 final 测试。

### 正确性验收

- 相同 protocol、策略和数据可复现相同结果。
- 未来函数测试能拒绝正向 bar 索引和数据越界。
- 预热交易被拒绝。
- 费用和最小佣金单位测试通过。
- 数据篡改会触发 checksum 失败。
- timeout/crash 不会晋级候选。
- final 结果不会进入自动评分队列。
- worker 不会修改 Backtrader 仓库和用户工作区。

### 研究质量验收

- 至少多个时间 fold 和两个成本场景。
- 有基准、有最差 fold、有回撤和换手门槛。
- 保留所有失败和丢弃实验。
- 能统计试验次数和研究选择偏差。
- 最终发布前有 paper trading 阶段。

## 18. 不在本阶段承诺的事项

- 不承诺自动发现可交易 alpha。
- 不承诺回测收益可以复制到实盘。
- 不承诺当前示例数据适用于中国市场。
- 不承诺 AST 检查提供安全隔离。
- 不承诺直接支持所有聚宽策略语义。
- 不承诺自动化 final 结果统计显著。
- 不承诺第一阶段支持分布式 GPU/云调度。

