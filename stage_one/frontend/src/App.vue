<template>
  <div
    class="flex flex-col flex-1 h-screen overflow-hidden bg-[#f8fafc] text-slate-800 subpixel-antialiased font-sans select-none">

    <!-- 头部导航栏 (明亮白 + 细微底边框) -->
    <header
      class="bg-white border-b border-slate-200/80 px-6 py-4 flex flex-col sm:flex-row items-center justify-between gap-4 shrink-0 shadow-sm z-10 animate-fade-in-down">
      <div class="flex items-center gap-3">
        <div
          class="bg-teal-600 p-2.5 rounded-xl shadow-md shadow-teal-100 shrink-0 transition-transform hover:scale-105 active:scale-95 cursor-pointer">
          <!-- 波动折线图标 -->
          <svg class="w-6 h-6 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
            stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
        </div>
        <div>
          <h1 class="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            智能股票技术分析平台
            <span
              class="text-[10px] bg-teal-50 text-teal-700 px-1.5 py-0.5 rounded border border-teal-200 font-semibold uppercase transition-all hover:bg-teal-100">MVP</span>
          </h1>
          <p class="text-xs text-slate-400">Vue 3 驱动 · 轻量化极简白主题</p>
        </div>
      </div>

      <!-- 搜索控件 -->
      <div class="flex items-center gap-3 w-full sm:w-auto">
        <div class="relative flex-1 sm:flex-initial">
          <span class="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 transition-colors"
            :class="{ 'text-teal-500': isFocused }">
            <svg class="w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
              stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </span>
          <input type="text" v-model="symbolInput" @keydown.enter="handleSearch" @focus="isFocused = true"
            @blur="handleBlur" @input="handleSearchInput" placeholder="输入美股代码 (如 AAPL, NVDA, TSLA)"
            class="w-full sm:w-64 bg-slate-50 border border-slate-200 text-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 focus:bg-white transition-all placeholder-slate-400 font-medium"
            autocomplete="off" />

          <!-- 搜索建议下拉 -->
          <transition name="dropdown">
            <div v-if="showSuggestions && suggestions.length > 0"
              class="absolute top-full left-0 right-0 mt-2 bg-white border border-slate-200 rounded-xl shadow-xl overflow-hidden z-50 animate-fade-in-down">
              <div v-for="(item, idx) in suggestions" :key="item.symbol" @click="selectSuggestion(item.symbol)"
                class="px-4 py-2.5 hover:bg-teal-50 cursor-pointer transition-colors flex items-center justify-between border-b border-slate-50 last:border-0"
                :style="{ animationDelay: idx * 50 + 'ms' }">
                <div class="flex items-center gap-3">
                  <span class="font-bold text-slate-800 text-sm">{{ item.symbol }}</span>
                  <span class="text-xs text-slate-400">{{ item.name }}</span>
                </div>
                <svg class="w-4 h-4 text-slate-300" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
                  stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </div>
            </div>
          </transition>
        </div>
        <button @click="createRipple($event); handleSearch()" :disabled="isLoading"
          class="ripple-container bg-teal-600 hover:bg-teal-500 text-white px-5 py-2.5 rounded-xl text-sm font-semibold shadow-lg shadow-teal-600/10 hover:shadow-teal-600/20 hover:shadow-xl active:scale-[0.97] transition-all disabled:opacity-50 disabled:pointer-events-none shrink-0 cursor-pointer relative overflow-hidden">
          <span v-if="isLoading" class="flex items-center gap-2">
            <svg class="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z">
              </path>
            </svg>
            加载中
          </span>
          <span v-else>载入行情</span>
        </button>
      </div>
    </header>

    <!-- 主交互区域 -->
    <main class="flex-1 flex overflow-hidden relative min-h-0 bg-white">

      <!-- 降级/错误提示横幅 -->
      <transition name="fade">
        <div v-if="errorMsg"
          class="absolute top-4 left-1/2 -translate-x-1/2 z-20 bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 rounded-xl text-xs font-medium shadow-md flex items-center gap-2 max-w-md animate-shake">
          <svg class="w-4 h-4 text-amber-600 shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none"
            viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span>{{ errorMsg }}</span>
          <button @click="errorMsg = ''"
            class="ml-auto text-amber-500 hover:text-amber-800 font-bold transition-colors hover:scale-110">&times;</button>
        </div>
      </transition>

      <!-- 左侧：图表容器 (支持拖拽调整宽度) -->
      <div :style="{ width: leftWidth + 'px' }"
        class="flex flex-col min-h-0 h-full min-w-[360px] shrink-0 bg-white transition-colors duration-300 ease-out">
        <!-- 图表上方状态条 -->
        <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between shrink-0">
          <div class="flex items-center gap-3">
            <span class="text-2xl font-bold text-slate-900 tracking-tight transition-all"
              :class="{ 'animate-pulse-slow': isLoading }">{{ currentSymbol || '--' }}</span>
            <!-- 收藏星标按钮 -->
            <button v-if="currentSymbol" @click="toggleWatchlist(currentSymbol)"
              class="p-1.5 rounded-lg hover:bg-slate-100 transition-all group cursor-pointer active:scale-90"
              :title="isWatchlisted(currentSymbol) ? '取消自选' : '加入自选'">
              <svg class="w-6 h-6 transition-all duration-300 group-hover:scale-110" :class="[
                isWatchlisted(currentSymbol) ? 'text-amber-400 fill-amber-400' : 'text-slate-300 hover:text-amber-400 fill-none',
                starBounce ? 'animate-bounce-once' : ''
              ]" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round"
                  d="M11.48 3.499c.174-.383.72-.383.894 0l2.64 5.352 5.9 1.15c.422.082.59.59.282.895l-4.244 4.14 1.002 5.86c.071.423-.372.746-.75.545l-5.267-2.77-5.268 2.77c-.378.201-.821-.122-.75-.545l1.002-5.86-4.244-4.14c-.308-.305-.14-.813.282-.895l5.9-1.15 2.64-5.352z" />
              </svg>
            </button>
            <span
              class="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full font-medium transition-all hover:bg-slate-200">日线
              · K线图 (Daily)</span>
          </div>
          <div class="text-xs text-slate-400 italic">
            提示: 拖拽/滚轮可平滑缩放和查看历史
          </div>
        </div>

        <!-- 实际图表绑定节点 -->
        <div ref="chartArea" class="flex-1 relative bg-white">
          <div ref="chartContainer" class="absolute inset-0 w-full h-full transition-opacity duration-300"
            :class="{ 'opacity-50': isLoading }"></div>

          <!-- 自定义K线悬停提示框 -->
          <div v-show="tooltipVisible" ref="tooltipEl"
            class="absolute z-40 pointer-events-none bg-white/95 backdrop-blur-sm border border-slate-200 rounded-xl shadow-xl py-3 px-4 text-xs font-mono animate-tooltip-in"
            :style="tooltipStyle">
            <!-- 日期 -->
            <div class="text-slate-400 mb-2 pb-2 border-b border-slate-100 font-sans text-[11px] font-semibold">
              {{ tooltipData.date }}
            </div>
            <!-- OHLC 数据 -->
            <div class="space-y-1">
              <div class="flex justify-between gap-4">
                <span class="text-slate-400">开盘</span>
                <span class="text-slate-800 font-semibold">{{ tooltipData.open }}</span>
              </div>
              <div class="flex justify-between gap-4">
                <span class="text-slate-400">最高</span>
                <span class="text-rose-600 font-semibold">{{ tooltipData.high }}</span>
              </div>
              <div class="flex justify-between gap-4">
                <span class="text-slate-400">最低</span>
                <span class="text-teal-600 font-semibold">{{ tooltipData.low }}</span>
              </div>
              <div class="flex justify-between gap-4">
                <span class="text-slate-400">收盘</span>
                <span class="font-semibold" :class="tooltipData.change >= 0 ? 'text-rose-600' : 'text-teal-600'">
                  {{ tooltipData.close }}
                </span>
              </div>
            </div>
            <!-- 分隔 -->
            <div class="my-2 border-t border-slate-100"></div>
            <!-- 涨跌 & 振幅 -->
            <div class="space-y-1">
              <div class="flex justify-between gap-4 items-center">
                <span class="text-slate-400">涨跌幅</span>
                <span class="font-semibold text-xs px-1.5 py-0.5 rounded"
                  :class="tooltipData.change >= 0 ? 'bg-rose-50 text-rose-600' : 'bg-teal-50 text-teal-600'">
                  {{ tooltipData.changeStr }}
                </span>
              </div>
              <div class="flex justify-between gap-4 items-center">
                <span class="text-slate-400">振幅</span>
                <span class="font-semibold text-slate-700">{{ tooltipData.amplitude }}%</span>
              </div>
              <div class="flex justify-between gap-4 items-center">
                <span class="text-slate-400">成交量</span>
                <span class="font-semibold text-slate-700">{{ tooltipData.volumeStr }}</span>
              </div>
            </div>
          </div>

          <!-- 骨架屏加载状态 -->
          <div v-if="isLoading && !klineData.length"
            class="absolute inset-0 flex flex-col items-center justify-center bg-slate-50/80 backdrop-blur-sm">
            <div class="w-64 space-y-4">
              <div class="skeleton h-8 w-32 mx-auto rounded-lg"></div>
              <div class="skeleton h-64 w-full rounded-xl"></div>
              <div class="skeleton h-6 w-48 mx-auto rounded-lg"></div>
            </div>
          </div>

          <div v-if="!klineData.length && !isLoading"
            class="absolute inset-0 flex items-center justify-center bg-slate-50/50">
            <div class="text-center animate-fade-in">
              <svg class="w-12 h-12 text-slate-300 mx-auto mb-3" xmlns="http://www.w3.org/2000/svg" fill="none"
                viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
              <span class="text-slate-400 text-xs font-semibold">请在上方搜索美股代码载入行情</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 比例调节拖拽条 -->
      <div @mousedown="startResize"
        class="w-1 bg-slate-100 hover:bg-teal-500 active:bg-teal-600 cursor-col-resize transition-colors shrink-0 z-20 group relative">
        <div class="absolute inset-y-0 -left-1 -right-1"></div>
      </div>

      <!-- 右侧：分析与设置面板 -->
      <div
        class="flex-1 bg-white border-l border-slate-200/80 flex flex-col shrink-0 overflow-y-auto scrollbar-thin min-w-[280px]">

        <!-- 1. 新增的自选股管理区域 -->
        <div class="p-6 border-b border-slate-100 bg-slate-50/30 animate-fade-in-up">
          <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center justify-between">
            <span>我的自选股 (Watchlist)</span>
            <span
              class="text-[10px] bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded-full font-semibold transition-all hover:scale-105">{{
                watchlist.length }}</span>
          </h3>

          <!-- 自选列表空状态 -->
          <div v-if="!watchlist.length"
            class="text-xs text-slate-400 bg-white border border-dashed border-slate-200 rounded-xl p-4 text-center transition-all hover:border-teal-300 hover:bg-teal-50/30">
            暂无自选，点击左侧星标收藏
          </div>

          <!-- 自选卡片平铺 -->
          <div v-else class="flex flex-wrap gap-2 max-h-32 overflow-y-auto scrollbar-thin">
            <transition-group name="list">
              <div v-for="item in watchlist" :key="item" @click="selectWatchlist(item)"
                class="group flex items-center gap-1.5 bg-white border rounded-lg px-2.5 py-1.5 transition-all cursor-pointer text-xs font-semibold text-slate-700 hover:border-teal-500 hover:bg-teal-50/20 hover:shadow-md hover:-translate-y-0.5"
                :class="currentSymbol === item ? 'border-teal-500 bg-teal-50/30 text-teal-700 shadow-sm' : 'border-slate-200'">
                <span class="transition-transform group-hover:scale-105">{{ item }}</span>
                <button @click.stop="removeFromWatchlist(item)"
                  class="text-slate-300 hover:text-rose-500 rounded p-0.5 transition-all cursor-pointer hover:bg-rose-50 hover:scale-110"
                  title="从自选移除">
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"></path>
                  </svg>
                </button>
              </div>
            </transition-group>
          </div>
        </div>

        <!-- 2. 智能触发区域 -->
        <div class="p-6 border-b border-slate-100 animate-fade-in-up delay-100">
          <h3 class="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-4 flex items-center gap-2">
            <!-- 靶心图标 -->
            <svg class="w-4 h-4 text-teal-600 transition-transform group-hover:rotate-45"
              xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            形态特征提取
          </h3>
          <button @click="createRipple($event); runAnalysis()" :disabled="!klineData.length"
            class="ripple-container w-full bg-slate-900 hover:bg-slate-800 text-white font-semibold py-3 px-4 rounded-xl text-sm transition-all shadow-md hover:shadow-lg hover:-translate-y-0.5 active:scale-[0.98] disabled:opacity-40 disabled:pointer-events-none flex items-center justify-center gap-2 cursor-pointer relative overflow-hidden">
            <!-- 雷达/分析图标 -->
            <svg class="w-4 h-4 transition-transform group-hover:rotate-180 duration-500"
              xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z" />
            </svg>
            执行智能技术分析
          </button>
        </div>

        <!-- 3. 支撑/阻力位列表 -->
        <div class="p-6 border-b border-slate-100 animate-fade-in-up delay-200">
          <h4 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">
            自动识别支撑/阻力线 (SR Levels)
          </h4>

          <div v-if="!srLevels.length"
            class="text-xs text-slate-400 bg-slate-50 border border-dashed border-slate-200 rounded-xl p-4 text-center italic transition-all hover:border-slate-300">
            请在上方点击 "执行分析" 进行局部极点检测与聚类
          </div>

          <div v-else class="space-y-2.5">
            <transition-group name="list">
              <div v-for="(level, idx) in srLevels" :key="idx"
                class="flex items-center justify-between p-3.5 rounded-xl border border-slate-100 bg-slate-50/50 hover:bg-slate-50 transition-all hover:shadow-md hover:-translate-y-0.5 cursor-default group"
                :style="{ animationDelay: idx * 100 + 'ms' }">
                <div class="flex items-center gap-2.5">
                  <span
                    :class="level.type === 'support' ? 'bg-teal-500 group-hover:scale-125' : 'bg-rose-500 group-hover:scale-125'"
                    class="w-2.5 h-2.5 rounded-full transition-transform duration-300"></span>
                  <span class="text-xs font-semibold text-slate-700">
                    {{ level.type === 'support' ? '支撑位' : '阻力位' }}
                  </span>
                </div>
                <div class="text-right">
                  <span class="text-sm font-bold text-slate-900 number-animate">${{ level.price.toFixed(2) }}</span>
                  <p class="text-[10px] text-slate-400">极值触碰: <span class="font-medium text-slate-600">{{ level.count }}
                      次</span> | 强度: <span :class="level.type === 'support' ? 'text-teal-600' : 'text-rose-600'"
                      class="font-bold">{{ level.level }}</span></p>
                </div>
              </div>
            </transition-group>
          </div>
        </div>

        <!-- 4. 区间极值统计 -->
        <div class="p-6 animate-fade-in-up delay-300">
          <div class="flex items-center justify-between mb-3">
            <h4 class="text-xs font-bold text-slate-400 uppercase tracking-wider">
              区间涨跌统计 (Range Stats)
            </h4>
            <!-- 信息小气泡 -->
            <div class="group relative cursor-help shrink-0">
              <span class="text-slate-400 hover:text-slate-600 transition-colors">
                <svg class="w-4 h-4 transition-transform group-hover:scale-110" xmlns="http://www.w3.org/2000/svg"
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round"
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </span>
              <div
                class="absolute right-0 bottom-6 hidden group-hover:block bg-slate-800 text-white text-[11px] leading-relaxed p-3 rounded-lg shadow-xl border border-slate-700 w-52 z-30 font-medium animate-fade-in-up">
                设定任意时间跨度，自动捕获该范围内的最大连贯上涨波段以及最大连贯下跌波段。
              </div>
            </div>
          </div>

          <!-- 时间选择表单 -->
          <div class="space-y-3 mb-3">
            <div class="group">
              <label
                class="text-[10px] font-bold text-slate-400 uppercase block mb-1 transition-colors group-focus-within:text-teal-500">起始日期</label>
              <input type="date" v-model="inputStartDate"
                class="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-xs font-semibold text-slate-700 focus:outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 transition-all" />
            </div>
            <div class="group">
              <label
                class="text-[10px] font-bold text-slate-400 uppercase block mb-1 transition-colors group-focus-within:text-teal-500">结束日期</label>
              <input type="date" v-model="inputEndDate"
                class="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-xs font-semibold text-slate-700 focus:outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 transition-all" />
            </div>
          </div>

          <!-- 重新计算按钮 -->
          <button @click="createRipple($event); handleReCalculate()" :disabled="!klineData.length"
            class="ripple-container w-full border border-slate-200 hover:bg-slate-50 text-slate-700 font-semibold py-2 px-4 rounded-xl text-xs transition-all active:scale-[0.98] disabled:opacity-40 disabled:pointer-events-none flex items-center justify-center gap-1.5 cursor-pointer mb-5 hover:border-slate-300 hover:shadow-sm relative overflow-hidden">
            <svg class="w-3.5 h-3.5 text-slate-500 transition-transform hover:rotate-180 duration-500"
              xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3-3 3 3m-3-3v12" />
            </svg>
            重新计算 (Re-calculate)
          </button>

          <!-- 统计数据输出面板 -->
          <div v-if="!rangeStats"
            class="text-xs text-slate-400 bg-slate-50 border border-dashed border-slate-200 rounded-xl p-4 text-center italic transition-all hover:border-slate-300">
            请在上方指定日期后执行智能分析
          </div>

          <div v-else class="space-y-3">
            <!-- 上涨 -->
            <div
              class="bg-teal-50/50 border border-teal-100 rounded-xl p-3.5 transition-all hover:shadow-md hover:-translate-y-0.5 hover:border-teal-200 group">
              <div class="flex items-center gap-1.5 text-teal-700 font-bold text-xs mb-1">
                <svg class="w-4 h-4 transition-transform group-hover:-translate-y-1" xmlns="http://www.w3.org/2000/svg"
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
                <span>最大连贯上涨</span>
              </div>
              <div class="text-lg font-extrabold text-teal-600 font-mono number-animate">
                +{{ animatedRisePct.toFixed(2) }}%
              </div>
              <div class="text-[10px] text-slate-400 mt-1 font-medium font-mono">
                {{ rangeStats.max_rise.start }} &rarr; {{ rangeStats.max_rise.end }}
              </div>
            </div>

            <!-- 下跌 -->
            <div
              class="bg-rose-50/50 border border-rose-100 rounded-xl p-3.5 transition-all hover:shadow-md hover:-translate-y-0.5 hover:border-rose-200 group">
              <div class="flex items-center gap-1.5 text-rose-700 font-bold text-xs mb-1">
                <svg class="w-4 h-4 transition-transform group-hover:translate-y-1" xmlns="http://www.w3.org/2000/svg"
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M13 17h8m0 0v-8m0 8l-8-8-4 4-6-6" />
                </svg>
                <span>最大连贯下跌</span>
              </div>
              <div class="text-lg font-extrabold text-rose-600 font-mono number-animate">
                {{ animatedFallPct.toFixed(2) }}%
              </div>
              <div class="text-[10px] text-slate-400 mt-1 font-medium font-mono">
                {{ rangeStats.max_fall.start }} &rarr; {{ rangeStats.max_fall.end }}
              </div>
            </div>
          </div>
        </div>

      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue';
