<template>
  <div class="relative w-full">
    <!-- 搜索输入（系统统一入口：常驻头部 + Ctrl/⌘K 唤起） -->
    <div
      class="flex items-center bg-slate-50 dark:bg-slate-700/60 border border-slate-200/60 dark:border-slate-600/60 rounded-lg pl-2.5 pr-3 py-1.5 focus-within:border-teal-400 focus-within:ring-1 focus-within:ring-teal-400/20 transition-all cursor-text"
      @click="focusInput"
    >
      <svg class="w-3.5 h-3.5 text-slate-400 shrink-0 mr-1.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
         <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
      <input
        ref="inputRef"
        v-model="query"
        type="text"
        @input="onInput"
        @focus="openPanel"
        @keydown="onKeydown"
        :placeholder="placeholder"
        class="flex-1 bg-transparent text-sm text-slate-700 dark:text-slate-200 focus:outline-none placeholder-slate-400 dark:placeholder-slate-500 min-w-0"
        autocomplete="off"
        spellcheck="false"
      />
    </div>

    <!-- 结果与历史面板（命令面板式：富信息 + 键盘导航 + 点击进入） -->
    <div
      v-if="open"
      class="absolute top-full left-0 right-0 mt-1 z-[9999] bg-white dark:bg-slate-800 border border-slate-200/60 dark:border-slate-700 rounded-xl shadow-lg overflow-hidden max-h-[22rem] overflow-y-auto select-none"
    >
      <!-- 1. 有输入时的搜索列表 -->
      <template v-if="query.trim()">
        <div v-if="loading" class="px-3 py-6 text-center text-xs text-slate-400">搜索中…</div>
        <div v-else-if="!results.length" class="px-3 py-6 text-center text-xs text-slate-400">
          未找到匹配的证券，换个关键词或试试代码 / 拼音
        </div>
        <div v-else>
          <button
            v-for="(r, i) in results"
            :key="r.symbol"
            @click="choose(r)"
            @mouseenter="active = i"
            class="w-full text-left px-3 py-2 flex items-center gap-2 border-b border-slate-50 dark:border-slate-700/50 last:border-0 transition-colors"
            :class="active === i ? 'bg-teal-50 dark:bg-teal-900/30' : 'hover:bg-slate-50 dark:hover:bg-slate-700/50'"
          >
            <span class="text-[9px] px-1 rounded bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 shrink-0 w-9 text-center leading-4">
              {{ badge(r.symbol) }}
            </span>
            <span class="flex-1 min-w-0">
              <span class="block text-sm text-slate-800 dark:text-slate-100 truncate">{{ r.name }}</span>
              <span class="block text-[10px] text-slate-400 font-mono truncate">{{ formatSymbol(r.symbol) }}</span>
            </span>
            <!-- 爱心收藏按钮（♡/♥） -->
            <span
              @click.stop="toggleFav(r.symbol)"
              :title="isFavored(r.symbol) ? '取消自选' : '加入自选'"
              class="shrink-0 cursor-pointer p-1 text-slate-300 dark:text-slate-500 hover:text-rose-500 dark:hover:text-rose-400 transition-colors"
              :class="isFavored(r.symbol) ? 'text-rose-500 dark:text-rose-400' : ''"
            >
              <svg class="w-4 h-4" :class="isFavored(r.symbol) ? 'fill-rose-500 dark:fill-rose-400' : 'fill-none'" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
              </svg>
            </span>
          </button>
        </div>
      </template>

      <!-- 2. 无输入时的历史与推荐面板 -->
      <template v-else>
        <!-- 最近搜索区域 -->
        <div v-if="recentSearches.length > 0" class="border-b border-slate-100 dark:border-slate-700/50 pb-1">
          <div class="px-3 pt-2.5 pb-1 flex justify-between items-center text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            <span>最近搜索</span>
            <button @click="clearAllRecent" class="text-slate-400 hover:text-rose-500 transition-colors capitalize text-[10px] font-medium">清空</button>
          </div>
          <button
            v-for="(r, idx) in recentSearches"
            :key="'recent-' + r.symbol"
            @click="choose(r)"
            @mouseenter="active = idx"
            class="w-full text-left px-3 py-2 flex items-center gap-2 transition-colors relative group"
            :class="active === idx ? 'bg-teal-50 dark:bg-teal-900/30' : 'hover:bg-slate-50 dark:hover:bg-slate-700/50'"
          >
            <span class="text-[9px] px-1 rounded bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 shrink-0 w-9 text-center leading-4">
              {{ badge(r.symbol) }}
            </span>
            <span class="flex-1 min-w-0">
              <span class="block text-sm text-slate-800 dark:text-slate-100 truncate">{{ r.name }}</span>
              <span class="block text-[10px] text-slate-400 font-mono truncate">{{ formatSymbol(r.symbol) }}</span>
            </span>
            <!-- 爱心收藏按钮 -->
            <span
              @click.stop="toggleFav(r.symbol)"
              :title="isFavored(r.symbol) ? '取消自选' : '加入自选'"
              class="shrink-0 cursor-pointer p-1 text-slate-300 dark:text-slate-500 hover:text-rose-500 dark:hover:text-rose-400 transition-colors"
              :class="isFavored(r.symbol) ? 'text-rose-500 dark:text-rose-400' : ''"
            >
              <svg class="w-4 h-4" :class="isFavored(r.symbol) ? 'fill-rose-500 dark:fill-rose-400' : 'fill-none'" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
              </svg>
            </span>
            <!-- 单条删除按钮 -->
            <span
              @click.stop="removeFromRecent(r.symbol)"
              title="删除此条记录"
              class="shrink-0 cursor-pointer p-1 text-slate-300 hover:text-slate-500 dark:text-slate-600 dark:hover:text-slate-400 transition-colors"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </span>
          </button>
        </div>

        <!-- 热门推荐区域 -->
        <div v-if="defaultRecommend.length > 0" class="pt-1.5">
          <div class="px-3 py-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            热门股票推荐
          </div>
          <button
            v-for="(r, idx) in defaultRecommend"
            :key="'rec-' + r.symbol"
            @click="choose(r)"
            @mouseenter="active = recentSearches.length + idx"
            class="w-full text-left px-3 py-2 flex items-center gap-2 transition-colors"
            :class="active === (recentSearches.length + idx) ? 'bg-teal-50 dark:bg-teal-900/30' : 'hover:bg-slate-50 dark:hover:bg-slate-700/50'"
          >
            <span class="text-[9px] px-1 rounded bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 shrink-0 w-9 text-center leading-4">
              {{ badge(r.symbol) }}
            </span>
            <span class="flex-1 min-w-0">
              <span class="block text-sm text-slate-800 dark:text-slate-100 truncate">{{ r.name }}</span>
              <span class="block text-[10px] text-slate-400 font-mono truncate">{{ formatSymbol(r.symbol) }}</span>
            </span>
            <!-- 爱心收藏按钮 -->
            <span
              @click.stop="toggleFav(r.symbol)"
              :title="isFavored(r.symbol) ? '取消自选' : '加入自选'"
              class="shrink-0 cursor-pointer p-1 text-slate-300 dark:text-slate-500 hover:text-rose-500 dark:hover:text-rose-400 transition-colors"
              :class="isFavored(r.symbol) ? 'text-rose-500 dark:text-rose-400' : ''"
            >
              <svg class="w-4 h-4" :class="isFavored(r.symbol) ? 'fill-rose-500 dark:fill-rose-400' : 'fill-none'" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
              </svg>
            </span>
          </button>
        </div>

        <div v-if="recentSearches.length === 0 && defaultRecommend.length === 0" class="px-3 py-6 text-center text-xs text-slate-400">
          暂无搜索记录与热门推荐
        </div>
      </template>
    </div>

    <!-- 点击空白关闭面板 -->
    <div v-if="open" class="fixed inset-0 z-40" @click="close" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue';
