# -*- coding: utf-8 -*-
"""
智能股票技术分析平台 - 技术分析核心模块
包含支撑/阻力位计算（基于局部价格极值 + 密度聚类）与区间最大涨跌幅统计逻辑。

支持多周期分析: 支撑阻力位会随 K 线周期 (4h/1d/1w/1M) 自适应调整算法参数，
使不同周期下呈现该周期级别的关键价位。
"""

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema
from typing import List, Dict, Any


# ============================================================
# 多周期算法参数表
# ============================================================
# 每个周期对应不同的:
#   half_life: 时间衰减半衰期 (K线根数)，近强远弱
#   window:    argrelextrema 局部极值窗口
#
# 设计思路:
#   4h  -> 半衰期 30 根 (约5个交易日)，捕捉短期波段高低点
#   1d  -> 半衰期 60 根 (约3个月)，  保持原有日线逻辑
#   1w  -> 半衰期 26 根 (约半年)，  适配周线级别中期趋势
#   1M  -> 半衰期 12 根 (约1年)，   适配月线级别长期结构
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
    period: str = '1d'
) -> List[Dict[str, Any]]:
    """
    自适应阻力支撑位算法 (多周期版本)。

    采用：
      1. 最近20根K线日均波幅(ATR近似)自适应价格合并区间。
      2. 基于 period 的指数衰减权重(近强远弱)。
      3. 基于最新价格分类支阻(支阻互换)，并根据 基础累加权重 * 价格临近度 综合得分排序，
         选出当前对交易最具操作指导意义的关键位置。

    参数:
        df:          K线 DataFrame，需含 ['date','open','high','low','close','volume']
        window:      局部极值窗口 (若为默认值5且period非日线，则自动按周期选取)
        distance_pct: 价格合并距离百分比 (已废弃，保留向后兼容)
        period:      K线周期 '4h'/'1d'/'1w'/'1M'，决定半衰期等参数
    """
    if df.empty:
        return []

    # 根据周期获取算法参数
    params = PERIOD_PARAMS.get(period, PERIOD_PARAMS['1d'])
    half_life = params['half_life']
    # 若调用方未显式指定非默认 window，则使用周期对应的默认值
    if window == 5 and period != '1d':
        window = params['window']

    if len(df) < (window * 2 + 1):
        return []

    try:
        # 最新价和总长度
        latest_price = float(df['close'].iloc[-1])
        total_len = len(df)

        # 1. 自适应聚类阈值 (根据最近20根K线均波幅 ATR 近似)
        df_copy = df.copy()
        df_copy['daily_range'] = df_copy['high'] - df_copy['low']
        lookback = min(20, total_len)
        atr_approx = float(df_copy['daily_range'].iloc[-lookback:].mean())

        # 设置安全上下边界 (防止低价股过窄，高价股过宽)
        min_dist = latest_price * 0.006
        max_dist = latest_price * 0.025
        abs_threshold = max(min_dist, min(atr_approx * 0.8, max_dist))

        high_values = df['high'].values
        low_values = df['low'].values

        # 2. 寻找极值点及其所在的K线索引
        max_idx = argrelextrema(high_values, np.greater_equal, order=window)[0]
        min_idx = argrelextrema(low_values, np.less_equal, order=window)[0]

        # 提取极点，包含 (价格, 所在 K 线索引)
        extrema = []
        for idx in max_idx:
            extrema.append((float(high_values[idx]), int(idx)))
        for idx in min_idx:
            extrema.append((float(low_values[idx]), int(idx)))

        if not extrema:
            return []

        # 3. 价格合并与时间衰减权重累加 (半衰期随周期变化)
        # 按价格从低到高排序
        extrema.sort(key=lambda x: x[0])

        clusters = []  # 元素格式：{'price': float, 'weight': float, 'count': int}

        for price, idx in extrema:
            # 计算该点的时间衰减权重: 最新K线=1.0，half_life根前=0.5
            bars_ago = total_len - 1 - idx
            weight = float((0.5) ** (bars_ago / float(half_life)))

            merged = False
            for c in clusters:
                # 判断价格差是否在自适应阈值内
                if abs(c['price'] - price) < abs_threshold:
                    # 动态更新价格均值
                    c['price'] = (c['price'] * c['weight'] + price * weight) / (c['weight'] + weight)
                    c['weight'] += weight
                    c['count'] += 1
                    merged = True
                    break

            if not merged:
                clusters.append({
                    'price': price,
                    'weight': weight,
                    'count': 1
                })

        # 4. 根据最新价，对所有累加出的关键位置重划支阻 (支阻互换机制)
        # 并引入临近度惩罚因子，计算综合操作指导分 (Score)
        support_candidates = []
        resistance_candidates = []

        for c in clusters:
            level_price = c['price']

            # 计算最新价的临近度系数 (接近程度越小，越靠近当前，临近度得分越高)
            dist_pct = abs(level_price - latest_price) / latest_price
            proximity_factor = 1.0 / (1.0 + 8.0 * dist_pct)

            # 综合得分
            score = c['weight'] * proximity_factor

            # 评估星级
            if c['weight'] >= 3.5:
                stars = 5
                level = 'Strong'
            elif c['weight'] >= 2.0:
                stars = 3
                level = 'Medium'
            else:
                stars = 2
                level = 'Weak'

            item = {
                'price': round(level_price, 2),
                'count': c['count'],
                'weight': round(c['weight'], 4),
                'stars': stars,
                'level': level,
                'score': round(score, 4)
            }

            if level_price < latest_price:
                item['type'] = 'support'
                support_candidates.append(item)
            elif level_price > latest_price:
                item['type'] = 'resistance'
                resistance_candidates.append(item)

        # 5. 按照综合指导得分 Score 倒序排序，各自挑选前 3 个
        top_support = sorted(support_candidates, key=lambda x: x['score'], reverse=True)[:3]
        top_resistance = sorted(resistance_candidates, key=lambda x: x['score'], reverse=True)[:3]

        return top_resistance + top_support

    except Exception as e:
        print(f"Error calculating SR levels: {str(e)}")
        return []


