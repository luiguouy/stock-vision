# -*- coding: utf-8 -*-
"""
加密货币专项单元测试
覆盖:
1. YahooProvider._to_yahoo_ticker 转换与清洗
2. DataProviderManager.fetch_klines 的加密货币独立路由与腾讯隔离
3. main.py 中 normalize_symbol、market_of、STOCKS_POOL 搜索别名
4. quote_config.py 与 quote_provider.py 中 YahooCryptoQuoteProvider 实时行情拉取与路由
"""

import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
import pandas as pd
from fastapi.testclient import TestClient

from main import app, normalize_symbol as main_norm, market_of as main_market_of, MARKET_LABEL
from data_provider import YahooProvider, DataProviderManager
from quote_config import MARKET, market_of as config_market_of, get_market_cfg
from quote_provider import YahooCryptoQuoteProvider, TencentQuoteProvider


class TestCryptoFeatures(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    # -------------------------------------------------------------
    # 1. 测试 YahooProvider._to_yahoo_ticker
    # -------------------------------------------------------------
    def test_to_yahoo_ticker_crypto_variants(self):
        cases = {
            "BTC/USDT": "BTC-USD",
            "BTCUSDT": "BTC-USD",
            "btcusdt": "BTC-USD",
            "BTC/USD": "BTC-USD",
            "btcusd": "BTC-USD",
            "USBTC": "BTC-USD",
            "usbtc": "BTC-USD",
            "usBTCUSDT": "BTC-USD",
            "usBTC/USDT": "BTC-USD",
            "usBTC-USDT": "BTC-USD",
            "BTC-USD": "BTC-USD",
            "BTC-USDT": "BTC-USD",
            "BTC": "BTC-USD",
            "btc": "BTC-USD",
            "ETH/USDT": "ETH-USD",
            "ETHUSDT": "ETH-USD",
            "USETH": "ETH-USD",
            "SOL/USDT": "SOL-USD",
            "SOLUSDT": "SOL-USD",
            "USSOL": "SOL-USD",
            "DOGE/USDT": "DOGE-USD",
            "DOGEUSDT": "DOGE-USD",
            "USDOGE": "DOGE-USD",
            "DOGEUSD": "DOGE-USD",
            "XRP/USDT": "XRP-USD",
            "XRPUSDT": "XRP-USD",
            "USXRP": "XRP-USD",
            "BNB/USDT": "BNB-USD",
            "BNBUSDT": "BNB-USD",
            "USBNB": "BNB-USD",
        }
        for raw, expected in cases.items():
            result = YahooProvider._to_yahoo_ticker(raw)
            self.assertEqual(result, expected, f"Failed for raw={raw}: got {result}, expected {expected}")

    def test_to_yahoo_ticker_non_crypto(self):
        self.assertEqual(YahooProvider._to_yahoo_ticker("usAAPL"), "AAPL")
        self.assertEqual(YahooProvider._to_yahoo_ticker("AAPL"), "AAPL")
        self.assertEqual(YahooProvider._to_yahoo_ticker("NQmain"), "NQ=F")

    # -------------------------------------------------------------
    # 2. 测试 main.py 中 normalize_symbol 与 market_of
    # -------------------------------------------------------------
    def test_normalize_symbol_crypto(self):
        cases = {
            "BTC/USDT": "BTC-USD",
            "BTCUSDT": "BTC-USD",
            "btcusdt": "BTC-USD",
            "BTC-USDT": "BTC-USD",
            "BTC/USD": "BTC-USD",
            "btcusd": "BTC-USD",
            "BTC-USD": "BTC-USD",
            "USBTC": "BTC-USD",
            "usbtc": "BTC-USD",
            "usBTCUSDT": "BTC-USD",
            "usBTC/USDT": "BTC-USD",
            "usBTC-USDT": "BTC-USD",
            "BTC": "BTC-USD",
            "btc": "BTC-USD",
            "ETH/USDT": "ETH-USD",
            "ETHUSDT": "ETH-USD",
            "USETH": "ETH-USD",
            "ETH": "ETH-USD",
            "SOL/USDT": "SOL-USD",
            "SOLUSDT": "SOL-USD",
            "USSOL": "SOL-USD",
            "SOL": "SOL-USD",
            "DOGE/USDT": "DOGE-USD",
            "DOGEUSDT": "DOGE-USD",
            "USDOGE": "DOGE-USD",
            "DOGEUSD": "DOGE-USD",
            "XRP/USDT": "XRP-USD",
            "XRPUSDT": "XRP-USD",
            "USXRP": "XRP-USD",
            "BNB/USDT": "BNB-USD",
            "BNBUSDT": "BNB-USD",
            "USBNB": "BNB-USD",
        }
        for raw, expected in cases.items():
            result = main_norm(raw)
            self.assertEqual(result, expected, f"normalize_symbol failed for {raw}: got {result}, expected {expected}")

    def test_normalize_symbol_stocks_and_futures(self):
        self.assertEqual(main_norm("AAPL"), "USAAPL")
        self.assertEqual(main_norm("usAAPL"), "USAAPL")
        self.assertEqual(main_norm("NQmain"), "NQmain")

    def test_market_of_crypto(self):
        crypto_symbols = [
            "BTC-USD", "ETH-USD", "SOL-USD",
            "BTC/USDT", "BTCUSDT", "btcusdt", "BTC-USDT", "BTC/USD", "btcusd",
            "USBTC", "usbtc", "usBTCUSDT", "usBTC/USDT", "usBTC-USDT",
            "BTC", "btc", "ETH", "SOL",
            "ETHUSDT", "USETH", "SOLUSDT", "USSOL",
            "DOGE/USDT", "DOGEUSDT", "USDOGE", "DOGE-USD", "DOGE", "DOGEUSD",
            "XRP/USDT", "XRPUSDT", "USXRP", "XRP-USD", "XRP", "XRPUSD",
            "BNB/USDT", "BNBUSDT", "USBNB", "BNB-USD", "BNB", "BNBUSD",
        ]
        for sym in crypto_symbols:
            self.assertEqual(main_market_of(sym), "crypto", f"main.market_of failed for {sym}")
            self.assertEqual(config_market_of(sym), "crypto", f"quote_config.market_of failed for {sym}")

    def test_market_labels_and_config(self):
        self.assertIn("crypto", MARKET_LABEL)
        self.assertEqual(MARKET_LABEL["crypto"], "加密")

        self.assertIn("crypto", MARKET)
        cfg = get_market_cfg("crypto")
        self.assertEqual(cfg["name"], "加密")
        self.assertEqual(cfg["delay_label"], "实时行情 (24/7)")

    # -------------------------------------------------------------
    # 3. 测试搜索接口命中加密货币别名
    # -------------------------------------------------------------
    def test_search_crypto_aliases(self):
        search_terms = ["BTC/USDT", "BTCUSDT", "BTC-USDT", "BTC", "BITCOIN", "BTCUSD"]
        for kw in search_terms:
            resp = self.client.get(f"/api/search?keyword={kw}")
            self.assertEqual(resp.status_code, 200)
            items = resp.json()
            self.assertTrue(len(items) > 0, f"No results for {kw}")
            self.assertEqual(items[0]["symbol"], "BTC-USD", f"First result for {kw} is not BTC-USD: {items[0]}")

        # ETH & SOL
        resp_eth = self.client.get("/api/search?keyword=ETH/USDT")
        self.assertEqual(resp_eth.status_code, 200)
        self.assertEqual(resp_eth.json()[0]["symbol"], "ETH-USD")

        resp_sol = self.client.get("/api/search?keyword=SOL/USDT")
        self.assertEqual(resp_sol.status_code, 200)
        self.assertEqual(resp_sol.json()[0]["symbol"], "SOL-USD")

        resp_doge = self.client.get("/api/search?keyword=DOGE/USDT")
        self.assertEqual(resp_doge.status_code, 200)
        self.assertEqual(resp_doge.json()[0]["symbol"], "DOGE-USD")

        resp_xrp = self.client.get("/api/search?keyword=XRP/USDT")
        self.assertEqual(resp_xrp.status_code, 200)
        self.assertEqual(resp_xrp.json()[0]["symbol"], "XRP-USD")

        resp_bnb = self.client.get("/api/search?keyword=BNB/USDT")
        self.assertEqual(resp_bnb.status_code, 200)
        self.assertEqual(resp_bnb.json()[0]["symbol"], "BNB-USD")

    def test_us_stock_prefix_not_colliding_with_crypto(self):
        """防止以 SOL/ETH/BTC 开头的非加密美股代码 (如 SOLV) 被误判为加密货币。"""
        self.assertEqual(main_market_of("usSOLV"), "us")
        self.assertEqual(config_market_of("usSOLV"), "us")
        self.assertEqual(main_norm("usSOLV"), "USSOLV")
        self.assertEqual(YahooProvider._to_yahoo_ticker("usSOLV"), "SOLV")

    # -------------------------------------------------------------
    # 4. 测试 DataProviderManager.fetch_klines 加密货币隔离腾讯源
    # -------------------------------------------------------------
    def test_data_provider_manager_crypto_routes_only_yahoo(self):
        manager = DataProviderManager()
        fake_df = pd.DataFrame({
            "date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"],
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [105.0, 106.0, 107.0, 108.0, 109.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [104.0, 105.0, 106.0, 107.0, 108.0],
            "volume": [1000.0, 1100.0, 1200.0, 1300.0, 1400.0],
        })

        test_variants = [
            "BTC-USD", "BTC/USDT", "BTCUSDT", "btcusdt",
            "USBTC", "usbtc", "usBTCUSDT", "usBTC/USDT", "usBTC-USDT",
            "ETHUSDT", "USETH", "SOLUSDT", "USSOL", "DOGEUSDT",
        ]

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            for sym in test_variants:
                manager.yahoo.fetch_klines = AsyncMock(return_value=fake_df)
                manager.tencent.fetch_klines = AsyncMock(return_value=pd.DataFrame())
                res = loop.run_until_complete(manager.fetch_klines(sym, period="1d", bypass_cache=True))
                self.assertFalse(res.empty, f"Failed for {sym}")
                self.assertEqual(manager.last_source, "yahoo", f"Wrong source for {sym}")
                manager.yahoo.fetch_klines.assert_called_once()
                manager.tencent.fetch_klines.assert_not_called()
        finally:
            loop.close()

    # -------------------------------------------------------------
    # 5. 测试 YahooCryptoQuoteProvider 实时行情拉取与错误兜底
    # -------------------------------------------------------------
    def test_yahoo_crypto_quote_provider_parsing(self):
        provider = YahooCryptoQuoteProvider()

        fake_resp_data = {
            "chart": {
                "result": [{
                    "meta": {
                        "regularMarketPrice": 92500.5,
                        "chartPreviousClose": 91000.0,
                        "regularMarketOpen": 91200.0,
                        "regularMarketDayHigh": 93000.0,
                        "regularMarketDayLow": 90800.0,
                    }
                }]
            }
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_resp_data

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_resp
                quotes = loop.run_until_complete(provider.get_quotes(["BTC-USD"]))
                self.assertEqual(len(quotes), 1)
                q = quotes[0]
                self.assertEqual(q["symbol"], "BTC-USD")
                self.assertEqual(q["price"], 92500.5)
                self.assertEqual(q["prev_close"], 91000.0)
                self.assertEqual(q["change"], 1500.5)
                self.assertEqual(q["change_pct"], 1.65)
                self.assertEqual(q["market"], "crypto")
                self.assertEqual(q["status"], "ok")

                # 测试网络波动时命中 _last_good 缓存
                mock_get.side_effect = httpx.ConnectError("Network timeout")
                fallback_quotes = loop.run_until_complete(provider.get_quotes(["BTC-USD"]))
                self.assertEqual(len(fallback_quotes), 1)
                self.assertEqual(fallback_quotes[0]["price"], 92500.5)

                # 测试从未成功过的标的返回 empty 错误结构
                empty_quotes = loop.run_until_complete(provider.get_quotes(["UNKNOWN-USD"]))
                self.assertEqual(len(empty_quotes), 1)
                self.assertEqual(empty_quotes[0]["status"], "empty")
        finally:
            loop.close()

    # -------------------------------------------------------------
    # 6. 测试 TencentQuoteProvider.get_quotes 路由到 crypto_provider
    # -------------------------------------------------------------
    def test_tencent_quote_provider_routes_crypto(self):
        t_provider = TencentQuoteProvider()
        t_provider.crypto_provider.get_quotes = AsyncMock(return_value=[{
            "symbol": "BTC-USD", "price": 93000.0, "status": "ok"
        }])
        t_provider._get_tencent_quotes = AsyncMock(return_value=[{
            "symbol": "usAAPL", "price": 230.0, "status": "ok"
        }])

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            res = loop.run_until_complete(t_provider.get_quotes(["BTC-USD", "usAAPL"]))
            self.assertEqual(len(res), 2)
            t_provider.crypto_provider.get_quotes.assert_called_once_with(["BTC-USD"])
            t_provider._get_tencent_quotes.assert_called_once_with(["usAAPL"])
        finally:
            loop.close()

    # -------------------------------------------------------------
    # 7. 测试 YahooProvider 加密货币日线使用 10y 周期并能成功拉取
    # -------------------------------------------------------------
    def test_yahoo_crypto_daily_uses_10y_range(self):
        yahoo = YahooProvider()
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            with patch("data_provider.get_proxy_client") as mock_get_client:
                mock_client = AsyncMock()
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                # 模拟 5 根日线数据
                mock_resp.json.return_value = {
                    "chart": {
                        "result": [{
                            "timestamp": [1700000000, 1700086400, 1700172800, 1700259200, 1700345600],
                            "indicators": {
                                "quote": [{
                                    "open": [90000, 91000, 92000, 93000, 94000],
                                    "high": [90500, 91500, 92500, 93500, 94500],
                                    "low": [89500, 90500, 91500, 92500, 93500],
                                    "close": [90200, 91200, 92200, 93200, 94200],
                                    "volume": [1000, 1100, 1200, 1300, 1400],
                                }]
                            }
                        }]
                    }
                }
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_get_client.return_value = mock_client

                df = loop.run_until_complete(yahoo._fetch_yahoo_direct("BTC-USD", "1d", False))
                self.assertFalse(df.empty)
                self.assertEqual(len(df), 5)
                # 确认请求的 URL 中包含了 range=10y
                call_args = mock_client.get.call_args[0][0]
                self.assertIn("range=10y", call_args)
        finally:
            loop.close()

    def test_live_get_klines_btc_usdt_daily(self):
        """端到端实盘验证：BTC/USDT 1d K线能正常返回且根数充足、校验通过。"""
        import asyncio
        from data_provider import provider_manager, validate_klines
        loop = asyncio.new_event_loop()
        try:
            df = loop.run_until_complete(provider_manager.fetch_klines("BTC/USDT", "1d", bypass_cache=True))
            self.assertFalse(df.empty)
            self.assertGreaterEqual(len(df), 100)
            self.assertTrue(validate_klines(df, "1d"))
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
