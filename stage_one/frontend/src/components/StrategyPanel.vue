<template>
  <div class="space-y-4 select-none text-slate-800 dark:text-slate-100 text-sm">
    <!-- 顶部操作栏 -->
    <div class="flex items-center justify-between gap-2 pb-2.5 border-b border-slate-200/80 dark:border-slate-800">
      <div class="flex items-center gap-2 flex-wrap">
        <h4 class="text-base font-bold tracking-tight">策略研判</h4>
        <span class="text-xs font-mono font-bold px-2 py-0.5 rounded bg-indigo-500/15 text-indigo-600 dark:text-indigo-400">
          {{ period }}
        </span>
        <span
          v-if="dowMarketInfo"
          class="text-xs font-mono font-bold px-2 py-0.5 rounded border"
          :class="dowMarketInfo.badgeClass"
          :title="dowMarketInfo.desc"
        >
          {{ dowMarketInfo.text }}
        </span>
        <span
          v-if="isCrypto"
          class="text-xs font-mono font-bold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30"
          title="加密资产风控门禁 (>=2.0R 盈亏比 / 容许浅穿浪4)"
        >
          CRYPTO
        </span>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="$emit('run', 'swing')"
          :disabled="loading || !symbol"
          class="btn-tactile px-3 py-1.5 rounded-lg text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-40 cursor-pointer transition-colors shadow-2xs"
        >
          {{ loading ? '计算中...' : '重算策略' }}
        </button>
        <button
          @click="$emit('clear')"
          :disabled="loading"
          class="btn-tactile px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 cursor-pointer transition-colors"
        >
          清屏
        </button>
        <button
          @click="$emit('toggle-collapse')"
          class="btn-tactile p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer transition-colors"
          title="收起右侧策略面板"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>

    <!-- 杠杆 ETF 提示 -->
    <div
      v-if="leveragePair"
      class="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-between gap-2"
    >
      <div class="text-xs text-amber-800 dark:text-amber-300 leading-relaxed">
        <span class="font-bold">{{ leveragePair.label }}</span>：杠杆损耗易使形态失真，建议参考正股。
      </div>
      <button
        @click="$emit('switch-symbol', leveragePair.underlying)"
        class="shrink-0 px-2.5 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-xs font-bold cursor-pointer transition-colors"
      >
        看正股 {{ formatSymbol(leveragePair.underlying) }}
      </button>
    </div>

    <!-- 空状态 -->
    <div
      v-if="!summary && !loading"
      class="py-12 text-center text-sm text-slate-400 dark:text-slate-500 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl"
    >
      点击「重算策略」或按 <kbd class="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 font-mono text-xs">Space</kbd> 生成分析
    </div>

    <template v-if="summary">
      <!-- 顶部四宫格状态卡片（等高 Grid，统一字号行高与基线，防截断并修正时间共振） -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
        <!-- 1. 个股道氏趋势 -->
        <div class="bg-slate-50 dark:bg-slate-800/70 p-2.5 rounded-lg flex flex-col justify-between min-h-[72px] border border-slate-200/50 dark:border-slate-700/50">
          <div class="text-xs text-slate-500 dark:text-slate-400">个股道氏趋势</div>
          <div class="font-bold text-slate-800 dark:text-slate-100 text-xs sm:text-sm mt-1 leading-snug break-words">
            {{ summary.dow_phase || '--' }}
          </div>
        </div>

        <!-- 2. 大盘印证 (SPY/QQQ) -->
        <div class="bg-slate-50 dark:bg-slate-800/70 p-2.5 rounded-lg flex flex-col justify-between min-h-[72px] border border-slate-200/50 dark:border-slate-700/50">
          <div class="text-xs text-slate-500 dark:text-slate-400">大盘印证 (SPY/QQQ)</div>
          <div
            class="font-bold text-xs sm:text-sm mt-1 leading-snug break-words"
            :class="
              dowMarketInfo
                ? (dowMarketInfo.status === 'PASS'
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : (dowMarketInfo.status === 'DIVERGENCE' || dowMarketInfo.status === 'WARN')
                      ? 'text-amber-600 dark:text-amber-400'
                      : (dowMarketInfo.status === 'BEAR' || dowMarketInfo.status === 'BLOCK')
                        ? 'text-rose-600 dark:text-rose-400'
                        : 'text-slate-500 dark:text-slate-400')
                : 'text-slate-500 dark:text-slate-400'
            "
            :title="dowMarketInfo ? dowMarketInfo.desc : '未开启大盘双指数验证'"
          >
            {{ dowMarketInfo ? dowMarketInfo.text : '未开启' }}
          </div>
        </div>

        <!-- 3. 波浪结构 -->
        <div class="bg-slate-50 dark:bg-slate-800/70 p-2.5 rounded-lg flex flex-col justify-between min-h-[72px] border border-slate-200/50 dark:border-slate-700/50">
          <div class="text-xs text-slate-500 dark:text-slate-400">波浪结构</div>
          <div class="font-bold text-purple-600 dark:text-purple-400 text-xs sm:text-sm mt-1 leading-snug break-words">
            {{ formatWavePattern(summary.wave?.pattern) }}
          </div>
        </div>

        <!-- 4. 道氏量价 -->
        <div class="bg-slate-50 dark:bg-slate-800/70 p-2.5 rounded-lg flex flex-col justify-between min-h-[72px] border border-slate-200/50 dark:border-slate-700/50">
          <div class="text-xs text-slate-500 dark:text-slate-400">道氏量价</div>
          <div class="font-bold text-xs sm:text-sm mt-1 leading-snug break-words" :class="volumeStatusInfo ? volumeStatusInfo.badgeClass.split(' ')[1] : 'text-slate-700 dark:text-slate-300'">
            {{ volumeStatusInfo ? volumeStatusInfo.text.split(' ')[0] : '量价平稳' }}
          </div>
        </div>
      </div>

      <!-- 区块 A：顶部核心结论 Banner（大字号加粗当前定调与核心风控状态） -->
      <div
        class="rounded-xl border-2 p-4 space-y-3 transition-all shadow-2xs"
        :class="directionTheme.cardClass"
      >
        <div class="flex items-center justify-between flex-wrap gap-2">
          <div class="flex items-center gap-2">
            <span class="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              核心定调
            </span>
            <span
              class="text-xs font-mono font-bold px-2 py-0.5 rounded border"
              :class="directionTheme.badgeClass"
            >
              {{ directionTheme.badgeText }}
            </span>
          </div>

          <span
            class="text-xs font-mono font-bold px-2.5 py-0.5 rounded"
            :class="summary.ema_200_gate?.status === 'PASS' ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400' : 'bg-rose-500/15 text-rose-600 dark:text-rose-400'"
          >
            {{ summary.ema_200_gate?.status === 'PASS' ? '站上 200EMA' : '跌破 200EMA' }}
          </span>
        </div>

        <div class="p-3.5 rounded-xl flex items-center justify-between gap-3" :class="directionTheme.bannerClass">
          <div>
            <div class="text-xs opacity-85 font-medium">策略定调结论</div>
            <div class="text-lg font-black tracking-tight mt-0.5">
              {{ directionTheme.headline }}
            </div>
          </div>
          <div class="text-right font-mono">
            <div class="text-xs opacity-85">现价</div>
            <div class="text-xl font-black tabular-nums">
              ${{ currentPriceFormatted }}
            </div>
          </div>
        </div>

        <p class="text-xs sm:text-sm leading-relaxed font-medium text-slate-700 dark:text-slate-200">
          {{ directionTheme.actionHint }}
        </p>

        <!-- 理论数浪客观失效/证伪线提示 -->
        <div
          v-if="summary.wave?.invalidation_price"
          class="pt-2 border-t border-slate-200/80 dark:border-slate-700/80 flex items-center justify-between text-xs"
        >
          <span class="text-slate-500 dark:text-slate-400">
            波浪客观证伪线（形态失效基准）:
          </span>
          <div class="font-mono font-bold text-purple-600 dark:text-purple-400">
            ${{ Number(summary.wave.invalidation_price).toFixed(2) }}
            <span class="text-slate-400 dark:text-slate-500 font-sans font-normal ml-1">
              ({{ summary.wave.invalidation_reason || '数浪客观铁律' }})
            </span>
          </div>
        </div>
      </div>

      <!-- 区块 B：双列买卖点对比卡片（彻底消除价格隐匿，提供完整触发条件与具体价格区间） -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3.5">
        <!-- 左列：右侧买入点（做多反转触发条件） 绿色系边框 -->
        <div class="p-3.5 rounded-xl border-2 border-emerald-500/40 bg-emerald-50/25 dark:bg-emerald-950/20 space-y-3 shadow-2xs">
          <div class="flex items-center justify-between border-b border-emerald-500/20 pb-2">
            <div class="flex items-center gap-1.5 font-bold text-sm text-emerald-700 dark:text-emerald-400">
              <span>🟢 右侧买入点</span>
              <span class="text-2xs font-normal px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-700 dark:text-emerald-300">
                {{ isShortMode ? '做多反转触发条件' : '顺势买入条件' }}
              </span>
            </div>
            <span class="text-2xs font-mono font-semibold text-emerald-600/80 dark:text-emerald-400/80">
              道氏定势 × 波浪找点
            </span>
          </div>

          <!-- 1. 激进波段买点 -->
          <div class="space-y-1.5 bg-white/80 dark:bg-slate-800/80 p-2.5 rounded-lg border border-emerald-200/70 dark:border-emerald-800/50">
            <div class="flex items-center justify-between text-xs">
              <span class="font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block"></span>
                {{ buyTriggers.aggressive.name }}
              </span>
              <span class="font-mono font-black text-emerald-600 dark:text-emerald-400 text-sm tabular-nums">
                {{ buyTriggers.aggressive.price_range_text }}
              </span>
            </div>
            <p class="text-2xs text-slate-600 dark:text-slate-300 leading-normal">
              {{ buyTriggers.aggressive.condition }}
            </p>
            <div class="flex items-center justify-between text-2xs pt-1 border-t border-slate-100 dark:border-slate-700/60 font-mono">
              <span class="text-rose-500 font-semibold">止损: {{ buyTriggers.aggressive.stop_loss_text }}</span>
              <span class="text-emerald-600 dark:text-emerald-400 font-semibold">目标: {{ buyTriggers.aggressive.target_text }}</span>
            </div>
          </div>

          <!-- 2. 稳健趋势买点 -->
          <div class="space-y-1.5 bg-white/80 dark:bg-slate-800/80 p-2.5 rounded-lg border border-emerald-200/70 dark:border-emerald-800/50">
            <div class="flex items-center justify-between text-xs">
              <span class="font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-600 inline-block"></span>
                {{ buyTriggers.conservative.name }}
              </span>
              <span class="font-mono font-black text-emerald-600 dark:text-emerald-400 text-sm tabular-nums">
                {{ buyTriggers.conservative.price_range_text }}
              </span>
            </div>
            <p class="text-2xs text-slate-600 dark:text-slate-300 leading-normal">
              {{ buyTriggers.conservative.condition }}
            </p>
            <div class="flex items-center justify-between text-2xs pt-1 border-t border-slate-100 dark:border-slate-700/60 font-mono">
              <span class="text-rose-500 font-semibold">止损: {{ buyTriggers.conservative.stop_loss_text }}</span>
              <span class="text-emerald-600 dark:text-emerald-400 font-semibold">目标: {{ buyTriggers.conservative.target_text }}</span>
            </div>
          </div>
        </div>

        <!-- 右列：顺势卖出点（多单止盈/止损 & 空单入场点） 红色系边框 -->
        <div class="p-3.5 rounded-xl border-2 border-rose-500/40 bg-rose-50/25 dark:bg-rose-950/20 space-y-3 shadow-2xs">
          <div class="flex items-center justify-between border-b border-rose-500/20 pb-2">
            <div class="flex items-center gap-1.5 font-bold text-sm text-rose-700 dark:text-rose-400">
              <span>🔴 顺势卖出点</span>
              <span class="text-2xs font-normal px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-700 dark:text-rose-300">
                {{ isShortMode ? '反弹做空 & 止损' : '止盈 & 逃顶清仓' }}
              </span>
            </div>
            <span class="text-2xs font-mono font-semibold text-rose-600/80 dark:text-rose-400/80">
              斐波回撤 × 动态通道
            </span>
          </div>

          <!-- 1. 反弹高抛卖出区 -->
          <div class="space-y-1.5 bg-white/80 dark:bg-slate-800/80 p-2.5 rounded-lg border border-rose-200/70 dark:border-rose-800/50">
            <div class="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
              <span>{{ sellTriggers.rebound_sell.name }}</span>
            </div>

            <!-- 第一阻力卖出区 -->
            <div class="space-y-0.5">
              <div class="flex items-center justify-between text-xs font-mono">
                <span class="text-slate-600 dark:text-slate-300 font-sans font-semibold">
                  {{ sellTriggers.rebound_sell.resistance_zone_1.label }}:
                </span>
                <span class="font-bold text-rose-600 dark:text-rose-400 text-sm tabular-nums">
                  {{ sellTriggers.rebound_sell.resistance_zone_1.price_range_text }}
                </span>
              </div>
              <div class="text-2xs text-slate-500 dark:text-slate-400 leading-tight">
                依据: {{ sellTriggers.rebound_sell.resistance_zone_1.basis }}
              </div>
            </div>

            <!-- 第二阻力卖出区 -->
            <div class="space-y-0.5 pt-1.5 border-t border-slate-100 dark:border-slate-700/60">
              <div class="flex items-center justify-between text-xs font-mono">
                <span class="text-slate-600 dark:text-slate-300 font-sans font-semibold">
                  {{ sellTriggers.rebound_sell.resistance_zone_2.label }}:
                </span>
                <span class="font-bold text-rose-600 dark:text-rose-400 text-sm tabular-nums">
                  {{ sellTriggers.rebound_sell.resistance_zone_2.price_range_text }}
                </span>
              </div>
              <div class="text-2xs text-slate-500 dark:text-slate-400 leading-tight">
                依据: {{ sellTriggers.rebound_sell.resistance_zone_2.basis }}
              </div>
            </div>
          </div>

          <!-- 2. 下探目标与破位止损红线 -->
          <div class="grid grid-cols-2 gap-2 text-2xs font-mono">
            <div class="bg-white/80 dark:bg-slate-800/80 p-2 rounded-lg border border-rose-100 dark:border-rose-900/40">
              <div class="text-slate-500 dark:text-slate-400 font-sans font-semibold">
                {{ isShortMode ? '下探止盈 TP1' : '第一目标 TP1' }}
              </div>
              <div class="font-black text-emerald-600 dark:text-emerald-400 text-sm mt-0.5 tabular-nums">
                {{ sellTriggers.take_profit.tp1.price_text }}
              </div>
              <div class="text-2xs text-slate-400 truncate mt-0.5" :title="sellTriggers.take_profit.tp1.basis">
                {{ sellTriggers.take_profit.tp1.basis }}
              </div>
            </div>

            <div class="bg-white/80 dark:bg-slate-800/80 p-2 rounded-lg border border-rose-100 dark:border-rose-900/40">
              <div class="text-slate-500 dark:text-slate-400 font-sans font-semibold">
                {{ isShortMode ? '空单突破止损' : '多单无条件清仓' }}
              </div>
              <div class="font-black text-rose-600 dark:text-rose-400 text-sm mt-0.5 tabular-nums">
                {{ isShortMode ? sellTriggers.breakdown_stop.short_stop_line.price_text : sellTriggers.breakdown_stop.long_clear_line.price_text }}
              </div>
              <div class="text-2xs text-slate-400 truncate mt-0.5" :title="isShortMode ? sellTriggers.breakdown_stop.short_stop_line.basis : sellTriggers.breakdown_stop.long_clear_line.basis">
                {{ isShortMode ? sellTriggers.breakdown_stop.short_stop_line.basis : sellTriggers.breakdown_stop.long_clear_line.basis }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 区块 C：变盘日期时间轴（横向徽章卡片展示斐波那契/卢卡斯共振与K线观察重点） -->
      <div v-if="turningDatesList.length" class="p-3.5 rounded-xl border border-amber-500/30 bg-amber-50/20 dark:bg-amber-950/25 space-y-2.5">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-1.5 text-xs font-bold text-amber-700 dark:text-amber-400">
            <span>⏳ 变盘日期时间轴</span>
            <span class="text-2xs px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-300 font-mono">
              斐波那契 & 卢卡斯共振推演
            </span>
          </div>
          <span class="text-2xs text-slate-500 dark:text-slate-400">
            点击变盘日在图表中高亮
          </span>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2">
          <div
            v-for="(td, tIdx) in turningDatesList"
            :key="tIdx"
            @click="$emit('highlight-time', td.date)"
            class="p-2.5 rounded-lg border bg-white/80 dark:bg-slate-800/80 cursor-pointer hover:border-amber-500 transition-colors flex flex-col justify-between"
            :class="td.is_resonance ? 'border-amber-500/60 shadow-2xs' : 'border-slate-200/80 dark:border-slate-700/60'"
          >
            <div>
              <div class="flex items-center justify-between">
                <span class="font-mono font-bold text-xs text-slate-800 dark:text-slate-100">
                  {{ td.date }}
                </span>
                <span
                  class="text-2xs font-mono font-bold px-1.5 py-0.5 rounded"
                  :class="td.is_resonance ? 'bg-amber-500 text-white' : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300'"
                >
                  {{ td.day_offset_text }}
                </span>
              </div>
              <div class="text-2xs text-amber-700 dark:text-amber-300/90 font-medium mt-1 leading-tight">
                {{ td.basis }}
              </div>
            </div>
            <div class="text-2xs text-slate-500 dark:text-slate-400 mt-1.5 border-t border-slate-100 dark:border-slate-700/50 pt-1 leading-snug">
              {{ td.focus }}
            </div>
          </div>
        </div>
      </div>

      <!-- 规范化支撑 / 阻力位列表（从高到低严格降序排列，显示精确价格、百分比与依据） -->
      <div v-if="sortedSRLevels.length" class="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900/50 p-4 space-y-2.5">
        <div class="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          <span>支撑 / 阻力位 (价格由高到低排列)</span>
          <span class="text-2xs font-sans font-normal opacity-75">悬浮高亮 / 点击定位</span>
        </div>
        <div class="space-y-1.5 font-mono">
          <div
            v-for="(lvl, idx) in sortedSRLevels"
            :key="idx"
            @mouseenter="$emit('highlight-sr', idx, true, lvl)"
            @mouseleave="$emit('highlight-sr', idx, false, lvl)"
            @click="$emit('scroll-to-sr', lvl, idx)"
            class="flex items-center justify-between px-3 py-2 rounded-lg text-xs sm:text-sm cursor-pointer transition-colors"
            :class="[
              lvl.type === 'resistance'
                ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 hover:bg-rose-500/20'
                : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/20',
              highlightedSR === idx ? 'ring-2 ring-indigo-500' : '',
            ]"
          >
            <div class="flex items-center gap-2">
              <span
                class="font-bold text-2xs px-1.5 py-0.5 rounded font-sans"
                :class="lvl.type === 'resistance' ? 'bg-rose-500/20 text-rose-700 dark:text-rose-300' : 'bg-emerald-500/20 text-emerald-700 dark:text-emerald-300'"
              >
                {{ lvl.type === 'resistance' ? '阻力' : '支撑' }}
              </span>
              <span class="font-bold tabular-nums">
                ${{ Number(lvl.price).toFixed(2) }}
              </span>
              <span class="text-2xs font-normal opacity-80 tabular-nums">
                ({{ lvl.diffPctStr }})
              </span>
            </div>
            <span class="text-xs font-sans font-medium text-slate-500 dark:text-slate-400 truncate max-w-[180px]" :title="lvl.basis">
              {{ lvl.basis }}
            </span>
          </div>
        </div>
      </div>

      <!-- 复制复盘笔记 -->
      <button
        @click="copyReviewMarkdown"
        class="btn-tactile w-full py-2.5 px-4 rounded-xl text-sm font-bold bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/50 dark:hover:bg-indigo-900/60 text-indigo-600 dark:text-indigo-300 border border-indigo-200/70 dark:border-indigo-800/60 cursor-pointer transition-colors"
      >
        {{ copied ? '已复制复盘笔记' : '复制复盘笔记' }}
      </button>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { LEVERAGE_ETF_MAP, formatSymbol, type SRLevel } from '../utils/api';