import { createChart, CandlestickSeries, HistogramSeries, createSeriesMarkers } from 'lightweight-charts';
import type { IChartApi } from 'lightweight-charts';
import { getKLines, getStockAnalysis, searchStocks } from './utils/api';
import type { KLinePoint, SRLevel, StockInfo } from './utils/api';
import { getChartOptions } from './utils/chartUtils';

const symbolInput = ref('AAPL');
const currentSymbol = ref('');
const klineData = ref<KLinePoint[]>([]);
const isLoading = ref(false);
const errorMsg = ref('');
const isFocused = ref(false);
const showSuggestions = ref(false);
const suggestions = ref<StockInfo[]>([]);
const starBounce = ref(false);

// 自选股列表 (存纯大写代码，如 AAPL, TSLA)
const watchlist = ref<string[]>([]);

// 分析数据状态
const srLevels = ref<SRLevel[]>([]);
const startDate = ref('');
const endDate = ref('');
const inputStartDate = ref('');
const inputEndDate = ref('');
const rangeStats = ref<any>(null);

// 数字动画状态
const animatedRisePct = ref(0);
const animatedFallPct = ref(0);

// 左右拖拽初始列宽
const leftWidth = ref(800);

// lightweight-charts 绘图实例引用
const chartContainer = ref<HTMLElement | null>(null);
const chartArea = ref<HTMLElement | null>(null);
const tooltipEl = ref<HTMLElement | null>(null);
let chartInstance: IChartApi | null = null;
let candlestickSeries: any = null;
let volumeSeries: any = null;
let priceLines: any[] = [];
let markersPlugin: any = null;

