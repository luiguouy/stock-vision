# -*- coding: utf-8 -*-
"""
智能股票技术分析平台 - 策略过渡层
原有粗糙局部极值聚类旧策略已完全废弃，全面采用 Investment_Assistant 价格行为策略矩阵。
"""

from typing import List, Dict, Any
import pandas as pd
from strategy_adapter import run_strategy_analysis

# 兼容旧测试引用的参数表
PERIOD_PARAMS = {
    '4h': {'half_life': 30, 'window': 5},
    '1d': {'half_life': 60, 'window': 5},
    '1w': {'half_life': 26, 'window': 4},
    '1M': {'half_life': 12, 'window': 3},
    '3M': {'half_life': 8, 'window': 3},
    '6M': {'half_life': 5, 'window': 3},
    '1Y': {'half_life': 4, 'window': 3},
}


def calculate_sr_levels(
    df: pd.DataFrame,
    window: int = 5,
    distance_pct: float = 0.015,
    period: str = "1d",
) -> List[Dict[str, Any]]:
    """
    原有粗糙聚类算法已废弃，重定向至 Investment_Assistant 关键水平位（结构入场/止损/证伪线/箱体边界）。
    """
    if df is None or df.empty:
        return []

    try:
        res = run_strategy_analysis("TEMP", period=period, df=df)
        lines = res.get("annotations", {}).get("lines", [])
        current_price = res.get("current_price", float(df["close"].iloc[-1]) if "close" in df else 0)

        levels = []
        for l in lines:
            price = l.get("price")
            if not price:
                continue
            levels.append({
                "price": round(float(price), 2),
                "count": 3,
                "type": "resistance" if price >= current_price else "support",
                "stars": 5 if "证伪" in l.get("title", "") else 3,
                "level": "Strong" if "证伪" in l.get("title", "") else "Medium",
            })
        return levels
    except Exception as e:
        print(f"[analysis.py] 重定向策略调用异常: {e}")
        return []


def calculate_range_stats(
    df: pd.DataFrame, start_date: str, end_date: str
) -> Dict[str, Any]:
    """
    计算特定日期区间内的连贯最大涨幅与最大回撤（纯数值统计）。
    """
    default_result = {
        "max_rise": {"pct": 0.0, "start": start_date, "end": start_date},
        "max_fall": {"pct": 0.0, "start": start_date, "end": start_date},
    }

    if df is None or df.empty:
        return default_result

    try:
        mask = (df["date"] >= start_date) & (df["date"] <= end_date)
        sub_df = df.loc[mask].reset_index(drop=True)
        if sub_df.empty:
            return default_result

        highs = sub_df["high"].values.astype(float)
        lows = sub_df["low"].values.astype(float)
        dates = sub_df["date"].values

        max_rise_pct = 0.0
        rise_start = dates[0]
        rise_end = dates[0]
        trough_low = lows[0]
        trough_date = dates[0]
        for i in range(len(sub_df)):
            if lows[i] < trough_low:
                trough_low = lows[i]
                trough_date = dates[i]
            if trough_low > 0:
                rally = (highs[i] - trough_low) / trough_low * 100
                if rally > max_rise_pct:
                    max_rise_pct = rally
                    rise_start = trough_date
                    rise_end = dates[i]

        max_fall_pct = 0.0
        fall_start = dates[0]
        fall_end = dates[0]
        peak_high = highs[0]
        peak_date = dates[0]
        for i in range(len(sub_df)):
            if highs[i] > peak_high:
                peak_high = highs[i]
                peak_date = dates[i]
            if peak_high > 0:
                drawdown = (lows[i] - peak_high) / peak_high * 100
                if drawdown < max_fall_pct:
                    max_fall_pct = drawdown
                    fall_start = peak_date
                    fall_end = dates[i]

        return {
            "max_rise": {"pct": round(max_rise_pct, 2), "start": str(rise_start), "end": str(rise_end)},
            "max_fall": {"pct": round(max_fall_pct, 2), "start": str(fall_start), "end": str(fall_end)},
        }
    except Exception as e:
        print(f"Error calculating range stats: {e}")
        return default_result