import { enrichSRLevels } from '../utils/srUtils';

const props = defineProps<{
  symbol: string;
  period: string;
  summary: any;
  loading: boolean;
  srLevels?: SRLevel[];
  highlightedSR?: number | null;
}>();

defineEmits<{
  (e: 'run', mode: string): void;
  (e: 'clear'): void;
  (e: 'highlight-sr', idx: number, isHover: boolean, level?: SRLevel): void;
  (e: 'scroll-to-sr', level: SRLevel, idx?: number): void;
  (e: 'highlight-time', dateStr: string | null): void;
  (e: 'switch-symbol', targetSymbol: string): void;
  (e: 'toggle-collapse'): void;
}>();

const copied = ref(false);

const leveragePair = computed(() => {
  if (!props.symbol) return null;
  const upper = props.symbol.toUpperCase();
  const key = Object.keys(LEVERAGE_ETF_MAP).find((k) => k.toUpperCase() === upper);
  return key ? LEVERAGE_ETF_MAP[key] : null;
});

const isCrypto = computed(() => {
  const sym = (props.symbol || '').toUpperCase();
  const summaryMarket = String(props.summary?.market || '').toLowerCase();
  return (
    sym.includes('BTC') ||
    sym.includes('ETH') ||
    sym.includes('SOL') ||
    sym.startsWith('CRYPTO') ||
    summaryMarket === 'crypto'
  );
});

