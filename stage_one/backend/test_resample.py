# -*- coding: utf-8 -*-
"""
_unit test_ for 季K/半年K/年K 重采样 (data_provider._resample_to_period)
以及前复权 + 重采样的正确顺序。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import numpy as np
from data_provider import TencentProvider, apply_forward_adjustment, validate_klines


def _make_daily(start_year=2020, n_years=3, base=100.0, drift=0.0):
    """生成 n_years 年的日线 (含周末, 仅用于重采样粒度测试, 不追求交易日精确)。"""
    dates = []
    prices = []
    d = pd.Timestamp(f"{start_year}-01-01")
    end = pd.Timestamp(f"{start_year + n_years}-01-01")
    p = base
    while d < end:
        if d.weekday() < 5:  # 仅工作日
            dates.append(d.strftime("%Y-%m-%d"))
            p = max(1.0, p + drift + np.random.randn() * 1.0)
            prices.append(p)
        d += pd.Timedelta(days=1)
    df = pd.DataFrame({
        "date": dates,
        "open": prices,
        "high": [x * 1.02 for x in prices],
        "low": [x * 0.98 for x in prices],
        "close": prices,
        "volume": [1000.0] * len(prices),
    })
    return df


def test_resample_quarterly():
    df = _make_daily(2020, 2, base=100)
    out = TencentProvider._resample_to_period(df, "QS")
    # 2 年 => 8 个季度
    assert len(out) == 8, f"季K应为8根, 实际{len(out)}"
    # 每根季度K的 OHLC 聚合正确
    assert (out["high"] >= out["open"]).all() and (out["low"] <= out["close"]).all()
    # 日期标签为季度起始 (01-01 / 04-01 / 07-01 / 10-01)
    for d in out["date"]:
        assert pd.Timestamp(d).day == 1
    print("✓ test_resample_quarterly")


def test_resample_semiannual():
    df = _make_daily(2020, 2, base=100)
    out = TencentProvider._resample_to_period(df, "2QS")
    assert len(out) == 4, f"半年K应为4根, 实际{len(out)}"
    print("✓ test_resample_semiannual")


def test_resample_yearly():
    df = _make_daily(2020, 3, base=100)
    out = TencentProvider._resample_to_period(df, "YS")
    assert len(out) == 3, f"年K应为3根, 实际{len(out)}"
    # 年K第一根应为 2020-01-01
    assert out["date"].iloc[0] == "2020-01-01"
    print("✓ test_resample_yearly")


def test_forward_adjust_before_resample_continuous():
    """前复权必须在重采样之前: 否则年K会出现拆股缺口。"""
    # 构造含一次 10:1 拆股 (向后) 的日线: 拆前价格 ~1000, 拆后 ~100
    rows = []
    d = pd.Timestamp("2020-01-01")
    price = 1000.0
    for i in range(220):
        if i == 110:
            price = 100.0  # 第110天拆股, 价格下折10倍
        rows.append({
            "date": d.strftime("%Y-%m-%d"),
            "open": price, "high": price * 1.01, "low": price * 0.99,
            "close": price, "volume": 1000.0,
        })
        d += pd.Timedelta(days=1)
    raw = pd.DataFrame(rows)
    # 正确顺序: 先前复权再重采样
    adj = apply_forward_adjustment(raw)
    yearly = TencentProvider._resample_to_period(adj, "YS")
    # 年K相邻应连续 (下一根开盘≈上一根收盘)
    for i in range(1, len(yearly)):
        ratio = yearly["open"].iloc[i] / yearly["close"].iloc[i - 1]
        assert 0.5 < ratio < 2.0, f"年K存在拆股缺口 ratio={ratio}"
    print("✓ test_forward_adjust_before_resample_continuous")


def test_validate_rejects_aggregated_as_daily():
    """validate_klines 必须能识别『被退化成季/年的数据』不是日线。"""
    # 每 90 天一根, 共 40 根 -> 应判为非日线
    dates = [pd.Timestamp("2010-01-01") + pd.Timedelta(days=90 * i) for i in range(40)]
    df = pd.DataFrame({
        "date": [d.strftime("%Y-%m-%d") for d in dates],
        "open": [1.0] * 40, "high": [1.0] * 40, "low": [1.0] * 40,
        "close": [1.0] * 40, "volume": [1.0] * 40,
    })
    assert validate_klines(df, "1d") is False
    # 但作为季K(3M)粒度是合理的
    assert validate_klines(df, "3M") is True
    print("✓ test_validate_rejects_aggregated_as_daily")


if __name__ == "__main__":
    np.random.seed(42)
    test_resample_quarterly()
    test_resample_semiannual()
    test_resample_yearly()
    test_forward_adjust_before_resample_continuous()
    test_validate_rejects_aggregated_as_daily()
    print("\nALL RESAMPLE TESTS PASSED ✅")
