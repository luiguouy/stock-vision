import type { ChartOptions, DeepPartial } from 'lightweight-charts';
import { CrosshairMode, LineStyle } from 'lightweight-charts';

export const getChartOptions = (): DeepPartial<ChartOptions> => {
  return {
    autoSize: true,
    layout: {
      background: { color: '#ffffff' },
      textColor: '#475569',
      fontSize: 11,
      fontFamily: 'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    },
    localization: {
      locale: 'zh-CN',
      timeFormatter: (time: any) => {
        let dateStr = '';
        if (typeof time === 'string') {
          dateStr = time;
        } else if (time && typeof time === 'object' && 'year' in time) {
          const mm = String(time.month).padStart(2, '0');
          const dd = String(time.day).padStart(2, '0');
          dateStr = `${time.year}-${mm}-${dd}`;
        } else {
          return '';
        }

        try {
          const date = new Date(dateStr);
          if (isNaN(date.getTime())) return dateStr;
          const year = date.getFullYear();
          const month = String(date.getMonth() + 1).padStart(2, '0');
          const day = String(date.getDate()).padStart(2, '0');
          const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
          const weekday = weekdays[date.getDay()];
          return `${year}/${month}/${day} ${weekday}`;
        } catch {
          return dateStr;
        }
      },
    },
    grid: {
      vertLines: { color: '#f1f5f9' },
      horzLines: { color: '#f1f5f9' },
    },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: { color: '#cbd5e1', style: LineStyle.Dashed },
      horzLine: { color: '#cbd5e1', style: LineStyle.Dashed },
    },
    rightPriceScale: {
      borderColor: '#e2e8f0',
      autoScale: true,
    },
    timeScale: {
      borderColor: '#e2e8f0',
      timeVisible: true,
    },
    // 显式开启鼠标滚轮缩放 / 触控板捏合缩放 / 拖拽平移
    handleScale: {
      mouseWheel: true,
      pinch: true,
      axisPressedMouseMove: true,
    },
    handleScroll: {
      mouseWheel: true,
      pressedMouseMove: true,
    },
  };
};
