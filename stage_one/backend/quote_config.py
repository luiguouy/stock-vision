# -*- coding: utf-8 -*-
"""
多市场免费公开行情 —— 集中式刷新与限流配置文件（纯美股 & 期货高实时性调优版）
路径: stage_one/backend/quote_config.py
"""

from typing import Optional
from symbols import market_of as _base_market_of

MARKET = {
    "us": {
        "name": "美股",
        "min_interval": 3.0,
        "server_update": [3.0, 15.0],
        "batch_interval": 3.0,
        "delay_label": "实时轮询 (3s)",
        "delay_full": "美股【免费公开数据源，盘中 3s 轮询】",
        "sessions": {
            "pre":     {"label": "盘前", "min_interval": 6.0, "max_interval": 15.0},
            "regular": {"label": "盘中", "min_interval": 3.0, "max_interval": 5.0},
            "post":    {"label": "盘后", "min_interval": 6.0, "max_interval": 15.0},
        },
    },
    "futures": {
        "name": "期货",
        "min_interval": 2.0,
        "server_update": [2.0, 5.0],
        "batch_interval": 2.5,
        "delay_label": "实时快照 (2s)",
        "delay_full": "期货【CME 连续合约实时快照】",
    },
    "crypto": {
        "name": "加密",
        "min_interval": 3.0,
        "server_update": [2.0, 5.0],
        "batch_interval": 3.0,
        "delay_label": "实时行情 (24/7)",
        "delay_full": "加密货币【Yahoo 实时行情，24小时交易】",
    },
}

ABSOLUTE_MIN_INTERVAL = 0.1
RATE_LIMIT_COOLDOWN = 20.0
EMPTY_COOLDOWN = 15.0
REQUEST_TIMEOUT = 5.0

IP_WINDOW_SECONDS = 60.0
IP_MAX_REQUESTS_PER_WINDOW = 120
IP_OVERLOAD_SLOWDOWN_FACTOR = 1.5

# 冷门自适应降频（仅对后台非主图自选股生效）
ADAPTIVE_COLD_THRESHOLD = 8
ADAPTIVE_COLD_FACTOR = 2.0
ADAPTIVE_MAX_FACTOR = 4.0

TICK_MS = 1000
DEDUP_ENABLED = True


def market_of(symbol: str) -> Optional[str]:
    """识别带前缀代码所属市场（无明确前缀且非停用市场时默认回退为美股）。"""
    return _base_market_of(symbol, default_us=True)


def get_market_cfg(market: Optional[str]) -> dict:
    """安全获取市场配置，默认回退到美股配置。"""
    return MARKET.get(market or "us", MARKET["us"])
