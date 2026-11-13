<template>
  <div class="bg-white dark:bg-[#0f172a] border border-slate-200/80 dark:border-white/10 rounded-xl shadow-sm p-4 text-xs font-sans transition-all space-y-4">
    <!-- 头部工具栏 -->
    <div class="flex items-center justify-between pb-3.5 border-b border-slate-100 dark:border-slate-800">
      <div class="flex items-center gap-2">
        <span class="relative flex h-2 w-2">
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
          <span class="relative inline-flex rounded-full h-2 w-2 bg-indigo-600 dark:bg-indigo-400"></span>
        </span>
        <h3 class="font-bold text-slate-900 dark:text-slate-100 text-xs tracking-tight">PA 策略矩阵</h3>
      </div>
      <div class="flex items-center gap-1.5">
        <select
          v-model="currentMode"
          class="bg-slate-50 dark:bg-[#141e33] border border-slate-200 dark:border-slate-700/80 text-slate-700 dark:text-slate-200 text-[11px] rounded-lg px-2 py-1 outline-none focus:border-indigo-500 font-medium cursor-pointer transition-colors"
        >
          <option value="swing">波段 (Swing)</option>
          <option value="day">日内 (Day)</option>
        </select>
        <button
          @click="handleRun"
          :disabled="loading"
          class="btn-tactile bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium px-2.5 py-1 rounded-lg text-[11px] transition-all shadow-sm flex items-center gap-1.5 cursor-pointer"
        >
          <svg v-if="loading" class="animate-spin h-3 w-3 text-white" viewBox="0 0 24 24" fill="none">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
          </svg>
          <svg v-else class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <span>{{ loading ? '计算中' : '执行分析' }}</span>
        </button>
        <button
          @click="$emit('clear')"
          class="btn-tactile bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 px-2 py-1 rounded-lg text-[11px] transition-colors cursor-pointer"
          title="清空图表标注"
        >
          清空
        </button>
      </div>
    </div>

    <!-- 策略摘要内容 (模块场网格划分) -->
    <div v-if="summary" class="space-y-2.5 animate-fade-in">
      <!-- 1. 结构与门禁双栏 -->
      <div class="grid grid-cols-2 gap-2">
        <!-- 道氏结构 -->
        <div class="bg-slate-50/80 dark:bg-slate-900/60 p-2.5 rounded-lg border border-slate-200/60 dark:border-slate-700/50 flex flex-col justify-between">
          <div class="flex items-center justify-between">
            <span class="text-slate-400 dark:text-slate-500 text-[10px] font-bold tracking-wider">道氏趋势</span>
            <span
              class="px-1.5 py-0.5 rounded text-[10px] font-bold"
              :class="
                summary.dow_bias > 0
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                  : summary.dow_bias < 0
                  ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20'
                  : 'bg-slate-500/10 text-slate-500 border border-slate-500/20'
              "
            >
              {{ summary.dow_bias > 0 ? '多头' : summary.dow_bias < 0 ? '空头' : '震荡' }}
            </span>
          </div>
          <div class="font-bold text-slate-800 dark:text-slate-100 text-xs mt-1.5 truncate">
            {{ summary.dow_phase || '—' }}
          </div>
        </div>

        <!-- 200 EMA 门禁 -->
        <div class="bg-slate-50/80 dark:bg-slate-900/60 p-2.5 rounded-lg border border-slate-200/60 dark:border-slate-700/50 flex flex-col justify-between">
          <div class="flex items-center justify-between">
            <span class="text-slate-400 dark:text-slate-500 text-[10px] font-bold tracking-wider">200 EMA</span>
            <span
              class="px-1.5 py-0.5 rounded text-[10px] font-bold"
              :class="
                summary.ema_200_gate?.status === 'PASS'
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                  : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'
              "
            >
              {{ summary.ema_200_gate?.status === 'PASS' ? 'PASS' : 'WARN' }}
            </span>
          </div>
          <div class="flex items-baseline justify-between mt-1.5">
            <span class="font-bold text-slate-800 dark:text-slate-100 text-xs truncate">
              {{ summary.ema_200_gate?.trend || '—' }}
            </span>
            <span v-if="summary.ema_200_gate?.value" class="font-mono text-indigo-600 dark:text-indigo-400 text-xs font-bold tabular-nums">
              ${{ summary.ema_200_gate.value }}
            </span>
          </div>
        </div>
      </div>

      <!-- 2. 波浪证伪 -->
      <div class="bg-purple-50/40 dark:bg-purple-950/20 p-2.5 rounded-lg border border-purple-200/60 dark:border-purple-800/40">
        <div class="flex items-center justify-between">
          <span class="text-purple-700 dark:text-purple-300 font-bold text-xs flex items-center gap-1.5">
            波浪结构与关键拐点
          </span>
          <span class="text-purple-700 dark:text-purple-300 font-mono text-[11px] font-semibold px-1.5 py-0.5 rounded bg-purple-100/60 dark:bg-purple-900/40">
            {{ summary.wave?.pattern || '无极值形态' }}
          </span>
        </div>
        <div class="mt-2 flex items-center justify-between text-slate-600 dark:text-slate-300 text-xs">
          <span class="font-mono text-slate-700 dark:text-slate-200">{{ summary.wave?.current_wave || '观察期' }}</span>
          <span v-if="summary.wave?.invalidation_price" class="text-rose-600 dark:text-rose-400 font-medium flex items-center gap-1">
            <span class="text-[10px] text-slate-400">证伪线:</span>
            <span class="font-mono font-bold text-xs tabular-nums">${{ summary.wave.invalidation_price }}</span>
          </span>
        </div>
        <!-- 波浪拐点序列 -->
        <div v-if="summary.wave?.points && summary.wave.points.length" class="mt-2 pt-2 border-t border-purple-200/40 dark:border-purple-800/30 flex flex-wrap gap-1">
          <span
            v-for="(pt, idx) in summary.wave.points"
            :key="idx"
            class="font-mono text-[10px] px-1.5 py-0.5 rounded bg-purple-100/70 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 border border-purple-200/60 dark:border-purple-800/40 tabular-nums"
          >
            {{ pt.label }}: ${{ pt.price }}
          </span>
        </div>
      </div>

      <!-- 3. 箱体形态 -->
      <div v-if="summary.box" class="bg-blue-50/40 dark:bg-blue-950/20 p-2.5 rounded-lg border border-blue-200/60 dark:border-blue-800/40 flex items-center justify-between">
        <div class="flex items-center gap-1.5">
          <span class="text-blue-700 dark:text-blue-300 font-bold text-xs">箱体形态</span>
          <span class="text-slate-800 dark:text-slate-200 font-semibold text-xs">{{ summary.box.status }}</span>
        </div>
        <div v-if="summary.box.box_high && summary.box.box_low" class="font-mono text-slate-700 dark:text-slate-300 text-xs font-semibold bg-blue-100/60 dark:bg-blue-900/40 px-2 py-0.5 rounded tabular-nums">
          [ ${{ summary.box.box_low }} ~ ${{ summary.box.box_high }} ]
        </div>
      </div>

      <!-- 3b. 动态价格通道 (LRC Channel) -->
      <div v-if="summary.channel" class="bg-amber-50/40 dark:bg-amber-950/20 p-2.5 rounded-lg border border-amber-200/60 dark:border-amber-800/40">
        <div class="flex items-center justify-between">
          <span class="text-amber-700 dark:text-amber-400 font-bold text-xs flex items-center gap-1.5">
            动态价格通道
          </span>
          <span class="text-amber-700 dark:text-amber-400 font-mono text-[11px] font-semibold px-1.5 py-0.5 rounded bg-amber-100/60 dark:bg-amber-900/40">
            {{ summary.channel.channel_type === 'ascending' ? '上升通道' : summary.channel.channel_type === 'descending' ? '下降通道' : '水平震荡' }}
            <span v-if="summary.channel.r_squared" class="opacity-80 font-normal"> (R²={{ summary.channel.r_squared }})</span>
          </span>
        </div>
        <div class="mt-2 grid grid-cols-3 gap-1 font-mono text-[11px] text-center">
          <div class="bg-white/80 dark:bg-slate-900/70 p-1.5 rounded border border-amber-100 dark:border-amber-900/30">
            <div class="text-[9px] text-slate-400 font-sans">通道下轨</div>
            <div class="font-bold text-emerald-600 dark:text-emerald-400 tabular-nums">${{ summary.channel.lower_rail || '—' }}</div>
          </div>
          <div class="bg-white/80 dark:bg-slate-900/70 p-1.5 rounded border border-amber-100 dark:border-amber-900/30">
            <div class="text-[9px] text-slate-400 font-sans">通道中轴</div>
            <div class="font-bold text-slate-600 dark:text-slate-300 tabular-nums">${{ summary.channel.mid_rail || '—' }}</div>
          </div>
          <div class="bg-white/80 dark:bg-slate-900/70 p-1.5 rounded border border-amber-100 dark:border-amber-900/30">
            <div class="text-[9px] text-slate-400 font-sans">通道上轨</div>
            <div class="font-bold text-amber-600 dark:text-amber-400 tabular-nums">${{ summary.channel.upper_rail || '—' }}</div>
          </div>
        </div>
        <div v-if="summary.channel.detail" class="mt-1.5 text-[10px] text-slate-500 dark:text-slate-400 truncate">
          {{ summary.channel.detail }}
        </div>
      </div>

      <!-- 4. 交易计划 -->
      <div
        v-if="summary.trade_plan"
        class="p-3 rounded-lg border transition-all"
        :class="
          summary.trade_plan.passed_gates
            ? 'bg-emerald-50/40 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800/50'
            : 'bg-slate-50/80 dark:bg-slate-900/60 border-slate-200/80 dark:border-slate-700/60'
        "
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span
              class="px-2 py-0.5 rounded-md text-xs font-bold"
              :class="
                summary.trade_plan.direction.includes('做多')
                  ? 'bg-emerald-500 text-white shadow-sm'
                  : summary.trade_plan.direction.includes('做空')
                  ? 'bg-rose-500 text-white shadow-sm'
                  : 'bg-slate-300 dark:bg-slate-700 text-slate-700 dark:text-slate-300'
              "
            >
              {{ summary.trade_plan.direction }}
            </span>
          </div>

          <div class="flex items-center gap-2">
            <span
              class="font-mono font-bold text-xs tabular-nums px-1.5 py-0.5 rounded"
              :class="summary.trade_plan.rr_ratio >= 2.5 ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'"
            >
              {{ summary.trade_plan.rr_ratio }}R
            </span>
          </div>
        </div>

        <!-- 价格点位网格 (2x2 Grid) -->
        <div v-if="summary.trade_plan.entry" class="grid grid-cols-2 gap-1.5 mt-2.5 pt-2.5 border-t border-slate-200/60 dark:border-slate-700/60 font-mono text-xs">
          <div class="bg-white dark:bg-[#141e33] p-2 rounded-lg border border-slate-100 dark:border-white/5">
            <div class="text-slate-400 dark:text-slate-500 text-[10px] font-sans">入场</div>
            <div class="font-bold text-indigo-600 dark:text-indigo-400 mt-0.5 tabular-nums">${{ summary.trade_plan.entry }}</div>
          </div>
          <div class="bg-white dark:bg-[#141e33] p-2 rounded-lg border border-slate-100 dark:border-white/5">
            <div class="text-slate-400 dark:text-slate-500 text-[10px] font-sans">止损</div>
            <div class="font-bold text-rose-600 dark:text-rose-400 mt-0.5 tabular-nums">${{ summary.trade_plan.stop_loss }}</div>
          </div>
          <div class="bg-white dark:bg-[#141e33] p-2 rounded-lg border border-slate-100 dark:border-white/5">
            <div class="text-slate-400 dark:text-slate-500 text-[10px] font-sans">目标 1 (2.5R)</div>
            <div class="font-bold text-emerald-600 dark:text-emerald-400 mt-0.5 tabular-nums">${{ summary.trade_plan.tp1 }}</div>
          </div>
          <div class="bg-white dark:bg-[#141e33] p-2 rounded-lg border border-slate-100 dark:border-white/5">
            <div class="text-slate-400 dark:text-slate-500 text-[10px] font-sans">目标 2 (3.5R)</div>
            <div class="font-bold text-emerald-600 dark:text-emerald-400 mt-0.5 tabular-nums">${{ summary.trade_plan.tp2 || '—' }}</div>
          </div>
        </div>
      </div>

      <!-- 4b. 独立高保真交互式波浪与通道 HTML 页面入口 -->
      <a
        :href="summary.html_url || (`/api/strategy/html?symbol=${symbol}&period=${period}`)"
        target="_blank"
        class="btn-tactile w-full py-2 px-3 rounded-xl border border-indigo-200 dark:border-indigo-800/60 bg-indigo-50/70 hover:bg-indigo-100/90 dark:bg-indigo-950/40 dark:hover:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-2xs group cursor-pointer"
        title="在独立窗口中打开 Investment_Assistant 交互式波浪与通道 HTML 页面"
      >
        <svg class="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400 group-hover:scale-110 transition-transform" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
        </svg>
        <span>在独立网页查看波浪与通道分析 HTML</span>
      </a>
    </div>

    <!-- 空状态 -->
    <div v-else class="py-6 text-center text-slate-400 dark:text-slate-500 text-xs border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
      <div class="font-medium text-slate-500 dark:text-slate-400 mb-2">暂无完整策略矩阵分析</div>
      <button
        @click="handleRun"
        :disabled="loading"
        class="btn-tactile bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-600 dark:text-indigo-400 font-semibold px-3 py-1.5 rounded-lg text-xs transition-colors cursor-pointer"
      >
        运行价格行为策略
      </button>
    </div>

    <!-- 5. 关键支撑/阻力位 (SR Levels) -->
    <div class="pt-3.5 border-t border-slate-100 dark:border-slate-800">
      <div class="flex items-center justify-between mb-2.5">
        <h4 class="text-[11px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <svg class="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z" />
          </svg>
          关键支撑与阻力位 (SR Levels)
        </h4>
        <span v-if="srLevels && srLevels.length" class="text-[10px] text-slate-400 font-mono">{{ srLevels.length }} 个关键位</span>
      </div>

      <div v-if="!srLevels || !srLevels.length"
        class="text-xs text-slate-400 dark:text-slate-500 bg-slate-50 dark:bg-slate-900/60 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl p-4 text-center italic">
        暂无提取到的关键位，可在上方点击「执行分析」
      </div>

      <div v-else class="space-y-2">
        <transition-group name="list">
          <div v-for="(level, idx) in srLevels" :key="idx"
            class="relative overflow-hidden rounded-xl border transition-all hover:shadow-sm cursor-pointer group"
            :class="[
              level.type === 'support' 
                ? 'border-emerald-500/20 bg-emerald-50/30 dark:bg-emerald-950/20' 
                : 'border-rose-500/20 bg-rose-50/30 dark:bg-rose-950/20',
              highlightedSR === idx ? 'ring-2 ring-offset-1 dark:ring-offset-slate-900 ' + (level.type === 'support' ? 'ring-emerald-400' : 'ring-rose-400') : ''
            ]"
            :style="{ animationDelay: idx * 60 + 'ms' }"
            @mouseenter="emit('highlight-sr', idx, true)"
            @mouseleave="emit('highlight-sr', idx, false)"
            @click="emit('scroll-to-sr', level)">
            <!-- 左侧装饰条 -->
            <div class="absolute left-0 top-0 bottom-0 w-1"
              :class="level.type === 'support' ? 'bg-emerald-500' : 'bg-rose-500'"></div>
            
            <div class="flex items-center justify-between p-2.5 pl-3.5">
              <div class="flex items-center gap-2.5">
                <div class="w-6 h-6 rounded-md flex items-center justify-center font-bold text-white text-[10px]"
                  :class="level.type === 'support' ? 'bg-emerald-500' : 'bg-rose-500'">
                  {{ level.type === 'support' ? '支' : '阻' }}
                </div>
                <div>
                  <span class="text-xs font-semibold text-slate-800 dark:text-slate-200 block">
                    {{ level.type === 'support' ? '支撑位' : '阻力位' }}
                  </span>
                  <!-- 星级评分 -->
                  <div class="flex items-center gap-0.5 mt-0.5">
                    <svg v-for="s in level.stars" :key="s" class="w-2.5 h-2.5 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
                    </svg>
                  </div>
                </div>
              </div>
              
              <div class="text-right">
                <span class="text-sm font-bold font-mono tabular-nums text-slate-900 dark:text-slate-100 block">${{ level.price.toFixed(2) }}</span>
                <!-- 强度进度条 -->
                <div class="flex items-center gap-1.5 mt-1">
                  <div class="w-12 h-1 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                    <div class="h-full rounded-full transition-all duration-500"
                      :class="level.type === 'support' ? 'bg-emerald-500' : 'bg-rose-500'"
                      :style="{ width: (level.count / 5 * 100) + '%' }"></div>
                  </div>
                  <span class="text-[9px] text-slate-400 font-mono">{{ level.count }}次</span>
                </div>
              </div>
            </div>
          </div>
        </transition-group>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import type { SRLevel } from '../utils/api';

const props = defineProps<{
  symbol: string;
  period: string;
  summary?: any;
  loading?: boolean;
  srLevels?: SRLevel[];
  highlightedSR?: number | null;
}>();

const emit = defineEmits<{
  (e: 'run', mode: string): void;
  (e: 'clear'): void;
  (e: 'highlight-sr', idx: number, isHover: boolean): void;
  (e: 'scroll-to-sr', level: SRLevel): void;
}>();

const currentMode = ref('swing');

function handleRun() {
  emit('run', currentMode.value);
}
</script>