/** 资产门禁阈值：标准资产 2.5R，加密资产 2.0R */
const minRR = computed(() => (isCrypto.value ? 2.0 : 2.5));

const currentPriceFormatted = computed(() => {
  const p = props.summary?.current_price ?? props.summary?.trade_plan?.entry;
  return p ? Number(p).toFixed(2) : '--';
});

/** 道氏理论大盘双指数相互印证信息 (SPY & QQQ) */
const dowMarketInfo = computed(() => {
  const dm = props.summary?.dow_market_verification || props.summary?.trade_plan?.dow_market_verification;
  if (!dm) return null;
  const status = dm.status;
  const desc = dm.description || dm.desc || '';
  if (status === 'PASS') {
    return {
      text: 'SPY/QQQ 相互印证 📈',
      badgeClass: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30',
      desc: desc || 'SPY 与 QQQ 相互印证上升趋势，道氏宏观做多环境健康',
      status,
    };
  }
  if (status === 'DIVERGENCE' || status === 'WARN') {
    return {
      text: '大盘指数背离 ⚠️',
      badgeClass: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30',
      desc: desc || 'SPY 与 QQQ 走势背离，道氏理论禁止单边激进做多',
      status,
    };
  }
  if (status === 'BEAR' || status === 'BLOCK') {
    return {
      text: '大盘指数空头 🛡️',
      badgeClass: 'bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/30',
      desc: desc || '大盘指数主趋势向下或破200EMA，禁止盲目做多抄底',
      status,
    };
  }
  if (status === 'UNAVAILABLE') {
    return {
      text: '大盘数据未载入 ⚪',
      badgeClass: 'bg-slate-500/15 text-slate-600 dark:text-slate-400 border border-slate-500/30',
      desc: desc || '大盘指数历史数据未配置，按单标的自身结构研判',
      status,
    };
  }
  return null;
});