// ================== K线悬停提示框状态 ==================
const tooltipVisible = ref(false);
const tooltipSide = ref<'left' | 'right'>('right');
const tooltipStyle = ref<Record<string, string>>({});
const tooltipData = ref({
  date: '',
  open: '',
  high: '',
  low: '',
  close: '',
  change: 0,
  changeStr: '',
  amplitude: 0,
  volumeStr: '',
});

// 搜索防抖定时器
let searchDebounceTimer: any = null;
let resizeRaf: number | null = null;

// ================== 涟漪效果 ==================
const createRipple = (event: MouseEvent) => {
  const button = event.currentTarget as HTMLElement;
  const ripple = document.createElement('span');
  const rect = button.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height);
  const x = event.clientX - rect.left - size / 2;
  const y = event.clientY - rect.top - size / 2;

  ripple.style.width = ripple.style.height = size + 'px';
  ripple.style.left = x + 'px';
  ripple.style.top = y + 'px';
  ripple.className = 'ripple-effect';

  button.appendChild(ripple);

  setTimeout(() => {
    ripple.remove();
  }, 600);
};

// ================== 数字滚动动画 ==================
const animateNumber = (target: number, isRise: boolean) => {
  const duration = 800;
  const startTime = performance.now();
  const startValue = isRise ? animatedRisePct.value : animatedFallPct.value;
  const diff = target - startValue;

  const animate = (currentTime: number) => {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);

    // 缓动函数 - easeOutCubic
    const easeProgress = 1 - Math.pow(1 - progress, 3);
    const currentValue = startValue + diff * easeProgress;

    if (isRise) {
      animatedRisePct.value = currentValue;
    } else {
      animatedFallPct.value = currentValue;
    }

    if (progress < 1) {
      requestAnimationFrame(animate);
    }
  };

  requestAnimationFrame(animate);
};

