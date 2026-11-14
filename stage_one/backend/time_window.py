# -*- coding: utf-8 -*-
"""
艾略特波浪理论 - 斐波那契与卢卡斯双数列变盘日预测引擎
路径: stage_one/backend/time_window.py
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd

# 斐波那契与卢卡斯核心周期数列（剔除过小的 1, 2, 3 以避免日线级别噪音过密）
FIB_SEQUENCE = [5, 8, 13, 21, 34, 55, 89, 144, 233]
LUCAS_SEQUENCE = [4, 7, 11, 18, 29, 47, 76, 123, 199]


def add_period_offset(start_date_str: str, bars_offset: int, period: str = "1d") -> str:
    """
    将锚点日期记为第 1 根 K 线，向后推算第 bars_offset 根 K 线所在的日期。
    日线自动跳过周六与周日。
    """
    dt = datetime.strptime(start_date_str[:10], "%Y-%m-%d")
    steps = max(0, bars_offset - 1)

    if period == "1d":
        while steps > 0:
            dt += timedelta(days=1)
            if dt.weekday() < 5:
                steps -= 1
    elif period == "1w":
        dt += timedelta(weeks=steps)
    elif period == "1M":
        year = dt.year + (dt.month - 1 + steps) // 12
        month = (dt.month - 1 + steps) % 12 + 1
        dt = datetime(year, month, min(dt.day, 28))

    return dt.strftime("%Y-%m-%d")


def trading_days_between(d1_str: str, d2_str: str) -> int:
    """计算两个日期之间的交易日差值（d2 > d1 为正）。"""
    dt1 = datetime.strptime(d1_str[:10], "%Y-%m-%d")
    dt2 = datetime.strptime(d2_str[:10], "%Y-%m-%d")
    if dt1 == dt2:
        return 0
    sign = 1 if dt2 > dt1 else -1
    cur, end = (dt1, dt2) if dt2 > dt1 else (dt2, dt1)
    days = 0
    while cur < end:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            days += 1
    return days * sign


def predict_turn_windows(
    df: pd.DataFrame,
    swings: List[Dict[str, Any]],
    wave_points: Optional[Dict[str, Any]] = None,
    period: str = "1d",
    lookahead_bars: int = 25,
    lookback_bars: int = 3,
) -> Dict[str, Any]:
    """
    计算未来变盘时间窗、多锚点共振簇与当前波段耗时比例。
    仅在 1d / 1w / 1M 周期启用。
    """
    if period not in ("1d", "1w", "1M") or df is None or df.empty or not swings:
        return {
            "enabled": False,
            "reason": "变盘时间窗预测仅适用于日K(1d)、周K(1w)与月K(1M)",
            "clusters": [],
            "wave_duration": None,
            "imminent_alert": None,
        }

    def _get_bar_date(idx: int) -> str:
        if 0 <= idx < len(df):
            for col in ("date", "Datetime", "datetime", "Date", "time", "Time"):
                if col in df.columns:
                    return str(df[col].iloc[idx])[:10]
            return str(df.index[idx])[:10]
        return ""

    last_date_str = _get_bar_date(len(df) - 1)
    try:
        dt_last = datetime.strptime(last_date_str, "%Y-%m-%d")
    except ValueError:
        return {
            "enabled": False,
            "reason": "K线时间索引格式不支持",
            "clusters": [],
            "wave_duration": None,
            "imminent_alert": None,
        }

    dt_min = dt_last - timedelta(days=lookback_bars * (7 if period == "1w" else 1))
    min_date_str = dt_min.strftime("%Y-%m-%d")
    max_date_str = add_period_offset(last_date_str, lookahead_bars + 1, period)

    # 1. 提取核心拐点锚点 (合并最近 5 个道氏拐点与波浪端点)
    anchors_map: Dict[str, Dict[str, Any]] = {}
    for sw in swings[-5:]:
        t_str = str(sw.get("time", ""))[:10]
        if (not t_str or len(t_str) < 10) and 0 <= int(sw.get("index", -1)) < len(df):
            t_str = _get_bar_date(int(sw["index"]))
        if t_str and len(t_str) == 10:
            lbl = sw.get("dow") or ("高点" if sw.get("type") == "High" else "低点")
            anchors_map[t_str] = {
                "date": t_str,
                "price": round(float(sw["price"]), 2),
                "label": f"{lbl}({t_str[5:]})",
            }

    if wave_points:
        for w_key, pt in wave_points.items():
            idx = int(pt.get("index", -1))
            t_str = str(pt.get("time", ""))[:10]
            if (not t_str or len(t_str) < 10) and 0 <= idx < len(df):
                t_str = _get_bar_date(idx)
            if t_str and len(t_str) == 10:
                anchors_map[t_str] = {
                    "date": t_str,
                    "price": round(float(pt["price"]), 2),
                    "label": f"浪{w_key}({t_str[5:]})",
                }

    anchors = sorted(anchors_map.values(), key=lambda x: x["date"])[-6:]
    raw_projections: List[Dict[str, Any]] = []

    # 2. 投射 Fibonacci 与 Lucas 周期
    for anc in anchors:
        a_date = anc["date"]
        for num in FIB_SEQUENCE:
            target_d = add_period_offset(a_date, num, period)
            if min_date_str <= target_d <= max_date_str:
                weight = 2.5 if num in (21, 34, 55, 89, 144) else 1.5
                raw_projections.append({
                    "target_date": target_d,
                    "seq_type": "Fib",
                    "weight": weight,
                    "desc": f"{anc['label']} + Fib({num})",
                })
        for num in LUCAS_SEQUENCE:
            target_d = add_period_offset(a_date, num, period)
            if min_date_str <= target_d <= max_date_str:
                weight = 2.2 if num in (18, 29, 47, 76, 123) else 1.2
                raw_projections.append({
                    "target_date": target_d,
                    "seq_type": "Lucas",
                    "weight": weight,
                    "desc": f"{anc['label']} + Lucas({num})",
                })

    # 3. 测算波段耗时比 (Wave Duration Ratio)
    wave_duration_info = None
    if len(swings) >= 3:
        idx_p1 = int(swings[-3].get("index", 0))
        idx_p2 = int(swings[-2].get("index", 0))
        idx_c1 = int(swings[-1].get("index", 0))

        prev_bars = max(1, idx_p2 - idx_p1 + 1)
        curr_bars = max(1, len(df) - idx_c1)
        curr_anchor_date = _get_bar_date(idx_c1) if 0 <= idx_c1 < len(df) else last_date_str
        if not curr_anchor_date:
            curr_anchor_date = last_date_str

        for ratio in (0.618, 1.000, 1.618):
            proj_bars = max(3, int(round(prev_bars * ratio)))
            target_d = add_period_offset(curr_anchor_date, proj_bars, period)
            if min_date_str <= target_d <= max_date_str:
                raw_projections.append({
                    "target_date": target_d,
                    "seq_type": "Ratio",
                    "weight": 2.0,
                    "desc": f"前波段耗时 {ratio}x ({proj_bars}根)",
                })

        next_fib = next((f for f in FIB_SEQUENCE if f >= curr_bars), 233)
        next_luc = next((l for l in LUCAS_SEQUENCE if l >= curr_bars), 199)
        next_seq = min(next_fib, next_luc)
        wave_duration_info = {
            "prev_wave_bars": prev_bars,
            "curr_wave_bars": curr_bars,
            "duration_ratio": round(curr_bars / prev_bars, 2),
            "next_seq_number": next_seq,
            "next_seq_type": "Fib" if next_seq == next_fib else "Lucas",
            "next_seq_date": add_period_offset(curr_anchor_date, next_seq, period),
        }

    # 4. 聚合共振时间簇
    by_date: Dict[str, List[Dict[str, Any]]] = {}
    for proj in raw_projections:
        by_date.setdefault(proj["target_date"], []).append(proj)

    clusters = []
    for d_str in sorted(by_date.keys()):
        hits = by_date[d_str]
        unique_reasons, seen_desc, seq_types = [], set(), set()
        score = 0.0
        for h in hits:
            if h["desc"] not in seen_desc:
                seen_desc.add(h["desc"])
                unique_reasons.append(h["desc"])
                score += h["weight"]
                seq_types.add(h["seq_type"])

        is_resonance = ("Fib" in seq_types and "Lucas" in seq_types) or len(unique_reasons) >= 2
        if is_resonance:
            score = round(score * 1.25, 1)

        days_from_now = trading_days_between(last_date_str, d_str)
        confidence = "极高 (多维共振)" if score >= 4.5 else ("高 (双因子共振)" if is_resonance else "中 (单周期窗)")

        clusters.append({
            "date": d_str,
            "days_from_now": days_from_now,
            "score": round(score, 1),
            "is_resonance": is_resonance,
            "confidence": confidence,
            "reasons": unique_reasons[:4],
        })

    top_clusters = sorted(
        [c for c in clusters if c["days_from_now"] >= -2],
        key=lambda x: (1 if x["is_resonance"] else 0, x["score"], -abs(x["days_from_now"])),
        reverse=True,
    )[:6]
    top_clusters.sort(key=lambda x: x["date"])

    # 5. 生成临近变盘风控预警
    imminent_alert = None
    for c in top_clusters:
        if 0 <= c["days_from_now"] <= 1 and (c["is_resonance"] or c["score"] >= 2.5):
            when_str = "今日" if c["days_from_now"] == 0 else "下一交易日"
            imminent_alert = (
                f"⏳ 变盘窗预警：{when_str} ({c['date']}) 触达{c['confidence']} "
                f"[{' + '.join(c['reasons'][:2])}]，谨防突破衰竭或转势！"
            )
            break

    return {
        "enabled": True,
        "anchor_count": len(anchors),
        "last_bar_date": last_date_str,
        "clusters": top_clusters,
        "wave_duration": wave_duration_info,
        "imminent_alert": imminent_alert,
    }
