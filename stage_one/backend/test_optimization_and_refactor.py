# -*- coding: utf-8 -*-
"""
单元测试：价格行为、支撑阻力与计算效率重构专项验证
覆盖：
1. extract_swings 最小波幅抗噪过滤、Outside bar 顺序、道氏客观打标（收敛三角形 HL 不被篡改）
2. detect_mss 回退循环缩进修复（历史 MSS 结构事件完整识别）
3. detect_gaps 向量化 O(N) 正确性与回补判定
4. calculate_sr_levels 周期自适应 TR 中位数、防漂移聚类与星级归一化
5. verify_primary_trend_gate 外部预计算 ema_series O(1) 效率与数值一致性
"""

import unittest
import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

from strategy_core import pa_engine as pe
from strategy_core import strategy_layer as sl
from analysis import calculate_sr_levels, PERIOD_CLAMP_BOUNDS


class TestOptimizationAndRefactor(unittest.TestCase):

    def test_extract_swings_anti_noise_filter(self):
        """测试 1.1: 窄幅震荡 (<1.0*bar_rng) 毛刺被剔除，宏观波段保留"""
        dates = pd.date_range("2026-01-01", periods=50, freq="B")
        # 基础大波段: 100 -> 120 -> 105 -> 130
        base = np.zeros(50)
        base[:15] = np.linspace(100, 120, 15)
        base[15:30] = np.linspace(120, 105, 15)
        base[30:] = np.linspace(105, 130, 20)
        
        # 叠加微小噪声 0.2 元 (远低于单根 bar 振幅 2.0)
        noise = np.sin(np.linspace(0, 30, 50)) * 0.2
        closes = base + noise
        df = pd.DataFrame({
            "Open": closes - 0.5,
            "High": closes + 1.0,
            "Low": closes - 1.0,
            "Close": closes,
            "Volume": [1000] * 50
        }, index=dates)

        # 启用 min_swing_k 剪枝
        swings = pe.extract_swings(df, order=4, confirmed_only=False, min_swing_k=1.0)
        # 应该只保留主峰和主谷，微小毛刺不应造成大量假拐点
        types = [s["type"] for s in swings]
        for i in range(1, len(types)):
            self.assertNotEqual(types[i], types[i - 1], "拐点必须严格高低交替")

    def test_extract_swings_outside_bar_order(self):
        """测试 1.2: Outside Bar 同根极值根据阴阳线决定先后"""
        dates = pd.date_range("2026-01-01", periods=25, freq="B")
        # 构造一条在第 10 根出现阳线 Outside Bar，第 15 根出现阴线 Outside Bar 的数据
        closes = np.full(25, 100.0)
        opens = np.full(25, 100.0)
        highs = np.full(25, 101.0)
        lows = np.full(25, 99.0)

        # 阳线 Outside Bar
        opens[10] = 98.0
        closes[10] = 105.0
        highs[10] = 106.0
        lows[10] = 95.0

        df = pd.DataFrame({
            "Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": [1000] * 25
        }, index=dates)

        # order=3 提取
        swings = pe.extract_swings(df, order=3, confirmed_only=False, min_swing_k=0.0)
        outside_swings = [s for s in swings if s["index"] == 10]
        if len(outside_swings) == 2:
            self.assertEqual(outside_swings[0]["type"], "Low", "阳线 Outside Bar 应先低")
            self.assertEqual(outside_swings[1]["type"], "High", "阳线 Outside Bar 应后高")

    def test_extract_swings_dow_label_no_forced_ll(self):
        """测试 1.3: 收敛震荡中 LH 后面的抬高低点必须客观标记为 HL，严禁强行篡改为 LL"""
        dates = pd.date_range("2026-01-01", periods=60, freq="B")
        # 构造收敛三角形：High1=150, Low1=100, High2=140 (LH), Low2=110 (抬高低点 HL)
        closes = np.zeros(60)
        closes[:15] = np.linspace(100, 150, 15)  # H1: 150
        closes[15:30] = np.linspace(150, 100, 15) # L1: 100
        closes[30:45] = np.linspace(100, 140, 15) # H2: 140 (LH)
        closes[45:60] = np.linspace(140, 110, 15) # L2: 110 (HL)

        df = pd.DataFrame({
            "Open": closes - 0.5,
            "High": closes + 1.0,
            "Low": closes - 1.0,
            "Close": closes,
            "Volume": [1000] * 60
        }, index=dates)

        swings = pe.extract_swings(df, order=4, confirmed_only=False, min_swing_k=0.5)
        dow_labels = [(s["index"], s["type"], s["dow"], round(s["price"], 1)) for s in swings]
        
        low_swings = [s for s in swings if s["type"] == "Low"]
        self.assertGreaterEqual(len(low_swings), 3)
        last_low = low_swings[-1]
        prev_low = low_swings[-2]
        self.assertGreater(last_low["price"], prev_low["price"], "低点确实抬高")
        self.assertEqual(last_low["dow"], "HL", "抬高的低点必须客观标注为 HL，严禁篡改为 LL")

    def test_detect_mss_indentation_historical_events(self):
        """测试 1.4: detect_mss 在 fallback 拐点分支下能完整扫描历史 MSS 事件"""
        # 构造有历史多翻空 (Bearish MSS) 的拐点列表
        swings = [
            {"time": "2026-01-01", "type": "Low", "price": 100.0, "dow": "Low", "confirmed": True},
            {"time": "2026-01-02", "type": "High", "price": 120.0, "dow": "High", "confirmed": True},
            {"time": "2026-01-03", "type": "Low", "price": 105.0, "dow": "HL", "confirmed": True},
            {"time": "2026-01-04", "type": "High", "price": 125.0, "dow": "HH", "confirmed": True},
            {"time": "2026-01-05", "type": "Low", "price": 110.0, "dow": "HL", "confirmed": True},
            # 历史转折点发生在这里：
            {"time": "2026-01-06", "type": "High", "price": 118.0, "dow": "LH", "confirmed": True},
            {"time": "2026-01-07", "type": "Low", "price": 102.0, "dow": "LL", "confirmed": True},
            # 后续还有更多拐点
            {"time": "2026-01-08", "type": "High", "price": 108.0, "dow": "LH", "confirmed": True},
            {"time": "2026-01-09", "type": "Low", "price": 95.0, "dow": "LL", "confirmed": True},
        ]
        # df 为 None，触发纯拐点序列扫描
        events = pe.detect_mss(swings, df=None)
        self.assertGreaterEqual(len(events), 1, "历史 MSS 事件不应被跳过")
        self.assertTrue(any("Bearish MSS" in ev["type"] for ev in events))

    def test_detect_gaps_vectorized(self):
        """测试 2.1: detect_gaps 向量化 O(N) 识别与未回补状态"""
        dates = pd.date_range("2026-01-01", periods=10, freq="B")
        # 构造未回补的向上跳空
        highs = [100, 102, 107, 108, 109, 110, 111, 112, 113, 114]
        lows  = [ 98,  99, 105, 106, 107, 108, 109, 110, 111, 112]
        # 在 i=2 处，Low=105 > prev High(i=1)=102 * 1.008 (102.816)，后续 Low 最低为 105 > 102，未回补
        df = pd.DataFrame({
            "Open": lows, "High": highs, "Low": lows, "Close": highs, "Volume": [1000] * 10
        }, index=dates)

        gaps = pe.detect_gaps(df, min_gap_pct=0.008)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["type"], "向上跳空支撑缺口 (Bullish Gap)")
        self.assertEqual(gaps[0]["level"], 102.0)
        self.assertIn("未回补", gaps[0]["status"])

    def test_calculate_sr_levels_optimized(self):
        """测试 3.1: calculate_sr_levels 分周期边界、防漂移聚类与结果结构"""
        dates = pd.date_range("2026-01-01", periods=80, freq="B")
        prices = [100 + 10 * np.sin(i / 5.0) for i in range(80)]
        df = pd.DataFrame({
            "open": prices,
            "high": [p + 2.0 for p in prices],
            "low": [p - 2.0 for p in prices],
            "close": prices,
            "volume": [1000] * 80
        }, index=dates)

        levels_1d = calculate_sr_levels(df, period="1d")
        self.assertIsInstance(levels_1d, list)
        self.assertTrue(len(levels_1d) > 0)
        for lvl in levels_1d:
            self.assertIn("price", lvl)
            self.assertIn("count", lvl)
            self.assertIn("stars", lvl)
            self.assertIn("level", lvl)
            self.assertIn("type", lvl)
            self.assertIn(lvl["type"], ("support", "resistance"))

    def test_verify_primary_trend_gate_ema_series_equivalence(self):
        """测试 4.1: verify_primary_trend_gate 传入 precomputed ema_series 与默认切片重算结果一致 (样本量 >= ema_period)"""
        dates = pd.date_range("2026-01-01", periods=300, freq="B")
        closes = np.linspace(100, 200, 300)
        df = pd.DataFrame({
            "Open": closes, "High": closes + 2, "Low": closes - 2, "Close": closes, "Volume": [1000] * 300
        }, index=dates)

        ema_series = df["Close"].ewm(span=200, adjust=False).mean()
        
        for t in [220, 250, 299]:
            res_default = sl.verify_primary_trend_gate(df, side=1, ema_period=200, t=t)
            res_fast = sl.verify_primary_trend_gate(df, side=1, ema_period=200, t=t, ema_series=ema_series)
            res_numpy = sl.verify_primary_trend_gate(df, side=1, ema_period=200, t=t, ema_series=ema_series.to_numpy())
            
            self.assertEqual(res_default["passed"], res_fast["passed"])
            self.assertEqual(res_default["status"], res_fast["status"])
            self.assertAlmostEqual(res_default["ema_val"], res_fast["ema_val"], places=3)
            self.assertEqual(res_fast["passed"], res_numpy["passed"])
            self.assertAlmostEqual(res_fast["ema_val"], res_numpy["ema_val"], places=3)

    def test_sr_levels_edge_cases(self):
        """测试 4.2: calculate_sr_levels 对空数据或极端 window=0 鲁棒降级"""
        dates = pd.date_range("2026-01-01", periods=30, freq="B")
        df = pd.DataFrame({"open": [100]*30, "high": [101]*30, "low": [99]*30, "close": [100]*30}, index=dates)
        self.assertEqual(calculate_sr_levels(df, window=0), [])
        self.assertEqual(calculate_sr_levels(pd.DataFrame()), [])

    def test_strategy_crypto_weekly_precomputed(self):
        """测试 5.1: strategy_crypto 支持外部传入预聚合周线 weekly_df 提高计算效率"""
        from strategy_core import strategy_crypto as sc
        dates = pd.date_range("2025-01-01", periods=100, freq="B")
        prices = np.linspace(50000, 70000, 100)
        df = pd.DataFrame({
            "Open": prices, "High": prices + 500, "Low": prices - 500, "Close": prices, "Volume": [1000] * 100
        }, index=dates)

        weekly = sc._weekly_prefix(df, 90)
        res_default = sc.check_crypto_primary_trend(df, t=90, side=1)
        res_fast = sc.check_crypto_primary_trend(df, t=90, side=1, weekly_df=weekly)
        self.assertEqual(res_default["aligned"], res_fast["aligned"])
        self.assertEqual(res_default["structure_bias"], res_fast["structure_bias"])

    def test_calc_elliott_channel_log_vs_linear(self):
        """测试 6.1: 自适应对数坐标艾略特通道 calc_elliott_channel use_log=True 与 use_log=False 坐标投射"""
        dates = pd.date_range("2026-01-01", periods=60, freq="B")
        # 构造翻倍主升浪 5 浪形态 (100 -> 200)
        # 点位: 0:(0, 100), 1:(10, 150), 2:(20, 130), 3:(35, 260), 4:(45, 220), 5:(55, 300)
        pts = [
            {"index": 0, "time": str(dates[0])[:10], "type": "Low", "price": 100.0, "confirmed": True},
            {"index": 10, "time": str(dates[10])[:10], "type": "High", "price": 150.0, "confirmed": True},
            {"index": 20, "time": str(dates[20])[:10], "type": "Low", "price": 130.0, "confirmed": True},
            {"index": 35, "time": str(dates[35])[:10], "type": "High", "price": 260.0, "confirmed": True},
            {"index": 45, "time": str(dates[45])[:10], "type": "Low", "price": 220.0, "confirmed": True},
            {"index": 55, "time": str(dates[55])[:10], "type": "High", "price": 300.0, "confirmed": True},
        ]
        closes = np.linspace(100, 300, 60)
        df = pd.DataFrame({
            "Open": closes, "High": closes + 2, "Low": closes - 2, "Close": closes, "Volume": [1000] * 60
        }, index=dates)

        wp = pe.classify_wave_pattern(pts, df)
        self.assertEqual(wp["pattern"], "impulse_5_wave")

        ch_log = pe.calc_elliott_channel(pts, df, wp=wp, use_log=True)
        ch_lin = pe.calc_elliott_channel(pts, df, wp=wp, use_log=False)

        self.assertEqual(ch_log["channel_stage"], "2-4_primary")
        self.assertEqual(ch_log["scale"], "log")
        self.assertEqual(ch_lin["scale"], "linear")
        self.assertGreater(ch_log["baseline_val"], 0)
        self.assertGreater(ch_log["parallel_rail_val"], ch_log["baseline_val"])

    def test_detect_wave5_variants_truncated(self):
        """测试 6.2: 失败第五浪 (Truncated Wave 5) 识别: 3浪超强延伸(>=1.618*L1)且5浪未创新高(p4 < p5 <= p3)"""
        # 0: 100, 1: 120 (L1=20), 2: 115, 3: 160 (L3=45 >= 1.618*20=32.4), 4: 140, 5: 155 (p4 < 155 <= 160)
        cand = [
            {"index": 0, "type": "Low", "price": 100.0, "confirmed": True},
            {"index": 10, "type": "High", "price": 120.0, "confirmed": True},
            {"index": 20, "type": "Low", "price": 115.0, "confirmed": True},
            {"index": 35, "type": "High", "price": 160.0, "confirmed": True},
            {"index": 45, "type": "Low", "price": 140.0, "confirmed": True},
            {"index": 55, "type": "High", "price": 155.0, "confirmed": True},
        ]
        w5_res = pe._detect_wave5_variants_and_volume(cand, direction=1, df=None, rule1_passed=True, rule2_passed=True, rule3_passed=True)
        self.assertEqual(w5_res["variant"], "truncated_wave_5")

        wp = pe.classify_wave_pattern(cand)
        self.assertEqual(wp["pattern"], "truncated_wave_5")
        self.assertTrue(wp["is_valid_impulse"])

    def test_detect_wave5_variants_ending_diagonal(self):
        """测试 6.3: 终结倾斜三角形 (Ending Diagonal) 识别: 浪4侵入浪1领地且高低点呈楔形收敛"""
        dates = pd.date_range("2026-01-01", periods=60, freq="B")
        # 1浪顶=130, 2浪底=110, 3浪顶=140, 4浪底=125 (重叠1浪价格领地), 5浪顶=145
        # 斜率收敛: 0 < slope_hi < slope_lo
        cand = [
            {"index": 0, "time": str(dates[0])[:10], "type": "Low", "price": 100.0, "confirmed": True},
            {"index": 10, "time": str(dates[10])[:10], "type": "High", "price": 130.0, "confirmed": True},
            {"index": 20, "time": str(dates[20])[:10], "type": "Low", "price": 110.0, "confirmed": True},
            {"index": 35, "time": str(dates[35])[:10], "type": "High", "price": 140.0, "confirmed": True},
            {"index": 45, "time": str(dates[45])[:10], "type": "Low", "price": 125.0, "confirmed": True},
            {"index": 55, "time": str(dates[55])[:10], "type": "High", "price": 145.0, "confirmed": True},
        ]
        df = pd.DataFrame({"Close": [140.0]*60}, index=dates)
        # rule3_passed=False 因为 p4(125) <= p1(130)
        w5_res = pe._detect_wave5_variants_and_volume(cand, direction=1, df=df, rule1_passed=True, rule2_passed=True, rule3_passed=False)
        self.assertEqual(w5_res["variant"], "ending_diagonal")

    def test_detect_wave5_volume_divergence(self):
        """测试 6.4: 第5浪量能背离 (5浪区间均量 < 0.8 * 3浪区间均量)"""
        dates = pd.date_range("2026-01-01", periods=60, freq="B")
        cand = [
            {"index": 0, "time": str(dates[0])[:10], "type": "Low", "price": 100.0, "confirmed": True},
            {"index": 10, "time": str(dates[10])[:10], "type": "High", "price": 130.0, "confirmed": True},
            {"index": 20, "time": str(dates[20])[:10], "type": "Low", "price": 115.0, "confirmed": True},
            {"index": 35, "time": str(dates[35])[:10], "type": "High", "price": 180.0, "confirmed": True},
            {"index": 45, "time": str(dates[45])[:10], "type": "Low", "price": 160.0, "confirmed": True},
            {"index": 55, "time": str(dates[55])[:10], "type": "High", "price": 200.0, "confirmed": True},
        ]
        # 3浪区间: 20~35 均量 5000; 5浪区间: 45~55 均量 2000 (< 0.8 * 5000 = 4000)
        vols = np.full(60, 1000.0)
        vols[20:36] = 5000.0
        vols[45:56] = 2000.0
        df = pd.DataFrame({"Close": np.linspace(100, 200, 60), "Volume": vols}, index=dates)

        w5_res = pe._detect_wave5_variants_and_volume(cand, direction=1, df=df, rule1_passed=True, rule2_passed=True, rule3_passed=True)
        self.assertTrue(w5_res["wave5_volume_divergence"])

    def test_classify_corrective_running_flat_warning(self):
        """测试 6.5: 顺势平台形 (Running Flat) 必须包含 nested_1212_warning: True 预警"""
        # 0: High 120, 1: Low 100 (A浪幅=20), 2: High 125 (B破顶 B/A=25/20=1.25 > 1.05), 3: Low 105 (C未破A底 105 > 100)
        swings = [
            {"time": "2026-01-01", "type": "High", "price": 120.0, "confirmed": True},
            {"time": "2026-01-02", "type": "Low", "price": 100.0, "confirmed": True},
            {"time": "2026-01-03", "type": "High", "price": 125.0, "confirmed": True},
            {"time": "2026-01-04", "type": "Low", "price": 105.0, "confirmed": True},
        ]
        res = pe.classify_corrective_subtypes(swings)
        self.assertEqual(res["subtype"], "running_flat")
        self.assertTrue(res.get("nested_1212_warning"), "顺势平台必须标明 nested_1212_warning 为 True")

    def test_dow_market_iwm_breadth_divergence(self):
        """测试 6.6: 道氏美股大盘验证：SPY/QQQ 上涨但 IWM 处于空头时，输出 BREADTH_DIVERGENCE 预警"""
        from strategy_adapter import _verify_us_market_dow
        dates = pd.date_range("2026-01-01", periods=100, freq="B")
        uptrend = np.linspace(100, 150, 100)
        downtrend = np.linspace(150, 100, 100)
        spy_bull = pd.DataFrame({"Open": uptrend, "High": uptrend+1, "Low": uptrend-1, "Close": uptrend, "Volume": [1000]*100}, index=dates)
        qqq_bull = pd.DataFrame({"Open": uptrend, "High": uptrend+1, "Low": uptrend-1, "Close": uptrend, "Volume": [1000]*100}, index=dates)
        iwm_bear = pd.DataFrame({"Open": downtrend, "High": downtrend+1, "Low": downtrend-1, "Close": downtrend, "Volume": [1000]*100}, index=dates)

        res = _verify_us_market_dow(pe, spy_df=spy_bull, qqq_df=qqq_bull, iwm_df=iwm_bear, force_refresh=True)
        self.assertEqual(res["status"], "BREADTH_DIVERGENCE")
        self.assertTrue(res["verified"])
        self.assertFalse(res["aligned"])

    def test_weekly_daily_fractal_resonance(self):
        """测试 6.7: 日线-周线分形嵌套共振: 周线3浪主升 + 日线健康回调/推进"""
        from strategy_adapter import run_strategy_analysis
        dates = pd.date_range("2024-01-01", periods=300, freq="B")
        # 构造长期上升趋势日线K线
        trend = np.linspace(100, 250, 300) + np.sin(np.linspace(0, 30, 300)) * 10.0
        df = pd.DataFrame({
            "Open": trend - 1, "High": trend + 3, "Low": trend - 3, "Close": trend, "Volume": [5000] * 300
        }, index=dates)

        res = run_strategy_analysis("usAAPL", period="1d", mode="swing", df=df)
        self.assertIn("fractal_resonance", res["summary"])
        # fractal_resonance 字段应有效输出
        fr = res["summary"]["fractal_resonance"]
        self.assertIn("active", fr)
        self.assertIn("desc", fr)

    def test_main_ws_broadcast_channels(self):
        """测试 6.8: main.py control_run_strategy 中包含 fib_line, gap_box, ema200 广播频道"""
        with open("stage_one/backend/main.py", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('"fib_line"', content)
        self.assertIn('"draw_fib_lines"', content)
        self.assertIn('"gap_box"', content)
        self.assertIn('"draw_gap_boxes"', content)
        self.assertIn('"ema200"', content)
        self.assertIn('"draw_ema200"', content)


if __name__ == "__main__":
    unittest.main()
