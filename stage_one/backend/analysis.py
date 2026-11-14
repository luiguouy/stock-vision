# -*- coding: utf-8 -*-
"""
智能股票技术分析平台 - 独立量化算术引擎
零项目内依赖，提供多周期支撑阻力聚类、区间波动率、最大回撤与胜率计算。
"""

from typing import List, Dict, Any
import numpy as np
import pandas as pd

PERIOD_PARAMS = {
    "5m": {"half_life": 30, "window": 5},
    "15m": {"half_life": 30, "window": 5},
    "1h": {"half_life": 30, "window": 5},
    "4h": {"half_life": 30, "window": 5},
    "1d": {"half_life": 60, "window": 5},
    "1w": {"half_life": 26, "window": 4},
    "1M": {"half_life": 12, "window": 3},
    "3M": {"half_life": 8, "window": 3},
    "6M": {"half_life": 5, "window": 3},
    "1Y": {"half_life": 4, "window": 3},
}


def _extract_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """标准化 OHLC 列名为小写。"""
    work_df = df.copy()
    for target_c, alt_c in [("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close")]:
        if target_c not in work_df.columns and alt_c in work_df.columns:
            work_df[target_c] = work_df[alt_c]
    return work_df


def calculate_sr_levels(
    df: pd.DataFrame,
    window: int = 5,
    distance_pct: float = 0.015,
    period: str = "1d",
) -> List[Dict[str, Any]]:
    """
    自适应支撑/阻力位聚类（与前端 mockEngine.calculateSRLevels 算法及输出结构完全一致）：
    基于近 20 根 ATR 估算合并阈值 + 指数半衰期时间衰减 + 现价临近度综合打分。
    """
    if df is None or df.empty:
        return []

    try:
        work_df = _extract_ohlc(df)
        highs = work_df["high"].values.astype(float)
        lows = work_df["low"].values.astype(float)
        closes = work_df["close"].values.astype(float)
        total_len = len(work_df)

        params = PERIOD_PARAMS.get(period, PERIOD_PARAMS["1d"])
        half_life = params["half_life"]
        win = params["window"] if (window == 5 and period != "1d") else window

        if total_len < win * 2 + 1:
            return []

        latest_price = float(closes[-1])
        if latest_price <= 0:
            return []

        # 1. 自适应合并阈值（近 20 根均波幅，钳制在 [0.6%, 2.5%] 之间）
        lookback = min(20, total_len)
        atr_approx = float(np.mean(highs[-lookback:] - lows[-lookback:]))
        abs_threshold = max(latest_price * 0.006, min(atr_approx * 0.8, latest_price * 0.025))

        # 2. 局部极值提取
        extrema: List[Dict[str, float]] = []
        for i in range(win, total_len - win):
            local_high = float(np.max(highs[i - win : i + win + 1]))
            local_low = float(np.min(lows[i - win : i + win + 1]))
            if highs[i] >= local_high:
                extrema.append({"price": float(highs[i]), "idx": i})
            if lows[i] <= local_low:
                extrema.append({"price": float(lows[i]), "idx": i})

        if not extrema:
            return []

        extrema.sort(key=lambda x: x["price"])

        # 3. 价格簇合并与时间衰减权重累加
        clusters: List[Dict[str, Any]] = []
        for ext in extrema:
            bars_ago = total_len - 1 - int(ext["idx"])
            weight = 0.5 ** (bars_ago / half_life)
            placed = False
            for c in clusters:
                if abs(c["price"] - ext["price"]) < abs_threshold:
                    total_w = c["weight"] + weight
                    c["price"] = (c["price"] * c["weight"] + ext["price"] * weight) / total_w
                    c["weight"] = total_w
                    c["count"] += 1
                    placed = True
                    break
            if not placed:
                clusters.append({"price": ext["price"], "weight": weight, "count": 1})

        # 4. 划分支撑/阻力并按临近度综合打分
        support_candidates: List[Dict[str, Any]] = []
        resistance_candidates: List[Dict[str, Any]] = []

        for c in clusters:
            lvl_price = float(c["price"])
            dist_pct = abs(lvl_price - latest_price) / latest_price
            score = c["weight"] * (1.0 / (1.0 + 8.0 * dist_pct))

            if c["weight"] >= 3.5:
                stars, rank = 5, "Strong"
            elif c["weight"] >= 2.0:
                stars, rank = 3, "Medium"
            else:
                stars, rank = 2, "Weak"

            item = {
                "price": round(lvl_price, 2),
                "count": int(c["count"]),
                "stars": stars,
                "level": rank,
                "_score": score,
            }
            if lvl_price < latest_price:
                support_candidates.append({**item, "type": "support"})
            elif lvl_price > latest_price:
                resistance_candidates.append({**item, "type": "resistance"})

        support_candidates.sort(key=lambda x: x["_score"], reverse=True)
        resistance_candidates.sort(key=lambda x: x["_score"], reverse=True)

        result = resistance_candidates[:3] + support_candidates[:3]
        for r in result:
            r.pop("_score", None)
        return result
    except Exception as e:
        print(f"[analysis.py] 支撑阻力位计算异常: {e}")
        return []


