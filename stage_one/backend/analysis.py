# -*- coding: utf-8 -*-
"""
智能股票技术分析平台 - 独立量化算术引擎
零项目内依赖，提供多周期支撑阻力聚类、区间波动率、最大回撤与胜率计算。
"""

from typing import List, Dict, Any
import numpy as np
import pandas as pd
from scipy.ndimage import maximum_filter1d, minimum_filter1d

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

PERIOD_CLAMP_BOUNDS = {
    "5m": (0.0015, 0.008), "15m": (0.002, 0.010), "1h": (0.003, 0.015),
    "4h": (0.004, 0.020),  "1d": (0.006, 0.025),  "1w": (0.012, 0.050),
    "1M": (0.020, 0.080),  "3M": (0.030, 0.120),  "6M": (0.040, 0.150), "1Y": (0.050, 0.200),
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
    自适应支撑/阻力位聚类：
    基于 True Range 中位数估算相对合并阈值 + 分周期上下限钳制 + O(N) 局部极值滤波
    + 锚点防漂移单趟聚类 + 相对归一化时间衰减打分。
    """
    if df is None or df.empty:
        return []

    try:
        work_df = _extract_ohlc(df)
        highs = work_df["high"].to_numpy(dtype=float)
        lows = work_df["low"].to_numpy(dtype=float)
        closes = work_df["close"].to_numpy(dtype=float)
        total_len = len(work_df)

        params = PERIOD_PARAMS.get(period, PERIOD_PARAMS["1d"])
        half_life = params["half_life"]
        win = params["window"] if (window == 5 and period != "1d") else window

        if win <= 0 or total_len < win * 2 + 1:
            return []

        latest_price = float(closes[-1])
        if latest_price <= 0:
            return []

        # 1. 严谨的相对波动率阈值：基于 True Range 中位数 + 分周期上下限钳制
        lookback = min(20, total_len - 1)
        if lookback >= 1:
            prev_c = closes[-lookback - 1 : -1]
            tr = np.maximum.reduce([
                highs[-lookback:] - lows[-lookback:],
                np.abs(highs[-lookback:] - prev_c),
                np.abs(lows[-lookback:] - prev_c),
            ])
            rel_tr_med = float(np.median(tr / np.maximum(prev_c, 1e-6)))
        else:
            rel_tr_med = float((highs[-1] - lows[-1]) / max(latest_price, 1e-6))

        lo_bound, hi_bound = PERIOD_CLAMP_BOUNDS.get(period, (0.006, 0.025))
        rel_threshold = max(lo_bound, min(rel_tr_med * 0.8, hi_bound))
        if distance_pct != 0.015:
            rel_threshold = distance_pct

        # 2. O(N) 向量化提取局部极值
        size = 2 * win + 1
        is_max = (highs == maximum_filter1d(highs, size=size, mode="nearest"))
        is_min = (lows == minimum_filter1d(lows, size=size, mode="nearest"))
        is_max[:win] = is_max[-win:] = False
        is_min[:win] = is_min[-win:] = False

        extrema: List[Dict[str, Any]] = (
            [{"price": float(highs[i]), "idx": int(i)} for i in np.where(is_max)[0]] +
            [{"price": float(lows[i]), "idx": int(i)} for i in np.where(is_min)[0]]
        )

        if not extrema:
            return []

        extrema.sort(key=lambda x: x["price"])

        # 3. O(M) 防漂移单趟聚类（以簇首锚点 anchor 限制总宽度，消除单链漂移与尺度非不变性）
        clusters: List[Dict[str, Any]] = []
        for ext in extrema:
            w = 0.5 ** ((total_len - 1 - ext["idx"]) / half_life)
            p = ext["price"]
            if clusters and (p - clusters[-1]["anchor"]) / max(clusters[-1]["anchor"], 1e-6) <= rel_threshold:
                c = clusters[-1]
                tot_w = c["weight"] + w
                c["price"] = (c["price"] * c["weight"] + p * w) / tot_w
                c["weight"] = tot_w
                c["count"] += 1
            else:
                clusters.append({"anchor": p, "price": p, "weight": w, "count": 1})

        # 4. 划分支撑/阻力并按相对归一化与现价临近度综合打分
        max_w = max((c["weight"] for c in clusters), default=1.0)
        support_candidates: List[Dict[str, Any]] = []
        resistance_candidates: List[Dict[str, Any]] = []

        for c in clusters:
            lvl_price = float(c["price"])
            dist_pct = abs(lvl_price - latest_price) / latest_price
            score = c["weight"] * (1.0 / (1.0 + 8.0 * dist_pct))
            rel_w = c["weight"] / max(max_w, 1e-6)

            if c["weight"] >= 3.5 or (max_w >= 1.5 and rel_w >= 0.85):
                stars, rank = 5, "Strong"
            elif c["weight"] >= 2.0 or (max_w >= 1.0 and rel_w >= 0.50):
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
