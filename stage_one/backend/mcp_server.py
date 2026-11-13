# -*- coding: utf-8 -*-
"""
StockVision MCP Server (面向 Antigravity Agent 的轻量控制面)

通过 stdio 协议提供给 Antigravity Agent，使用免代理 httpx 内部直连 127.0.0.1:8000。
工具列表:
  1. stock_get_state: 获取当前软件运行态与所有已有标注
  2. stock_open_chart: 切换图表标的与周期（必要时秒级唤醒拉起应用）
  3. stock_add_markers: 在 K 线图上打标记 (买卖点、波段高低点等)
  4. stock_draw_price_lines: 绘制水平价格线 (入场/止损/目标/波浪证伪线)
  5. stock_draw_boxes: 绘制矩形区域 (震荡箱体/失衡区)
  6. stock_run_pa_strategy: 一键运行 Investment_Assistant 价格行为交易策略并在图表上呈现
  7. stock_capture_chart: 截取当前图表画面保存并返回文件路径，供视觉复核
  8. stock_clear_annotations: 清理图表上的标注
  9. stock_get_watchlist: 获取自选股票分组和各组股票标的列表
  10. stock_update_watchlist: 添加或移除自选股票
  11. stock_search_symbols: 搜索与检索股票标的
"""

import sys
import os
import time
import subprocess
from typing import List, Dict, Any, Optional
import httpx

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP as MCPServer
    except ImportError:
        raise ImportError("未找到 mcp 服务模块，请确保已安装 mcp 包")

BASE_URL = "http://127.0.0.1:8000"
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# 彻底免除系统代理干扰
http_client = httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False)

server = MCPServer("stock-vision")


def _ensure_app_running():
    """确保 StockVision 后台服务在线，若未在线则秒级启动后台服务。"""
    try:
        resp = http_client.get("/api/health")
        if resp.status_code == 200:
            return True
    except Exception:
        pass

    # 尝试启动 desktop_main.py
    venv_py = os.path.join(os.path.dirname(os.path.dirname(APP_DIR)), ".venv", "Scripts", "python.exe")
    python_exe = venv_py if os.path.exists(venv_py) else sys.executable
    desktop_script = os.path.join(APP_DIR, "desktop_main.py")
    subprocess.Popen([python_exe, desktop_script], cwd=APP_DIR)

    # 等待最多 3 秒启动完成
    for _ in range(15):
        time.sleep(0.2)
        try:
            resp = http_client.get("/api/health")
            if resp.status_code == 200:
                return True
        except Exception:
            continue
    return False


@server.tool()
def stock_get_state() -> Dict[str, Any]:
    """读取 StockVision 桌面端当前展示的股票代码、周期、实时报价与所有已有图表标注。"""
    _ensure_app_running()
    try:
        resp = http_client.get("/api/control/state")
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": f"获取状态失败: {e}"}


@server.tool()
def stock_open_chart(symbol: str, period: str = "1d") -> Dict[str, Any]:
    """控制 StockVision 桌面软件切换当前显示的股票与K线周期（如 symbol='usAAPL', period='15m' 或 '1d'）。必要时自动秒级拉起应用。"""
    _ensure_app_running()
    try:
        resp = http_client.post("/api/control/open", json={"symbol": symbol, "period": period})
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": f"切换图表失败: {e}"}


