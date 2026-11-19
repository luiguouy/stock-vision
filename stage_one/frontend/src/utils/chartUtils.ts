import type { ChartOptions, DeepPartial } from 'lightweight-charts';
import { CrosshairMode, LineStyle } from 'lightweight-charts';

export const getChartOptions = (isDark: boolean = false): DeepPartial<ChartOptions> => {
  return {
    autoSize: true,
    layout: {
      background: { color: isDark ? '#090d16' : '#ffffff' },
      textColor: isDark ? '#94a3b8' : '#64748b',
      fontSize: 11,
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    },
    localization: {
      locale: 'zh-CN',
      timeFormatter: (time: any) => {
        let date: Date | null = null;
        let isIntraday = false;

        if (typeof time === 'number') {
          date = new Date(time * 1000);
          isIntraday = true;
        } else if (typeof time === 'string') {
          if (time.includes(' ') || time.includes(':')) {
            isIntraday = true;
            date = new Date(time.replace(/-/g, '/'));
          } else {
            date = new Date(time);
          }
        } else if (time && typeof time === 'object' && 'year' in time) {
          const mm = String(time.month).padStart(2, '0');
          const dd = String(time.day).padStart(2, '0');
          date = new Date(`${time.year}-${mm}-${dd}`);
        }

        if (!date || isNaN(date.getTime())) {
          return String(time || '');
        }

        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');

        if (isIntraday) {
          return `${year}/${month}/${day} ${hours}:${minutes}`;
        }

        const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
        const weekday = weekdays[date.getDay()];
        return `${year}/${month}/${day} ${weekday}`;
      },
    },
    grid: {
      vertLines: { color: isDark ? 'rgba(255, 255, 255, 0.04)' : '#f1f5f9' },
      horzLines: { color: isDark ? 'rgba(255, 255, 255, 0.04)' : '#f1f5f9' },
    },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: {
        color: isDark ? '#475569' : '#cbd5e1',
        style: LineStyle.Dashed,
        labelBackgroundColor: isDark ? '#1e293b' : '#334155',
      },
      horzLine: {
        color: isDark ? '#475569' : '#cbd5e1',
        style: LineStyle.Dashed,
        labelBackgroundColor: isDark ? '#1e293b' : '#334155',
      },
    },
    rightPriceScale: {
      borderColor: isDark ? 'rgba(255, 255, 255, 0.08)' : '#e2e8f0',
      autoScale: true,
    },
    timeScale: {
      borderColor: isDark ? 'rgba(255, 255, 255, 0.08)' : '#e2e8f0',
      timeVisible: true,
      rightOffset: 12,
      barSpacing: 8,
      minBarSpacing: 3,
      // 关键：当用户正在查看历史数据（未停留在最右侧）时，新 K 线到达不强制右移视口
      shiftVisibleRangeOnNewBar: false,
      // 窗口/侧边栏调整大小时，保持右侧锚定而非重置历史位置
      rightBarStaysOnScroll: true,
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
