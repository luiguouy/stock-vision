# -*- coding: utf-8 -*-
"""
智能股票技术分析平台 - 第一阶段 (MVP) 后端主入口文件
基于 FastAPI 框架，提供股票搜索、日K线获取以及支撑阻力位/区间统计接口。
"""

# pyrefly: ignore [missing-import]
import httpx
import pandas as pd
# pyrefly: ignore [missing-import]
import numpy as np
from datetime import datetime, timedelta
# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException, Query
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from analysis import calculate_sr_levels, calculate_range_stats

app = FastAPI(title="智能股票技术分析平台 ")
from fastapi.responses import RedirectResponse

@app.get("/")
def read_root():
    return RedirectResponse(url="/docs")

# 启用 CORS 跨域支持，允许前端本地调试
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 本地美股股票池，用于模糊匹配
STOCKS_POOL = [
    {"symbol": "usAAPL", "name": "苹果 Apple", "pinyin": "pg"},
    {"symbol": "usNVDA", "name": "英伟达 NVIDIA", "pinyin": "ywd"},
    {"symbol": "usTSLA", "name": "特斯拉 Tesla", "pinyin": "tsl"},
    {"symbol": "usAMD", "name": "超微半导体 AMD", "pinyin": "cw"},
    {"symbol": "usMSFT", "name": "微软 Microsoft", "pinyin": "wr"},
    {"symbol": "usMETA", "name": "Meta", "pinyin": "meta"},
    {"symbol": "usGOOGL", "name": "谷歌 Alphabet", "pinyin": "gg"},
    {"symbol": "usAMZN", "name": "亚马逊 Amazon", "pinyin": "ymx"},
    {"symbol": "usMU", "name": "美光科技 Micron", "pinyin": "mg"},
    {"symbol": "usSNDK", "name": "闪迪 SanDisk", "pinyin": "sd"}
]

# K线点数据定义
class KLinePoint(BaseModel):
    time: str      # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: float

# 分析请求报文定义
class AnalysisRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str

# 支撑位/阻力位响应数据定义
class SRLevel(BaseModel):
    price: float
    count: int
    type: str       # 'support' 或 'resistance'
    stars: int      # 2, 3, 5 星
    level: str      # 'Weak', 'Medium', 'Strong'

class RangeStat(BaseModel):
    pct: float
    start: str
    end: str

class AnalysisResponse(BaseModel):
    sr_levels: List[SRLevel]
    statistics: Dict[str, RangeStat]


async def _fetch_tencent_direct(symbol: str) -> pd.DataFrame:
    """
    直接从腾讯证券行情源拉取单只股票的日K线。
    """
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,320,qfq"
    
    async with httpx.AsyncClient() as client:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            response = await client.get(url, headers=headers, timeout=10.0, follow_redirects=True)
            
            if response.status_code != 200:
                return pd.DataFrame()
                
            json_data = response.json()
            if json_data.get("code") != 0:
                return pd.DataFrame()
                
            stock_data = json_data.get("data", {}).get(symbol, {})
            # 兼容带有前复权标识的 qfqday 或是普通的 day
            kline_key = "qfqday" if "qfqday" in stock_data else "day"
            
            if kline_key not in stock_data or not stock_data[kline_key]:
                return pd.DataFrame()
                
            raw_klines = stock_data[kline_key]
            parsed_data = []
            
            for item in raw_klines:
                # 腾讯行情日K点格式: ['2023-11-09', '1636.67', '1640.67', '1645.55', '1629.55', '12800.00']
                if len(item) >= 6:
                    parsed_data.append({
                        "date": item[0],
                        "open": float(item[1]),
                        "close": float(item[2]),
                        "high": float(item[3]),
                        "low": float(item[4]),
                        "volume": float(item[5])
                    })
                    
            if parsed_data and len(parsed_data) >= 5:
                return pd.DataFrame(parsed_data)
            return pd.DataFrame()
                
        except Exception:
            return pd.DataFrame()