@server.tool()
def stock_add_markers(symbol: str, markers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """向指定股票的 K 线图上批量打标。每个 marker 包含: time (时间字符串或秒戳), position ('aboveBar'|'belowBar'), color (如 '#10b981'|'#ef4444'), shape ('circle'|'arrowUp'|'arrowDown'), text (文本描述)。"""
    _ensure_app_running()
    try:
        resp = http_client.post("/api/control/markers", json={"symbol": symbol, "markers": markers})
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": f"添加标记失败: {e}"}


@server.tool()
def stock_draw_price_lines(symbol: str, lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    """在图表上绘制水平价格参考线（入场、止损、目标位、波浪证伪线等）。每个 line 包含: price (数值), color (如 '#3b82f6'), lineWidth (1或2), lineStyle (0=实线, 2=虚线), title (标题文字)。"""
    _ensure_app_running()
    try:
        resp = http_client.post("/api/control/lines", json={"symbol": symbol, "lines": lines})
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": f"绘制价格线失败: {e}"}


@server.tool()
def stock_draw_boxes(symbol: str, boxes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """在图表上绘制矩形区间（箱体震荡区、供求失衡区）。每个 box 包含: time1, time2, price1, price2, fillColor, borderColor, label。"""
    _ensure_app_running()
    try:
        resp = http_client.post("/api/control/boxes", json={"symbol": symbol, "boxes": boxes})
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": f"绘制矩形失败: {e}"}


@server.tool()
def stock_run_pa_strategy(
    symbol: str, mode: str = "swing", draw_on_chart: bool = True
) -> Dict[str, Any]:
    """执行 Investment_Assistant 价格行为交易策略（道氏结构、200 EMA、波浪证伪线、箱体状态机与 2.5R 硬门禁），并在桌面图表上自动标注入场/止损/目标位/拐点/证伪线。"""
    _ensure_app_running()
    try:
        resp = http_client.post(
            "/api/control/strategy",
            json={"symbol": symbol, "mode": mode, "draw_on_chart": draw_on_chart},
        )
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": f"执行策略失败: {e}"}


@server.tool()
def stock_capture_chart() -> Dict[str, Any]:
    """截取 StockVision 桌面端当前图表保存为本地高清 PNG 图片，返回图片保存绝对路径，供多模态视觉复核。"""
    _ensure_app_running()
    try:
        resp = http_client.post("/api/control/capture")
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": f"截取图表失败: {e}"}


@server.tool()
def stock_clear_annotations(symbol: str, source: Optional[str] = None) -> Dict[str, Any]:
    """清空图表上的所有标记、水平线与矩形框。"""
    _ensure_app_running()
    try:
        resp = http_client.post("/api/control/clear", json={"symbol": symbol, "source": source})
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": f"清空标注失败: {e}"}


def _norm_symbol(raw: str) -> str:
    s = (raw or "").strip()
    s_upper = s.upper()
    if s_upper.startswith(("US", "ASH", "ASZ", "HK", "SH", "SZ")):
        if s_upper.startswith("US"):
            return "us" + s_upper[2:]
        if s_upper.startswith("ASH"):
            return "ash" + s_upper[3:]
        if s_upper.startswith("ASZ"):
            return "asz" + s_upper[3:]
        if s_upper.startswith("HK"):
            return "hk" + s_upper[2:]
        if s_upper.startswith("SH"):
            return "ash" + s_upper[2:]
        if s_upper.startswith("SZ"):
            return "asz" + s_upper[2:]
    if s.isalpha():
        return "us" + s.upper()
    if s.isdigit():
        if len(s) == 6:
            return ("ash" if s[0] == "6" else "asz") + s
        if len(s) <= 5:
            return "hk" + s.zfill(5)
    return s


@server.tool()
def stock_get_watchlist() -> Dict[str, Any]:
    """获取 StockVision 桌面端当前的所有自选股票分组和各组股票标的列表。"""
    _ensure_app_running()
    try:
        resp = http_client.get("/api/watchlist")
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": f"获取自选列表失败: {e}"}


@server.tool()
def stock_update_watchlist(
    action: str, symbol: str, group_name: Optional[str] = None
) -> Dict[str, Any]:
    """在 StockVision 桌面端添加或移除自选股票。
    参数:
      action: 操作类型，'add' (添加自选) 或 'remove' (移出自选)
      symbol: 股票代码（如 'NVDA', 'usAAPL', 'TSLA', 'ash600519' 等，美股自动补充 'us' 前缀）
      group_name: 可选，指定自选分组名称（如'美股突破', '核心底仓'等）。若不提供则针对默认分组操作。
    """
    _ensure_app_running()
    target_sym = _norm_symbol(symbol)
    try:
        cur_resp = http_client.get("/api/watchlist")
        data = cur_resp.json()
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
                import uuid
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


@server.tool()
def stock_search_symbols(keyword: str, limit: int = 10) -> Dict[str, Any]:
    """根据代码、英文名称、拼音首字母检索股票标的。返回匹配结果列表（包含 symbol, name, market 等）。"""
    _ensure_app_running()
    try:
        resp = http_client.get("/api/search", params={"keyword": keyword})
        data = resp.json()
        if isinstance(data, list):
            results = data[:limit]
        elif isinstance(data, dict) and "data" in data:
            results = data["data"][:limit]
        else:
            results = data
        return {"status": "success", "count": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "message": f"检索股票失败: {e}"}


def main():
    server.run("stdio")


if __name__ == "__main__":
    main()
