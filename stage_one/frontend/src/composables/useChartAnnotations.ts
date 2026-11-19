// useChartAnnotations.ts
// Lightweight Charts v5 标注管理系统 (Markers / PriceLines / Canvas Overlay 矩形、通道线、波浪锚点卡片、右延Fib目标位与缺口共振带插件)
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
  short_label?: string;
  color?: string;
  pos?: string;
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
  subtle_swings?: Array<{ time: string | number; price: number }>;
}

export interface FibLineItem {
  id?: string;
  ratio?: string;
  name?: string;
  price: number;
  startTime: string | number;
  color?: string;
  label?: string;
}

export interface GapBoxItem {
  id?: string;
  startTime: string | number;
  price1: number;
  price2: number;
  fillColor?: string;
  borderColor?: string;
  label?: string;
}

export interface EmaPointItem {
  time: string | number;
  value: number;
}

export interface TimeLineItem {
  id?: string;
  time: any;
  color?: string;
  lineWidth?: number;
  lineStyle?: 'solid' | 'dashed' | 'dotted';
  isResonance?: boolean;
  score?: number;
  daysFromNow?: number;
  label?: string;
  reasons?: string[];
}

/**
 * 转换通用时间为 Lightweight Charts 接受的 HorzScaleItem (UTC 秒数或 YYYY-MM-DD 字符串)
 */
export function toChartTime(t: string | number): any {
  if (t === null || t === undefined) return '';
  if (typeof t === 'number') {
    if (isNaN(t) || !isFinite(t)) return '';
    return t > 1e11 ? Math.floor(t / 1000) : Math.floor(t);
  }
  const s = String(t).trim();
  if (!s || s === 'NaN' || s === 'undefined' || s === 'null') return '';

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
    return '';
  }

  // 日期: 'YYYY-MM-DD'
  const dateStr = s.slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    const ms = new Date(dateStr).getTime();
    if (!isNaN(ms)) {
      return dateStr;
    }
  }
  return '';
}

/**
 * 稳健解析时间坐标，防止因格式、时区、周末/非交易日导致坐标解析为 null
 */