// ================== 搜索建议 ==================
const handleBlur = () => {
  isFocused.value = false;
  setTimeout(() => {
    showSuggestions.value = false;
  }, 200);
};

const handleSearchInput = () => {
  clearTimeout(searchDebounceTimer);

  if (symbolInput.value.trim().length < 1) {
    showSuggestions.value = false;
    suggestions.value = [];
    return;
  }

  searchDebounceTimer = setTimeout(async () => {
    try {
      const results = await searchStocks(symbolInput.value.trim());
      suggestions.value = results.slice(0, 5);
      showSuggestions.value = true;
    } catch {
      // 搜索失败时静默处理
    }
  }, 300);
};

const selectSuggestion = (symbol: string) => {
  symbolInput.value = symbol;
  showSuggestions.value = false;
  handleSearch();
};

// ================== 自选股方法 ==================
const loadWatchlist = () => {
  const local = localStorage.getItem('stock_watchlist');
  if (local) {
    try {
      watchlist.value = JSON.parse(local);
    } catch {
      watchlist.value = ['AAPL', 'NVDA', 'TSLA'];
    }
  } else {
    watchlist.value = ['AAPL', 'NVDA', 'TSLA'];
    localStorage.setItem('stock_watchlist', JSON.stringify(watchlist.value));
  }
};