import { searchStocks, type StockInfo, MARKET_LABEL, marketOf, formatSymbol } from '../utils/api';

const props = withDefaults(defineProps<{
  watchlist?: string[]; // 已自选的股票列表，由父组件传入
  placeholder?: string;
}>(), {
  watchlist: () => [],
  placeholder: '搜索股票'
});

const emit = defineEmits<{
  select: [symbol: string];
  'add-watch': [symbol: string];
}>();

const query = ref('');
const results = ref<StockInfo[]>([]);
const loading = ref(false);
const open = ref(false);
const active = ref(0);
const inputRef = ref<HTMLInputElement | null>(null);

// 最近搜索与热门股票推荐列表
const recentSearches = ref<StockInfo[]>([]);
const defaultRecommend = ref<StockInfo[]>([]);

let timer: ReturnType<typeof setTimeout> | null = null;



// 将键盘导航列表扁平化，能无缝支持无输入时的【最近搜索】+【热门推荐】键盘光标移动
const displayList = computed<StockInfo[]>(() => {
  if (query.value.trim()) {
    return results.value;
  }
  return [...recentSearches.value, ...defaultRecommend.value];
});

function openPanel() {
  open.value = true;
  active.value = 0;
}

function focusInput() {
  inputRef.value?.focus();
}