const WAVE_LABELS: Record<string, string> = {
  corrective_abc: 'ABC 调整浪',
  impulse: '5浪驱动结构',
  impulse_5: '5浪驱动结构',
  impulse_5_wave: '5浪驱动结构',
  developing_wave_3: '第3浪推进中',
  developing_wave_5: '第5浪推进中',
  leading_diagonal: '引导楔形',
  ending_diagonal: '终结楔形',
  complex: '复合调整浪',
};

function formatWavePattern(pattern?: string): string {
  if (!pattern) return '--';
  return WAVE_LABELS[pattern] || pattern;
}

/** 严格方向枚举：'LONG' 做多 | 'SHORT' 做空 | 'WAIT' 观望 */
const dirMode = computed<'LONG' | 'SHORT' | 'WAIT'>(() => {
  const tp = props.summary?.trade_plan;
  if (tp?.direction_mode) {
    const dm = String(tp.direction_mode).toUpperCase();
    if (dm === 'LONG' || dm === 'SHORT' || dm === 'WAIT') return dm as any;
  }
  const raw = String(tp?.direction || '').toLowerCase();
  if (raw.includes('short') || raw.includes('空头') || raw.includes('做空')) return 'SHORT';
  if (raw.includes('long') || raw.includes('做多')) return 'LONG';
  return 'WAIT';
});

