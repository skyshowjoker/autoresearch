"""Editable candidate: long-only moving-average baseline, next-open execution."""

import backtrader as bt


class Strategy(bt.Strategy):
    params = (("fast", 20), ("slow", 60), ("allocation", 0.90))

    def __init__(self):
        self.fast_line = bt.ind.SMA(self.data.close, period=self.p.fast)
        self.slow_line = bt.ind.SMA(self.data.close, period=self.p.slow)
        self.pending = None

    def next(self):
        if self.pending:
            return
        if not self.position and self.fast_line[0] > self.slow_line[0]:
            self.pending = self.order_target_percent(target=self.p.allocation)
        elif self.position and self.fast_line[0] < self.slow_line[0]:
            self.pending = self.close()

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin, order.Rejected]:
            self.pending = None


def get_strategy_spec():
    return dict(strategy_class=Strategy, params={}, meta=dict(
        name="moving_average_baseline", version=1, universe=["ORCL"], frequency="1d", warmup_bars=252))
