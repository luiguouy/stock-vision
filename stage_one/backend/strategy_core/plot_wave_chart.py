"""Generate interactive Plotly Elliott Wave candlestick chart for US stocks."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Ensure project root is on sys.path when invoked from any working directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from . import pa_engine as pe  # noqa: E402


FIB_STYLE_MAP: dict[str, tuple[str, str]] = {
    "0.618": ("Fib 61.8%", "#DAA520"),
    "1.000": ("Fib 100%", "#FF8C00"),
    "1.272": ("Fib 127.2%", "#E67E22"),
    "1.618": ("Fib 161.8%", "#DC143C"),
    "2.000": ("Fib 200%", "#9B59B6"),
    "2.618": ("Fib 261.8%", "#8E44AD"),
    "0.618_w0_to_w3": ("Fib 61.8% (W0-W3)", "#5D6D7E"),
    "1.382_w0_to_w3": ("Fib 138.2% (W0-W3)", "#34495E"),
}

DISCLAIMER_TEXT = "注：浪型标注仅供结构观察与证伪参考，非交易信号"


def load_ohlcv(csv_path: Path) -> pd.DataFrame:
    """Load OHLCV CSV and normalize column names to Title Case."""
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    col_map = {c.lower(): c for c in df.columns}
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in col_map]
    if missing:
        raise ValueError(f"Missing required OHLCV columns in {csv_path}: {missing}")

    df = df[[col_map[c] for c in required]].copy()
    df.columns = ["Open", "High", "Low", "Close", "Volume"]
    df = df.dropna().sort_index()
    return df


def _resolve_wave_annotations(
    sub: pd.DataFrame,
    swings: list[dict],
    wave_pattern: dict,
) -> list[dict]:
    """Build ordered wave/swing pivot annotations for plotting."""
    wp = wave_pattern.get("wave_points") or {}
    annotations: list[dict] = []

    if wave_pattern.get("pattern") == "corrective_abc" and {"0", "A", "B", "C"}.issubset(wp):
        mapping = [
            ("0", "▼ A", "#D62728", "top"),
            ("A", "▲", "#2CA02C", "bottom"),
            ("B", "▼ B", "#D62728", "top"),
            ("C", "▲ C", "#2CA02C", "bottom"),
        ]
        for key, label, color, pos in mapping:
            pt = wp[key]
            idx = int(pt["index"])
            if 0 <= idx < len(sub):
                annotations.append(
                    {
                        "index": idx,
                        "date": sub.index[idx],
                        "price": float(pt["price"]),
                        "label": label,
                        "color": color,
                        "pos": pos,
                    }
                )
    elif wp:
        for key, pt in wp.items():
            idx = int(pt["index"])
            if 0 <= idx < len(sub):
                is_high = pt.get("type") == "High"
                annotations.append(
                    {
                        "index": idx,
                        "date": sub.index[idx],
                        "price": float(pt["price"]),
                        "label": f"{'▼' if is_high else '▲'} {key}",
                        "color": "#D62728" if is_high else "#2CA02C",
                        "pos": "top" if is_high else "bottom",
                    }
                )
        annotations.sort(key=lambda item: item["index"])
    else:
        for s in swings[-5:]:
            idx = int(s["index"])
            if 0 <= idx < len(sub):
                is_high = s.get("type") == "High"
                annotations.append(
                    {
                        "index": idx,
                        "date": sub.index[idx],
                        "price": float(s["price"]),
                        "label": "▼" if is_high else "▲",
                        "color": "#D62728" if is_high else "#2CA02C",
                        "pos": "top" if is_high else "bottom",
                    }
                )

    return annotations


def _future_bar_timestamp(last_dt: pd.Timestamp, offset_bars: int, has_weekends: bool) -> pd.Timestamp:
    """Estimate future bar timestamp from bar offset."""
    if has_weekends:
        return last_dt + pd.Timedelta(days=offset_bars)
    return last_dt + pd.offsets.BDay(offset_bars)


def _add_structure_and_sr_overlays(
    fig: go.Figure,
    sub: pd.DataFrame,
    swings: list[dict],
    x_end: pd.Timestamp,
) -> tuple[dict, dict, list[dict], list[dict]]:
    """Overlay price channel, consolidation box, unfilled gaps, and MSS markers."""
    box = pe.detect_consolidation_box(sub, swings)
    chan = pe.detect_price_channel(sub, swings)
    gaps = pe.detect_gaps(sub)
    mss_list = pe.detect_mss(swings, sub)

    # A. Price channel (30-bar LRC) or consolidation box
    chan_type = chan.get("channel_type", "horizontal")
    if chan_type in ("ascending", "descending") and chan.get("upper_rail") is not None:
        n_win = min(len(sub), 30)
        slope = float(chan.get("slope") or 0.0)
        x_vals = [sub.index[-n_win], sub.index[-1]]
        specs = [
            ("通道上轨", float(chan["upper_rail"]), "#E67E22", "dash"),
            ("通道中轴", float(chan["mid_rail"]), "#7F8C8D", "dot"),
            ("通道下轨", float(chan["lower_rail"]), "#16A085", "dash"),
        ]
        for idx_s, (name, end_val, color, dash_style) in enumerate(specs):
            start_val = end_val - slope * (n_win - 1)
            fig.add_trace(
                go.Scatter(
                    x=x_vals,
                    y=[start_val, end_val],
                    mode="lines",
                    name=f"{name} (${end_val:.2f})",
                    line=dict(color=color, width=1.6 if idx_s != 1 else 1.2, dash=dash_style),
                ),
                row=1,
                col=1,
            )
    elif box.get("is_box") and box.get("box_low") is not None and box.get("box_high") is not None:
        b_low = float(box["box_low"])
        b_high = float(box["box_high"])
        n_win = min(len(sub), 30)
        fig.add_shape(
            type="rect",
            x0=sub.index[-n_win],
            x1=sub.index[-1],
            y0=b_low,
            y1=b_high,
            fillcolor="rgba(52, 152, 219, 0.08)",
            line=dict(color="#3498DB", width=1.2, dash="dot"),
            row=1,
            col=1,
        )
        fig.add_annotation(
            x=sub.index[-n_win],
            y=b_high,
            text=f"盘整箱体 ${b_low:.2f}-${b_high:.2f}",
            showarrow=False,
            yshift=10,
            xanchor="left",
            font=dict(size=10, color="#2980B9"),
            row=1,
            col=1,
        )

    # B. Unfilled gaps (support / resistance zones)
    for gap in gaps[-2:]:
        nums = re.findall(r"\d+(?:\.\d+)?", str(gap.get("range", "")))
        if len(nums) < 2:
            continue
        g_low, g_high = sorted((float(nums[0]), float(nums[1])))
        is_bear = "Bearish" in str(gap.get("type", "")) or "阻力" in str(gap.get("type", ""))
        fill_col = "rgba(231, 76, 60, 0.11)" if is_bear else "rgba(46, 204, 113, 0.11)"
        border_col = "#E74C3C" if is_bear else "#27AE60"
        gap_dt = pd.Timestamp(gap["date"])
        fig.add_shape(
            type="rect",
            x0=gap_dt,
            x1=x_end,
            y0=g_low,
            y1=g_high,
            fillcolor=fill_col,
            line=dict(color=border_col, width=1.0, dash="dot"),
            layer="below",
            row=1,
            col=1,
        )
        fig.add_annotation(
            x=gap_dt,
            y=g_high if is_bear else g_low,
            text=f"{'跳空阻力缺口' if is_bear else '跳空支撑缺口'} ${g_low:.2f}-${g_high:.2f}",
            showarrow=False,
            xanchor="right",
            xshift=-6,
            yshift=10 if is_bear else -10,
            font=dict(size=10, color=border_col),
            bgcolor="rgba(255, 255, 255, 0.88)",
            bordercolor=border_col,
            borderwidth=1,
            borderpad=2,
            row=1,
            col=1,
        )

    # C. Latest Market Structure Shift (MSS)
    if mss_list:
        latest_mss = mss_list[-1]
        mss_dt = pd.Timestamp(latest_mss["trigger_time"])
        mss_price = float(latest_mss["trigger_price"])
        is_bear_mss = "空翻" in str(latest_mss.get("type", "")) or "Bearish" in str(
            latest_mss.get("type", "")
        )
        mss_color = "#C0392B" if is_bear_mss else "#1E8449"
        fig.add_annotation(
            x=mss_dt,
            y=mss_price,
            text=f"{'🔻 MSS 空翻' if is_bear_mss else '🔺 MSS 多翻'} ${mss_price:.2f}",
            showarrow=True,
            arrowhead=2,
            arrowcolor=mss_color,
            ax=-68,
            ay=-10 if is_bear_mss else 10,
            font=dict(size=10, color=mss_color),
            bgcolor="rgba(255, 255, 255, 0.9)",
            bordercolor=mss_color,
            borderwidth=1,
            borderpad=2,
            row=1,
            col=1,
        )

    return box, chan, gaps, mss_list


def _build_summary_lines(
    wave_pattern: dict,
    result: dict,
    ema_last: float,
    current_price: float,
    bars_since: int,
    next_lucas: int | None,
    next_fib: int | None,
    chan: dict | None = None,
    gaps: list[dict] | None = None,
    fib_levels: dict | None = None,
) -> list[str]:
    """Format structural summary box lines."""
    pattern_name = wave_pattern.get("pattern", "N/A")
    current_wave = wave_pattern.get("current_wave", "")
    lines = [
        f"<b>形态</b>: {pattern_name} ({current_wave})" if current_wave else f"<b>形态</b>: {pattern_name}",
    ]

    cs = result.get("corrective_subtype") or {}
    if cs:
        subtype = str(cs.get("subtype", "N/A")).upper()
        structure = cs.get("structure", "N/A")
        ba_ratio = cs.get("ba_ratio", "N/A")
        ca_ratio = cs.get("ca_ratio", "N/A")
        lines.append(f"修正类型: {subtype} | 结构: {structure}")
        lines.append(f"比率: B/A={ba_ratio} | C/A={ca_ratio}")

    lines.append(f"200 EMA: ${ema_last:.2f} | 现价: ${current_price:.2f}")

    if chan and chan.get("channel_type") in ("ascending", "descending"):
        c_label = "上升通道" if chan["channel_type"] == "ascending" else "下降通道"
        r2 = float(chan.get("r_squared") or 0.0)
        lines.append(
            f"通道: {c_label} (R²={r2:.2f}) | 上轨=${float(chan['upper_rail']):.2f} / 下轨=${float(chan['lower_rail']):.2f}"
        )

    sr_parts = []
    if fib_levels and fib_levels.get("PDL") is not None:
        sr_parts.append(f"PDL=${float(fib_levels['PDL']):.2f}")
    if gaps:
        latest_gap = gaps[-1]
        sr_parts.append(f"缺口={latest_gap.get('range', '')}")
    if sr_parts:
        lines.append("支撑/阻力: " + " | ".join(sr_parts))

    w4_inv = result.get("wave4_invalidation_level")
    r1_inv = result.get("rule1_invalidation_level")
    if w4_inv is not None or r1_inv is not None:
        inv_parts = []
        if w4_inv is not None:
            inv_parts.append(f"W4止损=${float(w4_inv):.2f}")
        if r1_inv is not None:
            inv_parts.append(f"Rule1=${float(r1_inv):.2f}")
        lines.append("证伪线: " + " | ".join(inv_parts))

    tw_parts = []
    if next_lucas is not None:
        tw_parts.append(f"L{next_lucas}")
    if next_fib is not None:
        tw_parts.append(f"F{next_fib}")
    tw_suffix = f" (下个 {' / '.join(tw_parts)})" if tw_parts else ""
    lines.append(f"时间窗: 距拐点 {bars_since} bar{tw_suffix}")
    lines.append(f"<i>* {DISCLAIMER_TEXT}</i>")
    return lines


def plot_wave_chart(
    ticker: str = "GOOGL",
    csv_path: Path | None = None,
    output_path: Path | None = None,
    lookback_bars: int = 120,
    include_plotlyjs: str | bool = "cdn",
) -> Path:
    """Generate and save an interactive single-file HTML Elliott Wave chart."""
    csv_path = csv_path or (PROJECT_ROOT / "data" / f"{ticker}.csv")
    output_path = output_path or (PROJECT_ROOT / "results" / f"{ticker}_wave_chart.html")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = load_ohlcv(csv_path)
    if df.empty:
        raise ValueError(f"No valid OHLCV bars in {csv_path}")

    actual_bars = min(len(df), lookback_bars)
    # Compute 200 EMA on full history before slicing the display window
    ema200_full = df["Close"].ewm(span=200, adjust=False).mean()
    sub = df.tail(actual_bars).copy()
    ema200_sub = ema200_full.tail(actual_bars)

    swings = pe.extract_swings(sub)
    current_price = float(sub["Close"].iloc[-1])
    result = pe.evaluate_wave_position(swings, df=sub, current_price=current_price)
    wave_pattern = result.get("wave_pattern_detail") or pe.classify_wave_pattern(swings)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.76, 0.24],
    )

    # 1. Candlestick OHLC
    fig.add_trace(
        go.Candlestick(
            x=sub.index,
            open=sub["Open"],
            high=sub["High"],
            low=sub["Low"],
            close=sub["Close"],
            name="OHLC",
            increasing_line_color="#26A69A",
            decreasing_line_color="#EF5350",
            increasing_fillcolor="#26A69A",
            decreasing_fillcolor="#EF5350",
        ),
        row=1,
        col=1,
    )

    # 2. Volume bars
    vol_colors = [
        "rgba(38, 166, 154, 0.65)" if c >= o else "rgba(239, 83, 80, 0.65)"
        for o, c in zip(sub["Open"], sub["Close"])
    ]
    fig.add_trace(
        go.Bar(
            x=sub.index,
            y=sub["Volume"],
            name="Volume",
            marker_color=vol_colors,
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    # 3. 200 EMA
    ema_last = float(ema200_sub.iloc[-1])
    fig.add_trace(
        go.Scatter(
            x=sub.index,
            y=ema200_sub,
            mode="lines",
            name=f"200 EMA (${ema_last:.2f})",
            line=dict(color="#1F77B4", width=2.0),
        ),
        row=1,
        col=1,
    )

    # 4. All swings (subtle) + active wave zig-zag
    if swings:
        fig.add_trace(
            go.Scatter(
                x=[sub.index[int(s["index"])] for s in swings if 0 <= int(s["index"]) < len(sub)],
                y=[float(s["price"]) for s in swings if 0 <= int(s["index"]) < len(sub)],
                mode="lines",
                name="Swings",
                line=dict(color="#95A5A6", width=1.1, dash="dot"),
                opacity=0.7,
            ),
            row=1,
            col=1,
        )

    wave_annots = _resolve_wave_annotations(sub, swings, wave_pattern)
    last_dt = sub.index[-1]
    if wave_annots:
        wx = [a["date"] for a in wave_annots]
        wy = [a["price"] for a in wave_annots]
        fig.add_trace(
            go.Scatter(
                x=wx,
                y=wy,
                mode="lines+markers",
                name="Wave Structure",
                line=dict(color="#2C3E50", width=2.4),
                marker=dict(size=7, color=[a["color"] for a in wave_annots]),
            ),
            row=1,
            col=1,
        )
        # Connect last wave pivot to current price
        fig.add_trace(
            go.Scatter(
                x=[wx[-1], last_dt],
                y=[wy[-1], current_price],
                mode="lines",
                name="To Current",
                line=dict(color="#2C3E50", width=1.5, dash="dash"),
                showlegend=False,
            ),
            row=1,
            col=1,
        )

        for a in wave_annots:
            is_top = a["pos"] == "top"
            date_str = a["date"].strftime("%m-%d")
            fig.add_annotation(
                x=a["date"],
                y=a["price"],
                text=f"<b>{a['label']}</b><br>${a['price']:.2f} ({date_str})",
                showarrow=True,
                arrowhead=2,
                arrowsize=0.9,
                arrowwidth=1.2,
                arrowcolor=a["color"],
                ax=0,
                ay=-34 if is_top else 34,
                font=dict(size=11, color=a["color"]),
                bgcolor="rgba(255, 255, 255, 0.9)",
                bordercolor=a["color"],
                borderwidth=1,
                borderpad=3,
                row=1,
                col=1,
            )

    # 5. Current price marker ("★ Now")
    fig.add_trace(
        go.Scatter(
            x=[last_dt],
            y=[current_price],
            mode="markers",
            name=f"Now (${current_price:.2f})",
            marker=dict(symbol="star", size=13, color="#8E44AD", line=dict(width=1, color="#FFFFFF")),
        ),
        row=1,
        col=1,
    )
    fig.add_annotation(
        x=last_dt,
        y=current_price,
        text=f"<b>★ Now</b><br>${current_price:.2f} ({last_dt.strftime('%m-%d')})",
        showarrow=True,
        arrowhead=2,
        arrowcolor="#8E44AD",
        ax=-52,
        ay=-36,
        font=dict(size=11, color="#6C3483"),
        bgcolor="rgba(245, 238, 248, 0.94)",
        bordercolor="#8E44AD",
        borderwidth=1,
        borderpad=3,
        row=1,
        col=1,
    )

    # 6. Fibonacci projection levels
    fib_proj = result.get("fib_projections") or {}
    for ratio_key, price_val in fib_proj.items():
        price_f = float(price_val)
        label_prefix, color = FIB_STYLE_MAP.get(ratio_key, (f"Fib {ratio_key}", "#555555"))
        fig.add_hline(
            y=price_f,
            line_dash="dash",
            line_color=color,
            line_width=1.3,
            opacity=0.85,
            annotation_text=f" {label_prefix}: ${price_f:.2f} ",
            annotation_position="right",
            annotation_font=dict(size=10, color=color),
            annotation_bgcolor="rgba(255, 255, 255, 0.88)",
            annotation_bordercolor=color,
            annotation_borderwidth=1,
            row=1,
            col=1,
        )

    # 7. Invalidation levels (when present, e.g., impulse waves)
    w4_inv = result.get("wave4_invalidation_level")
    if w4_inv is not None:
        w4_f = float(w4_inv)
        fig.add_hline(
            y=w4_f,
            line_dash="dot",
            line_color="#C0392B",
            line_width=1.6,
            annotation_text=f" W4 证伪止损: ${w4_f:.2f} ",
            annotation_position="left",
            annotation_font=dict(size=10, color="#C0392B"),
            annotation_bgcolor="rgba(253, 237, 236, 0.92)",
            annotation_bordercolor="#C0392B",
            annotation_borderwidth=1,
            row=1,
            col=1,
        )

    r1_inv = result.get("rule1_invalidation_level")
    if r1_inv is not None:
        r1_f = float(r1_inv)
        fig.add_hline(
            y=r1_f,
            line_dash="dashdot",
            line_color="#922B21",
            line_width=1.4,
            annotation_text=f" Rule 1 证伪: ${r1_f:.2f} ",
            annotation_position="left",
            annotation_font=dict(size=10, color="#922B21"),
            annotation_bgcolor="rgba(253, 237, 236, 0.92)",
            annotation_bordercolor="#922B21",
            annotation_borderwidth=1,
            row=1,
            col=1,
        )

    # 8. Future time windows (beyond last candle)
    tw = result.get("time_windows") or {}
    bars_since = int(tw.get("bars_since_pivot") or 0)
    next_lucas = tw.get("next_lucas")
    next_fib = tw.get("next_fib")
    has_weekends = bool((sub.index.dayofweek >= 5).any())

    future_dates: list[pd.Timestamp] = []
    tw_specs = [
        (next_lucas, "L", "#2980B9", 0.04),
        (next_fib, "F", "#8E44AD", 0.14),
    ]
    for target_bar, prefix, color, y_frac in tw_specs:
        if target_bar is None:
            continue
        offset = max(1, int(target_bar) - bars_since)
        future_dt = _future_bar_timestamp(last_dt, offset, has_weekends)
        future_dates.append(future_dt)
        x_iso = future_dt.strftime("%Y-%m-%d")
        fig.add_vline(
            x=x_iso,
            line_dash="dash",
            line_color=color,
            line_width=1.4,
            opacity=0.85,
            row=1,
            col=1,
        )
        fig.add_annotation(
            x=x_iso,
            y=y_frac,
            xref="x",
            yref="y domain",
            text=f"<b>时间窗 {prefix}{target_bar}</b><br>(~{future_dt.strftime('%m-%d')})",
            showarrow=False,
            xanchor="left",
            xshift=4,
            font=dict(size=10, color=color),
            bgcolor="rgba(255, 255, 255, 0.9)",
            bordercolor=color,
            borderwidth=1,
            borderpad=3,
        )

    # Extend x-axis range to comfortably display future time windows & right labels
    x_start = sub.index[0] - pd.Timedelta(days=2)
    max_future = max(future_dates) if future_dates else last_dt
    x_end = max(max_future, last_dt) + pd.Timedelta(days=10)

    # 8b. Support/Resistance & Pattern Overlays (Channel / Box / Gaps / MSS)
    _, chan, gaps, _ = _add_structure_and_sr_overlays(fig, sub, swings, x_end)
    fib_levels = pe.calc_fibonacci_and_levels(swings, sub)

    # 9. Summary annotation box (bottom-left open area inside main chart)
    summary_lines = _build_summary_lines(
        wave_pattern=wave_pattern,
        result=result,
        ema_last=ema_last,
        current_price=current_price,
        bars_since=bars_since,
        next_lucas=next_lucas,
        next_fib=next_fib,
        chan=chan,
        gaps=gaps,
        fib_levels=fib_levels,
    )
    fig.add_annotation(
        x=0.01,
        y=0.03,
        xref="paper",
        yref="y domain",
        text="<br>".join(summary_lines),
        showarrow=False,
        align="left",
        xanchor="left",
        yanchor="bottom",
        font=dict(size=11, color="#1C2833"),
        bgcolor="rgba(253, 254, 254, 0.92)",
        bordercolor="#5D6D7E",
        borderwidth=1,
        borderpad=6,
    )

    fig.update_layout(
        title=dict(
            text=(
                f"<b>{ticker} — Elliott Wave Structural Chart (Daily, {actual_bars}d)</b>"
                f"<br><sup>{DISCLAIMER_TEXT}</sup>"
            ),
            x=0.02,
            xanchor="left",
        ),
        template="plotly_white",
        hovermode="x unified",
        height=850,
        margin=dict(l=60, r=135, t=105, b=45),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.015,
            xanchor="right",
            x=1.0,
        ),
        xaxis_rangeslider_visible=False,
        xaxis2_rangeslider_visible=False,
    )
    fig.update_xaxes(range=[x_start, x_end])
    if not has_weekends:
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.update_yaxes(title_text="Price ($)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)

    fig.write_html(str(output_path), include_plotlyjs=include_plotlyjs, full_html=True)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot interactive Elliott Wave candlestick chart.")
    parser.add_argument("--ticker", default="GOOGL", help="Ticker symbol (default: GOOGL)")
    parser.add_argument("--bars", type=int, default=120, help="Lookback bars (default: 120)")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output HTML path (default: results/<ticker>_wave_chart.html)",
    )
    args = parser.parse_args()

    out = plot_wave_chart(
        ticker=args.ticker,
        output_path=args.output,
        lookback_bars=args.bars,
    )
    print(f"Saved wave chart to: {out}")


if __name__ == "__main__":
    main()
