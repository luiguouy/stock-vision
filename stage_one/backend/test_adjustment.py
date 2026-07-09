# -*- coding: utf-8 -*-
"""前复权 (拆股调整) 单元测试 — 自我验证"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
from data_provider import apply_forward_adjustment

PASS = 0
FAIL = 0

def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}")

print("== 1. 正向拆股 (10:1): 历史价应 ÷10, 最新价不变 ==")
# 拆前收盘 1200, 拆后开盘 120 (10:1 正向拆股)
df = pd.DataFrame({
    'date':   ['2024-06-06', '2024-06-07', '2024-06-10', '2024-06-11'],
    'open':   [1240.0,      1200.0,       120.0,        121.0],
    'high':   [1255.0,      1210.0,       123.0,        122.0],
    'low':    [1183.0,      1190.0,       117.0,        118.0],
    'close':  [1209.0,      1200.0,       121.0,        120.0],
    'volume': [100.0,       100.0,        100.0,        100.0],
})
adj = apply_forward_adjustment(df)
# 最新一根不应被调整
check("最新价不变 (120.0)", abs(adj.iloc[-1]['close'] - 120.0) < 1e-6)
# 拆前最后一根 1200 -> ~120 (÷10)
check("拆前收盘价折算 ≈120 (÷10)", abs(adj.iloc[1]['close'] - 120.0) < 1e-6)
# 成交量反向调整 (历史 ×10)
check("拆前成交量 ×10 (→1000)", abs(adj.iloc[1]['volume'] - 1000.0) < 1e-6)
# 连续: 拆前折算收 ≈ 拆后开
check("折算后拆前收≈拆后开 (连续)", abs(adj.iloc[1]['close'] - adj.iloc[2]['open']) < 1e-6)

print("== 2. 反向拆股 (1:10): 历史价应 ×10 ==")
df2 = pd.DataFrame({
    'date':   ['2024-06-06', '2024-06-07', '2024-06-10', '2024-06-11'],
    'open':   [12.0,        10.0,         100.0,       102.0],
    'high':   [13.0,        11.0,         103.0,       104.0],
    'low':    [11.0,         9.0,          98.0,       100.0],
    'close':  [10.0,        10.0,         101.0,       100.0],
    'volume': [100.0,       100.0,        100.0,       100.0],
})
adj2 = apply_forward_adjustment(df2)
check("最新价不变 (100.0)", abs(adj2.iloc[-1]['close'] - 100.0) < 1e-6)
check("拆前收盘价 ×10 (→100)", abs(adj2.iloc[1]['close'] - 100.0) < 1e-6)
check("拆前成交量 ÷10 (→10)", abs(adj2.iloc[1]['volume'] - 10.0) < 1e-6)

print("== 3. 无拆股普通波动 (单日 -30%) 不应误判 ==")
df3 = pd.DataFrame({
    'date':   ['2024-01-01', '2024-01-02', '2024-01-03'],
    'open':   [100.0,        70.0,         68.0],
    'high':   [101.0,        72.0,         69.0],
    'low':    [99.0,         69.0,         67.0],
    'close':  [100.0,        70.0,         68.0],
    'volume': [100.0,       100.0,        100.0],
})
adj3 = apply_forward_adjustment(df3)
check("普通波动不被调整 (收仍≈70)", abs(adj3.iloc[1]['close'] - 70.0) < 1e-6)

print("== 4. 空/单根 防御 ==")
check("空 DataFrame 返回空", apply_forward_adjustment(pd.DataFrame()).empty)
check("单根不被调整", len(apply_forward_adjustment(df3.head(1))) == 1)

print("== 5. 多拆股累计 (4:1 + 10:1 = 40x) ==")
# 2021-07 4:1, 2024-06 10:1
df5 = pd.DataFrame({
    'date':   ['2021-07-15', '2021-07-19', '2024-06-07', '2024-06-10', '2024-06-11'],
    'open':   [800.0,       200.0,        1200.0,       120.0,        121.0],
    'high':   [810.0,       210.0,        1210.0,       123.0,        122.0],
    'low':    [790.0,       190.0,        1190.0,       117.0,        118.0],
    'close':  [800.0,       200.0,        1200.0,       121.0,        120.0],
    'volume': [100.0,       100.0,        100.0,        100.0,        100.0],
})
adj5 = apply_forward_adjustment(df5)
# 2021-07-15 跨两次拆股 -> ÷40 -> 800/40=20
check("最早价累计 ÷40 (800→20)", abs(adj5.iloc[0]['close'] - 20.0) < 1e-6)
check("最新价不变 (120.0)", abs(adj5.iloc[-1]['close'] - 120.0) < 1e-6)

print(f"\n结果: {PASS} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
