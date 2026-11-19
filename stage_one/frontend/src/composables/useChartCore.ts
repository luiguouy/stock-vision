// useChartCore.ts
// Lightweight Charts 核心实例管理与响应式生命周期封装
import { shallowRef, ref, onUnmounted, type Ref } from 'vue';
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
} from 'lightweight-charts';
import { getChartOptions } from '../utils/chartUtils';

export interface UseChartCoreOptions {
  chartArea?: Ref<HTMLElement | null>;
  isDarkMode?: Ref<boolean>;
  onLogicalRangeChange?: (range: any) => void;
  onCrosshairMove?: (param: any) => void;
}

export function useChartCore(options?: UseChartCoreOptions) {
  const chartInstance = shallowRef<IChartApi | null>(null);
  const candlestickSeries = shallowRef<ISeriesApi<'Candlestick'> | any | null>(null);
  const volumeSeries = shallowRef<ISeriesApi<'Histogram'> | any | null>(null);
  const markersPlugin = shallowRef<any | null>(null);
  const chartReady = ref(false);

  let chartAreaResizeObserver: ResizeObserver | null = null;
  let rangeChangeCallback: ((range: any) => void) | null = null;

  function initChart(
    container: HTMLElement,
    cfg?: {
      isDark?: boolean;
      onRangeChange?: (range: any) => void;
      onCrosshairMove?: (param: any) => void;
    }
  ) {
    if (!container) return;
    const isDark = cfg?.isDark ?? options?.isDarkMode?.value ?? false;
    const chart = createChart(container, getChartOptions(isDark));
    chart.timeScale().applyOptions({ minBarSpacing: 3, rightOffset: 12, barSpacing: 8 });

    const upColor = isDark ? '#34d399' : '#10b981';
    const downColor = isDark ? '#fb7185' : '#f43f5e';

    const candle = chart.addSeries(CandlestickSeries, {
      upColor,
      downColor,
      borderVisible: false,
      wickUpColor: upColor,
      wickDownColor: downColor,
    });

    const markers = createSeriesMarkers(candle);

    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });

    chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 }, visible: false });
    chart.priceScale('right').applyOptions({ scaleMargins: { top: 0.1, bottom: 0.25 } });

    const cb = cfg?.onRangeChange || options?.onLogicalRangeChange;
    if (cb) {
      rangeChangeCallback = cb;
      chart.timeScale().subscribeVisibleLogicalRangeChange(cb);
    }

    const crosshairCb = cfg?.onCrosshairMove || options?.onCrosshairMove;
    if (crosshairCb) {
      chart.subscribeCrosshairMove(crosshairCb);
    }

    chartInstance.value = chart;
    candlestickSeries.value = candle;
    volumeSeries.value = volume;
    markersPlugin.value = markers;
    chartReady.value = true;

    return {
      chart,
      candlestickSeries: candle,
      volumeSeries: volume,
      markersPlugin: markers,
    };
  }

  function observeChartArea(areaEl?: HTMLElement | null) {
    if (chartAreaResizeObserver) {
      chartAreaResizeObserver.disconnect();
      chartAreaResizeObserver = null;
    }
    const el = areaEl || options?.chartArea?.value;
    if (!el) return;
    chartAreaResizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0 && entry.contentRect.height > 0) {
          if (chartInstance.value) {
            chartInstance.value.applyOptions({
              width: Math.floor(entry.contentRect.width),
              height: Math.floor(entry.contentRect.height),
            });
          }
        }
      }
    });
    chartAreaResizeObserver.observe(el);
  }

  function syncChartSize(areaEl?: HTMLElement | null) {
    const el = areaEl || options?.chartArea?.value;
    if (chartInstance.value && el) {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        chartInstance.value.applyOptions({
          width: Math.floor(rect.width),
          height: Math.floor(rect.height),
        });
      }
    }
  }

  function dispose() {
    if (chartAreaResizeObserver) {
      chartAreaResizeObserver.disconnect();
      chartAreaResizeObserver = null;
    }
    if (chartInstance.value) {
      if (rangeChangeCallback) {
        try {
          chartInstance.value.timeScale().unsubscribeVisibleLogicalRangeChange(rangeChangeCallback);
        } catch {}
        rangeChangeCallback = null;
      }
      try {
        chartInstance.value.remove();
      } catch {}
      chartInstance.value = null;
    }
    candlestickSeries.value = null;
    volumeSeries.value = null;
    markersPlugin.value = null;
    chartReady.value = false;
  }

  onUnmounted(() => {
    dispose();
  });

  return {
    chartInstance,
    candlestickSeries,
    volumeSeries,
    markersPlugin,
    chartReady,
    initChart,
    observeChartArea,
    syncChartSize,
    dispose,
  };
}
