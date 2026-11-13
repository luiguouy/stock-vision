// useChartAnnotations.ts
// Lightweight Charts v5 标注管理系统 (Markers / PriceLines / Canvas Overlay 矩形、通道线与波浪折线插件)
import { ref } from 'vue';
import type {
  IChartApi,
  ISeriesApi,
  ISeriesPrimitive,
  IPrimitivePaneView,
  IPrimitivePaneRenderer,
  SeriesMarker,
  IPriceLine,
} from 'lightweight-charts';
import { createSeriesMarkers, LineStyle } from 'lightweight-charts';

export interface ChartMarkerItem {
  id?: string;
  time: string | number;
  position: 'aboveBar' | 'belowBar' | 'inBar';
  color: string;
  shape: 'circle' | 'square' | 'arrowUp' | 'arrowDown';
  text: string;
}

export interface ChartPriceLineItem {
  id?: string;
  price: number;
  color: string;
  lineWidth?: number;
  lineStyle?: number; // 0=Solid, 1=Dotted, 2=Dashed, 3=LargeDashed
  title?: string;
}

export interface ChartBoxItem {
  id?: string;
  time1: string | number;
  time2: string | number;
  price1: number;
  price2: number;
  fillColor?: string;
  borderColor?: string;
  label?: string;
}

export interface ChartChannelLineItem {
  id?: string;
  time1: string | number;
  price1: number;
  time2: string | number;
  price2: number;
  color?: string;
  lineWidth?: number;
  lineStyle?: 'solid' | 'dashed' | 'dotted' | number;
  title?: string;
}

export interface WavePointItem {
  time: string | number;
  price: number;
  label?: string;
  color?: string;
  type?: 'High' | 'Low';
}

export interface ChartWaveLinesItem {
  id?: string;
  pattern?: string;
  color?: string;
  lineWidth?: number;
  points: WavePointItem[];
  extension?: {
    time: string | number;
    price: number;
  } | null;
}

/**
 * 转换通用时间为 Lightweight Charts 接受的 HorzScaleItem (UTC 秒数或 YYYY-MM-DD 字符串)
 */
export function toChartTime(t: string | number): any {
  if (typeof t === 'number') {
    return t > 1e11 ? Math.floor(t / 1000) : t;
  }
  const s = String(t).trim();
  if (!s) return '';
  // 分钟/小时: '2024-05-01 10:30' 或带秒或 ISO
  if (s.includes(' ') || s.includes('T') || s.includes(':')) {
    const cleanStr = s.replace('T', ' ').replace(/\.\d+/, '');
    const msSlash = new Date(cleanStr.replace(/-/g, '/')).getTime();
    if (!isNaN(msSlash)) {
      return Math.floor(msSlash / 1000);
    }
    const msDirect = new Date(s).getTime();
    if (!isNaN(msDirect)) {
      return Math.floor(msDirect / 1000);
    }
  }
  // 日期: 'YYYY-MM-DD'
  return s.slice(0, 10);
}

/**
 * 稳健解析时间坐标，防止因格式、时区、周末/非交易日导致坐标解析为 null
 */