const isWatchlisted = (sym: string): boolean => {
  const target = sym.toUpperCase().replace('US', '');
  return watchlist.value.includes(target);
};

const toggleWatchlist = (sym: string) => {
  if (!sym) return;
  const target = sym.toUpperCase().replace('US', '');
  const idx = watchlist.value.indexOf(target);

  // 触发弹跳动画
  starBounce.value = true;
  setTimeout(() => {
    starBounce.value = false;
  }, 500);

  if (idx > -1) {
    watchlist.value.splice(idx, 1);
  } else {
    watchlist.value.push(target);
  }
  localStorage.setItem('stock_watchlist', JSON.stringify(watchlist.value));
};

const removeFromWatchlist = (sym: string) => {
  const target = sym.toUpperCase().replace('US', '');
  const idx = watchlist.value.indexOf(target);
  if (idx > -1) {
    watchlist.value.splice(idx, 1);
    localStorage.setItem('stock_watchlist', JSON.stringify(watchlist.value));
  }
};

const selectWatchlist = (sym: string) => {
  symbolInput.value = sym;
  handleSearch();
};

// ================== 拖动调宽 ==================
const startResize = (e: MouseEvent) => {
  e.preventDefault();
  const startX = e.clientX;
  const startWidth = leftWidth.value;
  let latestWidth = startWidth;

  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';

  const handleMouseMove = (moveEvent: MouseEvent) => {
    const deltaX = moveEvent.clientX - startX;
    const newWidth = startWidth + deltaX;
    const minL = 360;
    const maxL = window.innerWidth - 300;
    latestWidth = Math.max(minL, Math.min(newWidth, maxL));

    if (resizeRaf === null) {
      resizeRaf = requestAnimationFrame(() => {
        leftWidth.value = latestWidth;
        resizeRaf = null;
      });
    }
  };

  const cleanup = () => {
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    if (resizeRaf !== null) {
      cancelAnimationFrame(resizeRaf);
      resizeRaf = null;
    }
  };

  const handleMouseUp = () => {
    cleanup();
  };

  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);
};

