# AutoQuant Research

量化版 autoresearch：`train.py` 保存可变策略，`autoquant/` 和 `configs/` 提供固定回测、验证与评分协议。本地 Backtrader 仓库只读。

完整实验操作流程见 [`docs/EXPERIMENT_OPERATION_MANUAL.md`](docs/EXPERIMENT_OPERATION_MANUAL.md)。

## 快速启动

```bash
uv sync --extra dev
export BACKTRADER_ROOT=/Users/mac/PycharmProjects/backtrader
uv run prepare.py
uv run autoquant evaluate --strategy train.py
```

默认示例采用 Backtrader 自带 ORCL 历史 CSV：2010、2011、2012 三个独立开发 fold，2013 最终留出区。示例用于验证软件，不是 ETF 数据、投资建议或经过认证的复权数据。每个 fold 重置资金和策略，预热 252 根，按下一根开盘撮合；评估段之前禁止交易。`train.py` 不直接执行回测，请用 CLI。

## 自主循环

```bash
uv run autoquant experiment --session artifacts/session-demo --iterations 3 --candidates /absolute/candidate_queue
uv run autoquant experiment --session artifacts/session-ai --iterations 10 --generator '/absolute/provider --candidate {candidate} --context {context}'
```

如果任务由控制台创建，可附上 `--task-id <id>`，实验会自动关联到该任务，并把任务状态更新为 `running/completed`。

结构化提示和 Gateway 模式：

```bash
uv run autoquant experiment --session artifacts/session-brief --iterations 2 \
  --brief examples/research_brief.json \
  --generator '/absolute/provider --candidate {candidate} --brief {brief}'
```

Gateway 强制要求 provider 同时接收候选和 brief 路径，记录 `agent_run.json`；候选会先通过 parent diff/复杂度门禁，再进入回测。旧的 `{context}` 生成器模式仍兼容，但只适合可信本地队列或已审计命令。

队列包含按文件名排序的 `.py` 候选。生成器接收候选路径及 context.json，在候选目录工作，只修改其 train.py，并写 hypothesis.json。生成器由用户配置，可连接自己的模型/Agent；框架不内置模型凭证或付费请求。生成命令不经 shell 展开，超时会终止进程组。

仓库带可直接验证循环的离线演示生成器（参数变化，不是 LLM）：

```bash
uv run autoquant experiment --session artifacts/local-demo --iterations 2 --generator '/Users/mac/PycharmProjects/autoresearch/.venv/bin/python /Users/mac/PycharmProjects/autoresearch/examples/local_generator.py --candidate {candidate} --context {context}'
```

生成器的 hypothesis.json 必须包含非空意图说明，例如 `{"hypothesis":"降低调仓频率以减少换手"}`。冠军晋级还要求最差 Sharpe 恶化不超过 0.1、最大回撤恶化不超过 0.02（均为默认工程阈值）。

同一 session 重新运行即续跑；每次指定新增实验次数。基线先评估，然后按固定 score（越高越好）和最小提升 0.03 晋级。失败、超时和 invalid 留痕；冠军保存在 session/champion.py，不覆盖工作区，不自动操作 Git。更换数据、引擎源码或固定框架后必须新建 session。

## 数据与协议

`AUTOQUANT_CACHE_DIR` 默认 `~/.cache/autoquant`。快照首次生成后不覆盖；数据文件校验和、输入文件哈希、清单、切分进入实验 provenance。使用新 dataset ID 发布数据版本。

导入自己的离线行情：每个 symbol 一个 CSV，列为 date,open,high,low,close,volume。基准也必须提供同样格式。

```bash
uv run prepare.py --dataset my_daily_v1 --source /absolute/csvs --splits /absolute/splits.json --benchmark BENCH
uv run autoquant evaluate --dataset my_daily_v1 --strategy train.py
```

splits.json 是数组，例如 `[{"name":"dev1","profile":"dev","start":"2020-01-01","end":"2021-12-31"},{"name":"holdout","profile":"final","start":"2022-01-01","end":"2023-12-31"}]`。日期不得重叠，final 必须在 dev 之后。数据需额外包含预热历史；不同标的必须严格同日历，不自动填充可交易行情。策略 universe 必须使用快照中的代码。

固定费用、滑点、资金、整手、预热、时限、评分与硬门槛在 configs/research.json。默认费用仅为演示，不代表任何市场现行费率。每个 fold 按基础和双倍成本各执行一次；综合中位数 Sharpe/Calmar/信息比率/年化超额，惩罚换手、离散度、最差 fold 和成本敏感度。所有压力场景均须通过最低交易/天数及回撤门槛。

最终测试仅人工运行：`uv run autoquant evaluate --profile final --allow-final`。它不会参与冠军选择。此开关是流程隔离，不是文件权限隔离；同一用户仍可读取本地 holdout，强隔离需要独立账号/容器与数据服务。

启动本地研究控制台：

```bash
uv run autoquant console --host 127.0.0.1 --port 8765
```

浏览器打开 `http://127.0.0.1:8765`，可以查看任务、实验、分数、策略版本、协议、净值和 artifacts，并为成功实验记录 final 审批。控制台当前仅适合本机使用，不包含登录认证，不应暴露到公网。

审批完成后导出发布包：

```bash
uv run autoquant release --experiment-id <id> --artifact-dir /absolute/artifacts/<id> --output releases
```

发布包包含策略、请求、协议、summary、fold 结果、审批记录、paper registration 和新的 artifact manifest；它明确标记为 paper-only，不会启动实盘。

## 产物与约束

每次评估 artifacts/<id>/ 保存策略副本、request、provenance、summary、folds、日志、各 fold 净值 Parquet、订单/交易 JSON；错误含 traceback。results.tsv 是带文件锁的追加索引。session/state.json 是原子更新的恢复点。

当前执行模型是 basic_next_open：长仓、市价单、现金约束、固定费用/滑点、零成交量禁止成交、整手检查；不支持融券、涨跌停队列、T+1、容量冲击、点时成分股/财务数据、真实公司行为。不得将其作为已完成 A 股生产级仿真。基准在策略数据外计算。

AST 检查和禁用 preload 仅减少误用，不是安全沙箱；只能执行可信候选/生成器。策略仍可通过 Python 对象访问内部状态。不可信代码须外置容器断网、只读挂载协议、隔离最终数据。外部命令在用户权限下运行。当前控制台为依赖无关的本机 HTTP 服务，SQLite 只保存 lineage/审批元数据。

这不是自动拟合 ML 模型的框架：当前 walk-forward 是逐段重置的固定策略 OOS 评估。未来可扩展独立 fit 契约；不要把回看预热误称为训练。paper trading、实盘接口、认证/RBAC、SSE/WebSocket 和完整 lineage 图仍未接入。
