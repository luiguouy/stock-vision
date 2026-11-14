# -*- coding: utf-8 -*-
"""
StockVision 统一控制面客户端
供 CLI (sv) 与 MCP Server 共用，集中管理后台进程拉起、免代理 HTTP 通信与自选股业务操作。
"""

import os
import sys
import time
import uuid
import subprocess
from typing import Any, Dict, List, Optional

import httpx

from symbols import normalize_symbol, norm_market_prefix

BASE_URL = "http://127.0.0.1:8000"
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# 彻底免除系统代理干扰的本地回环客户端
http_client = httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False)


def ensure_app_running() -> bool:
    """确保 StockVision 后台服务在线；若未启动则秒级拉起 desktop_main.py。"""
    try:
        resp = http_client.get("/api/health")
        if resp.status_code == 200:
            return True
    except Exception:
        pass

    venv_py = os.path.join(
        os.path.dirname(os.path.dirname(APP_DIR)), ".venv", "Scripts", "python.exe"
    )
    python_exe = venv_py if os.path.exists(venv_py) else sys.executable
    desktop_script = os.path.join(APP_DIR, "desktop_main.py")
    subprocess.Popen([python_exe, desktop_script], cwd=APP_DIR)

    for _ in range(15):
        time.sleep(0.2)
        try:
            resp = http_client.get("/api/health")
            if resp.status_code == 200:
                return True
        except Exception:
            continue
    return False


def _format_symbol(raw: str) -> str:
    """统一归一化为标准接口代码（如 aapl -> usAAPL, btc/usdt -> BTC-USD）。"""
    norm = normalize_symbol(raw) or (raw or "").strip()
    return norm_market_prefix(norm)


def _post(path: str, payload: Optional[Dict[str, Any]] = None, err_prefix: str = "请求失败") -> Dict[str, Any]:
    ensure_app_running()
    try:
        resp = http_client.post(path, json=payload) if payload is not None else http_client.post(path)
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": f"{err_prefix}: {e}"}


def get_state() -> Dict[str, Any]:
    ensure_app_running()
    try:
        return http_client.get("/api/control/state").json()
    except Exception as e:
        return {"status": "error", "message": f"获取状态失败: {e}"}


def open_chart(symbol: str, period: str = "1d") -> Dict[str, Any]:
    return _post("/api/control/open", {"symbol": symbol, "period": period}, "切换图表失败")


def add_markers(symbol: str, markers: List[Dict[str, Any]]) -> Dict[str, Any]:
    return _post("/api/control/markers", {"symbol": symbol, "markers": markers}, "添加标记失败")


def draw_lines(symbol: str, lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    return _post("/api/control/lines", {"symbol": symbol, "lines": lines}, "绘制价格线失败")


def draw_boxes(symbol: str, boxes: List[Dict[str, Any]]) -> Dict[str, Any]:
    return _post("/api/control/boxes", {"symbol": symbol, "boxes": boxes}, "绘制矩形失败")


def run_strategy(
    symbol: str,
    period: str = "1d",
    mode: str = "swing",
    draw_on_chart: bool = True,
) -> Dict[str, Any]:
    return _post(
        "/api/control/strategy",
        {
            "symbol": symbol,
            "period": period,
            "mode": mode,
            "draw_on_chart": draw_on_chart,
        },
        "执行策略失败",
    )


def capture_chart() -> Dict[str, Any]:
    return _post("/api/control/capture", None, "截取图表失败")


def clear_annotations(
    symbol: str,
    kind: Optional[str] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"symbol": symbol}
    if kind is not None:
        payload["kind"] = kind
    if source is not None:
        payload["source"] = source
    return _post("/api/control/clear", payload, "清空标注失败")


def get_watchlist() -> Dict[str, Any]:
    ensure_app_running()
    try:
        return http_client.get("/api/watchlist").json()
    except Exception as e:
        return {"status": "error", "message": f"获取自选列表失败: {e}"}


def update_watchlist(
    action: str,
    symbol: str,
    group_name: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_app_running()
    target_sym = _format_symbol(symbol)
    try:
        data = http_client.get("/api/watchlist").json()
        groups = data.get("groups", [])
        if not groups:
            groups = [{"id": "default", "name": "默认分组", "stocks": []}]

        target_group = None
        if group_name:
            for g in groups:
                if g.get("name") == group_name:
                    target_group = g
                    break
            if not target_group and action == "add":
                target_group = {"id": str(uuid.uuid4()), "name": group_name, "stocks": []}
                groups.append(target_group)
        else:
            target_group = groups[0]

        sym_upper = target_sym.upper()

        if action == "add":
            stocks_upper = [s.upper() for s in target_group.get("stocks", [])]
            if sym_upper not in stocks_upper:
                target_group.setdefault("stocks", []).append(target_sym)
                msg = f"已将 {target_sym} 添加至自选分组【{target_group.get('name')}】"
            else:
                msg = f"{target_sym} 已在自选分组【{target_group.get('name')}】中"
        elif action == "remove":
            if group_name and target_group:
                orig_stocks = target_group.get("stocks", [])
                target_group["stocks"] = [s for s in orig_stocks if s.upper() != sym_upper]
                msg = f"已将 {target_sym} 从自选分组【{group_name}】中移除"
            else:
                for g in groups:
                    g["stocks"] = [s for s in g.get("stocks", []) if s.upper() != sym_upper]
                msg = f"已从所有自选分组中移除 {target_sym}"
        else:
            return {"status": "error", "message": f"不支持的操作: {action}，只支持 'add' 或 'remove'"}

        save_resp = http_client.post("/api/watchlist", json={"groups": groups})
        return {
            "status": "success",
            "message": msg,
            "groups": save_resp.json().get("groups", groups),
        }
    except Exception as e:
        return {"status": "error", "message": f"更新自选失败: {e}"}


def search_symbols(keyword: str, limit: int = 10) -> Dict[str, Any]:
    ensure_app_running()
    try:
        data = http_client.get("/api/search", params={"keyword": keyword}).json()
        if isinstance(data, list):
            results = data[:limit]
        elif isinstance(data, dict) and "data" in data:
            results = data["data"][:limit]
        else:
            results = data
        return {"status": "success", "count": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "message": f"检索股票失败: {e}"}
