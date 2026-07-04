# -*- coding: utf-8 -*-
"""
智能股票技术分析平台 - 第一阶段 (MVP) 技术分析核心模块
包含支撑/阻力位计算（基于局部价格极值 + 密度聚类）与区间最大涨跌幅统计逻辑。
"""

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema
from typing import List, Dict, Any

def calculate_sr_levels(df: pd.DataFrame, window: int = 5, distance_pct: float = 0.015) -> List[Dict[str, Any]]:
    """
    自适应阻力支撑位算法。
    
    采用：
      1. 最近20天日均波幅(ATR近似)自适应价格合并区间。
      2. 半衰期为60天的指数衰减权重(近强远弱)。
      3. 基于最新价格分类支阻(支阻互换)，并根据 基础累加权重 * 价格临近度 综合得分排序，
         选出当前对交易最具操作指导意义的关键位置。
    """
    if df.empty or len(df) < (window * 2 + 1):
        return []

    try:
        # 最新价和总长度
        latest_price = float(df['close'].iloc[-1])
        total_len = len(df)
        
        # 1. 自适应聚类阈值 (根据最近20天均日内波幅 ATR 近似)
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
            
        # 3. 价格合并与时间衰减权重累加 (半衰期为60天)
        # 按价格从低到高排序
        extrema.sort(key=lambda x: x[0])
        
        clusters = [] # 元素格式：{'price': float, 'weight': float, 'count': int}
        
        for price, idx in extrema:
            # 计算该点的时间衰减权重：今天为1.0，60天前为0.5，120天前为0.25
            days_ago = total_len - 1 - idx
            weight = float((0.5) ** (days_ago / 60.0))
            
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
            # 使用倒数函数进行衰减控制
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
                'weight': c['weight'],
                'stars': stars,
                'level': level,
                'score': score
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
    计算特定日期区间内的最大上涨与最大下跌幅度及相应的起始和结束日期。
    
    参数:
        df: 包含 ['date', 'high', 'low'] 字段的 Pandas DataFrame。
        start_date: 区间开始日期 (YYYY-MM-DD)。
        end_date: 区间结束日期 (YYYY-MM-DD)。
        
    返回:
        字典，包含 max_rise (最大上涨) 和 max_fall (最大下跌) 信息。
    """
    default_result = {
        "max_rise": {"pct": 0.0, "start": "", "end": ""},
        "max_fall": {"pct": 0.0, "start": "", "end": ""}
    }
    
    if df.empty or not start_date or not end_date:
        return default_result
        
    try:
        # 筛选指定区间的数据并重置索引
        mask = (df['date'] >= start_date) & (df['date'] <= end_date)
        sub_df = df.loc[mask].reset_index(drop=True)
        
        if sub_df.empty:
            return default_result
            
        # 1. 计算最大上涨 (寻找区间内的最低点，以及该最低点之后的最高点)
        min_idx = int(sub_df['low'].idxmin())
        after_min_df = sub_df.loc[min_idx:]
        
        if not after_min_df.empty:
            max_after_min_idx = int(after_min_df['high'].idxmax())
            low_price = float(sub_df.loc[min_idx]['low'])
            high_price = float(sub_df.loc[max_after_min_idx]['high'])
            
            if low_price > 0:
                max_up_pct = ((high_price - low_price) / low_price) * 100
            else:
                max_up_pct = 0.0
                
            up_start = sub_df.loc[min_idx]['date']
            up_end = sub_df.loc[max_after_min_idx]['date']
        else:
            max_up_pct, up_start, up_end = 0.0, "", ""
            
        # 2. 计算最大下跌 (寻找区间内的最高点，以及该最高点之后的最低点)
        max_idx = int(sub_df['high'].idxmax())
        after_max_df = sub_df.loc[max_idx:]
        
        if not after_max_df.empty:
            min_after_max_idx = int(after_max_df['low'].idxmin())
            high_price = float(sub_df.loc[max_idx]['high'])
            low_price = float(sub_df.loc[min_after_max_idx]['low'])
            
            if high_price > 0:
                max_down_pct = ((low_price - high_price) / high_price) * 100
            else:
                max_down_pct = 0.0
                
            down_start = sub_df.loc[max_idx]['date']
            down_end = sub_df.loc[min_after_max_idx]['date']
        else:
            max_down_pct, down_start, down_end = 0.0, "", ""
            
        return {
            "max_rise": {"pct": round(max_up_pct, 2), "start": up_start, "end": up_end},
            "max_fall": {"pct": round(max_down_pct, 2), "start": down_start, "end": down_end}
        }
        
    except Exception as e:
        print(f"Error calculating range stats: {str(e)}")
        return default_result