async def fetch_kline_df(symbol: str) -> pd.DataFrame:
    """
    自腾讯证券接口拉取历史日K线数据。若出错，则直接报错，绝不使用 Mock 假数据。
    支持自动匹配美股交易所后缀（.OQ纳斯达克, .N纽交所, .AM美交所）。
    """
    # 1. 如果代码已经显式指定了后缀，直接查询
    if "." in symbol:
        df = await _fetch_tencent_direct(symbol)
        if not df.empty:
            return df
        raise HTTPException(status_code=404, detail=f"未找到股票 {symbol} 的 K 线数据")
        
    # 2. 否则，针对美股尝试自动补齐主流后缀并查询
    symbol_lower = symbol.lower()
    if symbol_lower.startswith("us"):
        ticker = symbol_lower[2:].upper()
        # 依次尝试 .OQ (纳斯达克), .N (纽交所), .AM (美交所)
        for suffix in [".OQ", ".N", ".AM"]:
            formatted_symbol = f"us{ticker}{suffix}"
            df = await _fetch_tencent_direct(formatted_symbol)
            if not df.empty:
                return df
                
    # 3. 兜底直接尝试拉取
    df = await _fetch_tencent_direct(symbol)
    if not df.empty:
        return df
        
    raise HTTPException(
        status_code=404, 
        detail=f"未找到股票 {symbol} 的 K 线数据，请检查网络连接或确认代码是否正确"
    )


@app.get("/api/search")
async def search_stocks(keyword: Optional[str] = Query(None, description="搜索股票名称、代码或拼音缩写")):
    """
    提供本地常用美股股票的模糊匹配。若无匹配，纯字母可以作为美股代码直接加载。
    """
    if not keyword:
        return STOCKS_POOL
        
    kw = keyword.strip().lower()
    matched = []
    
    # 1. 尝试匹配本地常用股票池
    for stock in STOCKS_POOL:
        if (kw in stock["symbol"].lower() or 
            kw in stock["name"].lower() or 
            kw in stock["pinyin"].lower()):
            matched.append(stock)
            
    if matched:
        return matched
        
    # 2. 如果无匹配，判定是否为美股代码格式
    if len(kw) > 2 and kw.startswith("us"):
        return [{"symbol": kw, "name": f"美股 {kw[2:].upper()}"}]
        
    if kw.isalpha():
        symbol_formatted = f"us{kw.upper()}"
        return [{"symbol": symbol_formatted, "name": f"美股 {kw.upper()}"}]
        
    return []


@app.get("/api/klines", response_model=List[KLinePoint])
async def get_klines(symbol: str = Query(..., description="股票代码，如 usAAPL")):
    """
    获取指定美股股票的日K线历史数据（最近320根）
    """
    df = await fetch_kline_df(symbol)
    
    if df.empty:
        raise HTTPException(status_code=404, detail="无法获取该股票数据")
        
    points = []
    for _, row in df.iterrows():
        points.append(KLinePoint(
            time=row['date'],
            open=row['open'],
            high=row['high'],
            low=row['low'],
            close=row['close'],
            volume=row['volume']
        ))
        
    return points


@app.post("/api/analysis", response_model=AnalysisResponse)
async def analyze_stock(request: AnalysisRequest):
    """
    获取股票在特定区间内的支撑阻力位分析结果及涨跌幅区间统计
    """
    # 1. 获取 K 线 DataFrame
    df = await fetch_kline_df(request.symbol)
    
    if df.empty:
        raise HTTPException(status_code=404, detail="分析时获取股票数据失败")
        
    # 2. 计算支撑与阻力位
    sr_levels = calculate_sr_levels(df)
    
    # 3. 计算特定日期区间的统计数据
    stats = calculate_range_stats(df, request.start_date, request.end_date)
    
    return {
        "sr_levels": sr_levels,
        "statistics": stats
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