export function getTimeCoordinate(timeScale: any, rawTime: string | number): number | null {
  if (!timeScale || rawTime === undefined || rawTime === null || rawTime === '') return null;

  // 防御：若传入纯数字且不是大时间戳，说明是未格式化的行索引，不能作为图表时间轴坐标
  if (typeof rawTime === 'number' && rawTime < 1e9) {
    return null;
  }
  const sRaw = String(rawTime).trim();
  if (/^\d{1,7}$/.test(sRaw)) {
    return null;
  }

  // 1. 尝试格式化为图表时间并直接查找坐标
  const ct = toChartTime(rawTime);
  let coord = timeScale.timeToCoordinate(ct);
  if (coord !== null) return coord;

  // 2. 若 rawTime 与 ct 不同，尝试直接查找 rawTime
  if (rawTime !== ct) {
    try {
      coord = timeScale.timeToCoordinate(rawTime as any);
      if (coord !== null) return coord;
    } catch {
      // ignore
    }
  }

  // 3. 截取前 10 位 'YYYY-MM-DD' 格式尝试
  const dateStr = sRaw.slice(0, 10);
  if (dateStr && dateStr !== ct) {
    try {
      coord = timeScale.timeToCoordinate(dateStr);
      if (coord !== null) return coord;
    } catch {
      // ignore
    }
  }

  // 4. 利用 timeToIndex(t, false) 精确匹配 Bar 索引 (严禁传 true 进行无限远距离模糊吸附，避免把旧标的或历史多年外的点强行吸附在 index 0)
  try {
    const idx = timeScale.timeToIndex(ct, false);
    if (idx !== null) {
      const c = timeScale.logicalToCoordinate(idx);
      if (c !== null) return c;
    }
  } catch {
    // ignore
  }

  // 5. 对 dateStr 执行精确匹配
  if (dateStr && dateStr !== ct) {
    try {
      const idx = timeScale.timeToIndex(dateStr, false);
      if (idx !== null) {
        const c = timeScale.logicalToCoordinate(idx);
        if (c !== null) return c;
      }
    } catch {
      // ignore
    }
  }

  return null;
}

/**
 * AnnotationOverlayPrimitive: 基于 Lightweight Charts v5 ISeriesPrimitive 的轻量级 Canvas 叠加图层
 * 统一管理 箱体 (Box)、动态价格通道 (Channel Lines) 与 波浪折线结构 (Wave Structure Lines)
 */
class AnnotationOverlayPrimitive implements ISeriesPrimitive<any> {
  private _boxes: ChartBoxItem[] = [];
  private _channelLines: ChartChannelLineItem[] = [];
  private _waveLines: ChartWaveLinesItem | null = null;
  private _param: any = null;
  private _paneViews: readonly IPrimitivePaneView[];
  private _renderer: IPrimitivePaneRenderer;

