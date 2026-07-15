# -*- coding: utf-8 -*-
"""
多市场免费公开行情 —— 集中式刷新与限流配置文件
================================================

本文件是「实时行情展示」模块的唯一配置入口，所有刷新间隔、限流阈值、
延迟标注、美股盘前/盘中/盘后配置、自适应与冷却参数都写在这里，
方便后续统一调整，不要在业务代码里硬编码数值。

⚠️ 硬性合规红线（必须严格遵守，否则会被数据源封禁 IP / 返回 403/429）：
  - 单标的轮询绝对禁止低于 100ms（ABSOLUTE_MIN_INTERVAL = 0.1s）。
  - A股本地稳定轮询最低 2s；批量查询（多标的）最低 3s。
  - 港股本地稳定轮询最低 2s。
  - 美股个股热门服务端 10s 更新一次（取 10s 为合规下限）；指数 5s；
    盘前/盘后流动性差，服务端 30-60s 才更新缓存，轮询应按 30-60s 配置。
  - 触发限流/超时/空数据时，自动冷却 30s（RATE_LIMIT_COOLDOWN）再重试。
"""

from typing import Optional


# ============================================================
# 1. 各市场刷新与延迟配置（核心，单位：秒 / 字符串）
# ============================================================
# 字段说明：
#   name          市场中文名
#   min_interval  本地稳定轮询「最低」间隔（合规下限，代码不得突破）
#   server_update 服务端有效更新频率区间 [min, max]（仅用于展示与说明）
#   batch_interval 批量查询（≥2 个标的）最低间隔
#   delay_label   精简延迟标注（用于标的旁小徽标）
#   delay_full    完整延迟提示语（用于风险提示）
#   sessions      仅美股：盘前/盘中/盘后三套刷新配置
MARKET = {
    "ash": {
        "name": "沪A",
        "min_interval": 2.0,                 # A股本地最低 2s（硬性）
        "server_update": [2.0, 6.0],         # 服务端有效更新 2-6s
        "batch_interval": 3.0,               # 批量查询最低 3s（硬性）
        "delay_label": "无延迟 LV1",
        "delay_full": "A股【无延迟 LV1】",
    },
    "asz": {
        "name": "深A",
        "min_interval": 2.0,                 # 深A与沪A同规
        "server_update": [2.0, 6.0],
        "batch_interval": 3.0,
        "delay_label": "无延迟 LV1",
        "delay_full": "A股【无延迟 LV1】",
    },
    "hk": {
        "name": "港股",
        "min_interval": 2.0,                 # 港股本地最低 2s（硬性）
        "server_update": [1.5, 4.0],         # 服务端有效更新 1.5-4s
        "batch_interval": 3.0,
        "delay_label": "秒级轻微延迟",
        "delay_full": "港股【秒级轻微延迟】",
    },
    "us": {
        "name": "美股",
        # 美股个股热门服务端 10s 更新一次 → 取 10s 为合规下限（指数 5s 更快，
        # 但个股统一按 10s 轮询更稳妥，且数据本质仍是交易所强制 15 分钟延迟快照）。
        "min_interval": 10.0,
        "server_update": [10.0, 900.0],       # 10s(热门) ~ 900s(15分钟延迟快照)
        "batch_interval": 5.0,
        "delay_label": "延迟 15 分钟，仅供参考，不可实盘交易",
        "delay_full": "美股【延迟 15 分钟，仅供参考，不可实盘交易】",
        # 美股按交易时段区分三套刷新配置（美东时间）
        "sessions": {
            "pre":     {"label": "盘前", "min_interval": 30.0, "max_interval": 60.0},  # 盘前 30-60s
            "regular": {"label": "盘中", "min_interval": 10.0, "max_interval": 15.0},  # 盘中热门 10s
            "post":    {"label": "盘后", "min_interval": 30.0, "max_interval": 60.0},  # 盘后 30-60s
        },
    },
}


# ============================================================
# 2. 限流红线与冷却（绝对不能低于以下数值）
# ============================================================
# 单标的轮询禁止低于 100ms 高频请求（任何调整都不得低于此值，否则触发封禁）
ABSOLUTE_MIN_INTERVAL = 0.1

# 触发限流 / 接口异常后的冷却时长（秒）：冷却期内停止请求，30s 后再试
RATE_LIMIT_COOLDOWN = 30.0
# 空数据（接口返回但无行情）冷却时长（秒）
EMPTY_COOLDOWN = 10.0
# 单次请求超时（秒）
REQUEST_TIMEOUT = 5.0

# 单 IP 单位时间请求计数器（滑动窗口）：超过阈值自动降速，避免被封
IP_WINDOW_SECONDS = 60.0          # 滑动窗口长度（秒）
IP_MAX_REQUESTS_PER_WINDOW = 120  # 单 IP 每分钟最多 120 次（≈2 次/秒，远低于红线）
IP_OVERLOAD_SLOWDOWN_FACTOR = 2.0 # 超额后全局轮询间隔放大倍率


# ============================================================
# 3. 自适应动态刷新（热门 / 冷门自动识别）
# ============================================================
ADAPTIVE_COLD_THRESHOLD = 6    # 连续 N 次轮询「无新行情」判定为冷门标的
ADAPTIVE_COLD_FACTOR = 2.0     # 冷门标的轮询间隔翻倍
ADAPTIVE_MAX_FACTOR = 8.0      # 间隔相对基准的最大放大倍数（防止无限拉长）


# ============================================================
# 4. 前端本地定时器粒度 & 去重开关
# ============================================================
TICK_MS = 1000                  # 前端本地定时器最小粒度（毫秒）：每秒检查一次是否需要请求
DEDUP_ENABLED = True            # 价格与涨跌幅均未变化时，不刷新前端渲染（减少开销）


# ============================================================
# 5. 市场识别工具（前后端共用同一套带前缀规则）
#    美股 usAAPL / 沪A sh600000 / 深A sz000001 / 港股 hk00700
# ============================================================
def market_of(symbol: str) -> Optional[str]:
    """识别带前缀代码所属市场。"""
    if not symbol:
        return None
    s = symbol.upper()
    if s.startswith("US"):
        return "us"
    if s.startswith("SH"):
        return "ash"
    if s.startswith("SZ"):
        return "asz"
    if s.startswith("HK"):
        return "hk"
    return None


def get_market_cfg(market: Optional[str]) -> dict:
    """安全获取市场配置，未知市场回退到美股配置。"""
    return MARKET.get(market or "us", MARKET["us"])