// ================== K线悬停提示框逻辑 ==================
const formatPrice = (val: number): string => val.toFixed(2);

const formatVolumeNum = (vol: number): string => {
  if (vol >= 1e9) return (vol / 1e9).toFixed(2) + 'B';
  if (vol >= 1e6) return (vol / 1e6).toFixed(2) + 'M';
  if (vol >= 1e3) return (vol / 1e3).toFixed(2) + 'K';
  return vol.toString();
};

const findPrevClose = (time: string): number | null => {
  const data = klineData.value;
  if (data.length < 2) return null;
  const idx = data.findIndex(d => d.time === time);
  if (idx > 0) return data[idx - 1].close;
  return null;
};

const formatDate = (timeStr: string): string => {
  try {
    const date = new Date(timeStr);
    if (isNaN(date.getTime())) return timeStr;
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    return `${y}/${m}/${d} ${weekdays[date.getDay()]}`;
  } catch {
    return timeStr;
  }
};

const updateTooltipPosition = (relX: number, _relY: number) => {
  if (!chartArea.value || !tooltipEl.value) return;

  const areaRect = chartArea.value.getBoundingClientRect();
  const tipRect = tooltipEl.value.getBoundingClientRect();
  const tipW = tipRect.width;

  const padding = 8; // 距图表边缘间距

  // 鼠标在左半区 → 提示框固定在右上角；鼠标在右半区 → 固定在左上角
  let left: number;
  if (relX > areaRect.width / 2) {
    // 鼠标在右侧 → 提示框放左上角，不遮挡右侧K线
    tooltipSide.value = 'left';
    left = padding;
  } else {
    // 鼠标在左侧 → 提示框放右上角，不遮挡左侧K线
    tooltipSide.value = 'right';
    left = areaRect.width - tipW - padding;
  }

  // 垂直固定在顶部
  const top = padding;

  tooltipStyle.value = {
    left: left + 'px',
    top: top + 'px',
  };
};

