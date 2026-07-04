# -*- coding: utf-8 -*-
"""
智能股票技术分析平台 - 第一阶段 (MVP) 后端单元测试与端点验证脚本
"""

import sys
import os
import unittest
import pandas as pd
from fastapi.testclient import TestClient

# 引入后端 main
from main import app, STOCKS_POOL
from analysis import calculate_sr_levels, calculate_range_stats

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

    def test_klines_endpoint(self):
        """测试 /api/klines 获取 K 线数据"""
        response = self.client.get("/api/klines?symbol=usAAPL")
        self.assertEqual(response.status_code, 200)
        points = response.json()
        self.assertTrue(len(points) > 0)
        self.assertIn("time", points[0])
        self.assertIn("open", points[0])
        self.assertIn("high", points[0])
        self.assertIn("low", points[0])
        self.assertIn("close", points[0])

    def test_analysis_endpoint(self):
        """测试 /api/analysis 是否能正常返回支撑阻力和区间统计"""
        payload = {
            "symbol": "usAAPL",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31"
        }
        response = self.client.post("/api/analysis", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("sr_levels", data)
        self.assertIn("statistics", data)
        
        # 验证统计中包含最大涨跌幅
        self.assertIn("max_rise", data["statistics"])
        self.assertIn("max_fall", data["statistics"])

    def test_range_stats_calculation(self):
        """测试区间统计算法准确性"""
        # 数据集最低点是第 6 天的 92.0 (2023-01-06)，之后最高点是第 20 天的 122.0 (2023-01-20)
        # 上涨幅度应该为 (122 - 92) / 92 * 100 = 32.61%
        stats = calculate_range_stats(self.df, "2023-01-01", "2023-01-20")
        self.assertEqual(stats["max_rise"]["pct"], 32.61)
        self.assertEqual(stats["max_rise"]["start"], "2023-01-06")
        self.assertEqual(stats["max_rise"]["end"], "2023-01-20")

        # 数据集最高点是第 20 天的 122.0，其后无数据，所以最大下跌应该是在它之前的极值。
        # 比如：前高点为第 3 天的 108.0，其后最低点为第 6 天的 92.0。跌幅为 (92 - 108) / 108 * 100 = -14.81%
        # 对全量求最大下跌：
        # 极值点：最高点是第20天的122，但在20之后没有最低点，跌幅为0。
        # 那么寻找整个区间内的最高点，以及之后的最低点：
        # 最高点是 2023-01-20 (122)，之后无最低点，所以返回 0。
        # 等等，如果最高点是最后一天，确实没有之后的下跌。
        # 我们用一个跌势子区间测试：
        # 区间为 2023-01-01 到 2023-01-06：最高点是 2023-01-03 (108.0)，之后最低点是 2023-01-06 (92.0)
        # 跌幅：(92.0 - 108.0) / 108.0 = -14.81%
        stats_fall = calculate_range_stats(self.df, "2023-01-01", "2023-01-06")
        self.assertEqual(stats_fall["max_fall"]["pct"], -14.81)
        self.assertEqual(stats_fall["max_fall"]["start"], "2023-01-03")
        self.assertEqual(stats_fall["max_fall"]["end"], "2023-01-06")


if __name__ == "__main__":
    unittest.main()
