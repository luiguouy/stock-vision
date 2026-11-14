<template>
  <div class="space-y-4 select-none">
    <!-- 顶部操作栏 -->
    <div class="flex items-center justify-between gap-2 pb-2.5 border-b border-slate-100 dark:border-slate-800">
      <div>
        <h4 class="text-xs font-bold text-slate-800 dark:text-slate-100 tracking-tight flex items-center gap-1.5">
          <span>价格行为 & 波浪矩阵</span>
          <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
            {{ period }}
          </span>
        </h4>
      </div>
      <div class="flex items-center gap-1.5">
        <button
          @click="$emit('run', 'swing')"
          :disabled="loading || !symbol"
          class="btn-tactile px-2.5 py-1 rounded-lg text-[11px] font-bold bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-40 cursor-pointer transition-colors shadow-2xs"
        >
          {{ loading ? '计算中...' : '重算策略' }}
        </button>
        <button
          @click="$emit('clear')"
          :disabled="loading"
          class="btn-tactile px-2 py-1 rounded-lg text-[11px] font-semibold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 cursor-pointer transition-colors"
          title="清除图表标注"
        >
          清屏
        </button>
      </div>
    </div>

    <!-- 杠杆 ETF 基准正股映射提示 -->
    <div
      v-if="leveragePair"
      class="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-between gap-2"
    >
      <div class="text-[11px] text-amber-800 dark:text-amber-300 leading-snug">
        <span class="font-bold">💡 {{ leveragePair.label }}</span>：杠杆损耗易使形态失真，建议参考正股分析。
      </div>
      <button
        @click="$emit('switch-symbol', leveragePair.underlying)"
        class="shrink-0 px-2 py-1 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-[10px] font-bold cursor-pointer transition-colors"
      >
        看正股 {{ formatSymbol(leveragePair.underlying) }}
      </button>
    </div>

    <!-- 空状态 -->
    <div
      v-if="!summary && !loading"
      class="py-10 text-center text-xs text-slate-400 dark:text-slate-500 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl"
    >
      点击上方「重算策略」或按 <kbd class="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 font-mono text-[10px]">Space</kbd> 启动分析
    </div>

    <template v-if="summary">
      <!-- 1. 艾略特波浪变盘时间窗预测卡片 (核心新增) -->
      <div
        v-if="summary.turn_windows?.enabled"
        class="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/50 p-3.5 space-y-2.5"
      >
        <div class="flex items-center justify-between">
          <h5 class="text-[11px] font-bold text-slate-700 dark:text-slate-200 uppercase tracking-wider flex items-center gap-1">
            <span>⏳ 艾略特变盘时间窗 (Fib & Lucas)</span>
          </h5>
          <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 font-bold">
            {{ summary.turn_windows.clusters?.length || 0 }} 窗口
          </span>
        </div>

        <!-- 临近变盘置顶强预警 -->
        <div
          v-if="summary.turn_windows.imminent_alert"
          class="p-2 rounded-lg bg-amber-500/15 border border-amber-500/30 text-[11px] text-amber-700 dark:text-amber-300 font-medium leading-relaxed"
        >
          {{ summary.turn_windows.imminent_alert }}
        </div>

        <!-- 当前波段耗时计量 -->
        <div
          v-if="summary.turn_windows.wave_duration"
          class="grid grid-cols-3 gap-1.5 text-center bg-white dark:bg-slate-800/70 p-2 rounded-lg border border-slate-100 dark:border-slate-700/60"
        >
          <div>
            <div class="text-[9px] text-slate-400">当前波段耗时</div>
            <div class="text-xs font-bold font-mono text-slate-800 dark:text-slate-100">
              {{ summary.turn_windows.wave_duration.curr_wave_bars }} 根
            </div>
          </div>
          <div>
            <div class="text-[9px] text-slate-400">前波段耗时比</div>
            <div class="text-xs font-bold font-mono text-indigo-600 dark:text-indigo-400">
              {{ summary.turn_windows.wave_duration.duration_ratio }}x
            </div>
          </div>
          <div>
            <div class="text-[9px] text-slate-400">下一神奇数窗</div>
            <div class="text-xs font-bold font-mono text-amber-600 dark:text-amber-400">
              {{ summary.turn_windows.wave_duration.next_seq_type }}({{ summary.turn_windows.wave_duration.next_seq_number }})
            </div>
          </div>
        </div>

        <!-- 变盘日时间簇列表 (悬停联动高亮主图垂直线) -->
        <div class="space-y-1.5">
          <div
            v-for="item in summary.turn_windows.clusters"
            :key="item.date"
            @mouseenter="$emit('highlight-time', item.date)"
            @mouseleave="$emit('highlight-time', null)"
            class="p-2 rounded-lg border transition-all cursor-pointer"
            :class="
              item.is_resonance
                ? 'bg-amber-50/70 dark:bg-amber-950/20 border-amber-300/60 dark:border-amber-700/50 hover:border-amber-500'
                : 'bg-white dark:bg-slate-800/50 border-slate-200/60 dark:border-slate-700/50 hover:border-indigo-400'
            "
          >
            <div class="flex items-center justify-between gap-2 mb-1">
              <div class="flex items-center gap-1.5">
                <span class="text-xs font-bold font-mono text-slate-900 dark:text-slate-100">{{ item.date }}</span>
                <span
                  class="text-[10px] font-mono px-1.5 py-0.2 rounded font-bold"
                  :class="
                    item.days_from_now === 0
                      ? 'bg-rose-500 text-white'
                      : item.days_from_now > 0
                        ? 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300'
                        : 'bg-slate-100 dark:bg-slate-800 text-slate-400'
                  "
                >
                  {{
                    item.days_from_now === 0
                      ? '今日变盘窗'
                      : item.days_from_now > 0
                        ? `T+${item.days_from_now}日`
                        : `已过${Math.abs(item.days_from_now)}日`
                  }}
                </span>
              </div>
              <span
                class="text-[10px] font-bold px-1.5 py-0.5 rounded"
                :class="
                  item.is_resonance
                    ? 'bg-amber-500/20 text-amber-700 dark:text-amber-300'
                    : 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400'
                "
              >
                {{ item.confidence }}
              </span>
            </div>
            <div class="text-[10px] text-slate-500 dark:text-slate-400 font-mono leading-snug">
              {{ item.reasons.join(' · ') }}
            </div>
          </div>
        </div>
      </div>

      <!-- 2. 交易计划卡片 (Entry / SL / TP1 / R:R) -->
      <div
        v-if="summary.trade_plan"
        class="rounded-xl border p-3.5 space-y-2.5"
        :class="
          summary.trade_plan.passed_gates
            ? 'bg-emerald-50/40 dark:bg-emerald-950/20 border-emerald-500/30'
            : 'bg-slate-50/70 dark:bg-slate-900/50 border-slate-200/80 dark:border-slate-800'
        "
      >
        <div class="flex items-center justify-between">
          <span class="text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            结构化交易计划
          </span>
          <span
            class="text-xs font-bold px-2 py-0.5 rounded-md"
            :class="
              summary.trade_plan.passed_gates
                ? 'bg-emerald-500 text-white'
                : 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300'
            "
          >
            {{ summary.trade_plan.direction }}
          </span>
        </div>

        <div class="grid grid-cols-2 gap-2 text-xs font-mono">
          <div class="bg-white dark:bg-slate-800/70 p-2 rounded-lg border border-slate-100 dark:border-slate-700/50">
            <div class="text-[9px] text-slate-400 font-sans">入场参考 (Entry)</div>
            <div class="font-bold text-blue-600 dark:text-blue-400">
              {{ summary.trade_plan.entry ? `$${summary.trade_plan.entry.toFixed(2)}` : '--' }}
            </div>
          </div>
          <div class="bg-white dark:bg-slate-800/70 p-2 rounded-lg border border-slate-100 dark:border-slate-700/50">
            <div class="text-[9px] text-slate-400 font-sans">净盈亏比 (R:R)</div>
            <div class="font-bold text-slate-800 dark:text-slate-100">
              {{ summary.trade_plan.rr_ratio }}R
            </div>
          </div>
          <div class="bg-white dark:bg-slate-800/70 p-2 rounded-lg border border-slate-100 dark:border-slate-700/50">
            <div class="text-[9px] text-slate-400 font-sans">止损防线 (SL)</div>
            <div class="font-bold text-rose-600 dark:text-rose-400">
              {{ summary.trade_plan.stop_loss ? `$${summary.trade_plan.stop_loss.toFixed(2)}` : '--' }}
            </div>
          </div>
          <div class="bg-white dark:bg-slate-800/70 p-2 rounded-lg border border-slate-100 dark:border-slate-700/50">
            <div class="text-[9px] text-slate-400 font-sans">第一目标 (TP1)</div>
            <div class="font-bold text-emerald-600 dark:text-emerald-400">
              {{ summary.trade_plan.tp1 ? `$${summary.trade_plan.tp1.toFixed(2)}` : '--' }}
            </div>
          </div>
        </div>

        <ul class="space-y-1 text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed pt-1 border-t border-slate-200/60 dark:border-slate-700/60">
          <li v-for="(r, idx) in summary.trade_plan.reasons" :key="idx" class="flex items-start gap-1.5">
            <span class="text-indigo-500 mt-0.5">•</span>
            <span>{{ r }}</span>
          </li>
        </ul>
      </div>

      <!-- 3. 宏观结构与波浪状态 -->
      <div class="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-3.5 space-y-2 text-xs">
        <div class="flex justify-between items-center">
          <span class="text-slate-400">道氏趋势</span>
          <span class="font-bold text-slate-800 dark:text-slate-100">{{ summary.dow_phase }}</span>
        </div>
        <div class="flex justify-between items-center">
          <span class="text-slate-400">200 EMA 门禁</span>
          <span
            class="font-mono font-bold"
            :class="summary.ema_200_gate?.status === 'PASS' ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500'"
          >
            {{ summary.ema_200_gate?.value ? `$${summary.ema_200_gate.value}` : '--' }}
          </span>
        </div>
        <div class="flex justify-between items-center">
          <span class="text-slate-400">波浪结构</span>
          <span class="font-bold text-purple-600 dark:text-purple-400">{{ summary.wave?.pattern }}</span>
        </div>
        <div v-if="summary.wave?.invalidation_price" class="flex justify-between items-center">
          <span class="text-slate-400">波浪客观证伪线</span>
          <span class="font-mono font-bold text-purple-600 dark:text-purple-400">
            ${{ summary.wave.invalidation_price.toFixed(2) }}
          </span>
        </div>
        <div v-if="summary.channel?.detail" class="flex justify-between items-center">
          <span class="text-slate-400">动态回归通道</span>
          <span class="font-medium text-slate-700 dark:text-slate-300 truncate max-w-[170px]" :title="summary.channel.detail">
            {{ summary.channel.detail }}
          </span>
        </div>
      </div>

      <!-- 4. 关键水平位联动 -->
      <div v-if="srLevels && srLevels.length" class="space-y-1.5">
        <div class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">关键价格水平位</div>
        <div
          v-for="(lvl, idx) in srLevels"
          :key="idx"
          @mouseenter="$emit('highlight-sr', idx, true)"
          @mouseleave="$emit('highlight-sr', idx, false)"
          @click="$emit('scroll-to-sr', lvl)"
          class="flex items-center justify-between px-3 py-1.5 rounded-lg border text-xs font-mono cursor-pointer transition-colors"
          :class="
            highlightedSR === idx
              ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/30'
              : 'border-slate-200/70 dark:border-slate-800 bg-white dark:bg-slate-900/40 hover:border-slate-300'
          "
        >
          <span :class="lvl.type === 'support' ? 'text-emerald-600 dark:text-emerald-400 font-bold' : 'text-rose-500 font-bold'">
            {{ lvl.type === 'support' ? '支撑' : '阻力' }} ${{ lvl.price.toFixed(2) }}
          </span>
          <span class="text-[10px] text-slate-400">{{ lvl.level }}</span>
        </div>
      </div>

      <!-- 5. 底部操作：独立 HTML 波浪报表 & 复盘 Markdown 导出 -->
      <div class="pt-2 flex items-center gap-2">
        <a
          v-if="summary.html_url"
          :href="summary.html_url"
          target="_blank"
          class="flex-1 text-center py-2 px-3 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 transition-colors"
        >
          交互式波浪报告 ↗
        </a>
        <button
          @click="copyReviewMarkdown"
          class="btn-tactile flex-1 py-2 px-3 rounded-xl text-xs font-semibold bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/50 dark:hover:bg-indigo-900/60 text-indigo-600 dark:text-indigo-300 border border-indigo-200/60 dark:border-indigo-800/60 cursor-pointer transition-colors"
        >
          {{ copied ? '✅ 已复制笔记' : '📋 复制复盘笔记' }}
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { LEVERAGE_ETF_MAP, formatSymbol, type SRLevel } from '../utils/api';

