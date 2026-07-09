<script setup lang="ts">
import { ref, computed } from 'vue';

const props = withDefaults(
  defineProps<{
    modelStart: string;
    modelEnd: string;
    minDate: string;
    maxDate: string;
    startLabel?: string;
    endLabel?: string;
  }>(),
  {
    startLabel: '起始日期',
    endLabel: '结束日期',
  }
);

const emit = defineEmits<{
  'update:modelStart': [value: string];
  'update:modelEnd': [value: string];
}>();

const open = ref(false);
const activeField = ref<'start' | 'end'>('start');

const viewYear = ref(0);
const viewMonth = ref(0); // 0-11

const weekdayLabels = ['日', '一', '二', '三', '四', '五', '六'];
const monthLabels = [
  '1月', '2月', '3月', '4月', '5月', '6月',
  '7月', '8月', '9月', '10月', '11月', '12月',
];

function parseYMD(s: string): Date {
  return new Date(s + 'T00:00:00');
}

function openPicker(field: 'start' | 'end') {
  activeField.value = field;
  const base = field === 'start' ? props.modelStart : props.modelEnd;
  const d = base ? parseYMD(base) : parseYMD(props.maxDate || new Date().toISOString().slice(0, 10));
  viewYear.value = d.getFullYear();
  viewMonth.value = d.getMonth();
  open.value = true;
}

function close() {
  open.value = false;
}

const years = computed<number[]>(() => {
  const minY = props.minDate ? parseYMD(props.minDate).getFullYear() : 2000;
  const maxY = props.maxDate ? parseYMD(props.maxDate).getFullYear() : new Date().getFullYear();
  const arr: number[] = [];
  for (let y = maxY; y >= minY; y--) arr.push(y);
  return arr;
});

function onYearChange(e: Event) {
  viewYear.value = parseInt((e.target as HTMLSelectElement).value, 10);
}
function onMonthChange(e: Event) {
  viewMonth.value = parseInt((e.target as HTMLSelectElement).value, 10);
}
function prevMonth() {
  if (viewMonth.value === 0) {
    viewMonth.value = 11;
    viewYear.value--;
  } else {
    viewMonth.value--;
  }
}
function nextMonth() {
  if (viewMonth.value === 11) {
    viewMonth.value = 0;
    viewYear.value++;
  } else {
    viewMonth.value++;
  }
}

const calendar = computed<(null | { day: number; dateStr: string; disabled: boolean; inRange: boolean; isEdge: boolean })[]>(() => {
  const y = viewYear.value;
  const m = viewMonth.value;
  const first = new Date(y, m, 1);
  const startWeekday = first.getDay();
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  const cells: (null | { day: number; dateStr: string; disabled: boolean; inRange: boolean; isEdge: boolean })[] = [];
  for (let i = 0; i < startWeekday; i++) cells.push(null);

  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const disabled = !!(
      (props.minDate && dateStr < props.minDate) || (props.maxDate && dateStr > props.maxDate)
    );
    const inRange =
      !!props.modelStart && !!props.modelEnd && dateStr > props.modelStart && dateStr < props.modelEnd;
    const isEdge = dateStr === props.modelStart || dateStr === props.modelEnd;
    cells.push({ day: d, dateStr, disabled, inRange, isEdge });
  }
  return cells;
});

function selectDate(cell: { day: number; dateStr: string; disabled: boolean }) {
  if (cell.disabled) return;
  if (activeField.value === 'start') {
    emit('update:modelStart', cell.dateStr);
    if (props.modelEnd && cell.dateStr > props.modelEnd) emit('update:modelEnd', cell.dateStr);
    // 选完起始后自动切到结束字段，方便连续选择
    activeField.value = 'end';
  } else {
    emit('update:modelEnd', cell.dateStr);
    if (props.modelStart && cell.dateStr < props.modelStart) emit('update:modelStart', cell.dateStr);
    close();
  }
}

function clearActive() {
  if (activeField.value === 'start') emit('update:modelStart', '');
  else emit('update:modelEnd', '');
}
</script>