def calculate_range_stats(df: pd.DataFrame, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    计算特定日期区间内的最大连贯上涨与最大连贯下跌幅度及相应的起始和结束日期。

    采用"运行谷值 / 运行峰值"的最大反弹 / 最大回撤算法：
      - 最大连贯上涨：扫描区间内每个低点（运行中的最低点），记录从该谷值到其后
        最高点的累计涨幅峰值。不再只锁定"全局最低点之后"，对任何区间都会响应。
      - 最大连贯下跌（最大回撤）：扫描区间内每个高点（运行中的最高点），记录从该
        峰值到其后最低点的最大跌幅。旧算法只取"全局最高点之后"的最低点，当区间
        最高点落在末尾时（近期上涨行情极常见）会退化为 0 且不随区间变化，故改为
        全程跟踪运行峰值，能正确捕获发生在最高点之前的大跌。

    参数:
        df: 包含 ['date', 'high', 'low'] 字段的 Pandas DataFrame。
        start_date: 区间开始日期 (YYYY-MM-DD 或 YYYY-MM-DD HH:MM)。
        end_date: 区间结束日期 (YYYY-MM-DD 或 YYYY-MM-DD HH:MM)。

    返回:
        字典，包含 max_rise (最大连贯上涨) 和 max_fall (最大连贯下跌) 信息。
    """
    default_result = {
        "max_rise": {"pct": 0.0, "start": "", "end": ""},
        "max_fall": {"pct": 0.0, "start": "", "end": ""}
    }

    if df.empty or not start_date or not end_date:
        return default_result

    try:
        # 筛选指定区间的数据并重置索引
        # 使用字符串比较，兼容 'YYYY-MM-DD' 和 'YYYY-MM-DD HH:MM' 两种格式
        mask = (df['date'] >= start_date) & (df['date'] <= end_date)
        sub_df = df.loc[mask].reset_index(drop=True)

        if sub_df.empty:
            return default_result

        highs = sub_df['high'].values.astype(float)
        lows = sub_df['low'].values.astype(float)
        dates = sub_df['date'].values

        # 1. 最大连贯上涨：从运行谷值到其后最高点的区间涨幅峰值
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

        # 2. 最大连贯下跌（最大回撤）：从运行峰值到其后最低点的区间跌幅谷值
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
            "max_fall": {"pct": round(max_fall_pct, 2), "start": str(fall_start), "end": str(fall_end)}
        }

    except Exception as e:
        print(f"Error calculating range stats: {str(e)}")
        return default_result