const isShortMode = computed(() => dirMode.value === 'SHORT');
const isLongMode = computed(() => dirMode.value === 'LONG');

/** 道氏理论量价验证状态 */
const volumeStatusInfo = computed(() => {
  let status =
    props.summary?.dow_volume_status ||
    props.summary?.trade_plan?.dow_volume_status ||
    props.summary?.volume_status ||
    '';

  if (!status) {
    const reasons: string[] = [
      ...(props.summary?.trade_plan?.reasons || []),
      ...(props.summary?.reasons || []),
    ];
    for (const r of reasons) {
      if (typeof r === 'string') {
        if (r.includes('顺势放量') || r.includes('量增价涨') || r.includes('放量突破') || r.includes('放量主推')) {
          status = '顺势放量 (主推确认)';
          break;
        }
        if (r.includes('缩量回调') || r.includes('缩量回踩') || r.includes('缩量整理') || r.includes('缩量反弹')) {
          status = '缩量回调 (调整健康)';
          break;
        }
        if (r.includes('背离') || r.includes('量价背离') || r.includes('顶背离') || r.includes('底背离')) {
          status = '量价背离预警 (动能衰竭)';
          break;
        }
      }
    }
  }

  if (!status) return null;

  if (status.includes('放量') || status.includes('配合')) {
    return {
      text: status,
      badgeClass: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30',
      desc: '道氏量价顺势共振',
    };
  }
  if (status.includes('缩量') || status.includes('健康')) {
    return {
      text: status,
      badgeClass: 'bg-sky-500/15 text-sky-600 dark:text-sky-400 border border-sky-500/30',
      desc: '调整期缩量蓄势',
    };
  }
  if (status.includes('背离') || status.includes('预警') || status.includes('衰竭')) {
    return {
      text: status,
      badgeClass: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30',
      desc: '量价背离谨慎追单',
    };
  }

  return {
    text: status,
    badgeClass: 'bg-slate-500/15 text-slate-600 dark:text-slate-400 border border-slate-500/30',
    desc: '道氏量价验证',
  };
});