  constructor() {
    this._boxes = [];
    this._channelLines = [];
    this._waveLines = null;
    const self = this;

    this._renderer = {
      draw(target: any) {
        if (!self._param) return;
        const chart = self._param.chart;
        const series = self._param.series;
        if (!chart || !series) return;

        const timeScale = chart.timeScale();

        target.useMediaCoordinateSpace((scope: any) => {
          const ctx = scope.context;

          // 1. 绘制盘整箱体 (Boxes)
          for (const box of self._boxes) {
            const rawX1 = getTimeCoordinate(timeScale, box.time1);
            const rawX2 = getTimeCoordinate(timeScale, box.time2);

            // 两端时间与价格必须均能在当前图表时间序列上有效定位，严禁回退至 0 或 width 避免畸变
            if (rawX1 === null || rawX2 === null) continue;
            const y1 = series.priceToCoordinate(box.price1);
            const y2 = series.priceToCoordinate(box.price2);
            if (y1 === null || y2 === null) continue;

            const x1 = rawX1;
            const x2 = rawX2;
            const left = Math.min(x1, x2);
            const top = Math.min(y1, y2);
            const width = Math.max(1, Math.abs(x2 - x1));
            const height = Math.max(1, Math.abs(y2 - y1));

            ctx.save();
            ctx.fillStyle = box.fillColor || 'rgba(59, 130, 246, 0.12)';
            ctx.fillRect(left, top, width, height);

            ctx.strokeStyle = box.borderColor || '#3b82f6';
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 2]);
            ctx.strokeRect(left, top, width, height);

            if (box.label) {
              ctx.fillStyle = box.borderColor || '#3b82f6';
              ctx.font = '11px sans-serif';
              ctx.fillText(box.label, left + 4, top + 13);
            }
            ctx.restore();
          }

          // 2. 绘制动态价格通道 (Channel Lines: 上轨 / 中轴 / 下轨)
          for (const chan of self._channelLines) {
            const rawX1 = getTimeCoordinate(timeScale, chan.time1);
            const rawX2 = getTimeCoordinate(timeScale, chan.time2);

            // 通道线两端时间与价格坐标必须均在当前图表上有效定位，严禁回退至 0 或 width 绘制畸变贯穿线
            if (rawX1 === null || rawX2 === null) continue;
            const y1 = series.priceToCoordinate(chan.price1);
            const y2 = series.priceToCoordinate(chan.price2);
            if (y1 === null || y2 === null) continue;
            if (!Number.isFinite(rawX1) || !Number.isFinite(rawX2) || !Number.isFinite(y1) || !Number.isFinite(y2)) continue;

            const x1 = rawX1;
            const x2 = rawX2;

            ctx.save();
            ctx.strokeStyle = chan.color || '#f59e0b';
            ctx.lineWidth = chan.lineWidth || 1.5;
            if (chan.lineStyle === 'dashed' || chan.lineStyle === 2) {
              ctx.setLineDash([6, 4]);
            } else if (chan.lineStyle === 'dotted' || chan.lineStyle === 1) {
              ctx.setLineDash([2, 2]);
            } else {
              ctx.setLineDash([]);
            }

            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.stroke();

            if (chan.title) {
              ctx.setLineDash([]);
              ctx.font = 'bold 10px sans-serif';
              ctx.fillStyle = chan.color || '#f59e0b';
              const labelX = x2 >= x1 ? x2 + 4 : x1 + 4;
              const labelY = x2 >= x1 ? y2 : y1;
              ctx.textAlign = 'left';
              ctx.textBaseline = 'middle';
              ctx.fillText(chan.title, labelX, labelY);
            }
            ctx.restore();
          }

          // 3. 绘制波浪折线结构 (Wave Structure Polyline & Extension)
          if (self._waveLines && self._waveLines.points && self._waveLines.points.length > 0) {
            const points = self._waveLines.points;
            const baseColor = self._waveLines.color || '#8b5cf6';
            const coords: { x: number; y: number; label?: string; price: number; color?: string }[] = [];

            for (const pt of points) {
              const x = getTimeCoordinate(timeScale, pt.time);
              const y = series.priceToCoordinate(pt.price);
              if (x !== null && y !== null && Number.isFinite(x) && Number.isFinite(y)) {
                coords.push({ x, y, label: pt.label, price: pt.price, color: pt.color });
              }
            }

            if (coords.length > 0) {
              ctx.save();

              // (A) 浪形折线连接
              if (coords.length > 1) {
                ctx.strokeStyle = baseColor;
                ctx.lineWidth = self._waveLines.lineWidth || 2.2;
                ctx.setLineDash([]);
                ctx.lineJoin = 'round';
                ctx.lineCap = 'round';
                ctx.beginPath();
                ctx.moveTo(coords[0].x, coords[0].y);
                for (let i = 1; i < coords.length; i++) {
                  ctx.lineTo(coords[i].x, coords[i].y);
                }
                ctx.stroke();
              }

              // (B) 当前价格虚线延伸连接
              if (self._waveLines.extension && self._waveLines.extension.time) {
                const extX = getTimeCoordinate(timeScale, self._waveLines.extension.time);
                const extY = series.priceToCoordinate(self._waveLines.extension.price);
                if (extX !== null && extY !== null && coords.length > 0) {
                  const lastPt = coords[coords.length - 1];
                  ctx.strokeStyle = baseColor;
                  ctx.lineWidth = 1.5;
                  ctx.setLineDash([5, 4]);
                  ctx.beginPath();
                  ctx.moveTo(lastPt.x, lastPt.y);
                  ctx.lineTo(extX, extY);
                  ctx.stroke();

                  ctx.beginPath();
                  ctx.arc(extX, extY, 3.5, 0, Math.PI * 2);
                  ctx.fillStyle = baseColor;
                  ctx.fill();
                }
              }

              // (C) 浪形节点圆圈与 Badge 气泡标签
              for (const c of coords) {
                // 节点外环
                ctx.beginPath();
                ctx.arc(c.x, c.y, 4.5, 0, Math.PI * 2);
                ctx.fillStyle = c.color || baseColor;
                ctx.fill();
                ctx.lineWidth = 1.5;
                ctx.strokeStyle = '#ffffff';
                ctx.setLineDash([]);
                ctx.stroke();

                // 节点标签气泡
                if (c.label) {
                  ctx.font = 'bold 10px sans-serif';
                  const txt = c.label;
                  const textMetrics = ctx.measureText(txt);
                  const textWidth = textMetrics.width;
                  const textHeight = 15;
                  const isHigh = c.y < (scope.mediaSize.height / 2);
                  const badgeY = isHigh ? c.y - 14 : c.y + 14;

                  ctx.fillStyle = 'rgba(15, 23, 42, 0.90)';
                  const padX = 5;
                  const pillLeft = c.x - textWidth / 2 - padX;
                  const pillTop = badgeY - textHeight / 2;
                  const pillW = textWidth + padX * 2;
                  const pillH = textHeight;

                  ctx.beginPath();
                  if (typeof ctx.roundRect === 'function') {
                    ctx.roundRect(pillLeft, pillTop, pillW, pillH, 4);
                  } else {
                    ctx.rect(pillLeft, pillTop, pillW, pillH);
                  }
                  ctx.fill();

                  ctx.strokeStyle = c.color || baseColor;
                  ctx.lineWidth = 1;
                  ctx.stroke();

                  ctx.fillStyle = '#ffffff';
                  ctx.textAlign = 'center';
                  ctx.textBaseline = 'middle';
                  ctx.fillText(txt, c.x, badgeY);
                }
              }

              ctx.restore();
            }
          }
        });
      },
    };

    this._paneViews = [
      {
        zOrder() {
          return 'normal';
        },
        renderer() {
          return self._renderer;
        },
      },
    ];
  }

  public setBoxes(boxes: ChartBoxItem[]) {
    this._boxes = boxes;
    this.requestUpdate();
  }

  public setChannelLines(channelLines: ChartChannelLineItem[]) {
    this._channelLines = channelLines;
    this.requestUpdate();
  }

  public setWaveLines(waveLines: ChartWaveLinesItem | null) {
    this._waveLines = waveLines;
    this.requestUpdate();
  }

  public clear() {
    this._boxes = [];
    this._channelLines = [];
    this._waveLines = null;
    this.requestUpdate();
  }

  private requestUpdate() {
    if (this._param && this._param.requestUpdate) {
      this._param.requestUpdate();
    }
  }

  public attached(param: any) {
    this._param = param;
  }

  public detached() {
    this._param = null;
  }

  public updateAllViews() {}

  public paneViews(): readonly IPrimitivePaneView[] {
    return this._paneViews;
  }
}