export function getTimeCoordinate(timeScale: any, rawTime: string | number): number | null {
  if (!timeScale || rawTime === undefined || rawTime === null || rawTime === '') return null;

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

  // 4. 精确匹配 Bar 索引
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
 * 全面集成：盘整箱体、动态价格通道、波浪节点卡片 & 淡灰辅助连线、局部右延 Fib 扩展虚线、缺口共振区与底部微型时间窗
 */
class AnnotationOverlayPrimitive implements ISeriesPrimitive<any> {
  private _isDarkMode: boolean = false;
  private _boxes: ChartBoxItem[] = [];
  private _channelLines: ChartChannelLineItem[] = [];
  private _waveLines: ChartWaveLinesItem | null = null;
  private _timeLines: TimeLineItem[] = [];
  private _fibLines: FibLineItem[] = [];
  private _gapBoxes: GapBoxItem[] = [];
  private _ema200Data: EmaPointItem[] = [];
  private _highlightedTime: string | null = null;
  private _param: any = null;
  private _paneViews: readonly IPrimitivePaneView[];
  private _renderer: IPrimitivePaneRenderer;

  constructor() {
    this._isDarkMode = false;
    this._boxes = [];
    this._channelLines = [];
    this._waveLines = null;
    this._timeLines = [];
    this._fibLines = [];
    this._gapBoxes = [];
    this._ema200Data = [];
    this._highlightedTime = null;
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
          const mediaW = scope.mediaSize.width;
          const mediaH = scope.mediaSize.height;

          // 0. 绘制 200 EMA 连续均线 (深蓝色平滑连线) - 裁剪至可视视口 [-20, mediaW + 20]
          if (self._ema200Data && self._ema200Data.length > 1) {
            ctx.save();
            ctx.strokeStyle = '#2563eb';
            ctx.lineWidth = 1.8;
            ctx.setLineDash([]);
            ctx.beginPath();
            let started = false;
            let prevPt: { x: number; y: number } | null = null;
            for (const pt of self._ema200Data) {
              const x = getTimeCoordinate(timeScale, pt.time);
              const y = series.priceToCoordinate(pt.value);
              if (x === null || y === null || !Number.isFinite(x) || !Number.isFinite(y)) {
                continue;
              }
              if (x < -20) {
                prevPt = { x, y };
                continue;
              }
              if (x > mediaW + 20) {
                if (started) {
                  ctx.lineTo(x, y);
                }
                break;
              }
              if (!started) {
                if (prevPt) {
                  ctx.moveTo(prevPt.x, prevPt.y);
                } else {
                  ctx.moveTo(x, y);
                }
                started = true;
              }
              ctx.lineTo(x, y);
              prevPt = { x, y };
            }
            if (started) {
              ctx.stroke();
            }
            ctx.restore();
          }

          // 1. 绘制盘整箱体 (Consolidation Boxes)
          for (const box of self._boxes) {
            const rawX1 = getTimeCoordinate(timeScale, box.time1);
            const rawX2 = getTimeCoordinate(timeScale, box.time2);
            if (rawX1 === null || rawX2 === null) continue;
            const y1 = series.priceToCoordinate(box.price1);
            const y2 = series.priceToCoordinate(box.price2);
            if (y1 === null || y2 === null) continue;

            const left = Math.min(rawX1, rawX2);
            const top = Math.min(y1, y2);
            const width = Math.max(1, Math.abs(rawX2 - rawX1));
            const height = Math.max(1, Math.abs(y2 - y1));

            ctx.save();
            ctx.fillStyle = box.fillColor || 'rgba(59, 130, 246, 0.10)';
            ctx.fillRect(left, top, width, height);

            ctx.strokeStyle = box.borderColor || '#3b82f6';
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 2]);
            ctx.strokeRect(left, top, width, height);

            if (box.label) {
              ctx.fillStyle = box.borderColor || '#3b82f6';
              ctx.font = '10px -apple-system, sans-serif';
              ctx.fillText(box.label, left + 4, top + 12);
            }
            ctx.restore();
          }

          // 2. 价格失衡带 / 跳空缺口 (右延共振带，右侧延伸至图表右边界)
          for (const gb of self._gapBoxes) {
            const startX = getTimeCoordinate(timeScale, gb.startTime);
            const y1 = series.priceToCoordinate(gb.price1);
            const y2 = series.priceToCoordinate(gb.price2);
            if (y1 === null || y2 === null) continue;

            const left = startX !== null ? Math.max(0, startX) : 0;
            const right = mediaW;
            const top = Math.min(y1, y2);
            const height = Math.max(2, Math.abs(y2 - y1));

            ctx.save();
            ctx.fillStyle = gb.fillColor || 'rgba(244, 63, 94, 0.12)';
            ctx.fillRect(left, top, right - left, height);

            ctx.strokeStyle = gb.borderColor || '#f43f5e';
            ctx.lineWidth = 1;
            ctx.setLineDash([3, 3]);
            ctx.strokeRect(left, top, right - left, height);

            if (gb.label) {
              ctx.setLineDash([]);
              ctx.font = '9px -apple-system, monospace';
              ctx.fillStyle = gb.borderColor || '#f43f5e';
              ctx.fillText(gb.label, left + 6, top + Math.min(11, height - 2));
            }
            ctx.restore();
          }

          // 3. 绘制动态价格通道 (Channel Lines: 上轨 / 中轴 / 下轨)
          for (const chan of self._channelLines) {
            const rawX1 = getTimeCoordinate(timeScale, chan.time1);
            const rawX2 = getTimeCoordinate(timeScale, chan.time2);
            if (rawX1 === null || rawX2 === null) continue;
            const y1 = series.priceToCoordinate(chan.price1);
            const y2 = series.priceToCoordinate(chan.price2);
            if (y1 === null || y2 === null) continue;

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

            // 标签增加半透明底色与 11px 加粗字体，避免压在 K 线实体上
            if (chan.title) {
              ctx.setLineDash([]);
              ctx.font = 'bold 11px -apple-system, BlinkMacSystemFont, "JetBrains Mono", monospace';
              const textMetrics = ctx.measureText(chan.title);
              const padX = 6;
              const boxW = textMetrics.width + padX * 2;
              const boxH = 18;
              const labelX = x2 >= x1 ? x2 + 4 : x1 + 4;
              const labelY = x2 >= x1 ? y2 : y1;

              // 半透明深色底色防遮挡
              ctx.fillStyle = 'rgba(15, 23, 42, 0.82)';
              ctx.beginPath();
              if (typeof ctx.roundRect === 'function') {
                ctx.roundRect(labelX, labelY - boxH / 2, boxW, boxH, 4);
              } else {
                ctx.rect(labelX, labelY - boxH / 2, boxW, boxH);
              }
              ctx.fill();

              ctx.strokeStyle = chan.color || '#f59e0b';
              ctx.lineWidth = 1;
              ctx.stroke();

              ctx.fillStyle = '#ffffff';
              ctx.textAlign = 'left';
              ctx.textBaseline = 'middle';
              ctx.fillText(chan.title, labelX + padX, labelY);
            }
            ctx.restore();
          }

          // 4. 绘制次级摆动线 (Subtle Swings: 淡灰虚线，弱化背景噪音)
          if (self._waveLines?.subtle_swings && self._waveLines.subtle_swings.length > 1) {
            ctx.save();
            ctx.strokeStyle = 'rgba(148, 163, 184, 0.45)';
            ctx.lineWidth = 1.0;
            ctx.setLineDash([3, 3]);
            ctx.beginPath();
            let swStarted = false;
            for (const s of self._waveLines.subtle_swings) {
              const x = getTimeCoordinate(timeScale, s.time);
              const y = series.priceToCoordinate(s.price);
              if (x !== null && y !== null) {
                if (!swStarted) {
                  ctx.moveTo(x, y);
                  swStarted = true;
                } else {
                  ctx.lineTo(x, y);
                }
              }
            }
            if (swStarted) {
              ctx.stroke();
            }
            ctx.restore();
          }

          // 5. 绘制波浪结构主折线 & 结构锚点白底细边框卡片
          if (self._waveLines && self._waveLines.points && self._waveLines.points.length > 0) {
            const points = self._waveLines.points;
            const baseColor = self._waveLines.color || '#8b5cf6';
            const coords: { x: number; y: number; label?: string; price: number; color?: string; type?: string }[] = [];

            for (const pt of points) {
              const x = getTimeCoordinate(timeScale, pt.time);
              const y = series.priceToCoordinate(pt.price);
              if (x !== null && y !== null && Number.isFinite(x) && Number.isFinite(y)) {
                coords.push({ x, y, label: pt.label, price: pt.price, color: pt.color, type: pt.type });
              }
            }

            if (coords.length > 0) {
              ctx.save();

              // (A) 核心浪形粗折线连接
              if (coords.length > 1) {
                ctx.strokeStyle = '#334155';
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

              // (B) 延伸至现价虚线
              if (self._waveLines.extension && self._waveLines.extension.time) {
                const extX = getTimeCoordinate(timeScale, self._waveLines.extension.time);
                const extY = series.priceToCoordinate(self._waveLines.extension.price);
                if (extX !== null && extY !== null && coords.length > 0) {
                  const lastPt = coords[coords.length - 1];
                  ctx.strokeStyle = '#64748b';
                  ctx.lineWidth = 1.4;
                  ctx.setLineDash([4, 3]);
                  ctx.beginPath();
                  ctx.moveTo(lastPt.x, lastPt.y);
                  ctx.lineTo(extX, extY);
                  ctx.stroke();
                }
              }

              // (C) 核心结构锚点白底细边框卡片（白底 + 细灰边框 + 完整“波浪序号+极值价格+日期”）
              for (const c of coords) {
                // 锚点小圆点
                ctx.beginPath();
                ctx.arc(c.x, c.y, 3.5, 0, Math.PI * 2);
                ctx.fillStyle = c.color || baseColor;
                ctx.fill();
                ctx.lineWidth = 1.2;
                ctx.strokeStyle = '#ffffff';
                ctx.setLineDash([]);
                ctx.stroke();

                if (c.label) {
                  ctx.font = 'bold 9.5px -apple-system, BlinkMacSystemFont, "JetBrains Mono", monospace';
                  const txt = c.label;
                  const textMetrics = ctx.measureText(txt);
                  const padX = 5;
                  const cardW = textMetrics.width + padX * 2;
                  const cardH = 17;
                  const isHigh = c.type === 'High' || c.y < (mediaH / 2);
                  const cardY = isHigh ? c.y - 18 : c.y + 18;

                  const cardLeft = c.x - cardW / 2;
                  const cardTop = cardY - cardH / 2;

                  // 卡片底色 (暗色模式 rgba(15, 23, 42, 0.92)，亮色模式 rgba(255, 255, 255, 0.96))
                  ctx.fillStyle = self._isDarkMode ? 'rgba(15, 23, 42, 0.92)' : 'rgba(255, 255, 255, 0.96)';
                  ctx.beginPath();
                  if (typeof ctx.roundRect === 'function') {
                    ctx.roundRect(cardLeft, cardTop, cardW, cardH, 4);
                  } else {
                    ctx.rect(cardLeft, cardTop, cardW, cardH);
                  }
                  ctx.fill();

                  // 细边框
                  ctx.strokeStyle = c.color || (self._isDarkMode ? '#475569' : '#94a3b8');
                  ctx.lineWidth = 1.0;
                  ctx.stroke();

                  // 文字 (暗色模式 #f8fafc，亮色模式 #0f172a)
                  ctx.fillStyle = self._isDarkMode ? '#f8fafc' : '#0f172a';
                  ctx.textAlign = 'center';
                  ctx.textBaseline = 'middle';
                  ctx.fillText(txt, c.x, cardY);
                }
              }

              ctx.restore();
            }
          }

          // 6. 局部右延的 Fibonacci 扩展目标位 (仅从最后一个波浪拐点向右延伸，绝不向左贯穿)
          for (const fib of self._fibLines) {
            const startX = getTimeCoordinate(timeScale, fib.startTime);
            const y = series.priceToCoordinate(fib.price);
            if (y === null) continue;

            // 精简非必要的中间斐波那契刻度文字，仅保留核心支撑/阻力与延展位
            const r = String(fib.ratio || '');
            const isKeyRatio = !r || ['0.382', '0.500', '0.5', '0.618', '1.000', '1.0', '1.618', '2.618'].includes(r);
            if (!isKeyRatio) continue;

            const fromX = startX !== null ? Math.max(0, startX) : mediaW * 0.7;
            const toX = mediaW;

            ctx.save();
            ctx.strokeStyle = fib.color || '#ea580c';
            ctx.lineWidth = 1.2;
            ctx.setLineDash([5, 4]);
            ctx.beginPath();
            ctx.moveTo(fromX, y);
            ctx.lineTo(toX, y);
            ctx.stroke();

            // 标注在右端，字号 11px 并增加半透明底色防遮挡
            if (fib.label) {
              ctx.setLineDash([]);
              ctx.font = 'bold 11px -apple-system, BlinkMacSystemFont, "JetBrains Mono", monospace';
              const textMetrics = ctx.measureText(fib.label);
              const padX = 6;
              const boxW = textMetrics.width + padX * 2;
              const boxH = 18;
              const boxX = toX - boxW - 6;
              const boxY = y - boxH - 2;

              ctx.fillStyle = 'rgba(15, 23, 42, 0.82)';
              ctx.beginPath();
              if (typeof ctx.roundRect === 'function') {
                ctx.roundRect(boxX, boxY, boxW, boxH, 4);
              } else {
                ctx.rect(boxX, boxY, boxW, boxH);
              }
              ctx.fill();

              ctx.strokeStyle = fib.color || '#ea580c';
              ctx.lineWidth = 0.8;
              ctx.stroke();

              ctx.fillStyle = '#ffffff';
              ctx.textAlign = 'left';
              ctx.textBaseline = 'middle';
              ctx.fillText(fib.label, boxX + padX, boxY + boxH / 2);
            }
            ctx.restore();
          }

          // 7. 变盘时间窗克制化：细虚线垂直贯通，顶部错落阶梯排布（Staggered Layout）
          // 彻底解决右下角多标签层层叠压成一团的问题
          const validTimeLines: { tl: TimeLineItem; x: number; label: string; isHighlighted: boolean; strokeColor: string }[] = [];
          for (const tl of self._timeLines || []) {
            const x = getTimeCoordinate(timeScale, tl.time);
            if (x === null || x < 0 || x > mediaW) continue;
            validTimeLines.push({
              tl,
              x,
              label: tl.label || '',
              isHighlighted: self._highlightedTime === String(tl.time),
              strokeColor: tl.color || (tl.isResonance ? '#f59e0b' : '#6366f1'),
            });
          }

          validTimeLines.sort((a, b) => a.x - b.x);

          let lastRight = -999;
          let tierIndex = 0;

          for (const item of validTimeLines) {
            ctx.save();
            // 细虚线垂直贯通
            ctx.beginPath();
            ctx.strokeStyle = item.strokeColor;
            ctx.lineWidth = item.isHighlighted ? 2.0 : 1.0;
            ctx.setLineDash([4, 4]);
            ctx.moveTo(item.x, 8);
            ctx.lineTo(item.x, mediaH - 8);
            ctx.stroke();

            if (item.label) {
              ctx.setLineDash([]);
              ctx.font = 'bold 10px -apple-system, BlinkMacSystemFont, "JetBrains Mono", monospace';
              const textMetrics = ctx.measureText(item.label);
              const padX = 6;
              const badgeW = textMetrics.width + padX * 2;
              const badgeH = 18;

              let badgeX = item.x - badgeW / 2;
              badgeX = Math.max(4, Math.min(mediaW - badgeW - 4, badgeX));

              if (badgeX < lastRight + 6) {
                tierIndex = (tierIndex + 1) % 3;
              } else {
                tierIndex = 0;
              }
              const badgeY = 10 + tierIndex * 22;
              lastRight = badgeX + badgeW;

              ctx.fillStyle = item.tl.isResonance ? 'rgba(245, 158, 11, 0.92)' : 'rgba(79, 70, 229, 0.90)';
              ctx.beginPath();
              if (typeof ctx.roundRect === 'function') {
                ctx.roundRect(badgeX, badgeY, badgeW, badgeH, 4);
              } else {
                ctx.rect(badgeX, badgeY, badgeW, badgeH);
              }
              ctx.fill();

              if (item.isHighlighted) {
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 1.5;
                ctx.stroke();
              }

              ctx.fillStyle = '#ffffff';
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillText(item.label, badgeX + badgeW / 2, badgeY + badgeH / 2);
            }
            ctx.restore();
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

  public setDarkMode(isDark: boolean) {
    this._isDarkMode = isDark;
    this.requestUpdate();
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

  public setTimeLines(timeLines: TimeLineItem[]) {
    this._timeLines = timeLines || [];
    this.requestUpdate();
  }

  public setFibLines(fibLines: FibLineItem[]) {
    this._fibLines = fibLines || [];
    this.requestUpdate();
  }

  public setGapBoxes(gapBoxes: GapBoxItem[]) {
    this._gapBoxes = gapBoxes || [];
    this.requestUpdate();
  }

  public setEma200Data(data: EmaPointItem[]) {
    this._ema200Data = (data || []).map((pt) => ({
      time: toChartTime(pt.time),
      value: pt.value,
    }));
    this.requestUpdate();
  }

  public setBatch(payload: {
    boxes?: ChartBoxItem[];
    channelLines?: ChartChannelLineItem[];
    waveLines?: ChartWaveLinesItem | null;
    timeLines?: TimeLineItem[];
    fibLines?: FibLineItem[];
    gapBoxes?: GapBoxItem[];
    ema200Data?: EmaPointItem[];
  }) {
    if (payload.boxes !== undefined) this._boxes = payload.boxes || [];
    if (payload.channelLines !== undefined) this._channelLines = payload.channelLines || [];
    if (payload.waveLines !== undefined) this._waveLines = payload.waveLines;
    if (payload.timeLines !== undefined) this._timeLines = payload.timeLines || [];
    if (payload.fibLines !== undefined) this._fibLines = payload.fibLines || [];
    if (payload.gapBoxes !== undefined) this._gapBoxes = payload.gapBoxes || [];
    if (payload.ema200Data !== undefined) {
      this._ema200Data = (payload.ema200Data || []).map((pt) => ({
        time: toChartTime(pt.time),
        value: pt.value,
      }));
    }
    this.requestUpdate();
  }

  public setHighlightedTime(timeStr: string | null) {
    this._highlightedTime = timeStr;
    this.requestUpdate();
  }

  public clear() {
    this._boxes = [];
    this._channelLines = [];
    this._waveLines = null;
    this._timeLines = [];
    this._fibLines = [];
    this._gapBoxes = [];
    this._ema200Data = [];
    this._highlightedTime = null;
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
  const timeLinesCount = ref(0);
  const fibLinesCount = ref(0);
  const gapBoxesCount = ref(0);

  function init(chart: IChartApi, series: ISeriesApi<any>, existingMarkersPlugin?: any) {
    _chartApi = chart;
    void _chartApi;
    seriesApi = series;

    if (existingMarkersPlugin) {
      markersPlugin = existingMarkersPlugin;
    } else {
      try {
        markersPlugin = createSeriesMarkers(seriesApi, []);
      } catch (e) {
        console.warn('createSeriesMarkers init warning:', e);
      }
    }

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

    formatted.sort((a, b) => {
      const ta = typeof a.time === 'number' ? a.time : new Date(String(a.time)).getTime();
      const tb = typeof b.time === 'number' ? b.time : new Date(String(b.time)).getTime();
      return ta - tb;
    });

    if (markersPlugin && markersPlugin.setMarkers) {
      markersPlugin.setMarkers(formatted);
    } else {
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
    for (const pl of activePriceLines) {
      try {
        seriesApi.removePriceLine(pl);
      } catch {
        // ignore
      }
    }
    activePriceLines = [];

    // Y 轴价格标签智能防重叠 (Anti-Overlap) 算法：
    // 当两条参考线价格距离过近 (<0.9%) 时，优先保留核心风控（止损 > 入场 > TP1 > TP2）在 Y 轴的显式价格标签，
    // 次要线仅在图表绘制虚线，避免 Y 轴刻度标签层叠遮挡。
    function getLinePriority(item: ChartPriceLineItem): number {
      const id = String(item.id || '').toLowerCase();
      const title = String(item.title || '');
      if (id.includes('sl') || title.includes('止损')) return 100;
      if (id.includes('entry') || title.includes('入场')) return 90;
      if (id.includes('tp1') || title.includes('TP1')) return 80;
      if (id.includes('tp2') || title.includes('TP2')) return 70;
      if (id.includes('inv') || title.includes('证伪')) return 60;
      return 50;
    }

    // 复制并按价格降序排列
    const sorted = [...lines].sort((a, b) => b.price - a.price);
    const visibleAxisLabels = new Set<string>();

    for (let i = 0; i < sorted.length; i++) {
      const cur = sorted[i];
      let canShowAxis = true;

      // 检查与已有已显示标签的间距
      for (let j = 0; j < i; j++) {
        const prev = sorted[j];
        const distRatio = Math.abs(cur.price - prev.price) / Math.max(1, cur.price);
        if (distRatio < 0.009) {
          // 距离过近，比较优先级
          if (getLinePriority(cur) <= getLinePriority(prev)) {
            canShowAxis = false;
            break;
          }
        }
      }

      if (canShowAxis) {
        visibleAxisLabels.add(`${cur.id || ''}_${cur.price}`);
      }
    }

    for (const l of lines) {
      try {
        const isAxisVisible = visibleAxisLabels.has(`${l.id || ''}_${l.price}`);
        const pl = seriesApi.createPriceLine({
          price: l.price,
          color: l.color,
          lineWidth: (l.lineWidth || 1) as any,
          lineStyle: (l.lineStyle ?? LineStyle.Dashed) as LineStyle,
          axisLabelVisible: isAxisVisible,
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

  function setTimeLines(lines: TimeLineItem[]) {
    if (!overlayPrimitive) return;
    overlayPrimitive.setTimeLines(lines || []);
    timeLinesCount.value = (lines || []).length;
  }

  function setFibLines(fibLines: FibLineItem[]) {
    if (!overlayPrimitive) return;
    overlayPrimitive.setFibLines(fibLines || []);
    fibLinesCount.value = (fibLines || []).length;
  }

  function setGapBoxes(gapBoxes: GapBoxItem[]) {
    if (!overlayPrimitive) return;
    overlayPrimitive.setGapBoxes(gapBoxes || []);
    gapBoxesCount.value = (gapBoxes || []).length;
  }

  function setEma200Data(data: EmaPointItem[]) {
    if (!overlayPrimitive) return;
    overlayPrimitive.setEma200Data(data || []);
  }

  function highlightTimeLine(dateStr: string | null) {
    if (!overlayPrimitive) return;
    overlayPrimitive.setHighlightedTime(dateStr);
  }

  function setDarkMode(isDark: boolean) {
    if (!overlayPrimitive) return;
    overlayPrimitive.setDarkMode(isDark);
  }

  function setBatch(payload: {
    boxes?: ChartBoxItem[];
    channelLines?: ChartChannelLineItem[];
    waveLines?: ChartWaveLinesItem | null;
    timeLines?: TimeLineItem[];
    fibLines?: FibLineItem[];
    gapBoxes?: GapBoxItem[];
    ema200Data?: EmaPointItem[];
  }) {
    if (payload.boxes !== undefined) boxesCount.value = payload.boxes.length;
    if (payload.channelLines !== undefined) channelLinesCount.value = payload.channelLines.length;
    if (payload.waveLines !== undefined) waveLinesCount.value = payload.waveLines ? payload.waveLines.points.length : 0;
    if (payload.timeLines !== undefined) timeLinesCount.value = payload.timeLines.length;
    if (payload.fibLines !== undefined) fibLinesCount.value = payload.fibLines.length;
    if (payload.gapBoxes !== undefined) gapBoxesCount.value = payload.gapBoxes.length;

    if (overlayPrimitive) {
      overlayPrimitive.setBatch(payload);
    }
  }

  function setAllAnnotations(anno: {
    markers?: ChartMarkerItem[];
    lines?: ChartPriceLineItem[];
    boxes?: ChartBoxItem[];
    channel_lines?: ChartChannelLineItem[];
    channelLines?: ChartChannelLineItem[];
    wave_lines?: ChartWaveLinesItem | null;
    waveLines?: ChartWaveLinesItem | null;
    time_lines?: TimeLineItem[];
    timeLines?: TimeLineItem[];
    fib_lines?: FibLineItem[];
    fibLines?: FibLineItem[];
    gap_boxes?: GapBoxItem[];
    gapBoxes?: GapBoxItem[];
    ema200_data?: EmaPointItem[];
    ema200Data?: EmaPointItem[];
  }) {
    setMarkers(anno.markers || []);
    setPriceLines(anno.lines || []);
    setBatch({
      boxes: anno.boxes || [],
      channelLines: anno.channel_lines ?? anno.channelLines ?? [],
      waveLines: anno.wave_lines !== undefined ? anno.wave_lines : (anno.waveLines !== undefined ? anno.waveLines : null),
      timeLines: anno.time_lines ?? anno.timeLines ?? [],
      fibLines: anno.fib_lines ?? anno.fibLines ?? [],
      gapBoxes: anno.gap_boxes ?? anno.gapBoxes ?? [],
      ema200Data: anno.ema200_data ?? anno.ema200Data ?? [],
    });
  }

  function clearAnnotations() {
    setMarkers([]);
    setPriceLines([]);
    setBatch({
      boxes: [],
      channelLines: [],
      waveLines: null,
      timeLines: [],
      fibLines: [],
      gapBoxes: [],
      ema200Data: [],
    });
    highlightTimeLine(null);
  }

  function dispose() {
    if (seriesApi && overlayPrimitive) {
      try {
        seriesApi.detachPrimitive(overlayPrimitive);
      } catch (e) {
        console.warn('detachPrimitive error:', e);
      }
    }
    if (seriesApi && activePriceLines.length > 0) {
      for (const pl of activePriceLines) {
        try {
          seriesApi.removePriceLine(pl);
        } catch {
          // ignore
        }
      }
      activePriceLines = [];
    }
    if (overlayPrimitive) {
      overlayPrimitive.clear();
      overlayPrimitive = null;
    }
    markersPlugin = null;
    seriesApi = null;
    _chartApi = null;
  }

  return {
    init,
    setDarkMode,
    setMarkers,
    setPriceLines,
    setBoxes,
    setChannelLines,
    setWaveLines,
    setTimeLines,
    setFibLines,
    setGapBoxes,
    setEma200Data,
    setBatch,
    highlightTimeLine,
    setAllAnnotations,
    clearAnnotations,
    dispose,
    markersCount,
    linesCount,
    boxesCount,
    channelLinesCount,
    waveLinesCount,
    timeLinesCount,
    fibLinesCount,
    gapBoxesCount,
  };
}