<template>
  <div class="relative">
    <!-- 双字段触发按钮 -->
    <div class="grid grid-cols-2 gap-2">
      <button
        type="button"
        @click="openPicker('start')"
        :class="[
          'w-full text-left bg-slate-50 dark:bg-slate-700 border rounded-lg px-2.5 py-2 text-xs font-semibold transition-all focus:outline-none',
          activeField === 'start' && open
            ? 'border-teal-500 ring-2 ring-teal-500/20 text-teal-700 dark:text-teal-300'
            : 'border-slate-200 dark:border-slate-600 text-slate-700 dark:text-slate-200 hover:border-slate-300 dark:hover:border-slate-500',
        ]"
      >
        <span class="block text-[9px] font-bold text-slate-400 uppercase mb-0.5">{{ startLabel }}</span>
        <span class="font-mono">{{ modelStart || '——' }}</span>
      </button>
      <button
        type="button"
        @click="openPicker('end')"
        :class="[
          'w-full text-left bg-slate-50 dark:bg-slate-700 border rounded-lg px-2.5 py-2 text-xs font-semibold transition-all focus:outline-none',
          activeField === 'end' && open
            ? 'border-teal-500 ring-2 ring-teal-500/20 text-teal-700 dark:text-teal-300'
            : 'border-slate-200 dark:border-slate-600 text-slate-700 dark:text-slate-200 hover:border-slate-300 dark:hover:border-slate-500',
        ]"
      >
        <span class="block text-[9px] font-bold text-slate-400 uppercase mb-0.5">{{ endLabel }}</span>
        <span class="font-mono">{{ modelEnd || '——' }}</span>
      </button>
    </div>

    <!-- 弹层日历 -->
    <Teleport to="body">
      <Transition name="fade-scale">
        <div
          v-if="open"
          class="fixed inset-0 z-50 flex items-center justify-center"
          @click.self="close"
        >
          <!-- 点击空白关闭的透明遮罩 -->
          <div class="absolute inset-0 bg-slate-900/30 backdrop-blur-[1px]"></div>

          <div
            class="relative w-[300px] bg-white dark:bg-slate-800 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-700 p-4"
            @click.stop
          >
            <!-- 头部：年月快速跳转 -->
            <div class="flex items-center justify-between mb-3">
              <button
                type="button"
                @click="prevMonth"
                class="w-8 h-8 grid place-items-center rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
              >
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
                </svg>
              </button>

              <div class="flex items-center gap-1.5">
                <select
                  :value="viewYear"
                  @change="onYearChange"
                  class="bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-100 text-xs font-bold rounded-md px-1.5 py-1 focus:outline-none cursor-pointer"
                >
                  <option v-for="y in years" :key="y" :value="y">{{ y }}年</option>
                </select>
                <select
                  :value="viewMonth"
                  @change="onMonthChange"
                  class="bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-100 text-xs font-bold rounded-md px-1.5 py-1 focus:outline-none cursor-pointer"
                >
                  <option v-for="(ml, i) in monthLabels" :key="i" :value="i">{{ ml }}</option>
                </select>
              </div>

              <button
                type="button"
                @click="nextMonth"
                class="w-8 h-8 grid place-items-center rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
              >
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>

            <!-- 星期表头 -->
            <div class="grid grid-cols-7 gap-1 mb-1">
              <div
                v-for="w in weekdayLabels"
                :key="w"
                class="text-center text-[10px] font-bold text-slate-400 py-1"
              >
                {{ w }}
              </div>
            </div>

            <!-- 日期网格 -->
            <div class="grid grid-cols-7 gap-1">
              <template v-for="(cell, idx) in calendar" :key="idx">
                <div v-if="cell === null"></div>
                <button
                  v-else
                  type="button"
                  :disabled="cell.disabled"
                  @click="selectDate(cell)"
                  :class="[
                    'h-8 rounded-lg text-xs font-semibold transition-all duration-150',
                    cell.disabled
                      ? 'text-slate-300 dark:text-slate-600 cursor-not-allowed'
                      : cell.isEdge
                      ? 'bg-teal-500 text-white shadow-sm hover:bg-teal-600'
                      : cell.inRange
                      ? 'bg-teal-100 dark:bg-teal-900/40 text-teal-700 dark:text-teal-300 hover:bg-teal-200 dark:hover:bg-teal-900/60'
                      : 'text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700',
                  ]"
                >
                  {{ cell.day }}
                </button>
              </template>
            </div>

            <!-- 底部操作 -->
            <div class="flex items-center justify-between mt-3 pt-3 border-t border-slate-100 dark:border-slate-700">
              <span class="text-[10px] text-slate-400">
                正在选择：<b :class="activeField === 'start' ? 'text-teal-600' : ''">{{ activeField === 'start' ? startLabel : endLabel }}</b>
              </span>
              <div class="flex items-center gap-2">
                <button
                  type="button"
                  @click="clearActive"
                  class="text-[11px] text-slate-400 hover:text-rose-500 transition-colors"
                >
                  清空
                </button>
                <button
                  type="button"
                  @click="close"
                  class="text-[11px] font-semibold text-white bg-teal-500 hover:bg-teal-600 rounded-lg px-3 py-1 transition-colors"
                >
                  完成
                </button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