def calculate_range_stats(
    df: pd.DataFrame, start_date: str, end_date: str
) -> Dict[str, Any]:
    """
    区间量化统计：
    计算指定日期区间内的最大连贯涨幅、最大连贯回撤、区间总收益、总振幅、日均波幅及阳线胜率。
    """
    default_result = {
        "bars_count": 0,
        "total_return_pct": 0.0,
        "period_amplitude_pct": 0.0,
        "avg_daily_range_pct": 0.0,
        "win_rate_pct": 0.0,
        "max_rise": {"pct": 0.0, "start": start_date, "end": start_date},
        "max_fall": {"pct": 0.0, "start": start_date, "end": start_date},
    }

    if df is None or df.empty:
        return default_result

    try:
        work_df = _extract_ohlc(df)
        if "date" not in work_df.columns:
            for col in ("Date", "datetime", "Datetime", "time", "Time"):
                if col in work_df.columns:
                    work_df["date"] = work_df[col]
                    break
            else:
                work_df["date"] = work_df.index

        date_strs = work_df["date"].astype(str).str.slice(0, 10)
        s_date = str(start_date)[:10]
        e_date = str(end_date)[:10]
        mask = (date_strs >= s_date) & (date_strs <= e_date)
        sub_df = work_df.loc[mask].reset_index(drop=True)
        if sub_df.empty:
            return default_result

        opens = sub_df["open"].values.astype(float)
        highs = sub_df["high"].values.astype(float)
        lows = sub_df["low"].values.astype(float)
        closes = sub_df["close"].values.astype(float)
        dates = date_strs.loc[mask].values

        # 1. 最大连贯上涨波段
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

        # 2. 最大连贯下跌回撤
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

        # 3. 区间拓展量化指标
        first_open = opens[0] if opens[0] > 0 else closes[0]
        total_return_pct = ((closes[-1] - first_open) / first_open * 100) if first_open > 0 else 0.0
        period_min = float(np.min(lows))
        period_max = float(np.max(highs))
        period_amplitude_pct = ((period_max - period_min) / period_min * 100) if period_min > 0 else 0.0

        daily_ranges = np.where(lows > 0, (highs - lows) / lows * 100, 0.0)
        avg_daily_range_pct = float(np.mean(daily_ranges))

        up_bars = int(np.sum(closes >= opens))
        win_rate_pct = (up_bars / len(sub_df)) * 100

        return {
            "bars_count": len(sub_df),
            "total_return_pct": round(total_return_pct, 2),
            "period_amplitude_pct": round(period_amplitude_pct, 2),
            "avg_daily_range_pct": round(avg_daily_range_pct, 2),
            "win_rate_pct": round(win_rate_pct, 2),
            "max_rise": {"pct": round(max_rise_pct, 2), "start": str(rise_start), "end": str(rise_end)},
            "max_fall": {"pct": round(max_fall_pct, 2), "start": str(fall_start), "end": str(fall_end)},
        }
    except Exception as e:
        print(f"[analysis.py] 区间量化统计计算异常: {e}")
        return default_result
