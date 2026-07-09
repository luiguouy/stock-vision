# -*- coding: utf-8 -*-
"""
粒度校验单元测试 (自我验证用)
验证 validate_klines 能正确识别「季度错位数据」与「正常日/周/月线」,
这是修复「每根 K 线跨 3 个月」问题的核心防线。
"""
import pandas as pd
from datetime import date, timedelta
from data_provider import validate_klines


def make_df(dates):
    return pd.DataFrame({
        "date": [d.isoformat() for d in dates],
        "open": [1.0] * len(dates),
        "high": [1.0] * len(dates),
        "low": [1.0] * len(dates),
        "close": [1.0] * len(dates),
        "volume": [1.0] * len(dates),
    })


def quarterly_dates(n=60, start=date(2010, 1, 1)):
    """每 3 个月一根 -> 模拟 Yahoo 代理退化出的季度桩数据"""
    out = []
    d = start
    for _ in range(n):
        out.append(d)
        # 加 3 个月 (近似 90 天)
        month = d.month + 3
        year = d.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        d = date(year, month, 1)
    return out


def daily_dates(n=400, start=date(2023, 1, 2)):
    """跳过周末的连续日线"""
    out = []
    d = start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def weekly_dates(n=200, start=date(2015, 1, 2)):
    """每周五一根"""
    out = []
    d = start
    while len(out) < n:
        if d.weekday() == 4:
            out.append(d)
        d += timedelta(days=1)
    return out


def monthly_dates(n=150, start=date(2010, 1, 31)):
    """每月最后一天一根"""
    out = []
    y, m = start.year, start.month
    for _ in range(n):
        # 取当月最后一天
        if m == 12:
            nxt = date(y + 1, 1, 1)
        else:
            nxt = date(y, m + 1, 1)
        last = nxt - timedelta(days=1)
        out.append(last)
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def semiannual_dates(n=10, start=date(2010, 1, 1)):
    """半年一根 (≈182 天, 模拟真实 6M 重采样)"""
    out = []
    d = start
    for _ in range(n):
        out.append(d)
        d += timedelta(days=182)
    return out


def annual_dates(n=10, start=date(2010, 1, 1)):
    """每年一根 (≈365 天, 模拟真实 1Y 重采样)"""
    out = []
    d = start
    for _ in range(n):
        out.append(d)
        d += timedelta(days=365)
    return out


def check(name, got, expect):
    status = "PASS" if got == expect else "FAIL"
    print(f"[{status}] {name}: got={got} expect={expect}")
    return got == expect


if __name__ == "__main__":
    results = []
    q = make_df(quarterly_dates())
    d = make_df(daily_dates())
    w = make_df(weekly_dates())
    m = make_df(monthly_dates())

    # 季度桩数据: 三个周期都应判定为「粒度不匹配」(拒绝)
    results.append(check("quarterly->1d rejected", validate_klines(q, "1d"), False))
    results.append(check("quarterly->1w rejected", validate_klines(q, "1w"), False))
    results.append(check("quarterly->1M rejected", validate_klines(q, "1M"), False))

    # 聚合周期粒度守卫（半年K/年K 由日线重采样，天然 bar 数少但间隔必须严格）:
    # 季度桩(90天) 冒充 半年K/年K 必须拒绝; 半年(182天) 冒充 年K 必须拒绝。
    sa = make_df(semiannual_dates(n=4))   # 4 根半年线 (≈182 天间隔)
    an = make_df(annual_dates(n=3))       # 3 根年线 (≈365 天间隔)
    results.append(check("semiannual->6M accepted", validate_klines(sa, "6M"), True))
    results.append(check("annual->1Y accepted", validate_klines(an, "1Y"), True))
    results.append(check("quarterly->6M rejected", validate_klines(q, "6M"), False))
    results.append(check("quarterly->1Y rejected", validate_klines(q, "1Y"), False))
    results.append(check("semiannual->1Y rejected", validate_klines(sa, "1Y"), False))
    # 短历史股票(如 SNDK 分拆后仅 ~1.4 年): 半年K 仅 3 根也应通过
    short_sa = make_df(semiannual_dates(n=3))
    results.append(check("short 3bars->6M accepted", validate_klines(short_sa, "6M"), True))

    # 正常数据: 各自周期应判定为「匹配」(通过)
    results.append(check("daily->1d accepted", validate_klines(d, "1d"), True))
    results.append(check("weekly->1w accepted", validate_klines(w, "1w"), True))
    results.append(check("monthly->1M accepted", validate_klines(m, "1M"), True))

    # 交叉校验: 周线数据当作日线 -> 应拒绝
    results.append(check("weekly->1d rejected", validate_klines(w, "1d"), False))

    # 空/过短数据 -> 拒绝
    results.append(check("empty rejected", validate_klines(pd.DataFrame(), "1d"), False))

    print("-" * 40)
    if all(results):
        print("ALL PASS ✅  粒度校验逻辑正确, 季度错位数据会被可靠拦截")
    else:
        print("SOME FAILED ❌")
        raise SystemExit(1)
