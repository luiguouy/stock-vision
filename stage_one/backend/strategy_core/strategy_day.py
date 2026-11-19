#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategy_day.py: 美股与高波动资产日内价格行为量化策略引擎 (Intraday Price Action Engine)

理论依据与设计原则（严格遵循纯价格行为学，100% 严禁任何滞后性技术指标）：
  1. 多周期日内结构 (Intraday Multi-timeframe Structure):
     - HTF (1h): 大势定性与主要支阻背景；
     - MTF (15m): 波浪与日内结构转换；
     - LTF (5m): 微观形态触发、挂单与秒级入场撮合。
  2. 日内核心价格锚点 (Core Intraday Reference Levels):
     - 开盘区间 (Opening Range 09:30-09:45 ET, ORH / ORL): 美股开盘机构流动性博弈形成的初始价格区间；
     - 昨高昨低昨收 (PDH / PDL / PDC): 前一交易日高低点与收盘价（极度关键的机构流动性聚集带）；
     - 盘前高低点 (PMH / PML, 04:00-09:30 ET): 盘前非农/财报/宏观脉冲定价极值。
  3. 日内核心战术 (Intraday Setups):
     - 战术 A: 开盘区间突破与回踩 (ORB & Retest): 突破 ORH/ORL 后等待次级回踩确认，避免假突破追单；
     - 战术 B: 昨高昨低 2B 流动性猎杀 (PDH/PDL 2B Liquidity Hunt): 盘中刺破 PDH/PDL 诱多/诱空后强力收回，反向狙击；
     - 战术 C: 盘前极值 2B 流动性猎杀 (PMH/PML 2B Liquidity Sweep): 盘前极值扫损反转；
     - 战术 D: 综合全闭环 (Day Combined Execution): 联动 2B 猎杀与 ORB 突破回踩。
  4. 日内铁律纪律与真实执行摩擦 (Intraday Risk Discipline & Friction Modeling):
     - 日内防隔夜强制平仓 (EOD Forced Square-Off): 15:55 ET 无论盈亏一律强制市价平仓，绝不持仓隔夜（无隔夜跳空黑天鹅风险）；
     - 动态保本防守 (Break-Even Protection at 1.5R): 浮盈达到 1.5R 时立即将止损推至开仓保本位；
     - 滑点与交易摩擦 (Slippage & Commission Friction): 实测模拟 3 bps 滑点 + 1 bps 规费，输出 Gross vs Net 净收益对比；
     - 纯因果零未来函数 (Zero Lookahead Walk-Forward): 第 t 根决策，t+1 根开盘入场；同根双触严格止损优先。
