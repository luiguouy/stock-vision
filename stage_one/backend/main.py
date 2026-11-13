# -*- coding: utf-8 -*-
"""
智能股票技术分析平台 - 后端主入口文件
基于 FastAPI 框架，提供股票搜索、多周期K线获取以及支撑阻力位/区间统计接口。

支持的数据源:
  主源: 腾讯证券 (web.ifzq.gtimg.cn)
  备源: Yahoo Finance (yfinance) — 自动故障转移

支持的K线周期:
  4h  -> 4小时K线 (由1小时数据重采样)
  1d  -> 日K线
  1w  -> 周K线
  1M  -> 月K线
  3M  -> 季K线 (由日线重采样, 每根=一个季度)
  6M  -> 半年K线 (由日线重采样, 每根=半年)
  1Y  -> 年K线 (由日线重采样, 每根=一年)
"""

# pyrefly: ignore [missing-import]
from contextlib import asynccontextmanager
import os
import re
import uuid
import json
import asyncio
from datetime import datetime, timedelta
# pyrefly: ignore [missing-import]
import httpx
from fastapi import FastAPI, HTTPException, Query
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from typing import List, Dict, Optional, Any, Union

from analysis import calculate_sr_levels, calculate_range_stats
from data_provider import provider_manager, SUPPORTED_PERIODS
from db_cache import init_db, get_cached_klines, save_klines
# 多市场实时行情模块（腾讯免费公开接口 qt.gtimg.cn/q=）
from quote_provider import quote_provider
from quote_config import (
    MARKET, TICK_MS, ABSOLUTE_MIN_INTERVAL, RATE_LIMIT_COOLDOWN,
    IP_MAX_REQUESTS_PER_WINDOW, IP_WINDOW_SECONDS, ADAPTIVE_COLD_THRESHOLD,
    ADAPTIVE_COLD_FACTOR, ADAPTIVE_MAX_FACTOR,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 确保数据库表存在
    init_db()
    # 后台预热 (不阻塞启动; 无外网时静默失败)
    asyncio.create_task(prewarm_cache())
    yield

app = FastAPI(title="智能股票技术分析平台", lifespan=lifespan)
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import WebSocket, WebSocketDisconnect

# 前端构建产物静态文件托管
DIST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
if os.path.exists(DIST_DIR):
    assets_dir = os.path.join(DIST_DIR, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

@app.get("/")
def read_root():
    if os.path.exists(DIST_DIR):
        index_file = os.path.join(DIST_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
    return RedirectResponse(url="/docs")


@app.get("/api/health")
def health_check():
    """轻量级健康检查：前端用于探测后端是否在线，从而自动决定
    演示模式(模拟数据) / 实时模式(真实数据)。不依赖任何外部数据源。"""
    return {"status": "ok", "mode": "real"}


# ============================================================
# 实时行情（多市场：美股 / A股 / 港股）—— 腾讯免费公开接口
# ============================================================

@app.get("/api/quote")
async def get_quote(
    symbols: str = Query(..., description="逗号分隔的带前缀代码, 如 usAAPL,sh600519,hk00700"),
):
    """
    批量获取多市场实时行情（腾讯 qt.gtimg.cn/q=）。

    返回结构:
      {
        "quotes": [ {symbol,name,price,prev_close,open,change,change_pct,
                     update_time,market,delay_label,status} , ... ],
        "engine": { cooling, reason, cooldown_remaining, slowdown, window_requests }
      }
    - 前端「分层刷新」：本地定时器按各市场最低间隔触发请求，本接口内置限流护盾，
      被限流的标的会带 status='cooling'/'rate_limited' 等，前端据此展示冷却状态。
    - 单批上限 50 个标的，避免一次性过大请求。
    """
    # 仅把市场前缀规范为小写（腾讯 q= 接口对大小写敏感：usAAPL 可识别，USAAPL 不行），
    # 其余字符保持原样，避免破坏代码本身。
    import re
    def _norm_code(s: str) -> str:
        s = s.strip()
        return re.sub(r'^(US|SH|SZ|HK)', lambda m: m.group(1).lower(), s)
    syms = [_norm_code(s) for s in symbols.split(",") if s.strip()]
    if not syms:
        raise HTTPException(status_code=400, detail="symbols 不能为空")
    if len(syms) > 50:
        raise HTTPException(status_code=400, detail="单次最多请求 50 个标的")

    quotes = await quote_provider.get_quotes(syms)
    engine = quote_provider.limiter.status()
    return {"quotes": quotes, "engine": engine}


@app.get("/api/quote_config")
async def quote_config():
    """
    下发前端实时行情引擎所需的全部配置（刷新间隔 / 延迟标注 / 限流阈值 / 美股盘前盘后）。
    所有数值集中在后端 quote_config.py，前端只读取、不自行硬编码，保证前后端一致。
    """
    return {
        "tickMs": TICK_MS,
        "absoluteMinInterval": ABSOLUTE_MIN_INTERVAL,
        "rateLimitCooldown": RATE_LIMIT_COOLDOWN,
        "ipMaxRequests": IP_MAX_REQUESTS_PER_WINDOW,
        "ipWindow": IP_WINDOW_SECONDS,
        "adaptive": {
            "coldThreshold": ADAPTIVE_COLD_THRESHOLD,
            "coldFactor": ADAPTIVE_COLD_FACTOR,
            "maxFactor": ADAPTIVE_MAX_FACTOR,
        },
        "markets": {
            k: {
                "name": v["name"],
                "minInterval": v["min_interval"],
                "batchInterval": v["batch_interval"],
                "serverUpdate": v["server_update"],
                "delayLabel": v["delay_label"],
                "delayFull": v["delay_full"],
                "sessions": v.get("sessions", {}),
            }
            for k, v in MARKET.items()
        },
    }


# 启用 CORS 跨域支持，允许前端本地调试
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 市场工具函数 (前后端约定: 带市场前缀的统一代码格式)
#   美股: usAAPL   沪A: sh600000   深A: sz000001   港股: hk00700
# ============================================================
MARKET_LABEL = {"us": "美股", "ash": "沪A", "asz": "深A", "hk": "港股", "futures": "期货"}


def norm_market_prefix(sym: str) -> str:
    """腾讯 k线 / 行情接口对市场前缀大小写敏感, 统一规范为小写 (HK00700 -> hk00700)。

    这是修复「港股 / A股 K线 404」的根因: 前端与 /api/watchlist 统一返回大写前缀
    (如 HK00700 / SH600519), 但腾讯要求小写 (hk00700 / sh600519), 否则返回
    "param error"。美股分支本身已自动小写 us 前缀, 此处对所有市场统一兜底。
    """
    if not sym:
        return sym
    return re.sub(r'^(US|SH|SZ|HK)', lambda m: m.group(1).lower(), sym, flags=re.IGNORECASE)


def normalize_symbol(raw: str, market: Optional[str] = None) -> Optional[str]:
    """把用户输入归一化为带市场前缀的统一代码。"""
    s = (raw or "").strip().upper()
    if not s:
        return None
    if s.startswith(("US", "SH", "SZ", "HK")):
        return s
    if s.endswith("MAIN"):
        # 期货: 平台以 xxxmain 作为期货标识, 保留 main 后缀(转小写), 不走股票兜底
        return s[:-4] + "main"
    if market == "us":
        return "US" + s
    if market == "ash":
        return "SH" + s
    if market == "asz":
        return "SZ" + s
    if market == "hk":
        digits = "".join(ch for ch in s if ch.isdigit())
        return "HK" + digits.zfill(5)
    # 自动识别
    if s.isdigit():
        if len(s) == 6:
            return ("SH" if s[0] == "6" else "SZ") + s
        if len(s) <= 5:
            return "HK" + s.zfill(5)
    return "US" + s


def market_of(symbol: str) -> Optional[str]:
    s = symbol.upper()
    if s.endswith("MAIN"):
        return "futures"
    if s.startswith("US"):
        return "us"
    if s.startswith("SH"):
        return "ash"
    if s.startswith("SZ"):
        return "asz"
    if s.startswith("HK"):
        return "hk"
    return None


def strip_prefix(symbol: str) -> str:
    s = symbol.upper()
    for p in ("US", "SH", "SZ", "HK"):
        if s.startswith(p):
            return s[len(p):]
    return s


# 本地常用股票池 (覆盖美股 / A股 / 港股 / 加密 / 期货)，用于高精度模糊匹配与纠错
STOCKS_POOL = [
    # ── 美股科技七巨头 (Mag 7) ──────────────────────────
    {"symbol": "usAAPL", "name": "苹果 Apple", "pinyin": "pg", "pinyin_full": "pingguo", "aliases": ["APPLE", "AAPL", "IPHONE", "MAC"], "market": "us"},
    {"symbol": "usNVDA", "name": "英伟达 NVIDIA", "pinyin": "ywd", "pinyin_full": "yingweida", "aliases": ["NVIDIA", "NVDA", "GPU", "AI"], "market": "us"},
    {"symbol": "usMSFT", "name": "微软 Microsoft", "pinyin": "wr", "pinyin_full": "weiruan", "aliases": ["MICROSOFT", "MSFT", "WINDOWS", "AZURE"], "market": "us"},
    {"symbol": "usGOOGL", "name": "谷歌 Google Alphabet (A类)", "pinyin": "gg", "pinyin_full": "guge", "aliases": ["GOOGLE", "GOOGL", "ALPHABET"], "market": "us"},
    {"symbol": "usGOOG", "name": "谷歌 Google Alphabet (C类)", "pinyin": "gg", "pinyin_full": "guge", "aliases": ["GOOGLE", "GOOG", "ALPHABET"], "market": "us"},
    {"symbol": "usAMZN", "name": "亚马逊 Amazon", "pinyin": "ymx", "pinyin_full": "yamaxun", "aliases": ["AMAZON", "AMZN", "AWS"], "market": "us"},
    {"symbol": "usMETA", "name": "Meta 脸书 Facebook", "pinyin": "fb", "pinyin_full": "meta", "aliases": ["META", "FACEBOOK", "FB", "INSTAGRAM"], "market": "us"},
    {"symbol": "usTSLA", "name": "特斯拉 Tesla", "pinyin": "tsl", "pinyin_full": "tesila", "aliases": ["TESLA", "TSLA", "ELON"], "market": "us"},

    # ── 美股核心半导体与硬科技 ──────────────────────────
    {"symbol": "usAVGO", "name": "博通 Broadcom", "pinyin": "bt", "pinyin_full": "botong", "aliases": ["BROADCOM", "AVGO"], "market": "us"},
    {"symbol": "usAMD", "name": "超微半导体 AMD", "pinyin": "cw", "pinyin_full": "chaowei", "aliases": ["AMD", "RADEON", "RYZEN"], "market": "us"},
    {"symbol": "usTSM", "name": "台积电 TSMC", "pinyin": "tjd", "pinyin_full": "taijidian", "aliases": ["TSMC", "TSM"], "market": "us"},
    {"symbol": "usQCOM", "name": "高通 Qualcomm", "pinyin": "gt", "pinyin_full": "gaotong", "aliases": ["QUALCOMM", "QCOM", "SNAPDRAGON"], "market": "us"},
    {"symbol": "usINTC", "name": "英特尔 Intel", "pinyin": "yte", "pinyin_full": "yingteer", "aliases": ["INTEL", "INTC"], "market": "us"},
    {"symbol": "usMU", "name": "美光科技 Micron", "pinyin": "mg", "pinyin_full": "meiguang", "aliases": ["MICRON", "MU", "MEMORY"], "market": "us"},
    {"symbol": "usASML", "name": "阿斯麦 ASML", "pinyin": "asm", "pinyin_full": "asimai", "aliases": ["ASML", "LITHOGRAPHY"], "market": "us"},
    {"symbol": "usARM", "name": "安谋 ARM", "pinyin": "am", "pinyin_full": "anmou", "aliases": ["ARM", "SOFTBANK"], "market": "us"},
    {"symbol": "usORCL", "name": "甲骨文 Oracle", "pinyin": "jgw", "pinyin_full": "jiaguwen", "aliases": ["ORACLE", "ORCL"], "market": "us"},
    {"symbol": "usPLTR", "name": "Palantir 帕兰提尔", "pinyin": "plt", "pinyin_full": "palantir", "aliases": ["PLTR", "PALANTIR", "AI"], "market": "us"},
    {"symbol": "usCOIN", "name": "Coinbase 加密货币", "pinyin": "cb", "pinyin_full": "coinbase", "aliases": ["COIN", "COINBASE", "CRYPTO"], "market": "us"},
    {"symbol": "usMSTR", "name": "微策略 MicroStrategy", "pinyin": "wcl", "pinyin_full": "weicelue", "aliases": ["MSTR", "MICROSTRATEGY", "BITCOIN"], "market": "us"},
    {"symbol": "usSNDK", "name": "闪迪 SanDisk", "pinyin": "sd", "pinyin_full": "shandi", "aliases": ["SANDISK", "SNDK"], "market": "us"},

    # ── 美股软件、流媒体与消费龙头 ──────────────────────
    {"symbol": "usNFLX", "name": "奈飞 Netflix", "pinyin": "nf", "pinyin_full": "naifei", "aliases": ["NETFLIX", "NFLX"], "market": "us"},
    {"symbol": "usUBER", "name": "优步 Uber", "pinyin": "yb", "pinyin_full": "youbu", "aliases": ["UBER"], "market": "us"},
    {"symbol": "usABNB", "name": "爱彼迎 Airbnb", "pinyin": "aby", "pinyin_full": "aibiying", "aliases": ["AIRBNB", "ABNB"], "market": "us"},
    {"symbol": "usCRM", "name": "赛富时 Salesforce", "pinyin": "sfs", "pinyin_full": "saifushi", "aliases": ["SALESFORCE", "CRM"], "market": "us"},
    {"symbol": "usADBE", "name": "Adobe 奥多比", "pinyin": "adb", "pinyin_full": "aoduobi", "aliases": ["ADOBE", "ADBE", "PHOTOSHOP"], "market": "us"},
    {"symbol": "usCSCO", "name": "思科 Cisco", "pinyin": "sk", "pinyin_full": "sike", "aliases": ["CISCO", "CSCO"], "market": "us"},
    {"symbol": "usSNOW", "name": "Snowflake", "pinyin": "xue", "pinyin_full": "snowflake", "aliases": ["SNOW", "SNOWFLAKE"], "market": "us"},
    {"symbol": "usDIS", "name": "迪士尼 Disney", "pinyin": "dsn", "pinyin_full": "dishini", "aliases": ["DISNEY", "DIS"], "market": "us"},
    {"symbol": "usNKE", "name": "耐克 Nike", "pinyin": "nk", "pinyin_full": "naike", "aliases": ["NIKE", "NKE"], "market": "us"},
    {"symbol": "usSBUX", "name": "星巴克 Starbucks", "pinyin": "xbk", "pinyin_full": "xingbake", "aliases": ["STARBUCKS", "SBUX"], "market": "us"},
    {"symbol": "usCOST", "name": "开市客 Costco", "pinyin": "ksk", "pinyin_full": "kaishike", "aliases": ["COSTCO", "COST"], "market": "us"},
    {"symbol": "usWMT", "name": "沃尔玛 Walmart", "pinyin": "wem", "pinyin_full": "woerma", "aliases": ["WALMART", "WMT"], "market": "us"},
    {"symbol": "usJPM", "name": "摩根大通 JPMorgan", "pinyin": "mgdt", "pinyin_full": "morgandatong", "aliases": ["JPM", "JPMORGAN"], "market": "us"},
    {"symbol": "usBAC", "name": "美国银行 BofA", "pinyin": "mgyh", "pinyin_full": "meiguoyinhang", "aliases": ["BAC", "BOFA"], "market": "us"},
    {"symbol": "usGS", "name": "高盛 Goldman Sachs", "pinyin": "gs", "pinyin_full": "gaosheng", "aliases": ["GS", "GOLDMAN"], "market": "us"},

    # ── 美股代表性 ETF ──────────────────────────────────
    {"symbol": "usSPY", "name": "标普500 ETF (SPY)", "pinyin": "spy", "pinyin_full": "biaopu500etf", "aliases": ["SPY", "SP500", "S&P500"], "market": "us"},
    {"symbol": "usQQQ", "name": "纳斯达克100 ETF (QQQ)", "pinyin": "qqq", "pinyin_full": "nasidaq100etf", "aliases": ["QQQ", "NASDAQ100", "NDX"], "market": "us"},
    {"symbol": "usDIA", "name": "道琼斯工业 ETF (DIA)", "pinyin": "dia", "pinyin_full": "daoqiongsi", "aliases": ["DIA", "DOW"], "market": "us"},
    {"symbol": "usIWM", "name": "罗素2000小盘股 ETF (IWM)", "pinyin": "iwm", "pinyin_full": "luosu2000", "aliases": ["IWM", "RUSSELL"], "market": "us"},
    {"symbol": "usSOXX", "name": "半导体行业 ETF (SOXX)", "pinyin": "soxx", "pinyin_full": "bandaoti", "aliases": ["SOXX", "SEMI", "CHIPS"], "market": "us"},
    {"symbol": "usTLT", "name": "20年+美债 ETF (TLT)", "pinyin": "tlt", "pinyin_full": "meizhai", "aliases": ["TLT", "BONDS"], "market": "us"},
    {"symbol": "usSQQQ", "name": "3倍做空纳指 ETF (SQQQ)", "pinyin": "sqqq", "pinyin_full": "sanbeizuokongnazhi", "aliases": ["SQQQ", "SHORT"], "market": "us"},
    {"symbol": "usTQQQ", "name": "3倍做多纳指 ETF (TQQQ)", "pinyin": "tqqq", "pinyin_full": "sanbeizuoduonazhi", "aliases": ["TQQQ", "LONG"], "market": "us"},

    # ── 热门中概股 ──────────────────────────────────────
    {"symbol": "usBABA", "name": "阿里巴巴 (美股 BABA)", "pinyin": "albb", "pinyin_full": "alibaba", "aliases": ["BABA", "ALIBABA", "TAOBAO"], "market": "us"},
    {"symbol": "usPDD", "name": "拼多多 PDD Holdings", "pinyin": "pdd", "pinyin_full": "pingduoduo", "aliases": ["PDD", "PINGDUODUO", "TEMU"], "market": "us"},
    {"symbol": "usJD", "name": "京东 JD.com", "pinyin": "jd", "pinyin_full": "jingdong", "aliases": ["JD", "JINGDONG"], "market": "us"},
    {"symbol": "usBILI", "name": "哔哩哔哩 Bilibili (B站)", "pinyin": "blbl", "pinyin_full": "bilibili", "aliases": ["BILI", "BILIBILI", "BZHAN"], "market": "us"},
    {"symbol": "usNIO", "name": "蔚来 NIO", "pinyin": "wl", "pinyin_full": "weilai", "aliases": ["NIO", "WEILAI"], "market": "us"},
    {"symbol": "usLI", "name": "理想汽车 Li Auto", "pinyin": "lx", "pinyin_full": "lixiang", "aliases": ["LI", "LIXIANG"], "market": "us"},
    {"symbol": "usXPEV", "name": "小鹏汽车 Xpeng", "pinyin": "xp", "pinyin_full": "xiaopeng", "aliases": ["XPEV", "XIAOPENG"], "market": "us"},
    {"symbol": "usBIDU", "name": "百度 Baidu", "pinyin": "bd", "pinyin_full": "baidu", "aliases": ["BIDU", "BAIDU"], "market": "us"},
    {"symbol": "usNTES", "name": "网易 NetEase", "pinyin": "wy", "pinyin_full": "wangyi", "aliases": ["NTES", "NETEASE"], "market": "us"},

    # ── A股 (沪市) ──────────────────────────────────────
    {"symbol": "sh600519", "name": "贵州茅台", "pinyin": "gzmt", "pinyin_full": "guizhoumaotai", "aliases": ["600519", "MAOTAI", "MT"], "market": "ash"},
    {"symbol": "sh601318", "name": "中国平安", "pinyin": "zgap", "pinyin_full": "zhongguopingan", "aliases": ["601318", "PINGAN"], "market": "ash"},
    {"symbol": "sh600036", "name": "招商银行", "pinyin": "zsyh", "pinyin_full": "zhaoshangyinhang", "aliases": ["600036", "ZHAOHANG"], "market": "ash"},
    {"symbol": "sh600276", "name": "恒瑞医药", "pinyin": "hryy", "pinyin_full": "hengruiyiyao", "aliases": ["600276", "HENGRUI"], "market": "ash"},
    {"symbol": "sh600900", "name": "长江电力", "pinyin": "cjdl", "pinyin_full": "changjiangdianli", "aliases": ["600900", "CHANGDIAN"], "market": "ash"},
    {"symbol": "sh601899", "name": "紫金矿业", "pinyin": "zjky", "pinyin_full": "zijinkuangye", "aliases": ["601899", "ZIJIN", "GOLD"], "market": "ash"},
    {"symbol": "sh688981", "name": "中芯国际 (A股)", "pinyin": "zxgj", "pinyin_full": "zhongxinguoji", "aliases": ["688981", "SMIC"], "market": "ash"},

    # ── A股 (深市) ──────────────────────────────────────
    {"symbol": "sz000001", "name": "平安银行", "pinyin": "payh", "pinyin_full": "pinganyinhang", "aliases": ["000001", "PAYH"], "market": "asz"},
    {"symbol": "sz000858", "name": "五粮液", "pinyin": "wly", "pinyin_full": "wuliangye", "aliases": ["000858", "WULIANGYE"], "market": "asz"},
    {"symbol": "sz300750", "name": "宁德时代", "pinyin": "ndsd", "pinyin_full": "ningdeshidai", "aliases": ["300750", "CATL", "NINGDE"], "market": "asz"},
    {"symbol": "sz002594", "name": "比亚迪 (A股)", "pinyin": "byd", "pinyin_full": "biyadi", "aliases": ["002594", "BYD"], "market": "asz"},
    {"symbol": "sz000333", "name": "美的集团", "pinyin": "mdjt", "pinyin_full": "meidejituan", "aliases": ["000333", "MIDEA"], "market": "asz"},
    {"symbol": "sz300059", "name": "东方财富", "pinyin": "dfcf", "pinyin_full": "dongfangcaifu", "aliases": ["300059", "DONGFANGCAIFU", "EASTMONEY"], "market": "asz"},

    # ── 港股 ────────────────────────────────────────────
    {"symbol": "hk00700", "name": "腾讯控股", "pinyin": "txkg", "pinyin_full": "tengxunkonggu", "aliases": ["00700", "700", "TENCENT", "WECHAT"], "market": "hk"},
    {"symbol": "hk09988", "name": "阿里巴巴 (港股 9988)", "pinyin": "albb", "pinyin_full": "alibaba", "aliases": ["09988", "9988", "ALIBABA", "BABA"], "market": "hk"},
    {"symbol": "hk03690", "name": "美团", "pinyin": "mt", "pinyin_full": "meituan", "aliases": ["03690", "3690", "MEITUAN"], "market": "hk"},
    {"symbol": "hk01810", "name": "小米集团", "pinyin": "xmjt", "pinyin_full": "xiaomijituan", "aliases": ["01810", "1810", "XIAOMI", "MI"], "market": "hk"},
    {"symbol": "hk09626", "name": "哔哩哔哩 (港股 9626)", "pinyin": "blbl", "pinyin_full": "bilibili", "aliases": ["09626", "9626", "BILI", "BILIBILI"], "market": "hk"},
    {"symbol": "hk00981", "name": "中芯国际 (港股)", "pinyin": "zxgj", "pinyin_full": "zhongxinguoji", "aliases": ["00981", "981", "SMIC"], "market": "hk"},
    {"symbol": "hk01211", "name": "比亚迪股份 (港股)", "pinyin": "byd", "pinyin_full": "biyadi", "aliases": ["01211", "1211", "BYD"], "market": "hk"},
    {"symbol": "hk00388", "name": "香港交易所", "pinyin": "gjs", "pinyin_full": "gangjiaosuo", "aliases": ["00388", "388", "HKEX"], "market": "hk"},

    # ── 期货与加密货币 ──────────────────────────────────
    {"symbol": "BTC-USD", "name": "比特币 Bitcoin (USD)", "pinyin": "btb", "pinyin_full": "bitebi", "aliases": ["BTC", "BITCOIN", "BTCUSD"], "market": "crypto"},
    {"symbol": "ETH-USD", "name": "以太坊 Ethereum (USD)", "pinyin": "ytf", "pinyin_full": "yitaifang", "aliases": ["ETH", "ETHEREUM", "ETHUSD"], "market": "crypto"},
    {"symbol": "SOL-USD", "name": "索拉纳 Solana (USD)", "pinyin": "sol", "pinyin_full": "suolana", "aliases": ["SOL", "SOLANA"], "market": "crypto"},
    {"symbol": "NQmain", "name": "纳斯达克100期货 主力", "pinyin": "nq", "pinyin_full": "nasidaq100", "aliases": ["NQ", "NQMAIN"], "market": "futures"},
    {"symbol": "ESmain", "name": "标普500期货 主力", "pinyin": "es", "pinyin_full": "biaopu500", "aliases": ["ES", "ESMAIN"], "market": "futures"},
    {"symbol": "YMmain", "name": "道琼斯期货 主力", "pinyin": "ym", "pinyin_full": "daoqiongsi", "aliases": ["YM", "YMMAIN"], "market": "futures"},
    {"symbol": "VXmain", "name": "VIX恐慌指数期货 主力", "pinyin": "vx", "pinyin_full": "vix", "aliases": ["VX", "VXMAIN", "VIX"], "market": "futures"},
]


# ============================================================
# 本地缓存封装 + 启动预热
# ============================================================
# 预热热门股列表 (首次打开页面 / 默认自选常用标的),
# 启动时在后台异步拉取并写入 SQLite, 后续请求直接命中缓存, 大幅提升首屏速度。
PREWARM_SYMBOLS = [
    "usAAPL", "usNVDA", "usTSLA", "usAMD", "usMSFT",
    "usMETA", "usGOOGL", "usAMZN", "usMU",
    "sh600519", "sh601318", "sz000858", "hk00700", "hk09988",
]
PREWARM_PERIODS = ["1d", "1w", "1M", "3M", "6M", "1Y"]
CACHE_TTL_HOURS = 24


async def get_klines_df(symbol: str, period: str, full: bool = True):
    """
    带本地缓存的 K线获取封装。

    返回: (df, source)
      - 命中且未过期的缓存: 从 SQLite 读取, source='cache'
      - 未命中 / 过期:      从数据源拉取并写回缓存, source=实际数据源名
    全量模式 (full=True) 才走缓存; 非全量场景极少, 直接拉取。
    """
    # 规范市场前缀为小写 (腾讯接口大小写敏感: HK00700/SH600519 会 param error)。
    # 统一在此处归一化, 保证缓存键与下游数据源调用一致, 杜绝港股/A股 404。
    symbol = norm_market_prefix(symbol)
    if full:
        # 分时周期 (5m/15m/1h/4h) 缓存 3 分钟 (0.05 小时)，日线及以上周期缓存 24 小时
        ttl = 0.05 if period in ('5m', '15m', '1h', '4h') else CACHE_TTL_HOURS
        cached = get_cached_klines(symbol, period, max_age_hours=ttl)
        if cached is not None:
            import pandas as pd
            df = pd.DataFrame(cached)
            return df, "cache"

    df = await provider_manager.fetch_klines(symbol, period=period, full=full)
    if df.empty:
        return df, None

    if full:
        klines = [
            {
                "date": str(row["date"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
            for _, row in df.iterrows()
        ]
        source = provider_manager.last_source or ""
        save_klines(symbol, period, klines, source)
        return df, source

    return df, provider_manager.last_source


async def prewarm_cache():
    """后台预热热门股历史数据到本地缓存 (best-effort, 失败不阻塞主流程)。"""
    for sym in PREWARM_SYMBOLS:
        for period in PREWARM_PERIODS:
            try:
                df, src = await get_klines_df(sym, period, full=True)
                if df is not None and not df.empty:
                    print(f"[Prewarm] 已缓存 {sym} {period} ({len(df)} 根) 来源={src}")
            except Exception as e:
                print(f"[Prewarm] 跳过 {sym} {period}: {e}")





# ============================================================
# 数据模型 (Pydantic)
# ============================================================

class KLinePoint(BaseModel):
    time: str          # 日/周/月线: 'YYYY-MM-DD' | 4小时线: 'YYYY-MM-DD HH:MM'
    open: float
    high: float
    low: float
    close: float
    volume: float


class AnalysisRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    period: str = "1d"   # K线周期: '4h'/'1d'/'1w'/'1M'


class WatchGroupModel(BaseModel):
    id: str
    name: str
    stocks: List[str] = []   # 该分组下的自选股 (带市场前缀, 如 usAAPL)


class WatchlistGroupsRequest(BaseModel):
    groups: List[WatchGroupModel] = []


class SRLevel(BaseModel):
    price: float
    count: int
    type: str           # 'support' 或 'resistance'
    stars: int          # 2, 3, 5 星
    level: str          # 'Weak', 'Medium', 'Strong'


class RangeStat(BaseModel):
    pct: float
    start: str
    end: str


class AnalysisResponse(BaseModel):
    sr_levels: List[SRLevel]
    statistics: Dict[str, RangeStat]
    period: str = "1d"          # 实际使用的K线周期
    data_source: str = ""       # 实际命中的数据源


# ============================================================
# API 端点
# ============================================================

def _score_stock(kw: str, stock: dict) -> int:
    """对搜索关键字与标的进行高精相关度评分与模糊纠错。"""
    kw_upper = kw.upper()
    sym = stock["symbol"].upper()
    raw_code = sym.replace("US", "").replace("SH", "").replace("SZ", "").replace("HK", "")
    name = stock["name"].upper()
    pinyin = stock.get("pinyin", "").upper()
    pinyin_full = stock.get("pinyin_full", "").upper()
    aliases = [a.upper() for a in stock.get("aliases", [])]

    # 1. 股票代码精准匹配 (AAPL, 600519, GOOGL, BTC-USD) -> 1000
    if kw_upper == raw_code or kw_upper == sym:
        return 1000

    # 2. 股票代码前缀匹配 (GOOG -> GOOGL, NV -> NVDA)
    if raw_code.startswith(kw_upper):
        return 850 - len(raw_code)

    # 3. 别名精准匹配 (GOOGLE -> GOOGL, BABA -> 9988, TESLA -> TSLA)
    if kw_upper in aliases:
        return 800

    # 4. 拼音首字母精准匹配 (GG -> 谷歌, YWD -> 英伟达, GZMT -> 贵州茅台)
    if kw_upper == pinyin:
        return 750

    # 5. 拼音全拼精准匹配 (GUGE -> 谷歌, MEITUAN -> 美团)
    if kw_upper == pinyin_full:
        return 700

    # 6. 中文名精准匹配
    clean_name = name.split()[0]
    if kw == clean_name:
        return 720
    if kw in clean_name:
        return 650

    # 7. 别名前缀匹配 (GOOG -> GOOGLE, ALIB -> ALIBABA)
    if any(a.startswith(kw_upper) for a in aliases):
        return 600

    # 8. 拼音全拼前缀匹配
    if pinyin_full and pinyin_full.startswith(kw.lower()):
        return 500

    # 9. 别名/名称/代码子串包含匹配
    if any(kw_upper in a for a in aliases):
        return 450
    if kw_upper in name:
        return 400
    if kw_upper in raw_code:
        return 350

    # 10. 英文打错字模糊纠错 (Difflib / 编辑距离容错)
    # 如: gogle -> GOOGL/GOOGLE, telsa -> TSLA/TESLA, aple -> AAPL/APPLE
    if len(kw) >= 3 and kw.isascii():
        import difflib
        targets = [raw_code] + aliases + name.split()
        best_ratio = 0.0
        for t in targets:
            if len(t) >= 3:
                r = difflib.SequenceMatcher(None, kw_upper, t.upper()).ratio()
                if r > best_ratio:
                    best_ratio = r
        if best_ratio >= 0.72:
            return int(300 * best_ratio)

    return 0


@app.get("/api/search")
async def search_stocks(
    keyword: Optional[str] = Query(None, description="搜索股票名称、英文名称、代码或拼音缩写（全市场范围内）"),
):
    """
    全局证券搜索（系统入口级检索）：
      - 本地常用核心股票池优先多级加权评分与模糊纠错；
      - 腾讯全量证券搜索异步补全与长尾标的兜底；
      - 严禁盲目臆造虚假代码，未收录标的须经实盘行情校验才放行。
    """
    if not keyword:
        # 空关键词：返回全部在池股票（浏览用）
        return STOCKS_POOL

    kw = keyword.strip()
    kw_clean = kw.replace("拼音", "").strip()
    if not kw_clean:
        return STOCKS_POOL

    # 1. 扫描本地多市场核心股票池并打分
    scored_candidates = []
    seen_symbols = set()
    for stock in STOCKS_POOL:
        score = _score_stock(kw_clean, stock)
        if score > 0:
            scored_candidates.append((score, stock))
            seen_symbols.add(stock["symbol"].upper())

    # 2. 如果最高分候选已非常精准 (>= 750)，直接排序返回，保证首屏毫秒级响应
    if scored_candidates:
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        if scored_candidates[0][0] >= 750 and len(scored_candidates) >= 3:
            return [c[1] for c in scored_candidates[:20]]

    # 3. 异步查腾讯全量证券搜索 (覆盖全市场长尾股票)
    try:
        tencent_results = await _tencent_security_search(kw_clean)
        for t_item in tencent_results:
            sym_upper = t_item["symbol"].upper()
            if sym_upper in seen_symbols:
                continue
            seen_symbols.add(sym_upper)
            t_score = 300 if t_item.get("type") == "GP" else 180
            if kw_clean.upper() in sym_upper:
                t_score += 150
            scored_candidates.append((t_score, t_item))
    except Exception as e:
        print(f"[search] 腾讯全量搜索异常: {e}")

    # 4. 排序结果
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    if scored_candidates:
        return [c[1] for c in scored_candidates[:20]]

    # 5. 仍无匹配：严禁盲目臆造虚假股票！进行实盘行情探测验证
    if kw_clean.isascii() and len(kw_clean) <= 10:
        norm = normalize_symbol(kw_clean)
        if norm:
            try:
                # 仅当真实存在行情报价时才放行，彻底消除类似 USGOGLE 虚假股票
                q_res = await quote_provider.get_quotes([norm])
                if q_res and q_res[0].get("status") == "ok" and q_res[0].get("price") is not None:
                    m = market_of(norm)
                    label = MARKET_LABEL.get(m, "")
                    real_name = q_res[0].get("name") or strip_prefix(norm)
                    return [{
                        "symbol": norm,
                        "name": f"{real_name} ({strip_prefix(norm)})",
                        "market": m or "us",
                        "label": label,
                        "type": "GP",
                    }]
            except Exception:
                pass

    return []


async def _tencent_security_search(kw: str) -> list:
    """
    腾讯全量证券搜索兜底：覆盖本地池之外的「任意证券」。
    优先用结构化 proxy 接口，失败回退到 smartbox JSONP 接口。
    返回 STOCKS_POOL 同构列表（symbol/market/name/name_en/pinyin?）。
    任何异常/超时均返回 []，由调用方降级。
    """
    # 规范化腾讯返回的各类代码为统一「带市场前缀」形态（去交易所后缀，避免污染缓存键）
    def _norm_code(code: str) -> Optional[str]:
        if not code:
            return None
        c = code.strip().lower()
        # 已带市场前缀：sh/sz/hk/us
        if c.startswith(("sh", "sz", "hk", "us")):
            # 美股可能带 .o/.oq/.n/.nq/.am 等后缀，仅保留前缀+主体
            if c.startswith("us") and "." in c:
                c = c.split(".", 1)[0]
            return c.upper()
        # 纯英文（无前缀）→ 美股
        if re.fullmatch(r"[a-z]+", c):
            return "US" + c.upper()
        # 纯数字 → 自动识别沪深/港股
        if c.isdigit():
            return normalize_symbol(c)
        return None

    def _pool_item(code: str, name: str, pinyin: str = "", type_: str = "") -> Optional[dict]:
        sym = _norm_code(code)
        if not sym:
            return None
        m = market_of(sym)
        label = MARKET_LABEL.get(m, "")
        # 名称中可能含中英文混写，尝试拆出英文名
        name_en = ""
        parts = re.split(r"[\s\-]+", name.strip())
        if len(parts) > 1:
            en = [p for p in parts if re.search(r"[a-zA-Z]", p)]
            if en:
                name_en = " ".join(en)
        return {
            "symbol": sym,
            "name": name.strip(),
            "name_en": name_en,
            "market": m or "",
            "pinyin": pinyin,
            "label": label,
            "type": type_,
        }

    candidates: list = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SecuritySearch/1.0)"}
    try:
        # 唯一可靠兜底源：smartbox.gtimg.cn（返回 v_hint="market~code~name~pinyin~type^..." 赋值形式，非 JSONP）。
        # 注：proxy.finance.qq.com 在本环境经常性超时/返回 code:11（Can't load controller），
        # 且其慢响应会吃掉超时预算、导致兜底源被饿死，故弃用，仅保留 smartbox。
        async with httpx.AsyncClient(timeout=5.0, headers=headers, follow_redirects=True) as client:
            url = f"https://smartbox.gtimg.cn/s3/?t=all&q={kw}"
            try:
                resp = await client.get(url)
                txt = resp.text
                # 提取所有 "..." 内容（腾讯以 v_xxx="..." 赋值返回）
                for q in re.findall(r'"([^"]*)"', txt):
                    try:
                        q = json.loads('"' + q + '"')  # 解码 \uXXXX 转义
                    except Exception:
                        pass
                    if not q or q == "N":
                        continue  # "N" 为腾讯「无结果」标记
                    # 多个证券以 ^ 分隔，每个内部以 ~ 分隔（市场~代码~名称~拼音~类型）
                    for seg in q.split("^"):
                        rows = seg.split("~")
                        if len(rows) >= 3 and rows[0] in ("us", "sh", "sz", "hk"):
                            full_code = rows[0] + rows[1]
                            name = rows[2]
                            pinyin = rows[3] if len(rows) > 3 else ""
                            type_ = rows[4] if len(rows) > 4 else ""
                            item = _pool_item(full_code, name, pinyin, type_)
                            if item and item["symbol"] not in [c["symbol"] for c in candidates]:
                                candidates.append(item)
                                if len(candidates) >= 20:
                                    break
                    if len(candidates) >= 20:
                        break
            except Exception:
                pass
    except Exception:
        return []

    # 优先展示普通股(GP)，指数/权证/基金/窝轮等靠后，结果更贴近「搜股票」预期
    candidates.sort(key=lambda c: (0 if c.get("type") == "GP" else 1))
    return candidates[:20]


@app.get("/api/klines", response_model=List[KLinePoint])
async def get_klines(
    symbol: str = Query(..., description="股票代码，如 usAAPL"),
    period: str = Query("1d", description="K线周期: 4h/1d/1w/1M/3M/6M/1Y"),
    full: bool = Query(True, description="是否拉取上市以来全部历史 (默认 True)")
):
    """
    获取指定美股股票的多周期K线历史数据。

    支持周期:
      - 4h: 4小时K线 (由1小时数据重采样合成)
      - 1d: 日K线 (默认)
      - 1w: 周K线
      - 1M: 月K线
      - 3M: 季K线 (由日线重采样, 每根=一个季度)
      - 6M: 半年K线 (由日线重采样, 每根=半年)
      - 1Y: 年K线 (由日线重采样, 每根=一年)

    full=True 时拉取该股票上市以来的全部历史数据 (优先 Yahoo range=max)。
    数据源自动故障转移: Yahoo(全量优先) -> 腾讯(兜底)
    """
    if period not in SUPPORTED_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的K线周期: '{period}'，支持: {', '.join(SUPPORTED_PERIODS)}"
        )

    df, source = await get_klines_df(symbol, period=period, full=full)

    if df.empty:
        raise HTTPException(status_code=404, detail="无法获取该股票数据")

    points = []
    for _, row in df.iterrows():
        points.append(KLinePoint(
            time=str(row['date']),
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=float(row['volume'])
        ))

    return points


@app.post("/api/analysis", response_model=AnalysisResponse)
async def analyze_stock(request: AnalysisRequest):
    """
    获取股票在特定区间内的支撑阻力位分析结果及涨跌幅区间统计。

    支撑阻力位会根据 K线周期 (period) 自适应调整:
      - 4h:  捕捉短期波段高低点 (半衰期30根)
      - 1d:  日线级别 (半衰期60根)
      - 1w:  周线级别 (半衰期26根)
      - 1M:  月线级别 (半衰期12根)
      - 3M:  季线级别 (半衰期8根)
      - 6M:  半年线级别 (半衰期5根)
      - 1Y:  年线级别 (半衰期4根)
    """
    period = request.period if request.period in SUPPORTED_PERIODS else '1d'

    # 1. 获取 K 线 DataFrame (全量历史，用于支撑阻力识别与时间衰减权重)
    df, source = await get_klines_df(request.symbol, period=period, full=True)

    if df.empty:
        raise HTTPException(status_code=404, detail="分析时获取股票数据失败")

    # 2. 计算支撑与阻力位 (传入 period 使算法自适应)
    sr_levels = calculate_sr_levels(df, period=period)

    # 3. 计算特定日期区间的统计数据
    stats = calculate_range_stats(df, request.start_date, request.end_date)

    return {
        "sr_levels": sr_levels,
        "statistics": stats,
        "period": period,
        "data_source": source or ""
    }


@app.get("/api/periods")
async def get_supported_periods():
    """获取支持的K线周期列表"""
    return {
        "periods": SUPPORTED_PERIODS,
        "descriptions": {
            "5m": "5分钟K线",
            "15m": "15分钟K线",
            "1h": "1小时K线",
            "4h": "4小时K线",
            "1d": "日K线 (默认)",
            "1w": "周K线 (中期趋势)",
            "1M": "月K线 (长期结构)",
            "3M": "季K线 (每根=一个季度)",
            "6M": "半年K线 (每根=半年)",
            "1Y": "年K线 (每根=一年)"
        }
    }


# ============================================================
# 自选股持久化 (后端 JSON 文件存储，跨浏览器/origin 生效)
# 数据模型: 用户自创「分组」，前缀/市场不再由系统硬分，而由用户把标的放进哪
#           个分组来表达 (如「港股观察」「美股核心」)。分组结构:
#             { "groups": [ { "id": str, "name": str, "stocks": [str] }, ... ] }
# ============================================================
WATCHLIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.json")
# 默认分组（首次启动即体现多市场能力，但仅作为示例分组，用户可自由改名/删除/另建）
DEFAULT_GROUP_NAME = "我的自选"
DEFAULT_WATCHLIST = ["usAAPL", "usNVDA", "sh600519", "hk00700"]


def _default_groups() -> List[dict]:
    return [{"id": "default", "name": DEFAULT_GROUP_NAME, "stocks": list(DEFAULT_WATCHLIST)}]


def _load_groups() -> List[dict]:
    """读取分组。兼容旧版扁平 list 文件（归入默认分组）。"""
    try:
        if os.path.exists(WATCHLIST_FILE):
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 新格式: {"groups": [...]}
            if isinstance(data, dict) and isinstance(data.get("groups"), list):
                return data["groups"]
            # 旧格式兼容: 扁平 list -> 归入默认分组
            if isinstance(data, list):
                stocks = [str(s).upper() for s in data if s]
                if stocks:
                    return [{"id": "default", "name": DEFAULT_GROUP_NAME, "stocks": stocks}]
        # 无文件则写入默认并返回
        groups = _default_groups()
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump({"groups": groups}, f)
        return groups
    except Exception:
        return _default_groups()


def _save_groups(groups: List[dict]) -> List[dict]:
    """规范化分组后落盘: 大写、去首尾空格、去重、保序；缺 id 自动生成。"""
    norm: List[dict] = []
    for g in groups:
        stocks: List[str] = []
        for s in g.get("stocks", []):
            s = str(s).upper().strip()
            if s and s not in stocks:
                stocks.append(s)
        gid = g.get("id") or str(uuid.uuid4())
        gname = (g.get("name") or "").strip() or DEFAULT_GROUP_NAME
        norm.append({"id": gid, "name": gname, "stocks": stocks})
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump({"groups": norm}, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存自选失败: {e}")
    return norm


@app.get("/api/watchlist")
async def get_watchlist():
    """获取用户自选分组 (后端持久化，跨会话/预览生效)。"""
    return {"groups": _load_groups()}


@app.post("/api/watchlist")
async def save_watchlist(req: WatchlistGroupsRequest):
    """保存用户自选分组到后端，并通过 WebSocket 通知前端实时刷新。"""
    norm = _save_groups([g.dict() for g in req.groups])
    try:
        await ws_manager.broadcast({"action": "refresh_watchlist"})
    except Exception:
        pass
    return {"groups": norm}


# ============================================================
# Antigravity 操控面: WebSocket 双向实时管道 + HTTP 控制 API
# ============================================================

from db_cache import (
    save_annotations_batch,
    get_annotations,
    clear_annotations,
)
from strategy_adapter import run_strategy_analysis, generate_wave_chart_html


class WSManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.capture_futures: Dict[str, asyncio.Future] = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections:
            self.active_connections.remove(ws)

    async def broadcast(self, data: dict):
        for conn in list(self.active_connections):
            try:
                await conn.send_json(data)
            except Exception:
                self.disconnect(conn)

    def resolve_capture(self, request_id: str, image_base64: str):
        if request_id in self.capture_futures and not self.capture_futures[request_id].done():
            self.capture_futures[request_id].set_result(image_base64)


ws_manager = WSManager()

# 客户端运行态缓存
active_chart_state = {
    "symbol": "usAAPL",
    "period": "1d",
    "current_price": 0.0,
    "last_seen": datetime.now().isoformat(),
}


@app.websocket("/ws/control")
async def websocket_control(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            msg_text = await websocket.receive_text()
            try:
                data = json.loads(msg_text)
                msg_type = data.get("type")
                if msg_type == "client_state_update":
                    active_chart_state["symbol"] = data.get("symbol", active_chart_state["symbol"])
                    active_chart_state["period"] = data.get("period", active_chart_state["period"])
                    if "current_price" in data:
                        active_chart_state["current_price"] = float(data["current_price"])
                    active_chart_state["last_seen"] = datetime.now().isoformat()
                elif msg_type == "capture_result":
                    req_id = data.get("request_id")
                    img = data.get("image_base64")
                    if req_id and img:
                        ws_manager.resolve_capture(req_id, img)
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


class OpenChartRequest(BaseModel):
    symbol: str
    period: Optional[str] = "1d"


class MarkerItem(BaseModel):
    id: Optional[str] = None
    time: Any
    position: str = "aboveBar"  # 'aboveBar' | 'belowBar' | 'inBar'
    color: str = "#10b981"
    shape: str = "arrowDown"
    text: str = ""


class AddMarkersRequest(BaseModel):
    symbol: str
    markers: List[MarkerItem]
    source: Optional[str] = "agent"


class LineItem(BaseModel):
    id: Optional[str] = None
    price: float
    color: str = "#3b82f6"
    lineWidth: Optional[int] = 1
    lineStyle: Optional[int] = 2  # 0=Solid, 1=Dotted, 2=Dashed
    title: Optional[str] = ""


class DrawLinesRequest(BaseModel):
    symbol: str
    lines: List[LineItem]
    source: Optional[str] = "agent"


class BoxItem(BaseModel):
    id: Optional[str] = None
    time1: Any
    time2: Any
    price1: float
    price2: float
    fillColor: Optional[str] = "rgba(59, 130, 246, 0.12)"
    borderColor: Optional[str] = "#3b82f6"
    label: Optional[str] = ""


class DrawBoxesRequest(BaseModel):
    symbol: str
    boxes: List[BoxItem]
    source: Optional[str] = "agent"


class RunStrategyRequest(BaseModel):
    symbol: str
    period: Optional[str] = "1d"
    mode: Optional[str] = "swing"  # 'swing' | 'day'
    draw_on_chart: Optional[bool] = True
    klines: Optional[List[Dict[str, Any]]] = None


class ClearAnnotationsRequest(BaseModel):
    symbol: str
    kind: Optional[str] = None
    source: Optional[str] = None


@app.post("/api/control/open")
async def control_open(req: OpenChartRequest):
    """控制前端桌面软件切换当前标的与周期"""
    norm_sym = normalize_symbol(req.symbol) or req.symbol
    period = req.period or "1d"
    active_chart_state["symbol"] = norm_sym
    active_chart_state["period"] = period
    active_chart_state["last_seen"] = datetime.now().isoformat()

    await ws_manager.broadcast({
        "action": "open",
        "symbol": norm_sym,
        "period": period,
    })
    return {"status": "ok", "state": active_chart_state}


@app.get("/api/control/state")
async def control_get_state():
    """读取当前股票、周期与数据库中的所有已有标注"""
    sym = active_chart_state["symbol"]
    annos = get_annotations(sym)
    return {
        "status": "ok",
        "state": active_chart_state,
        "connected_clients": len(ws_manager.active_connections),
        "annotations": annos,
    }


@app.post("/api/control/markers")
async def control_add_markers(req: AddMarkersRequest):
    """向当前或指定股票图表添加买卖点/拐点标注 (持久化并实时广播)"""
    norm_sym = normalize_symbol(req.symbol) or req.symbol
    raw_markers = [m.model_dump() if hasattr(m, "model_dump") else m.dict() for m in req.markers]
    save_annotations_batch(norm_sym, "marker", raw_markers, source=req.source or "agent")
    await ws_manager.broadcast({
        "action": "add_markers",
        "symbol": norm_sym,
        "markers": raw_markers,
    })
    return {"status": "ok", "count": len(raw_markers)}


@app.post("/api/control/lines")
async def control_draw_lines(req: DrawLinesRequest):
    """绘制水平价格线（入场、止损、目标、波浪证伪线）"""
    norm_sym = normalize_symbol(req.symbol) or req.symbol
    raw_lines = [l.model_dump() if hasattr(l, "model_dump") else l.dict() for l in req.lines]
    save_annotations_batch(norm_sym, "line", raw_lines, source=req.source or "agent")
    await ws_manager.broadcast({
        "action": "draw_lines",
        "symbol": norm_sym,
        "lines": raw_lines,
    })
    return {"status": "ok", "count": len(raw_lines)}


@app.post("/api/control/boxes")
async def control_draw_boxes(req: DrawBoxesRequest):
    """绘制震荡箱体与供求失衡区矩形"""
    norm_sym = normalize_symbol(req.symbol) or req.symbol
    raw_boxes = [b.model_dump() if hasattr(b, "model_dump") else b.dict() for b in req.boxes]
    save_annotations_batch(norm_sym, "box", raw_boxes, source=req.source or "agent")
    await ws_manager.broadcast({
        "action": "draw_boxes",
        "symbol": norm_sym,
        "boxes": raw_boxes,
    })
    return {"status": "ok", "count": len(raw_boxes)}


@app.post("/api/control/strategy")
async def control_run_strategy(req: RunStrategyRequest):
    """一键运行 Investment_Assistant 价格行为交易策略并在 K 线图上自动渲染"""
    import pandas as pd
    norm_sym = normalize_symbol(req.symbol) or req.symbol
    period = req.period or "1d"
    mode = req.mode or "swing"

    df = None
    # 优先使用前端直接传入的当前图表真实/演示K线
    if req.klines and len(req.klines) > 0:
        try:
            df = pd.DataFrame(req.klines)
        except Exception:
            df = None

    # 若未传K线或构建失败，向后端数据源拉取
    if df is None or df.empty:
        try:
            df, src = await get_klines_df(norm_sym, period=period, full=True)
        except Exception:
            df = None

    # 若远程拉取失败，尝试检查 Investment_Assistant 本地历史 CSV
    if df is None or df.empty:
        clean_sym = strip_prefix(norm_sym).upper()
        csv_file = os.path.join(INVESTMENT_ASSISTANT_DIR, "data", f"{clean_sym}.csv")
        if os.path.exists(csv_file):
            try:
                df = pd.read_csv(csv_file)
            except Exception:
                df = None

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"无法获取 {norm_sym} 的 {period} K线用于策略分析，请确认网络连接或传入K线数据")

    # 执行 Investment_Assistant 策略
    res = run_strategy_analysis(norm_sym, period=period, mode=mode, df=df)

    if req.draw_on_chart:
        # 清除该标的之前的所有策略标注，保证数据库只保留最新一版高精度标注
        clear_annotations(norm_sym, source="pa_strategy")
        annos = res.get("annotations", {})
        markers = annos.get("markers", [])
        lines = annos.get("lines", [])
        boxes = annos.get("boxes", [])
        channel_lines = annos.get("channel_lines", [])
        wave_lines = annos.get("wave_lines", None)

        if markers:
            save_annotations_batch(norm_sym, "marker", markers, source="pa_strategy")
        if lines:
            save_annotations_batch(norm_sym, "line", lines, source="pa_strategy")
        if boxes:
            save_annotations_batch(norm_sym, "box", boxes, source="pa_strategy")
        if channel_lines:
            save_annotations_batch(norm_sym, "channel_line", channel_lines, source="pa_strategy")
        if wave_lines:
            save_annotations_batch(norm_sym, "wave_line", [wave_lines], source="pa_strategy")

        await ws_manager.broadcast({
            "action": "add_markers",
            "symbol": norm_sym,
            "markers": markers,
        })
        await ws_manager.broadcast({
            "action": "draw_lines",
            "symbol": norm_sym,
            "lines": lines,
        })
        await ws_manager.broadcast({
            "action": "draw_boxes",
            "symbol": norm_sym,
            "boxes": boxes,
        })
        await ws_manager.broadcast({
            "action": "draw_channel_lines",
            "symbol": norm_sym,
            "channel_lines": channel_lines,
        })
        await ws_manager.broadcast({
            "action": "draw_wave_lines",
            "symbol": norm_sym,
            "wave_lines": wave_lines,
        })

    return res


@app.get("/api/strategy/html")
async def get_strategy_chart_html(symbol: str, period: str = "1d"):
    """返回由 Investment_Assistant 生成的高保真交互式波浪与通道分析 HTML 页面"""
    import pandas as pd
    from fastapi.responses import HTMLResponse
    norm_sym = normalize_symbol(symbol) or symbol
    df = None
    try:
        df, _ = await get_klines_df(norm_sym, period=period, full=True)
    except Exception:
        df = None

    if df is None or df.empty:
        clean_sym = strip_prefix(norm_sym).upper()
        csv_file = os.path.join(INVESTMENT_ASSISTANT_DIR, "data", f"{clean_sym}.csv")
        if os.path.exists(csv_file):
            try:
                df = pd.read_csv(csv_file)
            except Exception:
                df = None

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"无法获取 {norm_sym} 的K线数据")
    
    html_content = generate_wave_chart_html(norm_sym, period=period, df=df)
    return HTMLResponse(content=html_content, media_type="text/html")


@app.post("/api/control/clear")
async def control_clear_annotations(req: ClearAnnotationsRequest):
    """清理图表上的标注"""
    norm_sym = normalize_symbol(req.symbol) or req.symbol
    del_count = clear_annotations(norm_sym, kind=req.kind, source=req.source)
    await ws_manager.broadcast({
        "action": "clear",
        "symbol": norm_sym,
        "kind": req.kind,
    })
    return {"status": "ok", "deleted": del_count}


@app.get("/api/control/annotations")
async def control_get_annotations(
    symbol: str = Query(..., description="股票代码"),
    kind: Optional[str] = Query(None, description="标注类型: marker / line / box"),
):
    norm_sym = normalize_symbol(symbol) or symbol
    return {"symbol": norm_sym, "annotations": get_annotations(norm_sym, kind=kind)}


@app.post("/api/control/capture")
async def control_capture_chart():
    """截取当前前端图表 Canvas 图片保存为本地文件"""
    req_id = str(uuid.uuid4())
    future = asyncio.get_event_loop().create_future()
    ws_manager.capture_futures[req_id] = future

    await ws_manager.broadcast({
        "action": "capture_chart",
        "request_id": req_id,
    })

    try:
        base64_data = await asyncio.wait_for(future, timeout=5.0)
    except asyncio.TimeoutError:
        ws_manager.capture_futures.pop(req_id, None)
        return {"status": "error", "message": "截取图表超时 (可能前端窗口未连接或正在后台休眠)"}
    finally:
        ws_manager.capture_futures.pop(req_id, None)

    # 保存图片文件到本地
    import base64
    app_data = os.environ.get("APPDATA")
    out_dir = os.path.join(app_data, "StockVision", "screenshots") if app_data else os.path.join(os.path.dirname(__file__), "screenshots")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"chart_{active_chart_state['symbol']}_{int(datetime.now().timestamp())}.png")

    raw_b64 = base64_data.split(",")[-1]
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(raw_b64))

    return {
        "status": "ok",
        "file_path": out_path,
        "symbol": active_chart_state["symbol"],
        "timestamp": datetime.now().isoformat(),
    }



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
