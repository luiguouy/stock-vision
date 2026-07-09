# -*- coding: utf-8 -*-
"""
智能股票技术分析平台 - 本地 K线数据缓存层 (SQLite)

目标:
  把每个 (symbol, period) 拉取过的全量历史持久化到本地 SQLite 数据库,
  后续请求 (含服务重启、前端刷新) 直接从本地读取, 避免每次都重新从
  Yahoo / 腾讯 拉取上万根历史数据, 大幅提升二次加载速度。

设计:
  - klines 表: 逐根 K线 (symbol, period, date 为主键, 其余为 OHLCV)
  - meta  表: 记录每个 (symbol, period) 的最后更新时间与数据源
  - 读取带 TTL (默认 24h): 超过时效视为过期, 重新拉取后再写回
"""

import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import pandas as pd

# 复用数据源层的粒度校验, 防止被污染(如季度数据当日报)的缓存被直接返回
from data_provider import validate_klines

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_data.db")

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS klines (
        symbol TEXT NOT NULL,
        period TEXT NOT NULL,
        date   TEXT NOT NULL,
        open   REAL,
        high   REAL,
        low    REAL,
        close  REAL,
        volume REAL,
        PRIMARY KEY (symbol, period, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS meta (
        symbol       TEXT NOT NULL,
        period       TEXT NOT NULL,
        last_updated TEXT,
        source       TEXT,
        PRIMARY KEY (symbol, period)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_klines_sym_period ON klines(symbol, period)",
]


def init_db() -> None:
    """初始化数据库表结构 (幂等, 可重复调用)。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        for stmt in _SCHEMA:
            cur.execute(stmt)
        conn.commit()
    finally:
        conn.close()


def get_cached_klines(
    symbol: str, period: str, max_age_hours: int = 24
) -> Optional[List[Dict]]:
    """
    读取缓存的 K线数据。

    返回:
      - 命中且未过期: List[Dict] (含 date/open/high/low/close/volume, 已按日期升序)
      - 未命中 / 已过期 / 无数据: None
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT last_updated FROM meta WHERE symbol=? AND period=?",
            (symbol, period),
        )
        row = cur.fetchone()
        if not row:
            return None

        last_updated = datetime.fromisoformat(row[0])
        if datetime.now() - last_updated > timedelta(hours=max_age_hours):
            return None  # 过期, 视为未命中

        cur.execute(
            "SELECT date, open, high, low, close, volume "
            "FROM klines WHERE symbol=? AND period=? "
            "ORDER BY date ASC",
            (symbol, period),
        )
        rows = cur.fetchall()
        if not rows:
            return None

        data = [
            {
                "date": r[0],
                "open": r[1],
                "high": r[2],
                "low": r[3],
                "close": r[4],
                "volume": r[5],
            }
            for r in rows
        ]

        # 关键: 读取缓存后也做粒度校验。若缓存被污染 (例如某次拉到了
        # 每 3 个月一根的季度桩数据却按日线存了下来), 直接当作未命中,
        # 触发重新拉取正确粒度的数据, 避免错误数据在 TTL 内持续返回。
        df_check = pd.DataFrame(data)
        if not validate_klines(df_check, period):
            return None

        return data
    finally:
        conn.close()


def save_klines(
    symbol: str, period: str, klines: List[Dict], source: str = ""
) -> None:
    """将 K线数据批量写入缓存 (先清空旧数据再插入, 保证一致性)。"""
    if not klines:
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM klines WHERE symbol=? AND period=?", (symbol, period)
        )
        cur.executemany(
            "INSERT OR REPLACE INTO klines "
            "(symbol, period, date, open, high, low, close, volume) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    symbol,
                    period,
                    k["date"],
                    k["open"],
                    k["high"],
                    k["low"],
                    k["close"],
                    k["volume"],
                )
                for k in klines
            ],
        )
        cur.execute(
            "INSERT OR REPLACE INTO meta (symbol, period, last_updated, source) "
            "VALUES (?,?,?,?)",
            (symbol, period, datetime.now().isoformat(), source),
        )
        conn.commit()
    finally:
        conn.close()


def cache_status(symbol: str, period: str) -> Optional[Dict]:
    """查询某 (symbol, period) 的缓存元信息 (调试用)。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT last_updated, source FROM meta WHERE symbol=? AND period=?",
            (symbol, period),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {"last_updated": row[0], "source": row[1]}
    finally:
        conn.close()
