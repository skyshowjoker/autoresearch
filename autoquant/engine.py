from __future__ import annotations

import pandas as pd

from .backtrader_loader import load_backtrader
from .metrics import calculate
from laboratory.market import ExecutionRules, MarketRuleError, check_limit, tradable_on


def commission_info(bt, config, multiplier):
    class Costs(bt.CommInfoBase):
        params = (("stocklike", True), ("commtype", bt.CommInfoBase.COMM_PERC), ("percabs", True))

        def _getcommission(self, size, price, pseudoexec):
            if not size:
                return 0.0
            value = abs(size) * price
            fee = max(value * config["commission"], config["minimum_commission"])
            return multiplier * (fee + (value * config["sell_tax"] if size < 0 else 0))

    return Costs()


def run_fold(spec, snapshot, fold, config, multiplier=1):
    bt = load_backtrader()
    execution = config["execution"]
    rules = ExecutionRules(lot_size=int(execution["lot_size"]), max_participation=float(execution["max_participation"]),
                           enforce_tradable=bool(execution["enforce_tradable"]), enforce_limits=bool(execution["enforce_limits"]),
                           enforce_t1=bool(execution["enforce_t1"])).validate()
    start, end = pd.Timestamp(fold["start"]), pd.Timestamp(fold["end"])
    universe = spec.meta["universe"]
    if spec.meta["frequency"] != "1d" or spec.meta["warmup_bars"] > execution["warmup_bars"]:
        raise ValueError("unsupported frequency or warmup exceeds fixed budget")
    frames = {}
    for symbol in set(universe + [snapshot.manifest["benchmark"]]):
        frame = snapshot.load(symbol)
        history = frame.loc[frame.index < start].tail(execution["warmup_bars"])
        sample = frame.loc[start:end]
        if len(history) < execution["warmup_bars"] or sample.empty:
            raise ValueError(f"insufficient warmup or evaluation data: {symbol}")
        frames[symbol] = pd.concat([history, sample])
    calendar = frames[snapshot.manifest["benchmark"]].index
    if any(not frame.index.equals(calendar) for frame in frames.values()):
        raise ValueError("unaligned calendars: snapshot must be aligned without synthetic tradable bars")
    orders, trades, nav = [], [], []
    held_since = {}

    class Broker(bt.brokers.BackBroker):
        def submit(self, order, check=True):
            timestamp = pd.Timestamp(order.data.datetime.datetime(0))
            if timestamp < start:
                raise ValueError("strategy attempted trading during warmup")
            if order.exectype != bt.Order.Market:
                raise ValueError("basic execution supports market orders only")
            symbol = order.data._name
            timestamp = timestamp.normalize()
            frame = frames[symbol]
            if rules.enforce_tradable and not tradable_on(frame, timestamp):
                raise ValueError(f"{symbol} is not tradable on {timestamp.date()}")
            if rules.enforce_limits and not check_limit(frame, timestamp, float(order.data.open[0]), 1 if order.isbuy() else -1):
                raise ValueError(f"{symbol} market order blocked by limit on {timestamp.date()}")
            if rules.enforce_t1 and order.issell() and held_since.get(symbol) == timestamp:
                raise ValueError(f"{symbol} cannot be sold on its acquisition date (T+1)")
            if abs(order.size) % execution["lot_size"]:
                raise ValueError("order violates fixed lot size")
            if order.issell() and abs(order.size) > self.getposition(order.data).size:
                raise ValueError("short selling is disabled")
            return super().submit(order, check=check)

    class Audit(bt.Analyzer):
        def next(self):
            timestamp = pd.Timestamp(self.strategy.datetime.datetime(0))
            if timestamp >= start:
                nav.append(dict(date=timestamp, equity=self.strategy.broker.getvalue(), cash=self.strategy.broker.getcash()))

        def notify_order(self, order):
            if order.status == order.Completed:
                symbol = order.data._name
                timestamp = pd.Timestamp(order.executed.dt and bt.num2date(order.executed.dt) or order.data.datetime.datetime(0)).normalize()
                if order.isbuy():
                    held_since[symbol] = timestamp
                elif order.issell() and self.strategy.broker.getposition(order.data).size <= 0:
                    held_since.pop(symbol, None)
            orders.append(dict(date=str(self.strategy.datetime.date(0)), symbol=order.data._name,
                               status=order.getstatusname(), size=order.size,
                               executed_size=order.executed.size, price=order.executed.price,
                               commission=order.executed.comm))

        def notify_trade(self, trade):
            if trade.isclosed:
                trades.append(dict(symbol=trade.data._name, pnl=trade.pnl, pnl_net=trade.pnlcomm,
                                   bars=trade.barlen, closed=str(self.strategy.datetime.date(0))))

    class EvaluatedStrategy(spec.strategy_class):
        def prenext(self):
            if pd.Timestamp(self.datetime.datetime(0)) >= start:
                super().prenext()

        def nextstart(self):
            if pd.Timestamp(self.datetime.datetime(0)) >= start:
                super().nextstart()

        def next(self):
            if pd.Timestamp(self.datetime.datetime(0)) >= start:
                super().next()

    cerebro = bt.Cerebro(stdstats=False, cheat_on_open=False)
    broker = Broker(cash=execution["initial_cash"], coc=False, coo=False)
    broker.addcommissioninfo(commission_info(bt, execution, multiplier))
    broker.set_slippage_perc(execution["slippage"] * multiplier, slip_open=True)
    def filler(order, price, ago):
        volume = float(order.data.volume[ago])
        if volume <= 0:
            return 0
        size = min(abs(order.executed.remsize), volume * rules.max_participation)
        return int(size // rules.lot_size * rules.lot_size)

    broker.set_filler(filler)
    cerebro.setbroker(broker)
    for symbol in universe:
        cerebro.adddata(bt.feeds.PandasData(dataname=frames[symbol]), name=symbol)
    cerebro.addstrategy(EvaluatedStrategy, **spec.params)
    cerebro.addanalyzer(Audit, _name="audit")
    cerebro.run(runonce=False, preload=False)
    equity_frame = pd.DataFrame(nav).set_index("date")
    previous = calendar[calendar < start][-1]
    equity = pd.concat([pd.Series([execution["initial_cash"]], index=[previous]), equity_frame.equity])
    benchmark = frames[snapshot.manifest["benchmark"]].close
    metrics = calculate(equity, benchmark)
    fills = [order for order in orders if order["status"] == "Completed"]
    metrics.update(fills=len(fills), turnover=sum(abs(order["executed_size"]) * order["price"] for order in fills) / equity.mean(),
                   costs=sum(order["commission"] for order in fills))
    return dict(fold=fold["name"], cost_multiplier=multiplier, metrics=metrics), equity_frame, orders, trades