const hideTooltip = () => {
  tooltipVisible.value = false;
};

// ================== 绘图初始化 ==================
const initChart = () => {
  if (!chartContainer.value) return;

  chartInstance = createChart(chartContainer.value, getChartOptions());

  candlestickSeries = chartInstance.addSeries(CandlestickSeries, {
    upColor: '#0d9488',
    downColor: '#e11d48',
    borderVisible: false,
    wickUpColor: '#0d9488',
    wickDownColor: '#e11d48',
  });
  markersPlugin = createSeriesMarkers(candlestickSeries);

  volumeSeries = chartInstance.addSeries(HistogramSeries, {
    priceFormat: { type: 'volume' },
    priceScaleId: 'volume',
  });

  chartInstance.priceScale('volume').applyOptions({
    scaleMargins: {
      top: 0.8,
      bottom: 0,
    },
    visible: false,
  });

  chartInstance.priceScale('right').applyOptions({
    scaleMargins: {
      top: 0.1,
      bottom: 0.25,
    },
  });

  // Chart will auto-size based on the container size and CSS layout.

  // ---- 十字准线悬停 → 自定义提示框 ----
  chartInstance.subscribeCrosshairMove((param) => {
    if (!param.point || !param.time || !param.seriesData) {
      hideTooltip();
      return;
    }

    const candleData = param.seriesData.get(candlestickSeries) as any;
    if (!candleData) {
      hideTooltip();
      return;
    }

    const timeStr = typeof param.time === 'string' ? param.time : String(param.time);
    const prevClose = findPrevClose(timeStr);
    const change = prevClose !== null ? ((candleData.close - prevClose) / prevClose) * 100 : 0;
    const amplitude = prevClose !== null ? ((candleData.high - candleData.low) / prevClose) * 100 : 0;

    // 成交量
    const volData = param.seriesData.get(volumeSeries) as any;
    const volume = volData?.value ?? 0;

    tooltipData.value = {
      date: formatDate(timeStr),
      open: formatPrice(candleData.open),
      high: formatPrice(candleData.high),
      low: formatPrice(candleData.low),
      close: formatPrice(candleData.close),
      change,
      changeStr: (change >= 0 ? '+' : '') + change.toFixed(2) + '%',
      amplitude: +amplitude.toFixed(2),
      volumeStr: formatVolumeNum(volume),
    };

    // 先让 DOM 渲染，再计算位置
    tooltipVisible.value = true;
    nextTick(() => {
      updateTooltipPosition(param.point!.x, param.point!.y);
    });
  });
};

// ================== 行情搜索 ==================
const handleSearch = async () => {
  const code = symbolInput.value.trim().toUpperCase();
  if (!code) return;

  isLoading.value = true;
  errorMsg.value = '';
  srLevels.value = [];
  rangeStats.value = null;
  showSuggestions.value = false;

  // 接口查询拼接 us 前缀
  const querySymbol = code.startsWith('US') ? code : 'us' + code;

  try {
    const klines = await getKLines(querySymbol);
    if (!klines || klines.length === 0) {
      throw new Error('未获取到有效的K线行情数据');
    }

    klineData.value = klines;
    // currentSymbol 保持纯净的无前缀大写代码（如 AAPL），和 UI 对齐
    currentSymbol.value = code;

    // 重置绘图线与标记
    priceLines.forEach(line => candlestickSeries?.removePriceLine(line));
    priceLines = [];
    markersPlugin?.setMarkers([]);

    if (klines.length > 0) {
      startDate.value = klines[0].time;
      endDate.value = klines[klines.length - 1].time;
      inputStartDate.value = startDate.value;
      inputEndDate.value = endDate.value;
    }

    await runAnalysis();
  } catch (err: any) {
    errorMsg.value = err.message || '网络连接失败，无法加载行情图';
    klineData.value = [];
    currentSymbol.value = '';
  } finally {
    isLoading.value = false;
  }
};

// ================== 手动重算区间 ==================
const handleReCalculate = async () => {
  startDate.value = inputStartDate.value;
  endDate.value = inputEndDate.value;
  await runAnalysis();
};

