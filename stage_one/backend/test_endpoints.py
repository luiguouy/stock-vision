# -*- coding: utf-8 -*-
"""
智能股票技术分析平台 - 后端单元测试与端点验证脚本

测试覆盖:
  - 股票搜索 (模糊匹配)
  - 多周期K线获取 (4h/1d/1w/1M)
  - 技术分析 (支撑阻力位 + 区间统计)
  - 支撑阻力多周期算法 (不同周期参数自适应)
  - 区间统计算法精确性
"""

import sys
import os
import unittest
import pandas as pd
from fastapi.testclient import TestClient

# 引入后端 main
from main import app, STOCKS_POOL
from analysis import calculate_sr_levels, calculate_range_stats, PERIOD_PARAMS
from data_provider import SUPPORTED_PERIODS, DataProviderManager


class TestStockBackend(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

        # 准备一个包含极值和明确趋势的测试 K 线数据集
        # 共 20 天数据
        data = {
            "date": [
                "2023-01-01", "2023-01-02", "2023-01-03", "2023-01-04", "2023-01-05",
                "2023-01-06", "2023-01-07", "2023-01-08", "2023-01-09", "2023-01-10",
                "2023-01-11", "2023-01-12", "2023-01-13", "2023-01-14", "2023-01-15",
                "2023-01-16", "2023-01-17", "2023-01-18", "2023-01-19", "2023-01-20"
            ],
            "open":  [100.0, 102.0, 105.0, 103.0, 98.0,  95.0,  97.0,  102.0, 106.0, 110.0, 108.0, 105.0, 112.0, 115.0, 110.0, 105.0, 108.0, 112.0, 115.0, 118.0],
            "high":  [103.0, 106.0, 108.0, 105.0, 100.0, 97.0,  103.0, 107.0, 112.0, 113.0, 110.0, 108.0, 116.0, 118.0, 112.0, 109.0, 113.0, 116.0, 119.0, 122.0],
            "low":   [99.0,  101.0, 102.0, 97.0,  94.0,  92.0,  95.0,  100.0, 105.0, 107.0, 106.0, 103.0, 108.0, 111.0, 107.0, 103.0, 105.0, 110.0, 113.0, 115.0],
            "close": [102.0, 105.0, 103.0, 98.0,  95.0,  94.0,  102.0, 106.0, 110.0, 108.0, 107.0, 106.0, 115.0, 110.0, 105.0, 107.0, 112.0, 115.0, 118.0, 120.0],
            "volume": [1000] * 20
        }
        self.df = pd.DataFrame(data)

    def test_search_endpoint_pool(self):
        """测试 /api/search 获取预置股票池"""
        response = self.client.get("/api/search")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), len(STOCKS_POOL))

    def test_search_endpoint_by_keyword(self):
        """测试 /api/search 拼音及中文模糊搜索"""
        response = self.client.get("/api/search?keyword=pg")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.json()) >= 1)
        self.assertEqual(response.json()[0]["symbol"], "usAAPL")

        response = self.client.get("/api/search?keyword=苹果")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["symbol"], "usAAPL")

    def test_search_endpoint_custom_code(self):
        """测试 /api/search 识别自定义输入的代码形式"""
        # 测试带前缀的美股
        response = self.client.get("/api/search?keyword=usAAPL")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["symbol"], "usAAPL")

        # 测试纯英文美股代码
        response = self.client.get("/api/search?keyword=NVDA")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["symbol"], "usNVDA")

    def test_periods_endpoint(self):
        """测试 /api/periods 获取支持的周期列表"""
        response = self.client.get("/api/periods")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("periods", data)
        self.assertIn("descriptions", data)
        for p in ['4h', '1d', '1w', '1M']:
            self.assertIn(p, data["periods"])

    def test_klines_endpoint(self):
        """测试 /api/klines 获取日K线数据"""
        response = self.client.get("/api/klines?symbol=usAAPL")
        self.assertEqual(response.status_code, 200)
        points = response.json()
        self.assertTrue(len(points) > 0)
        self.assertIn("time", points[0])
        self.assertIn("open", points[0])
        self.assertIn("high", points[0])
        self.assertIn("low", points[0])
        self.assertIn("close", points[0])

    def test_klines_multi_period(self):
        """测试 /api/klines 多周期K线获取 (4h/1d/1w/1M)"""
        for period in SUPPORTED_PERIODS:
            response = self.client.get(f"/api/klines?symbol=usAAPL&period={period}")
            self.assertEqual(response.status_code, 200,
                             f"周期 {period} 请求失败: {response.status_code}")
            points = response.json()
            self.assertTrue(len(points) > 0, f"周期 {period} 返回空数据")
            # 验证 time 字段格式
            time_str = points[0]["time"]
            if period == '4h':
                # 4h 数据应包含时间部分
                self.assertIn(":", time_str, f"4h K线 time 缺少时间部分: {time_str}")
            else:
                # 日/周/月线应为日期格式
                self.assertIn("-", time_str)

    def test_klines_invalid_period(self):
        """测试 /api/klines 无效周期返回 400"""
        response = self.client.get("/api/klines?symbol=usAAPL&period=2h")
        self.assertEqual(response.status_code, 400)

    def test_analysis_endpoint(self):
        """测试 /api/analysis 是否能正常返回支撑阻力和区间统计"""
        payload = {
            "symbol": "usAAPL",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "period": "1d"
        }
        response = self.client.post("/api/analysis", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("sr_levels", data)
        self.assertIn("statistics", data)
        self.assertIn("period", data)
        self.assertEqual(data["period"], "1d")

        # 验证统计中包含最大涨跌幅
        self.assertIn("max_rise", data["statistics"])
        self.assertIn("max_fall", data["statistics"])

    def test_analysis_multi_period(self):
        """测试 /api/analysis 多周期支撑阻力位计算"""
        for period in ['1d', '1w', '1M']:
            payload = {
                "symbol": "usAAPL",
                "start_date": "2023-01-01",
                "end_date": "2025-12-31",
                "period": period
            }
            response = self.client.post("/api/analysis", json=payload)
            self.assertEqual(response.status_code, 200,
                             f"周期 {period} 分析失败: {response.status_code}")
            data = response.json()
            self.assertEqual(data["period"], period)
            self.assertIn("sr_levels", data)
            self.assertIn("data_source", data)

    def test_range_stats_calculation(self):
        """测试区间统计算法准确性"""
        # 数据集最低点是第 6 天的 92.0 (2023-01-06)，之后最高点是第 20 天的 122.0 (2023-01-20)
        # 上涨幅度应该为 (122 - 92) / 92 * 100 = 32.61%
        stats = calculate_range_stats(self.df, "2023-01-01", "2023-01-20")
        self.assertEqual(stats["max_rise"]["pct"], 32.61)
        self.assertEqual(stats["max_rise"]["start"], "2023-01-06")
        self.assertEqual(stats["max_rise"]["end"], "2023-01-20")

        # 跌势子区间测试:
        # 区间为 2023-01-01 到 2023-01-06：最高点是 2023-01-03 (108.0)，之后最低点是 2023-01-06 (92.0)
        # 跌幅：(92.0 - 108.0) / 108.0 = -14.81%
        stats_fall = calculate_range_stats(self.df, "2023-01-01", "2023-01-06")
        self.assertEqual(stats_fall["max_fall"]["pct"], -14.81)
        self.assertEqual(stats_fall["max_fall"]["start"], "2023-01-03")
        self.assertEqual(stats_fall["max_fall"]["end"], "2023-01-06")

    def test_sr_levels_multi_period(self):
        """测试支撑阻力位多周期算法 — 不同周期应使用不同半衰期"""
        # 构造足够长的测试数据 (60+ 根)
        dates = [(pd.Timestamp("2023-01-01") + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
                 for i in range(80)]
        prices = []
        base = 100.0
        for i in range(80):
            # 制造波动: 每10天一个波段
            wave = 10 * np_sin(i / 10.0 * 3.14159)
            prices.append(base + wave + i * 0.5)

        df_long = pd.DataFrame({
            "date": dates,
            "open": prices,
            "high": [p + 3 for p in prices],
            "low": [p - 3 for p in prices],
            "close": prices,
            "volume": [1000] * 80
        })

        # 不同周期应该都能正常计算
        for period in ['4h', '1d', '1w', '1M']:
            levels = calculate_sr_levels(df_long, period=period)
            self.assertIsInstance(levels, list,
                                  f"周期 {period} 应返回列表")

        # 验证不同周期的参数确实不同
        self.assertNotEqual(
            PERIOD_PARAMS['4h']['half_life'],
            PERIOD_PARAMS['1d']['half_life'],
            "4h 和 1d 的半衰期不应相同"
        )
        self.assertNotEqual(
            PERIOD_PARAMS['1w']['half_life'],
            PERIOD_PARAMS['1M']['half_life'],
            "1w 和 1M 的半衰期不应相同"
        )

    def test_data_provider_manager(self):
        """测试数据源管理器初始化"""
        manager = DataProviderManager()
        self.assertEqual(manager.tencent.name, "tencent")
        self.assertEqual(manager.yahoo.name, "yahoo")
        self.assertIsNone(manager.last_source)


def np_sin(x):
    """简易 sin 计算 (避免测试中引入 numpy 依赖问题)"""
    import math
    return math.sin(x)


if __name__ == "__main__":
    unittest.main()
