import pandas as pd
import pytest

from laboratory.market import ExecutionRules, MarketRuleError, executable_size, quality_report, validate_quality, check_limit


def sample_frame():
    frame = pd.DataFrame({
        "open": [10.0, 10.5], "high": [11.0, 11.0], "low": [9.5, 10.0],
        "close": [10.5, 10.8], "volume": [100, 10], "tradable": [True, False],
        "limit_up": [11.55, 11.88], "limit_down": [9.45, 9.72],
    }, index=pd.to_datetime(["2020-01-01", "2020-01-02"]))
    return frame


def test_quality_report_and_tradability():
    frame = sample_frame()
    report = quality_report(frame)
    validate_quality(report)
    rules = ExecutionRules(lot_size=10, max_participation=0.5).validate()
    assert executable_size(frame, frame.index[0], 80, rules) == 50
    assert executable_size(frame, frame.index[1], 80, rules) == 0


def test_quality_rejects_ohlc_error():
    frame = sample_frame()
    frame.loc[frame.index[0], "high"] = 8
    report = quality_report(frame)
    with pytest.raises(MarketRuleError):
        validate_quality(report)


def test_limit_checks_are_side_aware():
    frame = sample_frame()
    assert check_limit(frame, frame.index[0], 11.0, 1)
    assert not check_limit(frame, frame.index[0], 9.4, -1)