/** 核心定调与视觉样式主题 */
const directionTheme = computed(() => {
  const dmStatus = props.summary?.dow_market_verification?.status || props.summary?.trade_plan?.dow_market_verification?.status;
  const tp = props.summary?.trade_plan || {};

  if (dmStatus === 'DIVERGENCE' || dmStatus === 'WARN') {
    return {
      headline: '大盘背离 · 观望防守',
      badgeText: '大盘背离拦截',
      badgeClass: 'bg-amber-500/20 text-amber-800 dark:text-amber-300 border-amber-500/40',
      actionHint: '标普500与纳斯达克走势分化，道氏大盘相互验证否决，强制观望，严禁单边盲目做多。',
      cardClass: 'bg-amber-50/40 dark:bg-amber-950/20 border-amber-500/40',
      bannerClass: 'bg-amber-500/20 text-amber-900 dark:text-amber-200 border border-amber-500/40',
    };
  }

  if (isShortMode.value) {
    return {
      headline: '主趋势空头 · 反弹遇阻高抛 / 严禁左侧抄底',
      badgeText: '顺势空头 / 防守观望',
      badgeClass: 'bg-rose-500/20 text-rose-800 dark:text-rose-300 border-rose-500/40',
      actionHint:
        '标的价格处于 200 EMA 下方及下降通道 (LH+LL) 中。严格遵循道氏顺势铁律，严禁逆势抄底；多单以反弹高抛或清仓防守为主，空单关注阻力区高抛入场。',
      cardClass: 'bg-rose-50/40 dark:bg-rose-950/20 border-rose-500/40',
      bannerClass: 'bg-rose-600 text-white shadow-xs',
    };
  }

  if (isLongMode.value) {
    const passed = Boolean(tp.passed_gates);
    return {
      headline: passed ? '主趋势多头 · 顺势做多' : '偏向多头 · 空间不足等待回踩',
      badgeText: passed ? '多头达标可执行' : '等待回踩企稳',
      badgeClass: passed ? 'bg-emerald-500/20 text-emerald-800 dark:text-emerald-300 border-emerald-500/40' : 'bg-indigo-500/20 text-indigo-800 dark:text-indigo-300 border-indigo-500/40',
      actionHint: passed
        ? `多头主推结构确立，盈亏比达标 (>=${minRR.value}R)，可按计划顺势低吸跟进。`
        : '多头主趋势向上，但现价追高盈亏比偏低，上方受阻；严禁追高，耐心等待回踩关键支撑企稳。',
      cardClass: 'bg-emerald-50/40 dark:bg-emerald-950/20 border-emerald-500/40',
      bannerClass: passed ? 'bg-emerald-600 text-white shadow-xs' : 'bg-emerald-600/20 text-emerald-900 dark:text-emerald-200 border border-emerald-500/40',
    };
  }

  return {
    headline: '多空分歧 · 暂时观望',
    badgeText: '观望等待',
    badgeClass: 'bg-slate-500/20 text-slate-800 dark:text-slate-300 border-slate-500/40',
    actionHint: '趋势处于无序震荡或均线缠绕期，无明显顺势盈亏比优势，保持空仓等待突破确认。',
    cardClass: 'bg-slate-50/60 dark:bg-slate-900/40 border-slate-300 dark:border-slate-700',
    bannerClass: 'bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200',
  };
});