export function useChartAnnotations() {
  let _chartApi: IChartApi | null = null;
  let seriesApi: ISeriesApi<any> | null = null;
  let markersPlugin: any = null;
  let overlayPrimitive: AnnotationOverlayPrimitive | null = null;
  let activePriceLines: IPriceLine[] = [];

  const markersCount = ref(0);
  const linesCount = ref(0);
  const boxesCount = ref(0);
  const channelLinesCount = ref(0);
  const waveLinesCount = ref(0);

  function init(chart: IChartApi, series: ISeriesApi<any>, existingMarkersPlugin?: any) {
    _chartApi = chart;
    void _chartApi;
    seriesApi = series;

    // 初始化/复用 Markers 插件
    if (existingMarkersPlugin) {
      markersPlugin = existingMarkersPlugin;
    } else {
      try {
        markersPlugin = createSeriesMarkers(seriesApi, []);
      } catch (e) {
        console.warn('createSeriesMarkers init warning:', e);
      }
    }

    // 初始化 AnnotationOverlayPrimitive 插件
    overlayPrimitive = new AnnotationOverlayPrimitive();
    try {
      seriesApi.attachPrimitive(overlayPrimitive);
    } catch (e) {
      console.warn('attachPrimitive warning:', e);
    }
  }

  function setMarkers(markers: ChartMarkerItem[]) {
    if (!seriesApi) return;
    const formatted: SeriesMarker<any>[] = markers.map((m) => ({
      time: toChartTime(m.time),
      position: m.position,
      color: m.color,
      shape: m.shape,
      text: m.text,
      id: m.id,
    }));

    // 按时间严格排序 (lightweight-charts 要求 markers 必须单调递增)
    formatted.sort((a, b) => {
      const ta = typeof a.time === 'number' ? a.time : new Date(String(a.time)).getTime();
      const tb = typeof b.time === 'number' ? b.time : new Date(String(b.time)).getTime();
      return ta - tb;
    });

    if (markersPlugin && markersPlugin.setMarkers) {
      markersPlugin.setMarkers(formatted);
    } else {
      // 备用 fallback
      try {
        (seriesApi as any).setMarkers(formatted);
      } catch (e) {
        console.warn('setMarkers failed:', e);
      }
    }
    markersCount.value = formatted.length;
  }

  function setPriceLines(lines: ChartPriceLineItem[]) {
    if (!seriesApi) return;
    // 清空现有 priceLines
    for (const pl of activePriceLines) {
      try {
        seriesApi.removePriceLine(pl);
      } catch {
        // ignore
      }
    }
    activePriceLines = [];

    for (const l of lines) {
      try {
        const pl = seriesApi.createPriceLine({
          price: l.price,
          color: l.color,
          lineWidth: (l.lineWidth || 1) as any,
          lineStyle: (l.lineStyle ?? LineStyle.Dashed) as LineStyle,
          axisLabelVisible: true,
          title: l.title || '',
        });
        activePriceLines.push(pl);
      } catch (e) {
        console.warn('createPriceLine error:', e);
      }
    }
    linesCount.value = activePriceLines.length;
  }

  function setBoxes(boxes: ChartBoxItem[]) {
    if (!overlayPrimitive) return;
    overlayPrimitive.setBoxes(boxes);
    boxesCount.value = boxes.length;
  }

  function setChannelLines(channelLines: ChartChannelLineItem[]) {
    if (!overlayPrimitive) return;
    overlayPrimitive.setChannelLines(channelLines);
    channelLinesCount.value = channelLines.length;
  }

  function setWaveLines(waveLines: ChartWaveLinesItem | null) {
    if (!overlayPrimitive) return;
    overlayPrimitive.setWaveLines(waveLines);
    waveLinesCount.value = waveLines ? waveLines.points.length : 0;
  }

  function setAllAnnotations(anno: {
    markers?: ChartMarkerItem[];
    lines?: ChartPriceLineItem[];
    boxes?: ChartBoxItem[];
    channel_lines?: ChartChannelLineItem[];
    channelLines?: ChartChannelLineItem[];
    wave_lines?: ChartWaveLinesItem | null;
    waveLines?: ChartWaveLinesItem | null;
  }) {
    setMarkers(anno.markers || []);
    setPriceLines(anno.lines || []);
    setBoxes(anno.boxes || []);
    const chans = anno.channel_lines ?? anno.channelLines ?? [];
    setChannelLines(chans);
    const waves = anno.wave_lines !== undefined ? anno.wave_lines : (anno.waveLines !== undefined ? anno.waveLines : null);
    setWaveLines(waves);
  }

  function clearAnnotations() {
    setMarkers([]);
    setPriceLines([]);
    setBoxes([]);
    setChannelLines([]);
    setWaveLines(null);
  }

  return {
    init,
    setMarkers,
    setPriceLines,
    setBoxes,
    setChannelLines,
    setWaveLines,
    setAllAnnotations,
    clearAnnotations,
    markersCount,
    linesCount,
    boxesCount,
    channelLinesCount,
    waveLinesCount,
  };
}