const props = defineProps<{
  symbol: string;
  period: string;
  summary: any;
  loading: boolean;
  srLevels: SRLevel[];
  highlightedSR: number | null;
}>();

defineEmits<{
  (e: 'run', mode: string): void;
  (e: 'clear'): void;
  (e: 'highlight-sr', idx: number, isHover: boolean): void;
  (e: 'scroll-to-sr', level: SRLevel): void;
  (e: 'highlight-time', dateStr: string | null): void;
  (e: 'switch-symbol', targetSymbol: string): void;
}>();

const copied = ref(false);

const leveragePair = computed(() => {
  if (!props.symbol) return null;
  const upper = props.symbol.toUpperCase();
  const key = Object.keys(LEVERAGE_ETF_MAP).find((k) => k.toUpperCase() === upper);
  return key ? LEVERAGE_ETF_MAP[key] : null;
});

function copyReviewMarkdown() {
  if (!props.summary) return;
  const s = props.summary;
  const tp = s.trade_plan || {};
  const twClusters = s.turn_windows?.clusters || [];
  const twText = twClusters.length
    ? twClusters.map((c: any) => `${c.date} (${c.confidence})`).join(' | ')
    : '无近期窗口';

  const md = [
    `### 📈 ${props.symbol} (${props.period}) 价格行为与波浪复盘`,
    `- **生成时间**：${new Date().toLocaleString()}`,
    `- **道氏阶段**：${s.dow_phase || '--'}`,
    `- **200 EMA 门禁**：${s.ema_200_gate?.trend || '--'} ($${s.ema_200_gate?.value ?? '--'})`,
    `- **波浪形态**：${s.wave?.pattern || '--'} | 客观证伪线: $${s.wave?.invalidation_price ?? '--'}`,
    `- **艾略特变盘窗**：${twText}`,
    ``,
    `#### 🎯 交易计划 (${tp.direction || '观望'})`,
    `- **入场参考**：${tp.entry ? `$${tp.entry}` : '--'}`,
    `- **止损位**：${tp.stop_loss ? `$${tp.stop_loss}` : '--'}`,
    `- **第一目标 (TP1)**：${tp.tp1 ? `$${tp.tp1}` : '--'}`,
    `- **净盈亏比**：${tp.rr_ratio ?? 0}R (${tp.passed_gates ? '✅ 通过 2.5R 门禁' : '⚠️ 未达标/观望'})`,
  ].join('\n');

  navigator.clipboard.writeText(md);
  copied.value = true;
  setTimeout(() => {
    copied.value = false;
  }, 2000);
}
</script>
