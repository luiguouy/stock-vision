# -*- coding: utf-8 -*-
"""
StockVision MCP Server (面向 Antigravity Agent 的轻量控制面)

通过 stdio 协议提供给 Antigravity Agent，委托 control_client 免代理直连 127.0.0.1:8000。
"""

from typing import List, Dict, Any, Optional
import control_client as cc

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP as MCPServer
    except ImportError:
        MCPServer = None

if MCPServer is not None:
    server = MCPServer("stock-vision")
else:
    class _ToolInfo:
        def __init__(self, name):
            self.name = name

    class _DummyToolManager:
        def __init__(self):
            self._tools = []

        def list_tools(self):
            return self._tools

    class _DummyServer:
        def __init__(self):
            self._tool_manager = _DummyToolManager()

        def tool(self, *args, **kwargs):
            def decorator(f):
                self._tool_manager._tools.append(_ToolInfo(f.__name__))
                return f
            return decorator

        def run(self, *args, **kwargs):
            raise ImportError("未找到 mcp 服务模块，请确保已安装 mcp 包")

    server = _DummyServer()

# 向后兼容辅助别名（委托底层 symbols 模块）
_norm_symbol = cc._format_symbol


@server.tool()
def stock_get_state() -> Dict[str, Any]:
    """读取 StockVision 桌面端当前展示的股票代码、周期、实时报价与所有已有图表标注。"""
    return cc.get_state()


@server.tool()
def stock_open_chart(symbol: str, period: str = "1d") -> Dict[str, Any]:
    """控制 StockVision 桌面软件切换当前显示的股票与K线周期（如 symbol='usAAPL', period='15m' 或 '1d'）。必要时自动秒级拉起应用。"""
    return cc.open_chart(symbol, period=period)


@server.tool()
def stock_add_markers(symbol: str, markers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """向指定股票的 K 线图上批量打标。每个 marker 包含: time (时间字符串或秒戳), position ('aboveBar'|'belowBar'), color (如 '#10b981'|'#ef4444'), shape ('circle'|'arrowUp'|'arrowDown'), text (文本描述)。"""
    return cc.add_markers(symbol, markers)


@server.tool()
def stock_draw_price_lines(symbol: str, lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    """在图表上绘制水平价格参考线（入场、止损、目标位、波浪证伪线等）。每个 line 包含: price (数值), color (如 '#3b82f6'), lineWidth (1或2), lineStyle (0=实线, 2=虚线), title (标题文字)。"""
    return cc.draw_lines(symbol, lines)


@server.tool()
def stock_draw_boxes(symbol: str, boxes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """在图表上绘制矩形区间（箱体震荡区、供求失衡区）。每个 box 包含: time1, time2, price1, price2, fillColor, borderColor, label。"""
    return cc.draw_boxes(symbol, boxes)


@server.tool()
def stock_run_pa_strategy(
    symbol: str, mode: str = "swing", draw_on_chart: bool = True
) -> Dict[str, Any]:
    """执行价格行为交易策略（道氏结构、200 EMA、波浪证伪线、箱体状态机与 2.5R 硬门禁），并在桌面图表上自动标注入场/止损/目标位/拐点/证伪线。"""
    return cc.run_strategy(symbol, mode=mode, draw_on_chart=draw_on_chart)


@server.tool()
def stock_capture_chart() -> Dict[str, Any]:
    """截取 StockVision 桌面端当前图表保存为本地高清 PNG 图片，返回图片保存绝对路径，供多模态视觉复核。"""
    return cc.capture_chart()


@server.tool()
def stock_clear_annotations(symbol: str, source: Optional[str] = None) -> Dict[str, Any]:
    """清空图表上的所有标记、水平线与矩形框。"""
    return cc.clear_annotations(symbol, source=source)


@server.tool()
def stock_get_watchlist() -> Dict[str, Any]:
    """获取 StockVision 桌面端当前的所有自选股票分组和各组股票标的列表。"""
    return cc.get_watchlist()


@server.tool()
def stock_update_watchlist(
    action: str, symbol: str, group_name: Optional[str] = None
) -> Dict[str, Any]:
    """在 StockVision 桌面端添加或移除自选股票。
    参数:
      action: 操作类型，'add' (添加自选) 或 'remove' (移出自选)
      symbol: 股票代码（如 'NVDA', 'usAAPL', 'TSLA', 'BTC-USD' 等，自动归一化）
      group_name: 可选，指定自选分组名称（如'美股突破', '核心底仓'等）。若不提供则针对默认分组操作。
    """
    return cc.update_watchlist(action=action, symbol=symbol, group_name=group_name)


@server.tool()
def stock_search_symbols(keyword: str, limit: int = 10) -> Dict[str, Any]:
    """根据代码、英文名称、拼音首字母检索股票标的。返回匹配结果列表（包含 symbol, name, market 等）。"""
    return cc.search_symbols(keyword=keyword, limit=limit)


def main():
    server.run("stdio")


if __name__ == "__main__":
    main()
