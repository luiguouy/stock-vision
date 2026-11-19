# -*- coding: utf-8 -*-
"""
艾略特波浪理论 - 斐波那契与卢卡斯双数列变盘日预测引擎
路径: stage_one/backend/time_window.py
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd

# 斐波那契与卢卡斯完整周期数列（涵盖短期共振至大周期拐点推演）
FIB_SEQUENCE = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]
LUCAS_SEQUENCE = [1, 3, 4, 7, 11, 18, 29, 47, 76, 123]


def add_period_offset(start_date_str: str, bars_offset: int, period: str = "1d", is_crypto: bool = False) -> str:
    """
    将锚点日期记为第 1 根 K 线，向后推算第 bars_offset 根 K 线所在的交易日。
    日线自动跳过周六与周日（加密资产 7x24 小时运行不跳过）。
    """
    dt = datetime.strptime(start_date_str[:10], "%Y-%m-%d")
    steps = max(0, bars_offset - 1)

    if period == "1d":
        if is_crypto:
            dt += timedelta(days=steps)
        else:
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


def add_calendar_offset(start_date_str: str, days_offset: int, is_crypto: bool = False) -> str:
    """
    按自然日向后推算第 days_offset 天，非加密资产若落在周末自动顺延至紧随的交易日 (周一)。
    """
    dt = datetime.strptime(start_date_str[:10], "%Y-%m-%d")
    dt += timedelta(days=max(0, days_offset - 1))
    if not is_crypto:
        if dt.weekday() == 5:  # 周六顺延到周一
            dt += timedelta(days=2)
        elif dt.weekday() == 6:  # 周日顺延到周一
            dt += timedelta(days=1)
    return dt.strftime("%Y-%m-%d")


def trading_days_between(d1_str: str, d2_str: str, is_crypto: bool = False) -> int:
    """计算两个日期之间的交易日差值（d2 > d1 为正）。"""
    dt1 = datetime.strptime(d1_str[:10], "%Y-%m-%d")
    dt2 = datetime.strptime(d2_str[:10], "%Y-%m-%d")
    if is_crypto:
        return (dt2 - dt1).days
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
    lookahead_bars: int = 45,
    lookback_bars: int = 3,
    is_crypto: bool = False,
) -> Dict[str, Any]:
    """
    计算未来变盘时间窗、多锚点共振簇与当前波段耗时比例。
    支持交易日 K 线与自然日双维度推演斐波那契与卢卡斯数列。
    """
    if period not in ("1d", "1w", "1M") or df is None or df.empty or not swings:
        return {
            "enabled": False,
            "reason": "变盘时间窗预测仅适用于日K(1d)、周K(1w)与月K(1M)",
            "clusters": [],
            "turning_dates": [],
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
            "turning_dates": [],
            "wave_duration": None,
            "imminent_alert": None,
        }

    dt_min = dt_last - timedelta(days=lookback_bars * (7 if period == "1w" else 1))
    min_date_str = dt_min.strftime("%Y-%m-%d")
    max_date_str = add_period_offset(last_date_str, lookahead_bars + 1, period, is_crypto=is_crypto)

    conf_swings = [s for s in swings if s.get("confirmed", True)] or swings

    # 1. 提取核心拐点锚点 (优先波浪关键转折点 0点、A浪底、B浪顶、C浪底，辅以近 5 个道氏拐点)
    anchors_map: Dict[str, Dict[str, Any]] = {}

    if wave_points:
        for w_key, pt in wave_points.items():
            idx = int(pt.get("index", -1))
            t_str = str(pt.get("time", ""))[:10]
            if (not t_str or len(t_str) < 10) and 0 <= idx < len(df):
                t_str = _get_bar_date(idx)
            if t_str and len(t_str) == 10:
                clean_k = str(w_key).upper()
                name_lbl = f"{clean_k}点" if clean_k in ("0", "A", "B", "C") else f"浪{clean_k}"
                anchors_map[t_str] = {
                    "date": t_str,
                    "price": round(float(pt["price"]), 2),
                    "label": name_lbl,
                    "is_wave": True,
                }

    for sw in conf_swings[-5:]:
        t_str = str(sw.get("time", ""))[:10]
        if (not t_str or len(t_str) < 10) and 0 <= int(sw.get("index", -1)) < len(df):
            t_str = _get_bar_date(int(sw["index"]))
        if t_str and len(t_str) == 10 and t_str not in anchors_map:
            lbl = sw.get("dow") or ("波峰" if sw.get("type") == "High" else "波谷")
            anchors_map[t_str] = {
                "date": t_str,
                "price": round(float(sw["price"]), 2),
                "label": lbl,
                "is_wave": False,
            }

    anchors = sorted(anchors_map.values(), key=lambda x: x["date"])[-6:]
    raw_projections: List[Dict[str, Any]] = []

    # 2. 分别按交易日与自然日投射 Fibonacci 与 Lucas 周期
    for anc in anchors:
        a_date = anc["date"]
        lbl = anc["label"]

        # 交易日推演
        for num in FIB_SEQUENCE:
            target_d = add_period_offset(a_date, num, period, is_crypto=is_crypto)
            if min_date_str <= target_d <= max_date_str:
                weight = 2.5 if num in (13, 21, 34, 55, 89) else (1.8 if num in (5, 8) else 1.0)
                raw_projections.append({
                    "target_date": target_d,
                    "seq_type": "Fib_Trading",
                    "weight": weight,
                    "desc": f"{lbl}后第 {num} 交易日 (Fib)",
                })

        for num in LUCAS_SEQUENCE:
            target_d = add_period_offset(a_date, num, period, is_crypto=is_crypto)
            if min_date_str <= target_d <= max_date_str:
                weight = 2.2 if num in (11, 18, 29, 47, 76) else (1.5 if num in (4, 7) else 0.9)
                raw_projections.append({
                    "target_date": target_d,
                    "seq_type": "Lucas_Trading",
                    "weight": weight,
                    "desc": f"{lbl}后第 {num} 交易日 (Lucas)",
                })

        # 自然日推演 (仅针对核心波浪锚点与显著大周期)
        if anc.get("is_wave") or len(anchors) <= 3:
            for num in [8, 13, 21, 34, 55, 89]:
                target_d = add_calendar_offset(a_date, num, is_crypto=is_crypto)
                if min_date_str <= target_d <= max_date_str:
                    raw_projections.append({
                        "target_date": target_d,
                        "seq_type": "Fib_Calendar",
                        "weight": 2.0,
                        "desc": f"{lbl}后第 {num} 自然日 (Fib)",
                    })
            for num in [7, 11, 18, 29, 47, 76]:
                target_d = add_calendar_offset(a_date, num, is_crypto=is_crypto)
                if min_date_str <= target_d <= max_date_str:
                    raw_projections.append({
                        "target_date": target_d,
                        "seq_type": "Lucas_Calendar",
                        "weight": 1.8,
                        "desc": f"{lbl}后第 {num} 自然日 (Lucas)",
                    })

    # 3. 测算波段耗时比 (Wave Duration Ratio)
    wave_duration_info = None
    if len(conf_swings) >= 3:
        idx_p1 = int(conf_swings[-3].get("index", 0))
        idx_p2 = int(conf_swings[-2].get("index", 0))
        idx_c1 = int(conf_swings[-1].get("index", 0))

        prev_bars = max(1, idx_p2 - idx_p1 + 1)
        curr_bars = max(1, len(df) - idx_c1)
        curr_anchor_date = _get_bar_date(idx_c1) if 0 <= idx_c1 < len(df) else last_date_str
        if not curr_anchor_date:
            curr_anchor_date = last_date_str

        for ratio in (0.618, 1.000, 1.618):
            proj_bars = max(3, int(round(prev_bars * ratio)))
            target_d = add_period_offset(curr_anchor_date, proj_bars, period, is_crypto=is_crypto)
            if min_date_str <= target_d <= max_date_str:
                raw_projections.append({
                    "target_date": target_d,
                    "seq_type": "Ratio",
                    "weight": 2.0,
                    "desc": f"前波段耗时 {ratio}x ({proj_bars}根)",
                })

        next_fib = next((f for f in FIB_SEQUENCE if f >= curr_bars), 144)
        next_luc = next((l for l in LUCAS_SEQUENCE if l >= curr_bars), 123)
        next_seq = min(next_fib, next_luc)
        wave_duration_info = {
            "prev_wave_bars": prev_bars,
            "curr_wave_bars": curr_bars,
            "duration_ratio": round(curr_bars / prev_bars, 2),
            "next_seq_number": next_seq,
            "next_seq_type": "Fib" if next_seq == next_fib else "Lucas",
            "next_seq_date": add_period_offset(curr_anchor_date, next_seq, period, is_crypto=is_crypto),
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

        has_fib = any("Fib" in st for st in seq_types)
        has_lucas = any("Lucas" in st for st in seq_types)
        is_resonance = (has_fib and has_lucas) or len(unique_reasons) >= 2
        if is_resonance:
            score = round(score * 1.3, 1)

        days_from_now = trading_days_between(last_date_str, d_str, is_crypto=is_crypto)
        confidence = "强共振" if score >= 4.0 else ("双因子" if is_resonance else "单因子")

        clusters.append({
            "date": d_str,
            "days_from_now": days_from_now,
            "score": round(score, 1),
            "is_resonance": is_resonance,
            "confidence": confidence,
            "reasons": unique_reasons[:4],
        })

    # 提取未来核心变盘窗口 (days_from_now >= 0)
    future_clusters = [c for c in clusters if c["days_from_now"] >= 0]
    top_clusters = sorted(
        future_clusters,
        key=lambda x: (1 if x["is_resonance"] else 0, x["score"], -x["days_from_now"]),
        reverse=True,
    )[:6]
    top_clusters.sort(key=lambda x: x["date"])

    # 5. 精炼输出 3~4 个高置信度变盘日期推演模型
    turning_dates: List[Dict[str, Any]] = []
    for idx_td, c in enumerate(top_clusters[:4]):
        d_val = c["date"]
        dfn = c["days_from_now"]
        offset_text = "今日 (T+0)" if dfn == 0 else (f"明日 (T+{dfn})" if dfn == 1 else f"T+{dfn}日")
        basis_str = " / ".join(c["reasons"][:2]) if c["reasons"] else "周期时间窗口"

        # K线观察重点推导
        if idx_td == 0 and dfn <= 2:
            focus_str = "变盘临界窗：关注关键位是否放量突破阻力，或呈现冲高受阻滞涨长上影"
        elif c["is_resonance"]:
            focus_str = "多周期时间共振：密切观察K线形态是否出现主推突破或反转吞没信号"
        else:
            focus_str = "单因子时间节点：关注成交量异动与通道轨迹支撑/阻力确认"

        turning_dates.append({
            "date": d_val,
            "days_from_now": dfn,
            "day_offset_text": offset_text,
            "basis": basis_str,
            "focus": focus_str,
            "confidence": c["confidence"],
            "score": c["score"],
            "is_resonance": c["is_resonance"],
        })

    # 6. 生成临近变盘风控预警
    imminent_alert = None
    for c in top_clusters:
        if 0 <= c["days_from_now"] <= 1 and (c["is_resonance"] or c["score"] >= 2.5):
            when_str = "今日" if c["days_from_now"] == 0 else "次日"
            label = f"{when_str}共振变盘窗" if c["is_resonance"] else f"{when_str}变盘窗"
            d_fmt = c["date"][5:] if len(c["date"]) >= 10 else c["date"]
            factors_str = " / ".join(c["reasons"][:2])
            imminent_alert = f"⏳ {label} ({d_fmt}) · {factors_str}"
            break

    return {
        "enabled": True,
        "anchor_count": len(anchors),
        "last_bar_date": last_date_str,
        "clusters": top_clusters,
        "turning_dates": turning_dates,
        "wave_duration": wave_duration_info,
        "imminent_alert": imminent_alert,
    }

