# -*- coding: utf-8 -*-
"""
统一证券代码归一与市场识别模块
供路由层、行情引擎、缓存层、控制面及测试共用，避免反向依赖 main.py。
"""

import re
from typing import Optional

SUPPORTED_CRYPTO_BASES = ("BTC", "ETH", "SOL", "DOGE", "XRP", "BNB")

MARKET_LABEL = {
    "us": "美股",
    # 暂时停用 A股 与 港股，保留注释以备后用:
    # "ash": "沪A",
    # "asz": "深A",
    # "hk": "港股",
    "futures": "期货",
    "crypto": "加密",
}


def norm_market_prefix(sym: str) -> str:
    """将市场前缀规范为小写（如 USAAPL -> usAAPL），兼容腾讯行情/K线接口的大小写要求。"""
    if not sym:
        return sym
    # 暂时停用 SH/SZ/HK 前缀处理，保留注释以备后用:
    # return re.sub(r'^(US|SH|SZ|HK)', lambda m: m.group(1).lower(), sym.strip(), flags=re.IGNORECASE)
    return re.sub(r'^(US)', lambda m: m.group(1).lower(), sym.strip(), flags=re.IGNORECASE)


def _strip_crypto_us_prefix(clean: str) -> str:
    """剥离误加在主流加密货币前的 US 前缀（如 USBTC-USD -> BTC-USD）。"""
    if clean.startswith("US") and any(
        clean[2:] in (b, f"{b}-USD", f"{b}-USDT", f"{b}USD", f"{b}USDT")
        for b in SUPPORTED_CRYPTO_BASES
    ):
        return clean[2:]
    return clean


def normalize_symbol(raw: str, market: Optional[str] = None) -> Optional[str]:
    """把用户输入归一化为带市场前缀的统一代码（如 AAPL -> USAAPL, btc/usdt -> BTC-USD）。"""
    s = (raw or "").strip().upper()
    if not s:
        return None

    # 加密货币统一归一化为 XXX-USD
    s_crypto = s.replace("/", "-").replace("_", "-")
    clean_base = _strip_crypto_us_prefix(s_crypto)

    for base in SUPPORTED_CRYPTO_BASES:
        if clean_base in (base, f"{base}-USD", f"{base}-USDT", f"{base}USD", f"{base}USDT"):
            return f"{base}-USD"

    if clean_base.endswith(("-USD", "-USDT")):
        base = clean_base.split("-")[0]
        if base.startswith("US") and len(base) > 2:
            base = base[2:]
        return f"{base}-USD"

    if clean_base.endswith("USDT") and len(clean_base) > 4:
        base = clean_base[:-4]
        if base.startswith("US") and len(base) > 2:
            base = base[2:]
        return f"{base}-USD"

    if clean_base.endswith("USD") and len(clean_base) > 3:
        base = clean_base[:-3]
        if base.startswith("US") and len(base) > 2:
            base = base[2:]
        return f"{base}-USD"

    # 暂时停用 A股与港股前缀判断:
    # if s.startswith(("US", "SH", "SZ", "HK")):
    if s.startswith("US"):
        return s

    if s.endswith("MAIN"):
        return s[:-4] + "main"

    if market == "us":
        return "US" + s

    return "US" + s


def market_of(symbol: str, default_us: bool = False) -> Optional[str]:
    """
    识别代码所属市场。
    - default_us=False: 严格按前缀/后缀识别（无前缀返回 None，供接口校验使用）
    - default_us=True:  非停用市场且无明确前缀时默认回退为 'us'（供行情轮询配置使用）
    """
    if not symbol:
        return None
    s = symbol.upper()
    clean = s.replace("/", "-").replace("_", "-")
    clean_no_us = _strip_crypto_us_prefix(clean)

    if (
        clean.endswith(("-USD", "-USDT"))
        or clean.endswith("USDT")
        or clean in SUPPORTED_CRYPTO_BASES
        or clean_no_us in SUPPORTED_CRYPTO_BASES
        or clean_no_us.endswith(("-USD", "-USDT"))
        or clean_no_us.endswith("USDT")
        or any(
            clean_no_us in (b, f"{b}USD", f"{b}USDT", f"{b}-USD", f"{b}-USDT")
            for b in SUPPORTED_CRYPTO_BASES
        )
    ):
        return "crypto"

    if s.endswith("MAIN"):
        return "futures"
    if s.startswith("US"):
        return "us"
    if s.startswith(("SH", "SZ", "HK")):
        return None
    return "us" if default_us else None


def strip_prefix(symbol: str) -> str:
    """剥离市场前缀（如 usAAPL -> AAPL）。"""
    s = symbol.upper()
    for p in ("US",):
        if s.startswith(p):
            return s[len(p):]
    return s