// ================== 计算技术分析 ==================
const runAnalysis = async () => {
  if (!klineData.value.length || !currentSymbol.value) return;

  const querySymbol = currentSymbol.value.startsWith('US') ? currentSymbol.value : 'us' + currentSymbol.value;

  try {
    const res = await getStockAnalysis(querySymbol, startDate.value, endDate.value, klineData.value);
    if (!res) {
      throw new Error('支撑阻力计算失败');
    }

    srLevels.value = res.sr_levels;
    rangeStats.value = res.statistics;

    // 触发数字动画
    if (res.statistics) {
      animateNumber(res.statistics.max_rise.pct, true);
      animateNumber(res.statistics.max_fall.pct, false);
    }

    // 清除并重新绘制水平虚线
    priceLines.forEach(line => candlestickSeries?.removePriceLine(line));
    priceLines = [];

    res.sr_levels.forEach(lvl => {
      const isSupport = lvl.type === 'support';
      const line = candlestickSeries.createPriceLine({
        price: lvl.price,
        color: isSupport ? '#0d9488' : '#e11d48',
        lineWidth: 1.5,
        lineStyle: 2, // 虚线
        axisLabelVisible: true,
        title: `${isSupport ? '支撑' : '阻力'}: ${lvl.price.toFixed(2)} [${lvl.level}]`,
      });
      priceLines.push(line);
    });

    // 设置 K 线图上的最大上涨/下跌起点与终点标记 (SeriesMarker)
    const markers: any[] = [];
    if (res.statistics) {
      const rise = res.statistics.max_rise;
      if (rise && rise.start && rise.end && rise.pct > 0) {
        markers.push({
          time: rise.start,
          position: 'belowBar',
          color: '#0d9488',
          shape: 'arrowUp',
          text: `▲上涨起点 (+${rise.pct.toFixed(1)}%)`,
        });
        markers.push({
          time: rise.end,
          position: 'aboveBar',
          color: '#0d9488',
          shape: 'arrowDown',
          text: '▼上涨终点',
        });
      }

      const fall = res.statistics.max_fall;
      if (fall && fall.start && fall.end && fall.pct < 0) {
        markers.push({
          time: fall.start,
          position: 'aboveBar',
          color: '#e11d48',
          shape: 'arrowDown',
          text: `▼下跌起点 (${fall.pct.toFixed(1)}%)`,
        });
        markers.push({
          time: fall.end,
          position: 'belowBar',
          color: '#e11d48',
          shape: 'arrowUp',
          text: '▲下跌终点',
        });
      }
    }

    // 将 markers 排序，使日期从小到大排
    markers.sort((a, b) => a.time.localeCompare(b.time));
    markersPlugin?.setMarkers(markers);
  } catch (err: any) {
    errorMsg.value = err.message || '分析服务出错，请检查网络';
  }
};

watch(klineData, (newData) => {
  if (candlestickSeries && volumeSeries && newData.length > 0) {
    candlestickSeries.setData(newData.map(d => ({
      time: d.time,
      open: d.open,
      close: d.close,
      high: d.high,
      low: d.low,
    })));

    volumeSeries.setData(newData.map(d => ({
      time: d.time,
      value: d.volume,
      color: d.close >= d.open ? 'rgba(13, 148, 136, 0.2)' : 'rgba(225, 29, 72, 0.2)'
    })));

    chartInstance?.timeScale().fitContent();
  }
});

onMounted(() => {
  loadWatchlist();

  // 设置自适应的初始宽度
  leftWidth.value = Math.max(400, window.innerWidth - 340);

  nextTick(() => {
    if (!chartContainer.value) return;

    // 使用 ResizeObserver 确保图表在容器拥有实际高度后才初始化
    const observer = new ResizeObserver((entries) => {
      // 一旦容器高度大于1px (意味着布局已完成)，就执行初始化
      if (entries[0] && entries[0].contentRect.height > 1) {
        // 立即断开此观察者，因为它只用于首次初始化
        observer.disconnect();

        // 现在可以安全地初始化图表并加载数据
        initChart();
        handleSearch();
      }
    });

    // 开始观察容器尺寸变化
    observer.observe(chartContainer.value);
  });

  window.addEventListener('resize', () => {
    leftWidth.value = Math.max(400, window.innerWidth - 340);
  });
});

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.remove();
    chartInstance = null;
  }
  clearTimeout(searchDebounceTimer);
});
</script>

<style>
/* 淡入淡出过渡 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 下拉菜单过渡 */
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.2s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* 列表项过渡 */
.list-enter-active,
.list-leave-active {
  transition: all 0.3s ease;
}

.list-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}

.list-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

.list-move {
  transition: transform 0.3s ease;
}

/* ========== K线悬停提示框动画 ========== */
.animate-tooltip-in {
  animation: tooltipIn 0.15s ease-out;
}

@keyframes tooltipIn {
  from {
    opacity: 0;
    transform: scale(0.92);
  }

  to {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