/** 右侧买入触发点结构 */
const buyTriggers = computed(() => {
  const bt = props.summary?.buy_triggers || props.summary?.trade_plan?.buy_triggers;
  if (bt?.aggressive && bt?.conservative) return bt;
  const p = Number(props.summary?.current_price || props.summary?.trade_plan?.entry || 100);
  return {
    aggressive: {
      name: isShortMode.value ? '激进波段买点 (反转确认)' : '激进波段买点 (顺势低吸)',
      condition: isShortMode.value
        ? '放量突破下降通道上轨及前高 LH 阻力位后，缩量回踩不破前低，构筑有效 HL (0.500~0.618 回撤) 触发'
        : '次级趋势缩量回踩 0.500~0.618 斐波那契回撤位企稳低吸',
      price_range_text: `$${(p * 0.98).toFixed(2)} ~ $${p.toFixed(2)}`,
      stop_loss_text: `$${(p * 0.95).toFixed(2)}`,
      target_text: `$${(p * 1.06).toFixed(2)}`,
    },
    conservative: {
      name: isShortMode.value ? '稳健趋势买点 (收复200EMA)' : '稳健趋势买点 (放量加仓)',
      condition: isShortMode.value
        ? '价格放量收复并站稳 200 EMA，且核心大盘指数 (SPY 与 QQQ) 同步形成多头相互验证时触发买入'
        : '价格放量突破前高并站稳，大盘双指数相互印证顺风时顺势跟进',
      price_range_text: `$${(p * 1.02).toFixed(2)} ~ $${(p * 1.04).toFixed(2)}`,
      stop_loss_text: `$${(p * 0.98).toFixed(2)}`,
      target_text: `$${(p * 1.10).toFixed(2)}`,
    },
  };
});

/** 顺势卖出触发点结构 */
const sellTriggers = computed(() => {
  const st = props.summary?.sell_triggers || props.summary?.trade_plan?.sell_triggers;
  if (st?.rebound_sell && st?.take_profit && st?.breakdown_stop) return st;
  const p = Number(props.summary?.current_price || props.summary?.trade_plan?.entry || 100);
  return {
    rebound_sell: {
      name: isShortMode.value ? '反弹高抛卖出区 (空单入场/多单离场)' : '多头分级兑现与止盈区',
      resistance_zone_1: {
        label: '第一阻力卖出区 (TP1)',
        price_range_text: `$${(p * 1.03).toFixed(2)} ~ $${(p * 1.05).toFixed(2)}`,
        basis: '前一下跌波浪 0.382 ~ 0.500 斐波那契回撤与阻力带',
      },
      resistance_zone_2: {
        label: '第二阻力卖出区 (TP2)',
        price_range_text: `$${(p * 1.06).toFixed(2)} ~ $${(p * 1.08).toFixed(2)}`,
        basis: '0.618 黄金分割位与下降通道上轨重叠共振',
      },
    },
    take_profit: {
      tp1: {
        price_text: `$${(p * 0.96).toFixed(2)}`,
        basis: '道氏前期波谷支撑位 (减半兑现)',
      },
      tp2: {
        price_text: `$${(p * 0.92).toFixed(2)}`,
        basis: '空头顺势 1.618x 斐波那契延展位 / 通道下轨',
      },
    },
    breakdown_stop: {
      long_clear_line: {
        price_text: `$${(p * 0.95).toFixed(2)}`,
        basis: '跌破前低 C 浪支撑位，顺势空头破位严禁扛单',
      },
      short_stop_line: {
        price_text: `$${(p * 1.08).toFixed(2)}`,
        basis: '放量站稳前高 LH 阻力位，下降结构破坏',
      },
    },
  };
});