function onInput() {
  open.value = true;
  loading.value = true;
  active.value = 0; // 重置光标位置
  if (timer) clearTimeout(timer);
  timer = setTimeout(async () => {
    const kw = query.value.trim();
    if (!kw) {
      results.value = [];
      loading.value = false;
      return;
    }
    try {
      results.value = await searchStocks(kw);
      active.value = 0;
    } catch {
      results.value = [];
    } finally {
      loading.value = false;
    }
  }, 200);
}

function choose(r: StockInfo) {
  emit('select', r.symbol);
  addToRecent(r);
  query.value = '';
  results.value = [];
  open.value = false;
}

function close() {
  open.value = false;
}

// ================== 最近搜索历史记录维护 ==================
function addToRecent(r: StockInfo) {
  const idx = recentSearches.value.findIndex(item => item.symbol.toUpperCase() === r.symbol.toUpperCase());
  if (idx > -1) {
    recentSearches.value.splice(idx, 1);
  }
  // 插入到最近搜索的最前面
  recentSearches.value.unshift(r);
  if (recentSearches.value.length > 8) {
    recentSearches.value = recentSearches.value.slice(0, 8);
  }
  localStorage.setItem('recent_searches', JSON.stringify(recentSearches.value));
}

function removeFromRecent(symbol: string) {
  recentSearches.value = recentSearches.value.filter(
    item => item.symbol.toUpperCase() !== symbol.toUpperCase()
  );
  localStorage.setItem('recent_searches', JSON.stringify(recentSearches.value));
  // 删除当前项时，重置高亮索引，防止越界
  active.value = 0;
}

function clearAllRecent() {
  recentSearches.value = [];
  localStorage.removeItem('recent_searches');
  active.value = 0;
}

// ================== 自选收藏状态与爱心操作 ==================
function isFavored(symbol: string): boolean {
  if (!symbol) return false;
  const target = symbol.toUpperCase();
  return props.watchlist.some(s => s.toUpperCase() === target);
}

// 触发自选 (爱心按钮)
function toggleFav(symbol: string) {
  emit('add-watch', symbol);
}

// 加载默认推荐数据
async function fetchDefaultRecommend() {
  try {
    const list = await searchStocks('');
    // 从后端拿到的 STOCKS_POOL 中，我们只取前 6 只展示为热门推荐
    defaultRecommend.value = list.slice(0, 6);
  } catch (err) {
    console.warn('Failed to load default stock recommendations:', err);
  }
}

// 键盘导航
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    if (displayList.value.length) {
      active.value = Math.min(active.value + 1, displayList.value.length - 1);
    }
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    if (displayList.value.length) {
      active.value = Math.max(active.value - 1, 0);
    }
  } else if (e.key === 'Enter') {
    if (displayList.value[active.value]) {
      choose(displayList.value[active.value]);
    }
  } else if (e.key === 'Escape') {
    close();
  }
}

// 全局快捷键：Ctrl/⌘ + K 唤起全局证券搜索
function onGlobalKey(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    open.value = true;
    nextTick(() => inputRef.value?.focus());
  }
}

function badge(symbol: string): string {
  return MARKET_LABEL[marketOf(symbol) || 'us'] || '';
}

onMounted(() => {
  // 加载搜索历史
  const saved = localStorage.getItem('recent_searches');
  if (saved) {
    try {
      recentSearches.value = JSON.parse(saved);
    } catch {
      recentSearches.value = [];
    }
  }
  // 加载热门推荐股票
  fetchDefaultRecommend();

  document.addEventListener('keydown', onGlobalKey);
});

onUnmounted(() => {
  document.removeEventListener('keydown', onGlobalKey);
});
</script>
