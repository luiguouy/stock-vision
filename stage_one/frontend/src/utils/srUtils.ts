// srUtils.ts
// 支撑/阻力位 (SRLevel) 计算、动态锚点识别与富集纯函数
import type { SRLevel } from './api';

export interface EnrichedSRLevel extends SRLevel {
  basis?: string;
}

/**
 * 富集支撑与阻力位：
 * 严格按价格从高到低降序排序，并基于通道轨线、盘整箱体与 200 EMA 进行动态锚点识别与依据判定
 */
export function enrichSRLevels(levels: SRLevel[], summary?: any): EnrichedSRLevel[] {
  if (!levels || !levels.length) return [];

  // 严格按价格从高到低降序排序，保证图表 PriceLines 与侧边栏面板列表完全一一对应
  const sorted = [...levels].sort((a, b) => Number(b.price) - Number(a.price));

  const chan = summary?.channel || {};
  const ema = summary?.ema_200_gate?.value;
  const box = summary?.box || {};

  return sorted.map((lvl) => {
    const p = Number(lvl.price);
    let basis = (lvl as any).basis || (lvl as any).desc || '';
    if (!basis && summary) {
      const anchors: { dist: number; label: string }[] = [];
      if (chan.upper_rail) anchors.push({ dist: Math.abs(p - chan.upper_rail) / p, label: '动态通道上轨阻力' });
      if (chan.lower_rail) anchors.push({ dist: Math.abs(p - chan.lower_rail) / p, label: '动态通道下轨支撑' });
      if (chan.mid_rail) anchors.push({ dist: Math.abs(p - chan.mid_rail) / p, label: '动态通道中轴' });
      if (box.box_high) anchors.push({ dist: Math.abs(p - box.box_high) / p, label: '盘整箱体顶部阻力' });
      if (box.box_low) anchors.push({ dist: Math.abs(p - box.box_low) / p, label: '盘整箱体底部支撑' });
      if (ema) anchors.push({ dist: Math.abs(p - ema) / p, label: '200日均线 (200EMA)' });

      anchors.sort((a, b) => a.dist - b.dist);
      if (anchors.length > 0 && anchors[0].dist < 0.02) {
        basis = anchors[0].label;
      } else {
        basis = lvl.type === 'resistance' ? '前高关键阻力' : '前低波段支撑';
      }
    }
    return {
      ...lvl,
      price: p,
      basis: basis || undefined,
    };
  });
}
