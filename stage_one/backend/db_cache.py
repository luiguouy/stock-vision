# -*- coding: utf-8 -*-
"""
智能股票技术分析平台 - 本地 K线数据与图表标注缓存层 (SQLite WAL)

目标:
  把每个 (symbol, period) 拉取过的全量历史以及图表标注持久化到本地 SQLite 数据库，
  开启 WAL 模式保证高并发低 I/O，存储路径默认采用 %APPDATA%/StockVision/stock_data.db。
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union

import pandas as pd

# 优先存放在 %APPDATA%/StockVision/
app_data = os.environ.get("APPDATA")
if app_data:
    SV_DIR = os.path.join(app_data, "StockVision")
    os.makedirs(SV_DIR, exist_ok=True)
    DB_PATH = os.path.join(SV_DIR, "stock_data.db")
else:
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
    """
    CREATE TABLE IF NOT EXISTS annotations (
        id         TEXT PRIMARY KEY,
        symbol     TEXT NOT NULL,
        kind       TEXT NOT NULL,
        data       TEXT NOT NULL,
        source     TEXT,
        created_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_anno_sym ON annotations(symbol, kind)",
]


_tables_initialized = False


def _get_connection() -> sqlite3.Connection:
    """获取启用了 WAL 模式的高性能 SQLite 连接，并确保表结构已初始化。"""
    global _tables_initialized
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    if not _tables_initialized:
        cur = conn.cursor()
        for stmt in _SCHEMA:
            cur.execute(stmt)
        conn.commit()
        _tables_initialized = True
    return conn


def init_db() -> None:
    """初始化数据库表结构 (幂等, 可重复调用)。"""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        for stmt in _SCHEMA:
            cur.execute(stmt)
        conn.commit()
    finally:
        conn.close()


def get_cached_klines(
    symbol: str, period: str, max_age_hours: Union[int, float] = 24
) -> Optional[List[Dict]]:
    """
    读取缓存的 K线数据。
    """
    from data_provider import validate_klines

    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT last_updated FROM meta WHERE symbol=? AND period=?",
            (symbol, period),
        )
        row = cur.fetchone()
        if not row:
            return None

        try:
            last_updated = datetime.fromisoformat(row[0])
            if datetime.now() - last_updated > timedelta(hours=max_age_hours):
                return None  # 过期
        except Exception:
            return None

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
    conn = _get_connection()
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
    conn = _get_connection()
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


# ============================================================
# 图表标注持久化接口 (Markers / PriceLines / Boxes)
# ============================================================

def save_annotation(anno_id: str, symbol: str, kind: str, data: dict, source: str = "") -> None:
    """保存或更新单个图表标注。"""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        now_str = datetime.now().isoformat()
        cur.execute(
            "INSERT OR REPLACE INTO annotations (id, symbol, kind, data, source, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (anno_id, symbol.upper(), kind, json.dumps(data, ensure_ascii=False), source, now_str),
        )
        conn.commit()
    finally:
        conn.close()


def save_annotations_batch(symbol: str, kind: str, items: List[dict], source: str = "") -> None:
    """批量保存图表标注。"""
    if not items:
        return
    conn = _get_connection()
    try:
        cur = conn.cursor()
        now_str = datetime.now().isoformat()
        records = []
        for it in items:
            aid = str(it.get("id") or f"{kind}_{symbol}_{datetime.now().timestamp()}_{len(records)}")
            records.append((aid, symbol.upper(), kind, json.dumps(it, ensure_ascii=False), source, now_str))
        cur.executemany(
            "INSERT OR REPLACE INTO annotations (id, symbol, kind, data, source, created_at) "
            "VALUES (?,?,?,?,?,?)",
            records,
        )
        conn.commit()
    finally:
        conn.close()


def get_annotations(symbol: str, kind: Optional[str] = None) -> List[dict]:
    """获取指定股票的所有标注。"""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        if kind:
            cur.execute(
                "SELECT id, symbol, kind, data, source, created_at FROM annotations "
                "WHERE symbol=? AND kind=? ORDER BY created_at ASC",
                (symbol.upper(), kind),
            )
        else:
            cur.execute(
                "SELECT id, symbol, kind, data, source, created_at FROM annotations "
                "WHERE symbol=? ORDER BY created_at ASC",
                (symbol.upper(),),
            )
        rows = cur.fetchall()
        result = []
        for r in rows:
            try:
                payload = json.loads(r[3])
                payload["id"] = r[0]
                payload["symbol"] = r[1]
                payload["kind"] = r[2]
                payload["source"] = r[4]
                payload["created_at"] = r[5]
                result.append(payload)
            except Exception:
                continue
        return result
    finally:
        conn.close()


def clear_annotations(symbol: str, kind: Optional[str] = None, source: Optional[str] = None) -> int:
    """按条件清理标注。返回被删除的条数。"""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        sql = "DELETE FROM annotations WHERE symbol=?"
        params = [symbol.upper()]
        if kind:
            sql += " AND kind=?"
            params.append(kind)
        if source:
            sql += " AND source=?"
            params.append(source)
        cur.execute(sql, params)
        deleted = cur.rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()