/** 变盘日期时间轴数据 */
const turningDatesList = computed(() => {
  const td = props.summary?.turning_dates || props.summary?.turn_windows?.turning_dates;
  if (Array.isArray(td) && td.length > 0) return td;
  const clusters = props.summary?.turn_windows?.clusters;
  if (Array.isArray(clusters) && clusters.length > 0) {
    return clusters.slice(0, 4).map((c: any) => ({
      date: c.date,
      days_from_now: c.days_from_now,
      day_offset_text: c.days_from_now === 0 ? '今日 (T+0)' : (c.days_from_now === 1 ? '明日 (T+1)' : `T+${c.days_from_now}日`),
      basis: c.reasons?.length ? c.reasons.slice(0, 2).join(' / ') : '时间周期共振窗',
      focus: c.is_resonance ? '关注向上放量突破通道上轨还是滞涨反转' : '关注关键位支撑/阻力确认',
      confidence: c.confidence || '高',
      is_resonance: Boolean(c.is_resonance),
    }));
  }
  return [];
});

/** 规范化支撑/阻力位（价格由高到低降序排列，补充涨跌幅百分比与依据，剔除“弱”字） */
const sortedSRLevels = computed(() => {
  if (!props.srLevels || !props.srLevels.length) return [];
  const curPrice = Number(props.summary?.current_price || props.summary?.trade_plan?.entry || 0);

  const enriched = enrichSRLevels(props.srLevels, props.summary);

  return enriched.map((lvl) => {
    const p = Number(lvl.price);
    const diffPct = curPrice > 0 ? ((p - curPrice) / curPrice) * 100 : 0;
    const diffPctStr = `${diffPct >= 0 ? '+' : ''}${diffPct.toFixed(1)}%`;

    return {
      ...lvl,
      price: p,
      diffPctStr,
      basis: lvl.basis || '',
    };
  });
});

function copyReviewMarkdown() {
  if (!props.summary) return;
  const s = props.summary;
  const wave = s.wave || {};

  const lines = [
    `### ${props.symbol} (${props.period}) 策略复盘`,
    `- **核心定调**：${directionTheme.value.headline}`,
    `- **宏观指引**：${directionTheme.value.actionHint}`,
    `- **市场结构**：道氏 ${s.dow_phase || '--'} | 波浪 ${formatWavePattern(wave.pattern)} | 均线 ${s.ema_200_gate?.trend || '--'}`,
  ];

  if (dowMarketInfo.value) {
    lines.push(`- **大盘印证**：${dowMarketInfo.value.text} (${dowMarketInfo.value.desc})`);
  }

  // 买卖点输出
  const bt = buyTriggers.value;
  lines.push(`- **右侧买入点**：[激进] ${bt.aggressive.price_range_text} (${bt.aggressive.condition}) | [稳健] ${bt.conservative.price_range_text} (${bt.conservative.condition})`);

  const st = sellTriggers.value;
  lines.push(`- **顺势卖出点**：[第一阻力] ${st.rebound_sell.resistance_zone_1.price_range_text} | [第二阻力] ${st.rebound_sell.resistance_zone_2.price_range_text} | [下探目标] ${st.take_profit.tp1.price_text} | [清仓/止损线] ${isShortMode.value ? st.breakdown_stop.short_stop_line.price_text : st.breakdown_stop.long_clear_line.price_text}`);

  if (turningDatesList.value.length) {
    const datesDesc = turningDatesList.value.map((d: any) => `${d.date}(${d.day_offset_text}: ${d.basis})`).join(' -> ');
    lines.push(`- **变盘日期时间轴**：${datesDesc}`);
  }

  if (wave.invalidation_price) {
    lines.push(
      `- **理论证伪线**：$${Number(wave.invalidation_price).toFixed(2)} (${wave.invalidation_reason || '数浪铁律'})`
    );
  }

  navigator.clipboard.writeText(lines.join('\n'));
  copied.value = true;
  setTimeout(() => {
    copied.value = false;
  }, 2000);
}
</script>