"""

import os
import sys
import json
from datetime import time as dtime
import numpy as np
import pandas as pd
from . import pa_engine as pe

# 日内核心默认参数
DEFAULT_DAY_STOP_BUFFER_K = 0.35      # 紧密止损缓冲（0.35x 5分K中位振幅）
DEFAULT_DAY_MIN_RR = 2.5              # 日内最小盈亏比硬闸门 (统一升级至 >= 2.5R)
DEFAULT_SLIPPAGE_BPS = 3.0            # 默认单边滑点 3 个基点 (0.03%)
DEFAULT_COMMISSION_BPS = 1.0          # 默认单边交易佣金与规费 1 个基点 (0.01%)
DEFAULT_TOTAL_FRICTION_BPS = 8.0      # 双边总摩擦 8 个基点 (3 bps slippage + 1 bps fee 单边, 往返 8 bps = 0.0008)
DEFAULT_TOTAL_FRICTION_RATE = 0.0008  # 往返 8 bps 绝对费率 (0.0008)
DEFAULT_LOW_VOLATILITY_CHURN_MULTIPLIER = 2.0  # 低波动防刷单阈值乘数 (2 * friction = 16 bps)
DAY_EOD_EXIT_TIME = dtime(15, 55)      # 15:55 ET 强制平仓
DAY_MARKET_OPEN_TIME = dtime(9, 30)   # 09:30 ET 美股常规开盘
DAY_OR_END_TIME = dtime(9, 45)        # 09:45 ET 开盘15分钟区间结束
EXCHANGE_TZ = "America/New_York"


# ==============================================================================
# 1. 时区与交易会话规整 (Session Management)
# ==============================================================================

def normalize_intraday_tz(df: pd.DataFrame) -> pd.DataFrame:
    """
    规整日内 K 线时区至美东时间 (America/New_York)。
    支持 tz-aware 或 tz-naive，保证按 ET 时间精确截断开盘区间与收盘强平。
    """
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.copy()
    if not isinstance(d.index, pd.DatetimeIndex):
        d.index = pd.to_datetime(d.index)
    if d.index.tz is None:
        # 若无时区，默认假定为 UTC 并转为 America/New_York，或已为本地时间
        try:
            d.index = d.index.tz_localize("UTC").tz_convert(EXCHANGE_TZ)
        except Exception:
            d.index = d.index.tz_localize(EXCHANGE_TZ)
    else:
        d.index = d.index.tz_convert(EXCHANGE_TZ)
    return d.sort_index()


def split_intraday_sessions(df: pd.DataFrame) -> dict:
    """
    按交易日（Session Date）切分日内 K 线序列。
    返回按日期升序排列的字典: {session_date: df_session}
    """
    if df.empty:
        return {}
    df_ny = normalize_intraday_tz(df)
    sessions = {}
    for dt, group in df_ny.groupby(df_ny.index.date):
        if len(group) >= 5:
            sessions[dt] = group
    return dict(sorted(sessions.items(), key=lambda x: x[0]))


# ==============================================================================
# 2. 关键价格锚点提取 (Key Levels Extraction)
# ==============================================================================

def extract_session_key_levels(df_session: pd.DataFrame,
                               prev_session_df: pd.DataFrame = None) -> dict:
    """
    提取单个交易会话的关键参考价位（开盘前与开盘后计算，严格无未来函数）：
      - ORH / ORL: 09:30 - 09:45 ET 开盘 15 分钟极值
      - PMH / PML: 04:00 - 09:30 ET 盘前高低点
      - PDH / PDL / PDC: 前一交易日高低收
      - bar_rng: 会话内 5m K 线中位振幅
    """
    if df_session.empty:
        return {}

    t = df_session.index.time
    # 盘前区间 (04:00 - 09:30 ET)
    pm_mask = [(x >= dtime(4, 0)) and (x < dtime(9, 30)) for x in t]
    df_pm = df_session[pm_mask]
    pmh = round(float(df_pm["High"].max()), 2) if len(df_pm) > 0 else None
    pml = round(float(df_pm["Low"].min()), 2) if len(df_pm) > 0 else None

    # 开盘区间 (09:30 - 09:45 ET)
    or_mask = [(x >= dtime(9, 30)) and (x < dtime(9, 45)) for x in t]
    df_or = df_session[or_mask]
    orh = round(float(df_or["High"].max()), 2) if len(df_or) > 0 else None
    orl = round(float(df_or["Low"].min()), 2) if len(df_or) > 0 else None

    # 前一日关键位
    pdh, pdl, pdc = None, None, None
    if prev_session_df is not None and not prev_session_df.empty:
        pdh = round(float(prev_session_df["High"].max()), 2)
        pdl = round(float(prev_session_df["Low"].min()), 2)
        pdc = round(float(prev_session_df["Close"].iloc[-1]), 2)

    # 严格杜绝日内未来函数：只使用前一日（或盘前/开盘前已发生K线）计算基准振幅 bar_rng
    if prev_session_df is not None and not prev_session_df.empty:
        bar_rng = pe.median_bar_range(prev_session_df, n=14)
        if bar_rng <= 0:
            bar_rng = float((prev_session_df["High"] - prev_session_df["Low"]).median())
    else:
        df_hist = df_session[df_session.index.time <= DAY_OR_END_TIME]
        if len(df_hist) >= 3:
            bar_rng = float((df_hist["High"] - df_hist["Low"]).median())
        else:
            bar_rng = float((df_session["High"] - df_session["Low"]).iloc[:min(len(df_session), 5)].median())

    return {
        "PMH": pmh, "PML": pml,
        "ORH": orh, "ORL": orl,
        "PDH": pdh, "PDL": pdl, "PDC": pdc,
        "bar_rng": max(0.01, round(bar_rng, 2))
    }


# ==============================================================================
# 3. 日内微观形态检测 (Intraday Trigger Detection)
# ==============================================================================

def detect_intraday_2b_sweep(df: pd.DataFrame, k: int, level: float,
                             level_name: str, bar_rng: float,
                             buffer_k: float = DEFAULT_DAY_STOP_BUFFER_K,
                             level_type: str = "auto") -> dict:
    """
    检测单根 5m K 线在指定日内关键位（PDH/PDL/PMH/PML/ORH/ORL）的 2B 流动性猎杀形态：
      - level_type: 'high' (阻力/买方流动性池), 'low' (支撑/卖方流动性池), 'auto' 自动推断
      - 2B Sweep High (做空): 盘中刺破关键高点，但收盘收回其下方，且为阴线或留长上影（仅在 High 关键位触发）
      - 2B Sweep Low (做多): 盘中跌破关键低点，但收盘强力收复其上方，且为阳线或留长下影（仅在 Low 关键位触发）
      严格禁止反向倒错（如在 PDH 做多或 PDL 做空）！
    """
    if k < 1 or k >= len(df) or level is None or level <= 0 or bar_rng <= 0:
        return {"triggered": False}

    curr = df.iloc[k]
    prev = df.iloc[k - 1]

    c_o, c_h, c_l, c_c = float(curr["Open"]), float(curr["High"]), float(curr["Low"]), float(curr["Close"])
    p_h, p_l = float(prev["High"]), float(prev["Low"])

    rng = c_h - c_l
    if rng <= 0:
        return {"triggered": False}

    body = abs(c_c - c_o)
    upper_shadow = c_h - max(c_o, c_c)
    lower_shadow = min(c_o, c_c) - c_l

    # 推断关键位属性
    l_type = level_type.lower()
    if l_type == "auto":
        name_u = level_name.upper()
        if any(x in name_u for x in ("PDH", "PMH", "ORH", "HIGH")):
            l_type = "high"
        elif any(x in name_u for x in ("PDL", "PML", "ORL", "LOW")):
            l_type = "low"
        else:
            l_type = "both"

    # 1. 2B 高位假突破做空 (Sweep High) - 仅限 High 级别阻力/买方流动性池
    if l_type in ("high", "both"):
        # 刺破关键高点（本根最高价 > level），且前一根最高价 <= level（首次或当期突破），收盘收回 level 下方
        if c_h > level and c_c < level and p_h <= level + 0.2 * bar_rng:
            # 要求收出阻力特征：阴线实体或上影线 >= 实体 1.2 倍
            is_bear_candle = (c_c <= c_o) or (upper_shadow >= 1.2 * body) or (upper_shadow / rng >= 0.40)
            if is_bear_candle:
                tight_stop = round(c_h + buffer_k * bar_rng, 2)
                return {
                    "triggered": True,
                    "side": -1,
                    "pattern": f"2B_sweep_high_{level_name}",
                    "trigger_t": k,
                    "sweep_level": level,
                    "level_name": level_name,
                    "tight_stop": tight_stop,
                    "trigger_high": c_h,
                    "trigger_low": c_l
                }

    # 2. 2B 低位假跌破做多 (Sweep Low) - 仅限 Low 级别支撑/卖方流动性池
    if l_type in ("low", "both"):
        # 击穿关键低点（本根最低价 < level），且前一根最低价 >= level - 0.2 * bar_rng，收盘收复 level 上方
        if c_l < level and c_c > level and p_l >= level - 0.2 * bar_rng:
            # 要求收出探底回升特征：阳线实体或下影线 >= 实体 1.2 倍
            is_bull_candle = (c_c >= c_o) or (lower_shadow >= 1.2 * body) or (lower_shadow / rng >= 0.40)
            if is_bull_candle:
                tight_stop = round(c_l - buffer_k * bar_rng, 2)
                return {
                    "triggered": True,
                    "side": 1,
                    "pattern": f"2B_sweep_low_{level_name}",
                    "trigger_t": k,
                    "sweep_level": level,
                    "level_name": level_name,
                    "tight_stop": tight_stop,
                    "trigger_high": c_h,
                    "trigger_low": c_l
                }

    return {"triggered": False}


def detect_orb_breakout_retest(df: pd.DataFrame, k: int, orh: float, orl: float,
                               bar_rng: float, buffer_k: float = DEFAULT_DAY_STOP_BUFFER_K) -> dict:
    """
    开盘区间突破与回踩确认检测 (Opening Range Breakout & Retest):
      - 09:45 之后，若前K有效突破 ORH，当前K回踩 ORH 获得支撑收阳，触发顺势做多；
      - 若前K有效跌破 ORL，当前K反抽 ORL 受阻收阴，触发顺势做空。
    """
    if k < 2 or k >= len(df) or orh is None or orl is None or orh <= orl:
        return {"triggered": False}

    curr = df.iloc[k]
    prev = df.iloc[k - 1]
    c_o, c_h, c_l, c_c = float(curr["Open"]), float(curr["High"]), float(curr["Low"]), float(curr["Close"])
    p_o, p_c = float(prev["Open"]), float(prev["Close"])

    tol = 0.3 * bar_rng

    # 多头：前K收在 ORH 上方，本K探低至 ORH 附近获得支撑收阳
    if p_c > orh and c_l <= orh + tol and c_c >= orh and c_c >= c_o:
        or_mid = (orh + orl) / 2.0
        tight_stop = round(max(c_l - buffer_k * bar_rng, or_mid), 2)
        return {
            "triggered": True,
            "side": 1,
            "pattern": "orb_retest_long",
            "trigger_t": k,
            "sweep_level": orh,
            "level_name": "ORH",
            "tight_stop": tight_stop,
            "trigger_high": c_h,
            "trigger_low": c_l
        }

    # 空头：前K收在 ORL 下方，本K反抽至 ORL 附近受阻收阴
    if p_c < orl and c_h >= orl - tol and c_c <= orl and c_c <= c_o:
        or_mid = (orh + orl) / 2.0
        tight_stop = round(min(c_h + buffer_k * bar_rng, or_mid), 2)
        return {
            "triggered": True,
            "side": -1,
            "pattern": "orb_retest_short",
            "trigger_t": k,
            "sweep_level": orl,
            "level_name": "ORL",
            "tight_stop": tight_stop,
            "trigger_high": c_h,
            "trigger_low": c_l
        }

    return {"triggered": False}


# ==============================================================================
# 4. 日内全闭环撮合推演 (Intraday Trade Simulation with EOD & Friction)
# ==============================================================================

def simulate_day_trade(df: pd.DataFrame, entry_t: int, entry_price: float,
                       side: int, stop_price: float, tp_price: float,
                       tp2_price: float = None,
                       min_rr: float = DEFAULT_DAY_MIN_RR,
                       slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
                       commission_bps: float = DEFAULT_COMMISSION_BPS,
                       use_be_at_1_5r: bool = True,
                       eod_exit_time: dtime = DAY_EOD_EXIT_TIME,
                       max_hold_bars: int = 78,
                       pattern: str = None,
                       htf_bias: int = None,
                       market_dow: dict = None,
                       **kwargs) -> dict:
    """
    日内全闭环持仓生命周期推演：
      - 零未来函数：entry_t 为入场K线索引，以 Open[entry_t] 为基准挂单撮合；
      - 低波动防刷单：止损距离 |entry - stop| / entry < 2 * friction (16 bps) 一票否决 (rejected_by_low_volatility_churn)；
      - 盈亏比硬闸门：初始计划盈亏比 RR = |tp - entry| / |entry - stop| 必须 >= min_rr (默认 2.5R)；
      - 非对称做空门禁：多头大势下禁止常规盲目做空 (rejected_by_macro_short_gate)，仅允许 2B 顶扫损反转或宏观破位放行；
      - 保守撮合：同根 K 线若同时触及当期止损与止盈，一律判定为止损优先出场；
      - 动态保本防守 (1.5R BE)：价格运行达到 1.5R 浮盈时，止损推至开仓价 (entry_price)；
      - 日内防隔夜平仓 (EOD Forced Square-Off)：美东时间 15:55 或最后一个 bar 无论盈亏强平，绝不留单隔夜；
      - 真实滑点与摩擦扣减：
        * 单边滑点 3 bps + 佣金 1 bps，往返总摩擦 8 bps (0.0008)；
        * 计算并输出毛收益 (Gross) 与扣除滑点摩擦后的真实净收益 (Net)。
    """
    n = len(df)
    if entry_t >= n or entry_price <= 0 or stop_price <= 0 or tp_price <= 0:
        return {"status": "invalid_trade"}

    risk = abs(entry_price - stop_price)
    reward = abs(tp_price - entry_price)

    if risk <= 0:
        return {"status": "zero_risk_invalid"}

    slippage_rate = slippage_bps / 10000.0
    commission_rate = commission_bps / 10000.0
    friction_pct = 2.0 * slippage_rate + 2.0 * commission_rate
    churn_threshold = DEFAULT_LOW_VOLATILITY_CHURN_MULTIPLIER * friction_pct

    # 1. 低波动标的微利刷单风控拦截 (Low-Volatility Churn Protection)
    risk_pct = risk / entry_price
    if risk_pct < churn_threshold - 1e-9:
        return {
            "status": "rejected_by_low_volatility_churn",
            "reason": "rejected_by_low_volatility_churn",
            "rejection_reason": "rejected_by_low_volatility_churn",
            "risk": round(risk, 4),
            "risk_pct": float(risk_pct),
            "churn_threshold": float(churn_threshold),
            "entry_price": float(entry_price),
            "stop_price": float(stop_price)
        }

    # 2. 盈亏比硬闸门 (Universal Minimum RR >= 2.5R)
    planned_rr = reward / risk
    if planned_rr < min_rr - 1e-6:
        return {
            "status": "rejected_by_min_rr",
            "reason": "rejected_by_rr",
            "rejection_reason": "rejected_by_rr",
            "rr": round(planned_rr, 2),
            "min_rr": min_rr,
            "risk": round(risk, 2),
            "reward": round(reward, 2)
        }

    # 3. 非对称做空风险门禁拦截 (Asymmetric Short Risk Gate)
    if side == -1:
        is_verified_2b_sweep = bool(
            pattern and any(p in str(pattern).lower() for p in ["2b_sweep_high", "2b_top", "sweep_high"])
        )
        if kwargs.get("micro_conviction") in ["strong_2b_reversal", "2b_top_sweep"]:
            is_verified_2b_sweep = True

        # 若处于 1h 顺势多头大势，且非高确定性 2B 假突破反转，拒绝常规做空
        if htf_bias is not None and htf_bias > 0 and not is_verified_2b_sweep:
            return {
                "status": "rejected_by_macro_short_gate",
                "reason": "美股长牛大势下禁止常规盲目日内做空 (rejected_by_macro_short_gate)",
                "rejection_reason": "rejected_by_macro_short_gate",
                "side": side,
                "htf_bias": htf_bias,
                "pattern": pattern
            }

        # 若提供 market_dow 大盘数据，验证大盘做空门禁
        if market_dow is not None:
            has_bearish = any(
                (isinstance(v, dict) and (v.get("bias", 0) <= -1 or v.get("is_breakdown", False)))
                or (isinstance(v, (int, float)) and v <= -1)
                or (isinstance(v, str) and ("空头" in v or "bear" in v.lower() or "破位" in v))
                or market_dow.get(f"{k}_bias", 0) <= -1
                or market_dow.get(f"{k}_breakdown", False)
                for k, v in market_dow.items()
            )
            if not has_bearish and not is_verified_2b_sweep:
                return {
                    "status": "rejected_by_macro_short_gate",
                    "reason": "大盘处于多头顺势环境，长牛向上漂移环境下禁止常规日内做空 (rejected_by_macro_short_gate)",
                    "rejection_reason": "rejected_by_macro_short_gate",
                    "side": side,
                    "market_dow": market_dow,
                    "pattern": pattern
                }

    opens = df["Open"].to_numpy(dtype=float)
    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    closes = df["Close"].to_numpy(dtype=float)
    times = df.index.time

    end_t = min(entry_t + max_hold_bars, n - 1)
    curr_stop = stop_price
    be_active = False

    exit_t = None
    exit_price = None
    exit_reason = None

    entry_date = df.index[entry_t].date()

    # 从 entry_t 根开盘入场后开始推演
    for bar in range(entry_t, end_t + 1):
        o, h, l, c = opens[bar], highs[bar], lows[bar], closes[bar]
        bar_time = times[bar]
        bar_date = df.index[bar].date()

        # 1. 严格日内防隔夜强平纪律：
        #    - 若到达或超过 15:55 ET，开盘市价强制平仓出场
        if bar_time >= eod_exit_time:
            exit_t = bar
            exit_price = o
            exit_reason = "eod_forced_close"
            break

        #    - 若当前 bar 已经跨入次日，必须以入场日最后一根 K 线收盘价截断平仓
        if bar_date != entry_date:
            exit_t = bar - 1 if bar > entry_t else bar
            exit_price = closes[exit_t] if bar > entry_t else opens[bar]
            exit_reason = "eod_forced_close"
            break

        if side == 1:
            hit_stop = (l <= curr_stop)
            hit_tp = (h >= tp_price)

            if hit_stop and hit_tp:
                # 同根双触保守判定：止损优先
                exit_t = bar
                exit_price = min(o, curr_stop)
                exit_reason = "break_even_conservative" if be_active else "stop_loss_conservative"
                break
            elif hit_stop:
                exit_t = bar
                exit_price = min(o, curr_stop)
                exit_reason = "break_even_stop" if be_active else "stop_loss"
                break
            elif hit_tp:
                exit_t = bar
                exit_price = max(o, tp_price)
                exit_reason = "take_profit"
                break

            # 1.5R 保本触发检查（仅在未触及止损的正常推进K线上激活）
            if use_be_at_1_5r and not be_active and h >= entry_price + 1.5 * risk:
                curr_stop = max(curr_stop, entry_price)
                be_active = True
        else:
            hit_stop = (h >= curr_stop)
            hit_tp = (l <= tp_price)

            if hit_stop and hit_tp:
                exit_t = bar
                exit_price = max(o, curr_stop)
                exit_reason = "break_even_conservative" if be_active else "stop_loss_conservative"
                break
            elif hit_stop:
                exit_t = bar
                exit_price = max(o, curr_stop)
                exit_reason = "break_even_stop" if be_active else "stop_loss"
                break
            elif hit_tp:
                exit_t = bar
                exit_price = min(o, tp_price)
                exit_reason = "take_profit"
                break

            # 1.5R 保本触发检查（空头）
            if use_be_at_1_5r and not be_active and l <= entry_price - 1.5 * risk:
                curr_stop = min(curr_stop, entry_price)
                be_active = True

        # 若未触及止盈止损，且下一根即跨入次日（例如半日市提前休市），则在当根收盘强制平仓
        if bar + 1 < n and df.index[bar + 1].date() != entry_date:
            exit_t = bar
            exit_price = c
            exit_reason = "eod_forced_close"
            break

    if exit_t is None:
        exit_t = end_t
        exit_price = closes[end_t]
        exit_reason = "session_end_close"

    # 毛收益计算 (Gross)
    gross_pnl_pct = (exit_price / entry_price - 1.0) * side
    gross_r = ((exit_price - entry_price) * side) / risk

    # 净收益计算 (Net after Slippage & Commission)
    # 买入实际成交价更高，卖出实际成交价更低
    eff_entry = entry_price * (1.0 + side * slippage_rate)
    eff_exit = exit_price * (1.0 - side * slippage_rate)
    friction_pct = 2.0 * slippage_rate + 2.0 * commission_rate
    net_pnl_pct = (eff_exit / eff_entry - 1.0) * side - 2.0 * commission_rate
    net_r = ((eff_exit - eff_entry) * side - entry_price * 2.0 * commission_rate) / risk

    hold_bars = exit_t - entry_t

    # MAE / MFE
    if side == 1:
        sub_low = float(np.min(lows[entry_t:exit_t + 1]))
        sub_high = float(np.max(highs[entry_t:exit_t + 1]))
        mae = min(sub_low / entry_price - 1.0, 0.0)
        mfe = max(sub_high / entry_price - 1.0, 0.0)
    else:
        sub_low = float(np.min(lows[entry_t:exit_t + 1]))
        sub_high = float(np.max(highs[entry_t:exit_t + 1]))
        mae = min(-(sub_high / entry_price - 1.0), 0.0)
        mfe = max(-(sub_low / entry_price - 1.0), 0.0)

    return {
        "status": "completed",
        "entry_t": entry_t,
        "entry_date": df.index[entry_t],
        "entry_price": round(entry_price, 2),
        "side": int(side),
        "exit_t": exit_t,
        "exit_date": df.index[exit_t],
        "exit_price": round(exit_price, 2),
        "exit_reason": exit_reason,
        "gross_pnl_pct": float(gross_pnl_pct),
        "net_pnl_pct": float(net_pnl_pct),
        "gross_r": float(gross_r),
        "net_r": float(net_r),
        "r_multiple": float(net_r),
        "pnl_pct": float(net_pnl_pct),
        "hold_bars": int(hold_bars),
        "mae": float(mae),
        "mfe": float(mfe),
        "win": bool(net_pnl_pct > 0),
        "gross_win": bool(gross_pnl_pct > 0),
        "risk": float(risk),
        "reward": float(reward),
        "planned_rr": float(planned_rr),
        "be_triggered": bool(be_active),
        "slippage_drag_pct": float(gross_pnl_pct - net_pnl_pct)
    }


def extract_intraday_htf_bias(df_5m: pd.DataFrame, cutoff_ts: pd.Timestamp = None) -> int:
    """
    提取日内更高时间框架 (HTF 1h) 的道氏趋势偏向：
      - 仅基于 <= cutoff_ts 已经完全走完的 1 小时 K 线（严格零未来函数）
      - 返回: +1 (多头偏向), -1 (空头偏向), 0 (中性/盘整)
    """
    if df_5m is None or df_5m.empty:
        return 0
    sub_5m = df_5m[df_5m.index <= cutoff_ts] if cutoff_ts is not None else df_5m
    if len(sub_5m) < 24:
        return 0

    # 重采样为 1 小时 K 线
    df_1h = sub_5m.resample("1h").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last"
    }).dropna()
    if len(df_1h) >= 2:
        df_1h = df_1h.iloc[:-1]  # 剔除尚未走完的当期 1h 柱
    if len(df_1h) < 5:
        return 0

    sw_1h = pe.extract_swings(df_1h, order=3)
    if len(sw_1h) >= 2:
        bias = pe.dow_bias(sw_1h, df=df_1h)
        if bias >= 1:
            return 1
        elif bias <= -1:
            return -1

    c_last = float(df_1h["Close"].iloc[-1])
    mid_struct = (float(df_1h["High"].tail(12).max()) + float(df_1h["Low"].tail(12).min())) / 2.0
    return 1 if c_last > mid_struct else (-1 if c_last < mid_struct else 0)


# ==============================================================================
# 5. 日内事件枚举引擎 (Intraday Event Enumeration - Walk-Forward)
# ==============================================================================

def enumerate_day_events(df: pd.DataFrame, strategy_type: str = "day_combined",
                         min_rr: float = DEFAULT_DAY_MIN_RR,
                         buffer_k: float = DEFAULT_DAY_STOP_BUFFER_K,
                         avoid_overlap: bool = True,
                         use_htf_filter: bool = True,
                         slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
                         commission_bps: float = DEFAULT_COMMISSION_BPS,
                         market_data: dict = None,
                         df_1h: pd.DataFrame = None,
                         **kwargs) -> list:
    """
    日内事件枚举器（纯因果 walk-forward，零未来函数）：
    逐交易日推进，在 09:45 确定 ORH/ORL 后开始扫描：
      - strategy_type="orb": 仅扫描开盘区间突破回踩 (ORB)
      - strategy_type="sweep_pdh_pdl" / "2b_pdh_pdl": 仅扫描昨高昨低 2B 猎杀
      - strategy_type="sweep_pmh_pml" / "2b_pmh_pml": 仅扫描盘前高低 2B 猎杀
      - strategy_type="day_combined": 综合价格行为（ORB + 2B 流动性猎杀）
      - strategy_type="day_htf_aligned": 日内多周期共振全闭环 (HTF 1h + MTF 15m + 5m)
    参数说明：
      - avoid_overlap: 模拟单标的在途持仓独占，持仓未平前不重复开仓或反向锁仓；
      - use_htf_filter: 强制开启 1 小时 HTF 顺势门禁（默认 True，仅做与大周期共振方向，除非高确定性 2B 反转）；
      - min_rr: 最小计划盈亏比硬闸门（默认 >= 2.5R）；
      - slippage_bps / commission_bps: 真实滑点与规费（单边 3+1 bps，双边 8 bps）。
    """
    if strategy_type == "day_htf_aligned":
        use_htf_filter = True

    sessions = split_intraday_sessions(df)
    events = []
    session_dates = list(sessions.keys())

    for idx, s_date in enumerate(session_dates):
        df_sess = sessions[s_date]
        prev_sess = sessions[session_dates[idx - 1]] if idx > 0 else None
        lvls = extract_session_key_levels(df_sess, prev_session_df=prev_sess)

        orh, orl = lvls.get("ORH"), lvls.get("ORL")
        pdh, pdl, pdc = lvls.get("PDH"), lvls.get("PDL"), lvls.get("PDC")
        pmh, pml = lvls.get("PMH"), lvls.get("PML")
        bar_rng = lvls.get("bar_rng", 0.5)

        # 09:45 之后才允许触发入场
        times = df_sess.index.time
        n_bars = len(df_sess)

        # 评估大周期 HTF 1h 趋势偏向（基于开盘前已完全走完的历史 1h K 线，纯因果零未来函数）
        htf_bias = 0
        if use_htf_filter:
            sess_open_ts = df_sess.index[0]
            if df_1h is not None and not df_1h.empty:
                sub_1h = df_1h[df_1h.index < sess_open_ts]
                if len(sub_1h) >= 5:
                    sw_1h = pe.extract_swings(sub_1h, order=3)
                    htf_bias = pe.dow_bias(sw_1h, df=sub_1h) if len(sw_1h) >= 2 else 0
                    if htf_bias == 0:
                        c_last = float(sub_1h["Close"].iloc[-1])
                        mid_struct = (float(sub_1h["High"].tail(12).max()) + float(sub_1h["Low"].tail(12).min())) / 2.0
                        htf_bias = 1 if c_last > mid_struct else (-1 if c_last < mid_struct else 0)
            if htf_bias == 0:
                htf_bias = extract_intraday_htf_bias(df, cutoff_ts=sess_open_ts)

        # 每天限制触发次数，防止高频过拟合
        day_trades_count = 0
        max_trades_per_day = 3
        active_exit_idx = -1

        k = 3
        while k < n_bars - 2:
            if day_trades_count >= max_trades_per_day:
                break
            # 必须在 09:45 之后，且在 15:30 之前（留出至少 25 分钟持仓时间）
            if times[k] < DAY_OR_END_TIME or times[k] >= dtime(15, 30):
                k += 1
                continue

            # 若开启持仓独占，且当前 bar 仍处于在途持仓中，跳过
            if avoid_overlap and k <= active_exit_idx:
                k += 1
                continue

            sub_k = df_sess.iloc[:k + 1]
            trig = None

            # 1. 2B PDH / PDL 扫损检测（严格限定 High 仅做空，Low 仅做多）
            # 高确定性 2B 顶流动性猎杀反转允许在多头大势下作为验证性反转触发；2B 底在空头大势下亦然
            if strategy_type in ("sweep_pdh_pdl", "2b_pdh_pdl", "day_combined", "day_htf_aligned"):
                if pdh and not trig:
                    trig = detect_intraday_2b_sweep(sub_k, k, pdh, "PDH", bar_rng, buffer_k=buffer_k, level_type="high")
                    if not trig.get("triggered"):
                        trig = None
                if pdl and not trig:
                    trig = detect_intraday_2b_sweep(sub_k, k, pdl, "PDL", bar_rng, buffer_k=buffer_k, level_type="low")
                    if not trig.get("triggered"):
                        trig = None

            # 2. 2B PMH / PML 扫损检测（严格限定 High 仅做空，Low 仅做多）
            if strategy_type in ("sweep_pmh_pml", "2b_pmh_pml", "day_combined", "day_htf_aligned") and not trig:
                if pmh and not trig:
                    trig = detect_intraday_2b_sweep(sub_k, k, pmh, "PMH", bar_rng, buffer_k=buffer_k, level_type="high")
                    if not trig.get("triggered"):
                        trig = None
                if pml and not trig:
                    trig = detect_intraday_2b_sweep(sub_k, k, pml, "PML", bar_rng, buffer_k=buffer_k, level_type="low")
                    if not trig.get("triggered"):
                        trig = None

            # 3. 2B ORH / ORL 扫损检测
            if strategy_type in ("day_combined", "day_htf_aligned") and not trig:
                if orh and not trig:
                    trig = detect_intraday_2b_sweep(sub_k, k, orh, "ORH", bar_rng, buffer_k=buffer_k, level_type="high")
                    if not trig.get("triggered"):
                        trig = None
                if orl and not trig:
                    trig = detect_intraday_2b_sweep(sub_k, k, orl, "ORL", bar_rng, buffer_k=buffer_k, level_type="low")
                    if not trig.get("triggered"):
                        trig = None

            # 4. ORB 突破回踩检测（常规顺势突破形态：多头大势严禁做空，空头大势严禁做多）
            if strategy_type in ("orb", "day_combined", "day_htf_aligned") and not trig:
                if orh and orl:
                    tr = detect_orb_breakout_retest(sub_k, k, orh, orl, bar_rng, buffer_k=buffer_k)
                    if tr.get("triggered"):
                        # 1h HTF 趋势与宏观非对称做空门禁严格约束：
                        # - 多头突破仅在 1h 偏多或中性时放行 (htf_bias >= 0)
                        # - 常规做空突破仅在 1h 偏空或中性时放行 (htf_bias <= 0)；大牛顺势下一票否决 (rejected_by_macro_short_gate)
                        side_ok = True
                        if use_htf_filter:
                            if tr["side"] == 1 and htf_bias < 0:
                                side_ok = False
                            elif tr["side"] == -1 and htf_bias > 0:
                                side_ok = False  # 顺势长牛拦截常规做空
                        if side_ok:
                            trig = tr

            if trig and trig.get("triggered"):
                # 第 k 根收盘形态确认，第 k+1 根开盘执行入场（严格零未来函数）
                entry_idx = k + 1
                if entry_idx >= n_bars:
                    k += 1
                    continue
                entry_price = float(df_sess["Open"].iloc[entry_idx])
                stop_p = float(trig["tight_stop"])
                side = int(trig["side"])
                risk = abs(entry_price - stop_p)

                # 止损有效性校验与最小风险安全垫（防止 5m 超微噪音）
                min_risk_floor = max(0.01, 0.20 * bar_rng)
                if risk < min_risk_floor:
                    risk = min_risk_floor
                    stop_p = round(entry_price - side * risk, 2)

                if (side == 1 and entry_price <= stop_p) or (side == -1 and entry_price >= stop_p):
                    k += 1
                    continue

                # 低波动标的微利刷单风控拦截 (Low-Volatility Churn Protection)
                # 若止损空间不足覆盖双倍摩擦 (|Entry - SL| / Entry < 16 bps)，无法逾越买卖价差与滑点噪音
                roundtrip_friction = 2.0 * (slippage_bps + commission_bps) / 10000.0
                churn_threshold = DEFAULT_LOW_VOLATILITY_CHURN_MULTIPLIER * roundtrip_friction
                if (risk / entry_price) < churn_threshold - 1e-9:
                    k += 1
                    continue

                # 结构化止盈锚定规划（确保初始计划盈亏比 >= min_rr，默认 2.5R）：
                or_width = (orh - orl) if (orh and orl and orh > orl) else (min_rr * risk)
                if "orb" in trig["pattern"]:
                    # ORB 顺势突破回踩：以开盘区间 1:1 测量目标幅距或 min_rr*risk 中较大者为目标
                    target_dist = max(min_rr * risk, or_width)
                    tp_p = round(entry_price + side * target_dist, 2)
                else:
                    # 2B 猎杀反转：优先以昨日收盘价 PDC 为流动性锚点
                    target_dist = max(min_rr * risk, 2.5 * risk)
                    if side == 1 and pdc and pdc >= entry_price + min_rr * risk:
                        tp_p = pdc
                    elif side == -1 and pdc and pdc <= entry_price - min_rr * risk:
                        tp_p = pdc
                    else:
                        tp_p = round(entry_price + side * target_dist, 2)

                if tp_p <= 0:
                    k += 1
                    continue

                # 全局索引定位
                global_entry_t = df.index.get_loc(df_sess.index[entry_idx])

                events.append({
                    "session_date": s_date,
                    "trigger_t": k,
                    "entry_t": global_entry_t,
                    "entry_date": df_sess.index[entry_idx],
                    "entry_price": entry_price,
                    "stop_price": stop_p,
                    "tp_price": tp_p,
                    "side": side,
                    "pattern": trig["pattern"],
                    "strategy_type": strategy_type,
                    "risk": risk
                })
                day_trades_count += 1

                # 若开启持仓独占，推演本笔出场并跳过在途 K 线
                if avoid_overlap:
                    sim_tr = simulate_day_trade(df_sess, entry_idx, entry_price, side, stop_p, tp_p,
                                                min_rr=min_rr, slippage_bps=slippage_bps,
                                                commission_bps=commission_bps, pattern=trig["pattern"],
                                                htf_bias=htf_bias, market_dow=market_data)
                    if sim_tr.get("status") == "completed":
                        exit_dt = pd.to_datetime(sim_tr["exit_date"])
                        if exit_dt.date() == s_date and exit_dt in df_sess.index:
                            active_exit_idx = df_sess.index.get_loc(exit_dt)
                        else:
                            active_exit_idx = n_bars
            k += 1

    return events


# ==============================================================================
# 6. 合成日内数据生成器 (Synthetic Intraday Data Generator)
# ==============================================================================

def synthetic_intraday_days(n_days: int = 15, seed: int = 42,
                            base_price: float = 150.0) -> pd.DataFrame:
    """
    生成高度仿真的美股多日 5 分钟连续 K 线数据（包含盘前、开盘区间、盘中及尾盘）：
      - 04:00 - 09:30: 盘前低波震荡 (PMH / PML)
      - 09:30 - 09:45: 开盘高波动脉冲 (ORH / ORL)
      - 09:45 - 15:55: 盘中趋势推进或区间震荡 (含 2B 猎杀与 ORB)
      - 15:55 - 16:00: 尾盘收盘平仓
    严格支持可重复执行的无网络单元测试与纯因果零未来函数验证。
    """
    rng = np.random.default_rng(seed)
    # 每个交易日生成从 04:00 到 16:00 的 5 分钟 K 线
    records = []
    curr_close = base_price
    b_dates = pd.bdate_range("2026-09-01", periods=n_days)

    for d in b_dates:
        # 当天日内生成 04:00 到 16:00 共 144 根 5 分钟 K 线
        d_str = d.strftime("%Y-%m-%d")
        ts_range = pd.date_range(f"{d_str} 04:00:00", f"{d_str} 16:00:00", freq="5min", tz=EXCHANGE_TZ)

        # 隔夜跳空
        gap = curr_close * rng.normal(0, 0.005)
        curr_close += gap

        for ts in ts_range:
            t = ts.time()
            # 波动率 U 形特征
            if t < dtime(9, 30):
                vol = 0.0015
            elif t < dtime(10, 0):
                vol = 0.0045   # 开盘高波动
            elif t < dtime(15, 30):
                vol = 0.0020   # 盘中稳定
            else:
                vol = 0.0035   # 尾盘活跃

            ret = rng.normal(0, vol)
            o = curr_close
            c = o * (1.0 + ret)
            spread = max(o, c) * rng.uniform(0.0005, 0.0020)
            h = max(o, c) + spread
            l = min(o, c) - spread
            volume = rng.integers(10000, 200000)

            records.append({
                "Datetime": ts,
                "Open": round(o, 2),
                "High": round(h, 2),
                "Low": round(l, 2),
                "Close": round(c, 2),
                "Volume": volume
            })
            curr_close = c

    df = pd.DataFrame(records).set_index("Datetime")
    return df


# ==============================================================================
# 7. 日内回测分析与报告汇总 (Intraday Summary & Reporting)
# ==============================================================================

def summarize_day_trades(trades: list, label: str = "") -> dict:
    """
    汇总日内交易生命周期指标（毛净双轨、滑点摩擦损耗、胜率、PF、平均R、出场分布等）。
    """
    if not trades:
        return {}

    df_tr = pd.DataFrame(trades)
    n_total = len(df_tr)

    # 毛指标 vs 净指标
    gross_wins = df_tr[df_tr["gross_pnl_pct"] > 0]
    gross_losses = df_tr[df_tr["gross_pnl_pct"] <= 0]
    net_wins = df_tr[df_tr["net_pnl_pct"] > 0]
    net_losses = df_tr[df_tr["net_pnl_pct"] <= 0]

    gross_wr = len(gross_wins) / n_total if n_total else 0.0
    net_wr = len(net_wins) / n_total if n_total else 0.0

    gross_pf = (float(gross_wins["gross_pnl_pct"].sum() / abs(gross_losses["gross_pnl_pct"].sum()))) \
        if len(gross_losses) and gross_losses["gross_pnl_pct"].sum() != 0 else (float("inf") if len(gross_wins) else 0.0)
    net_pf = (float(net_wins["net_pnl_pct"].sum() / abs(net_losses["net_pnl_pct"].sum()))) \
        if len(net_losses) and net_losses["net_pnl_pct"].sum() != 0 else (float("inf") if len(net_wins) else 0.0)

    avg_gross_r = float(df_tr["gross_r"].mean())
    avg_net_r = float(df_tr["net_r"].mean())

    exp_gross = float(df_tr["gross_pnl_pct"].mean())
    exp_net = float(df_tr["net_pnl_pct"].mean())
    avg_friction = float(df_tr["slippage_drag_pct"].mean())

    # 出场分布
    n_stop = int(df_tr["exit_reason"].str.contains("stop_loss").sum())
    n_be = int(df_tr["exit_reason"].str.contains("break_even").sum())
    n_tp = int((df_tr["exit_reason"] == "take_profit").sum())
    n_eod = int(df_tr["exit_reason"].str.contains("eod_forced_close|session_end").sum())

    # 多空细分
    longs = df_tr[df_tr["side"] == 1]
    shorts = df_tr[df_tr["side"] == -1]

    def sub_stats(sub_df):
        if sub_df.empty:
            return {"trades": 0, "net_wr": 0.0, "net_pf": 0.0, "avg_net_r": 0.0}
        w = sub_df[sub_df["net_pnl_pct"] > 0]
        l = sub_df[sub_df["net_pnl_pct"] <= 0]
        pf = (float(w["net_pnl_pct"].sum() / abs(l["net_pnl_pct"].sum()))) if len(l) and l["net_pnl_pct"].sum() != 0 else (float("inf") if len(w) else 0.0)
        return {
            "trades": len(sub_df),
            "net_wr": len(w) / len(sub_df),
            "net_pf": float(pf),
            "avg_net_r": float(sub_df["net_r"].mean()),
            "exp_net": float(sub_df["net_pnl_pct"].mean())
        }

    return {
        "trades": n_total,
        "gross_win_rate": gross_wr,
        "net_win_rate": net_wr,
        "gross_pf": gross_pf,
        "net_pf": net_pf,
        "avg_gross_r": avg_gross_r,
        "avg_net_r": avg_net_r,
        "exp_gross": exp_gross,
        "exp_net": exp_net,
        "avg_friction_drag": avg_friction,
        "hold_bars_mean": float(df_tr["hold_bars"].mean()),
        "mae_med": float(df_tr["mae"].median()),
        "mfe_med": float(df_tr["mfe"].median()),
        "exits": {
            "stop_loss": n_stop,
            "break_even": n_be,
            "take_profit": n_tp,
            "eod_close": n_eod
        },
        "long_stats": sub_stats(longs),
        "short_stats": sub_stats(shorts)
    }
