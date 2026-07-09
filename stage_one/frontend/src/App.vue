<template>
  <div
    class="flex flex-col flex-1 h-screen overflow-hidden bg-[#f8fafc] dark:bg-slate-900 text-slate-800 dark:text-slate-200 subpixel-antialiased font-sans select-none">

    <!-- 头部导航栏 (简化版，只保留标题) -->
    <header
      class="bg-white dark:bg-slate-800 border-b border-slate-200/80 dark:border-slate-700 px-6 py-3 flex items-center justify-between gap-4 shrink-0 shadow-sm dark:shadow-slate-900/50 z-10 animate-fade-in-down">
      <div class="flex items-center gap-3">
        <div
          class="bg-teal-600 p-2 rounded-lg shadow-md shadow-teal-100 shrink-0 transition-transform hover:scale-105 active:scale-95 cursor-pointer">
          <svg class="w-5 h-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
            stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
        </div>
        <div>
          <h1 class="text-lg font-bold text-slate-900 dark:text-slate-100 tracking-tight">智能股票技术分析平台</h1>
          <p class="text-[10px] text-slate-400">美股多周期K线 · 自动支撑阻力识别</p>
        </div>
      </div>

      <!-- 当前选中股票信息 -->
      <div v-if="currentSymbol" class="flex items-center gap-4">
        <div class="flex items-center gap-3">
          <div class="text-right">
            <span class="text-xl font-bold text-slate-900 dark:text-slate-100">{{ currentSymbol }}</span>
          </div>
          <!-- 最新价格和涨跌幅 -->
          <div v-if="latestPrice" class="flex items-center gap-2 pl-3 border-l border-slate-200 dark:border-slate-600">
            <span class="text-lg font-bold font-mono tabular-nums" 
              :class="latestChange >= 0 ? 'text-rose-600' : 'text-teal-600'">
              ${{ latestPrice.toFixed(2) }}
            </span>
            <span class="text-xs font-semibold px-1.5 py-0.5 rounded"
              :class="latestChange >= 0 ? 'bg-rose-50 text-rose-600' : 'bg-teal-50 text-teal-600'">
              {{ latestChange >= 0 ? '+' : '' }}{{ latestChange.toFixed(2) }}%
            </span>
          </div>
        </div>
        <button @click="toggleWatchlist(currentSymbol)"
          class="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-all group cursor-pointer active:scale-90"
          :title="isWatchlisted(currentSymbol) ? '取消自选' : '加入自选'">
          <svg class="w-5 h-5 transition-all duration-300 group-hover:scale-110" :class="[
            isWatchlisted(currentSymbol) ? 'text-amber-400 fill-amber-400' : 'text-slate-300 hover:text-amber-400 fill-none',
            starBounce ? 'animate-bounce-once' : ''
          ]" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M11.48 3.499c.174-.383.72-.383.894 0l2.64 5.352 5.9 1.15c.422.082.59.59.282.895l-4.244 4.14 1.002 5.86c.071.423-.372.746-.75.545l-5.267-2.77-5.268 2.77c-.378.201-.821-.122-.75-.545l1.002-5.86-4.244-4.14c-.308-.305-.14-.813.282-.895l5.9-1.15 2.64-5.352z" />
          </svg>
        </button>
      </div>

      <!-- 右侧控制区：测试模式 + 深色模式 -->
      <div class="flex items-center gap-4">
        <!-- 测试模式切换开关 -->
        <label class="flex items-center gap-2 cursor-pointer select-none">
          <input type="checkbox" v-model="useMockData" class="sr-only peer" />
          <div class="relative w-10 h-5 bg-slate-300 dark:bg-slate-600 rounded-full peer peer-checked:bg-teal-500 transition-colors">
            <div class="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow-md transition-transform peer-checked:translate-x-5"></div>
          </div>
          <span class="text-xs text-slate-600 dark:text-slate-400 font-medium">
            {{ useMockData ? '🧪 测试模式' : '🌐 真实数据' }}
          </span>
        </label>
        
        <!-- 分隔线 -->
        <div class="w-px h-5 bg-slate-200 dark:bg-slate-600"></div>
        
        <!-- 深色模式切换开关 -->
        <button @click="toggleDarkMode()" 
          class="flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all hover:bg-slate-100 dark:hover:bg-slate-700"
          :title="isDarkMode ? '切换到浅色模式' : '切换到深色模式'">
          <svg class="w-4 h-4 transition-transform" :class="isDarkMode ? 'text-amber-400 rotate-180' : 'text-slate-500'" 
            xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path v-if="!isDarkMode" stroke-linecap="round" stroke-linejoin="round" 
              d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            <path v-else stroke-linecap="round" stroke-linejoin="round" 
              d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
          </svg>
          <span class="text-xs font-medium" :class="isDarkMode ? 'text-amber-400' : 'text-slate-600'">
            {{ isDarkMode ? '深色' : '浅色' }}
          </span>
        </button>
      </div>
    </header>

    <!-- 主交互区域 -->
    <main class="flex-1 flex overflow-hidden relative min-h-0 bg-white dark:bg-slate-900">

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

      <!-- 左侧边栏：搜索 + 自选股列表 -->
      <aside
        :style="{ width: leftSidebarWidth + 'px' }"
        class="bg-white dark:bg-slate-800 border-r border-slate-200/80 dark:border-slate-700 flex flex-col shrink-0 overflow-y-auto scrollbar-thin">
        
        <!-- 搜索区域 -->
        <div class="p-4 border-b border-slate-100 dark:border-slate-700 sticky top-0 bg-white dark:bg-slate-800 z-10">
          <div class="relative">
            <span class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 transition-colors"
              :class="{ 'text-teal-500': isFocused }">
              <svg class="w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
                stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </span>
            <input type="text" v-model="symbolInput" @keydown="handleSearchKeydown" @focus="isFocused = true"
              @blur="handleBlur" @input="handleSearchInput" placeholder="搜索股票代码/名称"
              class="w-full bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 text-slate-800 dark:text-slate-200 rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 focus:bg-white dark:focus:bg-slate-700 transition-all placeholder-slate-400 dark:placeholder-slate-500 font-medium"
              autocomplete="off" />

            <!-- 搜索建议下拉 -->
            <transition name="dropdown">
              <div v-if="showSuggestions && suggestions.length > 0"
                class="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-xl overflow-hidden z-50 animate-fade-in-down max-h-60 overflow-y-auto">
                <div v-for="(item, idx) in suggestions" :key="item.symbol" 
                  @click="selectSuggestion(item.symbol)"
                  @mouseenter="highlightIndex = idx"
                  class="px-3 py-2 cursor-pointer transition-colors flex items-center justify-between border-b border-slate-50 dark:border-slate-700 last:border-0"
                  :class="highlightIndex === idx ? 'bg-teal-50 dark:bg-teal-900/30' : 'hover:bg-teal-50/50 dark:hover:bg-teal-900/20'"
                  :style="{ animationDelay: idx * 50 + 'ms' }">
                  <div class="flex items-center gap-2">
                    <span class="font-bold text-slate-800 dark:text-slate-200 text-sm">{{ item.symbol }}</span>
                    <span class="text-xs text-slate-400">{{ item.name }}</span>
                  </div>
                  <svg class="w-3.5 h-3.5" :class="highlightIndex === idx ? 'text-teal-500' : 'text-slate-300'" 
                    xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"
                    stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </div>
              </div>
            </transition>
          </div>
          <button @click="createRipple($event); handleSearch()" :disabled="isLoading"
            class="ripple-container w-full mt-2 bg-teal-600 hover:bg-teal-500 text-white px-4 py-2 rounded-lg text-sm font-semibold shadow-md shadow-teal-600/10 hover:shadow-teal-600/20 active:scale-[0.98] transition-all disabled:opacity-50 disabled:pointer-events-none cursor-pointer relative overflow-hidden">
            <span v-if="isLoading" class="flex items-center justify-center gap-2">
              <svg class="animate-spin h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
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

        <!-- 自选股列表 -->
        <div class="flex-1 overflow-y-auto">
          <div class="px-4 py-3 border-b border-slate-100 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-700/50">
            <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center justify-between">
              <span>我的自选 ({{ watchlist.length }})</span>
              <span class="text-[10px] text-slate-400">点击切换</span>
            </h3>
          </div>

          <!-- 空状态 -->
          <div v-if="!watchlist.length"
            class="p-8 text-center text-xs text-slate-400">
            <svg class="w-10 h-10 mx-auto mb-2 text-slate-300" xmlns="http://www.w3.org/2000/svg" fill="none"
              viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M11.48 3.499c.174-.383.72-.383.894 0l2.64 5.352 5.9 1.15c.422.082.59.59.282.895l-4.244 4.14 1.002 5.86c.071.423-.372.746-.75.545l-5.267-2.77-5.268 2.77c-.378.201-.821-.122-.75-.545l1.002-5.86-4.244-4.14c-.308-.305-.14-.813.282-.895l5.9-1.15 2.64-5.352z" />
            </svg>
            <p>暂无自选股</p>
            <p class="mt-1 text-[10px]">在图表区点击星标添加</p>
          </div>

          <!-- 自选列表 -->
          <transition-group v-else name="list" tag="div" class="divide-y divide-slate-100 dark:divide-slate-700">
            <div v-for="item in watchlist" :key="item" @click="selectWatchlist(item)"
              class="group px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-700 cursor-pointer transition-all"
              :class="currentSymbol === item ? 'bg-teal-50/50 dark:bg-teal-900/20 border-l-2 border-teal-500' : 'border-l-2 border-transparent'">
              <div class="flex items-center justify-between mb-1">
                <div class="flex items-center gap-2">
                  <span class="font-bold text-sm text-slate-900 dark:text-slate-100">{{ item }}</span>
                  <button @click.stop="removeFromWatchlist(item)"
                    class="text-slate-300 hover:text-rose-500 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                    title="移除">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                  </button>
                </div>
                <!-- 显示当前股票的价格和涨跌幅 -->
                <div class="text-right" v-if="currentSymbol === item && latestPrice">
                  <div class="text-xs font-bold font-mono tabular-nums" 
                    :class="latestChange >= 0 ? 'text-rose-600' : 'text-teal-600'">
                    ${{ latestPrice.toFixed(2) }}
                  </div>
                  <div class="text-[10px] font-semibold"
                    :class="latestChange >= 0 ? 'text-rose-500' : 'text-teal-500'">
                    {{ latestChange >= 0 ? '+' : '' }}{{ latestChange.toFixed(2) }}%
                  </div>
                </div>
                <div class="text-right" v-else>
                  <span class="text-xs text-slate-400">--</span>
                </div>
              </div>
              <div class="text-[10px] text-slate-400">
                {{ currentSymbol === item ? '当前显示中' : '点击查看K线图' }}
              </div>
            </div>
          </transition-group>
        </div>
      </aside>

      <!-- 比例调节拖拽条 -->
      <div @mousedown="startResizeLeft"
        class="w-1 bg-slate-100 dark:bg-slate-700 hover:bg-teal-500 active:bg-teal-600 cursor-col-resize transition-colors shrink-0 z-50 group relative">
        <div class="absolute inset-y-0 -left-4 -right-4"></div>
        <!-- 拖拽指示器 -->
        <div class="absolute inset-y-0 -left-1 -right-1 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center pointer-events-none">
          <div class="w-1 h-8 rounded-full bg-teal-500/40"></div>
        </div>
      </div>

      <!-- 中间：图表容器 -->
      <div class="flex-1 flex flex-col min-h-0 min-w-0 bg-white dark:bg-slate-900">
        <!-- 图表工具栏：K线周期 + 时间范围（一行式，参考同花顺/东方财富风格） -->
        <div class="h-9 flex items-center justify-between px-3 border-b border-slate-100 dark:border-slate-700 bg-slate-50/30 dark:bg-slate-800/30 shrink-0">
          <!-- 左侧：股票代码 + 周期选择（辅助信息，不抢焦点） -->
          <div class="flex items-center gap-2 shrink-0">
            <span v-if="currentSymbol" class="text-xs font-bold text-slate-700 dark:text-slate-300">{{ currentSymbol }}</span>
            <!-- 周期按钮组：仅在未选时间范围时高亮当前周期；选中时间范围后降为灰色辅助显示 -->
            <div class="flex items-center gap-0.5">
              <button
                v-for="p in periodOptions"
                :key="p"
                @click="changePeriod(p)"
                class="px-2 py-0.5 text-[11px] font-medium rounded transition-colors cursor-pointer"
                :class="activeTimeRange === 'ALL' && currentPeriod === p
                  ? 'text-indigo-600 dark:text-indigo-400 font-bold bg-indigo-50 dark:bg-indigo-900/20'
                  : 'text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700'">
                {{ periodLabels[p] }}
              </button>
            </div>
          </div>
          <!-- 右侧：时间范围下拉（主角，选中时高亮） -->
          <div v-if="klineData.length > 0" class="relative shrink-0">
            <button
              @click="showTimeRangeMenu = !showTimeRangeMenu"
              class="flex items-center gap-1 px-2.5 py-0.5 text-[11px] font-medium rounded transition-colors cursor-pointer"
              :class="activeTimeRange === 'ALL'
                ? 'border border-slate-200 dark:border-slate-600 text-slate-500 dark:text-slate-400 hover:bg-white dark:hover:bg-slate-700'
                : 'bg-teal-500 text-white shadow-sm hover:bg-teal-600'">
              {{ timeRangeLabel(activeTimeRange) }}
              <svg class="w-3 h-3" :class="activeTimeRange === 'ALL' ? '' : 'opacity-80'" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg>
            </button>
            <!-- 下拉菜单 -->
            <Transition name="fade-scale">
              <div v-if="showTimeRangeMenu" class="absolute right-0 top-full mt-1 z-50 min-w-[90px] bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-600 py-1">
                <button
                  v-for="range in timeRanges"
                  :key="range.value"
                  @click="selectTimeRange(range.value)"
                  class="w-full text-left px-3 py-1.5 text-[11px] transition-colors cursor-pointer"
                  :class="activeTimeRange === range.value
                    ? 'text-indigo-600 dark:text-indigo-400 font-bold bg-indigo-50 dark:bg-indigo-900/20'
                    : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700'">
                  {{ range.label }}
                </button>
              </div>
            </Transition>
          </div>
        </div>
        
        <!-- 数据完整性提示 (真实模式返回根数过少时显示) -->
        <div v-if="dataWarning"
          class="px-4 py-2 bg-amber-50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 text-xs font-medium flex items-center gap-2">
          <span>⚠️</span><span>{{ dataWarning }}</span>
        </div>

        <!-- 实际图表绑定节点 -->
        <div ref="chartArea" class="flex-1 relative min-w-0 bg-white dark:bg-slate-900">
          <div ref="chartContainer" class="absolute inset-0 w-full h-full transition-opacity duration-300"
            :class="{ 'opacity-50': isLoading }"></div>

          <!-- 自定义K线悬停提示框 -->
          <div v-show="tooltipVisible" ref="tooltipEl"
            class="absolute z-40 pointer-events-none bg-white/95 dark:bg-slate-800/95 backdrop-blur-sm border border-slate-200 dark:border-slate-700 rounded-xl shadow-xl py-3 px-4 text-xs font-mono animate-tooltip-in"
            :style="tooltipStyle">
            <!-- 日期 -->
            <div class="text-slate-400 dark:text-slate-500 mb-2 pb-2 border-b border-slate-100 dark:border-slate-700 font-sans text-[11px] font-semibold">
              {{ tooltipData.date }}
            </div>
            <!-- OHLC 数据 -->
            <div class="space-y-1">
              <div class="flex justify-between gap-4">
                <span class="text-slate-400 dark:text-slate-500">开盘</span>
                <span class="text-slate-800 dark:text-slate-200 font-semibold">{{ tooltipData.open }}</span>
              </div>
              <div class="flex justify-between gap-4">
                <span class="text-slate-400 dark:text-slate-500">最高</span>
                <span class="text-rose-600 font-semibold">{{ tooltipData.high }}</span>
              </div>
              <div class="flex justify-between gap-4">
                <span class="text-slate-400 dark:text-slate-500">最低</span>
                <span class="text-teal-600 font-semibold">{{ tooltipData.low }}</span>
              </div>
              <div class="flex justify-between gap-4">
                <span class="text-slate-400 dark:text-slate-500">收盘</span>
                <span class="font-semibold" :class="tooltipData.change >= 0 ? 'text-rose-600' : 'text-teal-600'">
                  {{ tooltipData.close }}
                </span>
              </div>
            </div>
            <!-- 分隔 -->
            <div class="my-2 border-t border-slate-100 dark:border-slate-700"></div>
            <!-- 涨跌 & 振幅 -->
            <div class="space-y-1">
              <div class="flex justify-between gap-4 items-center">
                <span class="text-slate-400 dark:text-slate-500">涨跌幅</span>
                <span class="font-semibold text-xs px-1.5 py-0.5 rounded"
                  :class="tooltipData.change >= 0 ? 'bg-rose-50 text-rose-600' : 'bg-teal-50 text-teal-600'">
                  {{ tooltipData.changeStr }}
                </span>
              </div>
              <div class="flex justify-between gap-4 items-center">
                <span class="text-slate-400 dark:text-slate-500">振幅</span>
                <span class="font-semibold text-slate-700 dark:text-slate-300">{{ tooltipData.amplitude }}%</span>
              </div>
              <div class="flex justify-between gap-4 items-center">
                <span class="text-slate-400 dark:text-slate-500">成交量</span>
                <span class="font-semibold text-slate-700 dark:text-slate-300">{{ tooltipData.volumeStr }}</span>
              </div>
            </div>
          </div>

          <!-- 骨架屏加载状态 (加载中显示，shimmer 动画优化感知速度；每次加载都会出现，含切换股票) -->
          <div v-if="isLoading"
            class="absolute inset-0 flex bg-slate-50/70 dark:bg-slate-900/70 backdrop-blur-sm z-10">
            <!-- 主图区：仿 K线柱 + 量能条 -->
            <div class="flex-1 flex flex-col justify-end p-4 gap-3">
              <div class="flex-1 flex items-end gap-[3px]">
                <div v-for="(h, i) in skeletonCandles" :key="'c' + i"
                  class="skeleton flex-1 rounded-sm" :style="{ height: h + '%' }"></div>
              </div>
              <div class="h-14 flex items-end gap-[3px]">
                <div v-for="(h, i) in skeletonVol" :key="'v' + i"
                  class="skeleton flex-1 rounded-sm" :style="{ height: h + '%' }"></div>
              </div>
            </div>
            <!-- 右侧价格轴占位 -->
            <div class="w-12 flex flex-col justify-between py-6 pr-3 gap-2">
              <div v-for="n in 9" :key="'a' + n" class="skeleton h-2.5 w-full rounded"></div>
            </div>
          </div>

          <div v-if="!klineData.length && !isLoading"
            class="absolute inset-0 flex items-center justify-center bg-slate-50/50 dark:bg-slate-900/50">
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

      <!-- 比例调节拖拽条（右侧） -->
      <div @mousedown="startResizeRight"
        class="w-1 bg-slate-100 dark:bg-slate-700 hover:bg-teal-500 active:bg-teal-600 cursor-col-resize transition-colors shrink-0 z-50 group relative">
        <div class="absolute inset-y-0 -left-4 -right-4"></div>
        <!-- 拖拽指示器 -->
        <div class="absolute inset-y-0 -left-1 -right-1 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center pointer-events-none">
          <div class="w-1 h-8 rounded-full bg-teal-500/40"></div>
        </div>
      </div>

      <!-- 右侧：技术分析面板 -->
      <div
        :style="{ width: rightPanelWidth + 'px' }"
        class="bg-white dark:bg-slate-800 border-l border-slate-200/80 dark:border-slate-700 flex flex-col shrink-0 overflow-hidden">

        <!-- Tab 导航 -->
        <div class="flex border-b border-slate-200/80 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50 shrink-0">
          <button 
            @click="rightPanelTab = 'analysis'"
            class="flex-1 px-4 py-3 text-xs font-semibold uppercase tracking-wider transition-all relative"
            :class="rightPanelTab === 'analysis' 
              ? 'text-teal-600 bg-white dark:bg-slate-800' 
              : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 hover:bg-slate-100/50 dark:hover:bg-slate-700/50'">
            <span class="flex items-center justify-center gap-1.5">
              <svg class="w-3.5 h-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z" />
              </svg>
              技术分析
            </span>
            <!-- 激活指示器 -->
            <div v-if="rightPanelTab === 'analysis'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-teal-500"></div>
          </button>
          <button 
            @click="rightPanelTab = 'range'"
            class="flex-1 px-4 py-3 text-xs font-semibold uppercase tracking-wider transition-all relative"
            :class="rightPanelTab === 'range' 
              ? 'text-teal-600 bg-white dark:bg-slate-800' 
              : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 hover:bg-slate-100/50 dark:hover:bg-slate-700/50'">
            <span class="flex items-center justify-center gap-1.5">
              <svg class="w-3.5 h-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
              区间统计
            </span>
            <!-- 激活指示器 -->
            <div v-if="rightPanelTab === 'range'" class="absolute bottom-0 left-0 right-0 h-0.5 bg-teal-500"></div>
          </button>
        </div>

        <!-- Tab 内容容器 -->
        <div class="flex-1 overflow-y-auto scrollbar-thin">
          <!-- Tab 1: 技术分析 -->
          <div v-show="rightPanelTab === 'analysis'" class="h-full">
            <!-- 1. 智能分析触发区域 -->
            <div class="p-5 border-b border-slate-100 dark:border-slate-700">
              <h3 class="text-sm font-semibold text-slate-900 dark:text-slate-100 uppercase tracking-wider mb-3 flex items-center gap-2">
                <svg class="w-4 h-4 text-teal-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                形态特征提取
              </h3>
              <button @click="createRipple($event); runAnalysis()" :disabled="!klineData.length"
                class="ripple-container w-full bg-slate-900 dark:bg-slate-700 hover:bg-slate-800 dark:hover:bg-slate-600 text-white font-semibold py-3 px-4 rounded-xl text-sm transition-all shadow-md hover:shadow-lg hover:-translate-y-0.5 active:scale-[0.98] disabled:opacity-40 disabled:pointer-events-none flex items-center justify-center gap-2 cursor-pointer relative overflow-hidden">
                <svg class="w-4 h-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z" />
                </svg>
                执行智能技术分析
              </button>
            </div>

            <!-- 2. 支撑/阻力位列表 -->
            <div class="p-5">
              <div class="panel-card-header">
                <h4 class="text-xs font-bold text-slate-400 uppercase tracking-wider">
                  自动识别支撑/阻力线 (SR Levels)
                </h4>
              </div>

              <div v-if="!srLevels.length"
                class="text-xs text-slate-400 dark:text-slate-500 bg-slate-50 dark:bg-slate-700/50 border border-dashed border-slate-200 dark:border-slate-600 rounded-xl p-4 text-center italic transition-all hover:border-slate-300 dark:hover:border-slate-500">
                请在上方点击 "执行分析" 进行局部极点检测与聚类
              </div>

              <div v-else class="space-y-2.5">
                <transition-group name="list">
                  <div v-for="(level, idx) in srLevels" :key="idx"
                    class="relative overflow-hidden rounded-xl border transition-all hover:shadow-md hover:-translate-y-0.5 cursor-pointer group"
                    :class="[
                      level.type === 'support' 
                        ? 'border-teal-200 dark:border-teal-700 bg-gradient-to-r from-teal-50 to-teal-50/30 dark:from-teal-900/40 dark:to-teal-900/10' 
                        : 'border-rose-200 dark:border-rose-700 bg-gradient-to-r from-rose-50 to-rose-50/30 dark:from-rose-900/40 dark:to-rose-900/10',
                      highlightedSR === idx ? 'ring-2 ring-offset-1 dark:ring-offset-slate-800 ' + (level.type === 'support' ? 'ring-teal-400' : 'ring-rose-400') : ''
                    ]"
                    :style="{ animationDelay: idx * 100 + 'ms' }"
                    @mouseenter="highlightSRLevel(idx, true)"
                    @mouseleave="highlightSRLevel(idx, false)"
                    @click="scrollToSRLevel(level)">
                    <!-- 左侧装饰条 -->
                    <div class="absolute left-0 top-0 bottom-0 w-1"
                      :class="level.type === 'support' ? 'bg-teal-500' : 'bg-rose-500'"></div>
                    
                    <div class="flex items-center justify-between p-3.5 pl-4">
                      <div class="flex items-center gap-2.5">
                        <!-- 类型图标 -->
                        <div class="w-7 h-7 rounded-lg flex items-center justify-center"
                          :class="level.type === 'support' ? 'bg-teal-500' : 'bg-rose-500'">
                          <svg class="w-4 h-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                            <path v-if="level.type === 'support'" stroke-linecap="round" stroke-linejoin="round" d="M5 15l7-7 7 7" />
                            <path v-else stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
                          </svg>
                        </div>
                        <div>
                          <span class="text-xs font-semibold text-slate-700 dark:text-slate-200 block">
                            {{ level.type === 'support' ? '支撑位' : '阻力位' }}
                          </span>
                          <!-- 星级评分 -->
                          <div class="flex items-center gap-0.5 mt-0.5">
                            <svg v-for="s in level.stars" :key="s" class="w-3 h-3 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
                            </svg>
                          </div>
                        </div>
                      </div>
                      
                      <div class="text-right">
                        <span class="text-sm font-bold text-slate-900 dark:text-slate-100 number-animate block">${{ level.price.toFixed(2) }}</span>
                        <!-- 强度进度条 -->
                        <div class="flex items-center gap-1.5 mt-1">
                          <div class="w-12 h-1.5 bg-slate-200 dark:bg-slate-600 rounded-full overflow-hidden">
                            <div class="h-full rounded-full transition-all duration-500"
                              :class="level.type === 'support' ? 'bg-teal-500' : 'bg-rose-500'"
                              :style="{ width: (level.count / 5 * 100) + '%' }"></div>
                          </div>
                          <span class="text-[9px] text-slate-500 dark:text-slate-400 font-medium">{{ level.count }}次</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </transition-group>
              </div>
            </div>
          </div>

          <!-- Tab 2: 区间统计 -->
          <div v-show="rightPanelTab === 'range'" class="h-full p-5">
            <div class="panel-card-header mb-4">
              <div class="flex items-center justify-between">
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
            </div>

            <!-- 时间选择表单 -->
            <div class="space-y-3 mb-4">
              <div class="group">
                <label
                  class="text-[10px] font-bold text-slate-400 uppercase block mb-1 transition-colors group-focus-within:text-teal-500">起始日期</label>
                <input type="date" v-model="inputStartDate"
                  class="w-full bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg p-2 text-xs font-semibold text-slate-700 dark:text-slate-200 focus:outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 transition-all" />
              </div>
              <div class="group">
                <label
                  class="text-[10px] font-bold text-slate-400 uppercase block mb-1 transition-colors group-focus-within:text-teal-500">结束日期</label>
                <input type="date" v-model="inputEndDate"
                  class="w-full bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg p-2 text-xs font-semibold text-slate-700 dark:text-slate-200 focus:outline-none focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 transition-all" />
              </div>
            </div>

            <!-- 重新计算按钮 -->
            <button @click="createRipple($event); handleReCalculate()" :disabled="!klineData.length"
              class="ripple-container w-full border border-slate-200 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-semibold py-2 px-4 rounded-xl text-xs transition-all active:scale-[0.98] disabled:opacity-40 disabled:pointer-events-none flex items-center justify-center gap-1.5 cursor-pointer mb-5 hover:border-slate-300 dark:hover:border-slate-500 hover:shadow-sm relative overflow-hidden">
              <svg class="w-3.5 h-3.5 text-slate-500 transition-transform hover:rotate-180 duration-500"
                xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3-3 3 3m-3-3v12" />
              </svg>
              重新计算 (Re-calculate)
            </button>

            <!-- 统计数据输出面板 -->
            <div v-if="!rangeStats"
              class="text-xs text-slate-400 dark:text-slate-500 bg-slate-50 dark:bg-slate-700/50 border border-dashed border-slate-200 dark:border-slate-600 rounded-xl p-4 text-center italic transition-all hover:border-slate-300 dark:hover:border-slate-500">
              请在上方指定日期后执行智能分析
            </div>

            <div v-else class="space-y-3">
              <!-- 上涨 -->
              <div
                class="bg-teal-50/50 dark:bg-teal-900/30 border border-teal-100 dark:border-teal-700 rounded-xl p-3.5 transition-all hover:shadow-md hover:-translate-y-0.5 hover:border-teal-200 dark:hover:border-teal-600 group">
                <div class="flex items-center gap-1.5 text-teal-700 dark:text-teal-400 font-bold text-xs mb-1">
                  <svg class="w-4 h-4 transition-transform group-hover:-translate-y-1" xmlns="http://www.w3.org/2000/svg"
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                  <span>最大连贯上涨</span>
                </div>
                <div class="text-lg font-extrabold text-teal-600 dark:text-teal-400 font-mono number-animate">
                  +{{ animatedRisePct.toFixed(2) }}%
                </div>
                <div class="text-[10px] text-slate-400 dark:text-slate-500 mt-1 font-medium font-mono">
                  {{ rangeStats.max_rise.start }} &rarr; {{ rangeStats.max_rise.end }}
                </div>
              </div>

              <!-- 下跌 -->
              <div
                class="bg-rose-50/50 dark:bg-rose-900/30 border border-rose-100 dark:border-rose-700 rounded-xl p-3.5 transition-all hover:shadow-md hover:-translate-y-0.5 hover:border-rose-200 dark:hover:border-rose-600 group">
                <div class="flex items-center gap-1.5 text-rose-700 dark:text-rose-400 font-bold text-xs mb-1">
                  <svg class="w-4 h-4 transition-transform group-hover:translate-y-1" xmlns="http://www.w3.org/2000/svg"
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M13 17h8m0 0v-8m0 8l-8-8-4 4-6-6" />
                  </svg>
                  <span>最大连贯下跌</span>
                </div>
                <div class="text-lg font-extrabold text-rose-600 dark:text-rose-400 font-mono number-animate">
                  {{ animatedFallPct.toFixed(2) }}%
                </div>
                <div class="text-[10px] text-slate-400 dark:text-slate-500 mt-1 font-medium font-mono">
                  {{ rangeStats.max_fall.start }} &rarr; {{ rangeStats.max_fall.end }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 底部状态栏 -->
    <footer class="h-6 bg-slate-800 dark:bg-slate-950 text-slate-400 dark:text-slate-500 text-[10px] flex items-center justify-between px-4 shrink-0">
      <div class="flex items-center gap-4">
        <span class="flex items-center gap-1">
          <span class="w-1.5 h-1.5 rounded-full" :class="useMockData ? 'bg-amber-400' : 'bg-green-400'"></span>
          {{ useMockData ? '测试模式' : '实时数据' }}
        </span>
        <span v-if="currentSymbol">{{ currentSymbol }} · {{ klineData.length }} 根K线</span>
      </div>
      <div class="flex items-center gap-4">
        <span>自选股: {{ watchlist.length }} 只</span>
        <span>Ctrl+K 搜索 | R 重算</span>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch, computed } from 'vue';
import { createChart, CandlestickSeries, HistogramSeries, createSeriesMarkers } from 'lightweight-charts';
import type { IChartApi } from 'lightweight-charts';
import { getKLines, getStockAnalysis, searchStocks, generateMockKLines, getWatchlist, saveWatchlist, SUPPORTED_PERIODS, PERIOD_LABELS } from './utils/api';
import type { KLinePoint, SRLevel, StockInfo, AnalysisResponse, Period } from './utils/api';
import { getChartOptions } from './utils/chartUtils';
import { calculateSRLevels, calculateRangeStats } from './utils/mockEngine';

const symbolInput = ref('AAPL');
const currentSymbol = ref('');
const klineData = ref<KLinePoint[]>([]);
// 按 "symbol_period" 缓存K线和分析结果，避免切换周期时重复网络请求
const klineCache = new Map<string, KLinePoint[]>();
const analysisCache = new Map<string, AnalysisResponse>();
const cacheKey = (symbol: string, period: Period) => `${symbol}_${period}`;
const isLoading = ref(false);
const errorMsg = ref('');
const isFocused = ref(false);
const showSuggestions = ref(false);
const suggestions = ref<StockInfo[]>([]);
const starBounce = ref(false);
const highlightIndex = ref(-1); // 搜索建议键盘导航高亮索引

// 测试模式开关（用于前端独立调试）
const useMockData = ref(true); // 默认开启测试模式

// 深色模式开关
const isDarkMode = ref(false);

// 切换深色模式
const toggleDarkMode = () => {
  isDarkMode.value = !isDarkMode.value;
  document.documentElement.classList.toggle('dark', isDarkMode.value);
  localStorage.setItem('darkMode', isDarkMode.value ? 'true' : 'false');
  // 更新图表配色
  if (chartInstance) {
    chartInstance.applyOptions({
      layout: {
        background: { color: isDarkMode.value ? '#0f172a' : '#ffffff' },
        textColor: isDarkMode.value ? '#94a3b8' : '#475569',
      },
      grid: {
        vertLines: { color: isDarkMode.value ? '#1e293b' : '#f1f5f9' },
        horzLines: { color: isDarkMode.value ? '#1e293b' : '#f1f5f9' },
      },
      crosshair: {
        vertLine: { color: isDarkMode.value ? '#475569' : '#94a3b8', labelBackgroundColor: isDarkMode.value ? '#334155' : '#475569' },
        horzLine: { color: isDarkMode.value ? '#475569' : '#94a3b8', labelBackgroundColor: isDarkMode.value ? '#334155' : '#475569' },
      },
      timeScale: {
        borderColor: isDarkMode.value ? '#334155' : '#e2e8f0',
        timeVisible: true,
      },
      rightPriceScale: {
        borderColor: isDarkMode.value ? '#334155' : '#e2e8f0',
      },
    });
  }
};

// 初始化深色模式
const initDarkMode = () => {
  const saved = localStorage.getItem('darkMode');
  if (saved === 'true') {
    isDarkMode.value = true;
    document.documentElement.classList.add('dark');
  }
};

// 最新价格和涨跌幅计算
const latestPrice = computed(() => {
  if (klineData.value.length === 0) return null;
  return klineData.value[klineData.value.length - 1].close;
});

const latestChange = computed(() => {
  if (klineData.value.length < 2) return 0;
  const current = klineData.value[klineData.value.length - 1].close;
  const previous = klineData.value[klineData.value.length - 2].close;
  return ((current - previous) / previous) * 100;
});

// 自选股列表 (存纯大写代码，如 AAPL, TSLA)
const watchlist = ref<string[]>([]);

// 分析数据状态
const srLevels = ref<SRLevel[]>([]);
const startDate = ref('');
const endDate = ref('');
const inputStartDate = ref('');
const inputEndDate = ref('');
const rangeStats = ref<any>(null);

// 数据完整性提示 (真实模式下返回根数过少时给出警告)
const dataWarning = ref('');

// SR 联动高亮状态
const highlightedSR = ref<number | null>(null);

// 右侧面板 Tab 状态
const rightPanelTab = ref<'analysis' | 'range'>('analysis');

// 时间范围配置（仅负责缩放视图，与上方K线周期按钮相互独立）
const timeRanges = [
  { label: '近1月', value: 'r1m' },
  { label: '近3月', value: 'r3m' },
  { label: '近6月', value: 'r6m' },
  { label: '近1年', value: 'r1y' },
  { label: '全部', value: 'ALL' },
];
const activeTimeRange = ref('ALL');
const showTimeRangeMenu = ref(false);

// 时间范围中文标签映射
const timeRangeLabel = (v: string): string => {
  const found = timeRanges.find(r => r.value === v);
  return found ? found.label : v;
};


// K线周期选择 (日K/周K/月K)
const currentPeriod = ref<Period>('1d');
const periodOptions = SUPPORTED_PERIODS;
const periodLabels = PERIOD_LABELS;

// 数字动画状态
const animatedRisePct = ref(0);
const animatedFallPct = ref(0);

// 左右拖拽初始列宽
const leftSidebarWidth = ref(280); // 左侧边栏固定宽度
const rightPanelWidth = ref(340); // 右侧面板固定宽度

// lightweight-charts 绘图实例引用
const chartContainer = ref<HTMLElement | null>(null);
const chartArea = ref<HTMLElement | null>(null);
const tooltipEl = ref<HTMLElement | null>(null);
let chartInstance: IChartApi | null = null;
let candlestickSeries: any = null;
let volumeSeries: any = null;
let priceLines: any[] = [];
let markersPlugin: any = null;

// ================== 缩放记忆 (鼠标滚轮缩放后跨切换保持) ==================
// 以"可见逻辑范围占全长的比例"存储缩放，跨股票 / 周期 / 日期范围均可按比例还原。
const ZOOM_MEMORY_KEY = 'kline_zoom_memory_v1';
let zoomMemory: { fromFrac: number; toFrac: number } | null = null;
// 程序化设置可见范围时抑制回调，避免回声写回
let suppressRangeEvents = false;
// 持久化节流定时器
let persistThrottleTimer: any = null;

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

// 骨架屏占位：预生成假 K线/量能柱高度，避免渲染时 Math.random 抖动
const skeletonCandles = Array.from({ length: 56 }, () => 28 + Math.floor(Math.random() * 68));
const skeletonVol = Array.from({ length: 56 }, () => 18 + Math.floor(Math.random() * 62));

// 骨架屏最短展示时长 (ms)：即使本地/测试数据瞬时返回，也保证扫光动画可被用户感知
const MIN_SKELETON_MS = 700;

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
    highlightIndex.value = -1;
    return;
  }

  searchDebounceTimer = setTimeout(async () => {
    try {
      const results = await searchStocks(symbolInput.value.trim());
      suggestions.value = results.slice(0, 5);
      showSuggestions.value = true;
      highlightIndex.value = -1; // 重置高亮
    } catch {
      // 搜索失败时静默处理
    }
  }, 300);
};

// 搜索框键盘导航
const handleSearchKeydown = (e: KeyboardEvent) => {
  if (!showSuggestions.value || suggestions.value.length === 0) {
    // 没有建议时，Enter 直接搜索
    if (e.key === 'Enter') {
      handleSearch();
    }
    return;
  }

  switch (e.key) {
    case 'ArrowDown':
      e.preventDefault();
      highlightIndex.value = (highlightIndex.value + 1) % suggestions.value.length;
      break;
    case 'ArrowUp':
      e.preventDefault();
      highlightIndex.value = highlightIndex.value <= 0 
        ? suggestions.value.length - 1 
        : highlightIndex.value - 1;
      break;
    case 'Enter':
      e.preventDefault();
      if (highlightIndex.value >= 0 && highlightIndex.value < suggestions.value.length) {
        selectSuggestion(suggestions.value[highlightIndex.value].symbol);
      } else {
        handleSearch();
      }
      break;
    case 'Escape':
      e.preventDefault();
      showSuggestions.value = false;
      highlightIndex.value = -1;
      break;
  }
};

const selectSuggestion = (symbol: string) => {
  symbolInput.value = symbol;
  showSuggestions.value = false;
  handleSearch();
};

// ================== 自选股方法 ==================
const loadWatchlist = async () => {
  // 优先从后端加载 (跨浏览器 / 跨 origin / 跨预览会话持久)
  try {
    const remote = await getWatchlist();
    if (Array.isArray(remote) && remote.length) {
      watchlist.value = remote;
      localStorage.setItem('stock_watchlist', JSON.stringify(remote)); // 同步本地兜底
      return;
    }
  } catch {
    // 后端不可用时忽略，回退本地
  }
  // 回退：本地 localStorage
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

// 同时写后端 + 本地兜底
const persistWatchlist = () => {
  localStorage.setItem('stock_watchlist', JSON.stringify(watchlist.value));
  saveWatchlist(watchlist.value); // 异步写后端，不阻塞 UI
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
  persistWatchlist();
};

const removeFromWatchlist = (sym: string) => {
  const target = sym.toUpperCase().replace('US', '');
  const idx = watchlist.value.indexOf(target);
  if (idx > -1) {
    watchlist.value.splice(idx, 1);
    persistWatchlist();
  }
};

const selectWatchlist = (sym: string) => {
  symbolInput.value = sym;
  handleSearch();
};

// ================== 拖拽时显式同步图表尺寸 ==================
const syncChartSize = () => {
  // 双重 RAF：第一帧更新 DOM，第二帧读取实际布局尺寸
  requestAnimationFrame(() => {
    if (chartInstance && chartArea.value) {
      const rect = chartArea.value.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        chartInstance.applyOptions({
          width: Math.floor(rect.width),
          height: Math.floor(rect.height),
        });
      }
    }
  });
};

// ================== 拖动调宽 - 左侧边栏 ==================
const startResizeLeft = (e: MouseEvent) => {
  e.preventDefault();
  const startX = e.clientX;
  const startWidth = leftSidebarWidth.value;
  let latestWidth = startWidth;

  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';

  const handleMouseMove = (moveEvent: MouseEvent) => {
    const deltaX = moveEvent.clientX - startX;
    const newWidth = startWidth + deltaX;
    const minL = 200;
    const maxL = Math.floor(window.innerWidth / 3);
    latestWidth = Math.max(minL, Math.min(newWidth, maxL));

    if (resizeRaf === null) {
      resizeRaf = requestAnimationFrame(() => {
        leftSidebarWidth.value = latestWidth;
        syncChartSize();
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

// ================== 拖动调宽 - 右侧面板 ==================
const startResizeRight = (e: MouseEvent) => {
  e.preventDefault();
  const startX = e.clientX;
  const startWidth = rightPanelWidth.value;
  let latestWidth = startWidth;

  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';

  const handleMouseMove = (moveEvent: MouseEvent) => {
    const deltaX = startX - moveEvent.clientX; // 反向计算
    const newWidth = startWidth + deltaX;
    const minL = 260;
    const maxL = Math.floor(window.innerWidth / 3);
    latestWidth = Math.max(minL, Math.min(newWidth, maxL));

    if (resizeRaf === null) {
      resizeRaf = requestAnimationFrame(() => {
        rightPanelWidth.value = latestWidth;
        syncChartSize();
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

const formatDate = (input: Date | string): string => {
  try {
    const date = input instanceof Date ? input : new Date(input);
    if (isNaN(date.getTime())) return String(input);
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    return `${y}/${m}/${d} ${weekdays[date.getDay()]}`;
  } catch {
    return String(input);
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

// ================== 缩放记忆相关 ==================
// 节流持久化到 localStorage，避免滚轮缩放过程中高频写入
const persistZoomMemory = () => {
  if (persistThrottleTimer) return;
  persistThrottleTimer = setTimeout(() => {
    persistThrottleTimer = null;
    if (zoomMemory) {
      try {
        localStorage.setItem(ZOOM_MEMORY_KEY, JSON.stringify(zoomMemory));
      } catch {
        // localStorage 不可用时静默忽略
      }
    }
  }, 400);
};

// 订阅缩放 / 平移变化：把当前可见逻辑范围折算成"占全长比例"并记忆
const onVisibleLogicalRangeChanged = (range: any) => {
  if (suppressRangeEvents) return;
  if (!range) return;
  const n = klineData.value.length;
  if (n < 2) return;
  const fromFrac = range.from / n;
  const toFrac = range.to / n;
  if (!isFinite(fromFrac) || !isFinite(toFrac)) return;
  if (toFrac - fromFrac < 0.0005) return; // 防止异常窄范围
  zoomMemory = { fromFrac, toFrac };
  persistZoomMemory();
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

  // ---- 缩放记忆：恢复上次记忆 + 订阅缩放变化 ----
  try {
    const saved = localStorage.getItem(ZOOM_MEMORY_KEY);
    if (saved) {
      const o = JSON.parse(saved);
      if (typeof o.fromFrac === 'number' && typeof o.toFrac === 'number' && o.toFrac > o.fromFrac) {
        zoomMemory = o;
      }
    }
  } catch {
    // 忽略损坏的记忆数据
  }

  chartInstance.timeScale().subscribeVisibleLogicalRangeChange(onVisibleLogicalRangeChanged);

  // 如果初始为深色模式，应用图表暗色配色
  if (isDarkMode.value) {
    chartInstance.applyOptions({
      layout: {
        background: { color: '#0f172a' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      crosshair: {
        vertLine: { color: '#475569', labelBackgroundColor: '#334155' },
        horzLine: { color: '#475569', labelBackgroundColor: '#334155' },
      },
      timeScale: { borderColor: '#334155' },
      rightPriceScale: { borderColor: '#334155' },
    });
  }

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

    // param.time 为 'YYYY-MM-DD' 字符串格式
    const timeStr = String(param.time);
    const prevClose = findPrevClose(param.time as any);
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

// ================== 设置时间范围 ==================
// 下拉选择时间范围（仅图表缩放，不触发网络请求）
const selectTimeRange = (range: string) => {
  showTimeRangeMenu.value = false;
  setTimeRange(range);
};

const setTimeRange = (range: string) => {
  if (!chartInstance || !klineData.value.length) return;

  activeTimeRange.value = range;

  const data = klineData.value;
  const n = data.length;
  const lastDate = new Date(data[n - 1].time);
  let startDate: Date;

  switch (range) {
    case 'r1m':
      startDate = new Date(lastDate);
      startDate.setMonth(startDate.getMonth() - 1);
      break;
    case 'r3m':
      startDate = new Date(lastDate);
      startDate.setMonth(startDate.getMonth() - 3);
      break;
    case 'r6m':
      startDate = new Date(lastDate);
      startDate.setMonth(startDate.getMonth() - 6);
      break;
    case 'r1y':
      startDate = new Date(lastDate);
      startDate.setFullYear(startDate.getFullYear() - 1);
      break;
    case 'ALL':
    default:
      // 全部：清除缩放记忆，下次 setData 会 fitContent
      zoomMemory = null;
      try { localStorage.removeItem(ZOOM_MEMORY_KEY); } catch {}
      chartInstance.timeScale().fitContent();
      return;
  }

  // 在数据中查找目标起始日期对应的柱子索引（从末尾向前找第一个 <= startDate 的位置）
  // 这样无论日K/周K/月K都能精确定位到正确的柱子
  const startStr = toLocalDateStr(startDate);
  let fromIndex = n - 1;  // 默认从第一根开始
  for (let i = n - 1; i >= 0; i--) {
    if (data[i].time <= startStr) {
      fromIndex = i;
      break;
    }
  }

  // 用逻辑索引设置可见范围（精确到柱子级别，不依赖日期字符串匹配）
  // 同时更新 zoomMemory：这样切换股票/周期时也会按此比例还原
  const toIndex = n - 1;
  if (toIndex - fromIndex >= 1) {
    suppressRangeEvents = true;
    zoomMemory = {
      fromFrac: fromIndex / n,
      toFrac: toIndex / n,
    };
    persistZoomMemory();  // 立即持久化
    chartInstance.timeScale().setVisibleLogicalRange({ from: fromIndex, to: toIndex });
    suppressRangeEvents = false;
  } else {
    // 目标范围太窄（数据不足），显示全部
    zoomMemory = null;
    chartInstance.timeScale().fitContent();
  }
};

// ================== 切换K线周期 ==================
const changePeriod = (period: Period) => {
  if (period === currentPeriod.value) return;
  currentPeriod.value = period;
  // 切换周期后重新拉取K线并重算支撑阻力
  if (currentSymbol.value) {
    handleSearch();
  }
};

// ================== 时间格式转换 ==================
// 日/周/月线统一使用 'YYYY-MM-DD' 字符串格式，lightweight-charts 原生支持
const toChartTime = (timeStr: string): string => timeStr;

// 本地日期格式化：避免 toISOString() 在东八区（本地 0~8 点）把日期回退一天
const toLocalDateStr = (d: Date): string => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
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
  activeTimeRange.value = 'ALL'; // 重置时间范围

  // 记录开始时间，用于保证骨架屏最短展示时长
  const startedAt = performance.now();

  // 接口查询拼接 us 前缀
  const querySymbol = code.startsWith('US') ? code : 'us' + code;

  try {
    let klines: KLinePoint[];

    if (useMockData.value) {
      // 使用测试数据模式
      console.log(`[测试模式] 生成 ${querySymbol} 的模拟K线数据`);
      const basePriceMap: Record<string, number> = {
        'AAPL': 180,
        'NVDA': 450,
        'TSLA': 250,
        'MSFT': 370,
        'GOOGL': 140,
        'AMZN': 175,
        'META': 480,
        'AMD': 160,
        'MU': 130,
        'SNDK': 95,
      };
      const basePrice = basePriceMap[code] || 150;
      // 测试模式也生成"上市以来"的长历史 (约 4500 交易日 ≈ 18 年)，便于直观查看全量K线
      klines = generateMockKLines(code, 4500, basePrice);
    } else {
      // 真实API模式：优先命中缓存，避免重复请求
      const key = cacheKey(querySymbol, currentPeriod.value);
      if (klineCache.has(key)) {
        console.log(`[缓存命中] 直接复用 ${key} 的K线数据`);
        klines = klineCache.get(key)!;
      } else {
        klines = await getKLines(querySymbol, currentPeriod.value);
        if (klines.length > 0) klineCache.set(key, klines);
      }
    }
    
    if (!klines || klines.length === 0) {
      throw new Error('未获取到有效的K线行情数据');
    }

    klineData.value = klines;
    // currentSymbol 保持纯净的无前缀大写代码（如 AAPL），和 UI 对齐
    currentSymbol.value = code;

    // 真实模式下，若日K返回根数过少，提示数据可能不完整
    // (例如 Yahoo 被限流导致后端退回腾讯 ~320 根上限)
    if (!useMockData.value && currentPeriod.value === '1d' && klines.length > 0 && klines.length < 400) {
      dataWarning.value = `⚠️ 当前仅返回 ${klines.length} 根日K线，可能不是该股票的完整历史（数据源被限流或网络异常时会发生）。请稍后重试，或确认后端 Yahoo 数据源可用。`;
    } else {
      dataWarning.value = '';
    }

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
    // 保证骨架屏至少展示 MIN_SKELETON_MS 毫秒，让扫光动画可被感知
    const elapsed = performance.now() - startedAt;
    const remain = Math.max(0, MIN_SKELETON_MS - elapsed);
    if (remain > 0) {
      setTimeout(() => { isLoading.value = false; }, remain);
    } else {
      isLoading.value = false;
    }
  }
};

// ================== SR 联动函数 ==================
const highlightSRLevel = (idx: number, isHover: boolean) => {
  highlightedSR.value = isHover ? idx : null;
  
  // 高亮对应的图表价格线
  if (priceLines[idx]) {
    if (isHover) {
      // 悬停时加粗线条
      priceLines[idx].applyOptions({
        lineWidth: 3,
        lineStyle: 0, // 实线
      });
    } else {
      // 离开时恢复
      priceLines[idx].applyOptions({
        lineWidth: 1.5,
        lineStyle: 2, // 虚线
      });
    }
  }
};

const scrollToSRLevel = (level: SRLevel) => {
  if (!chartInstance) return;
  
  // 将图表滚动到该价位附近
  // 由于 lightweight-charts 没有直接滚动到价位的 API，
  // 我们可以通过设置可见价格范围来实现
  const currentRange = chartInstance.timeScale().getVisibleLogicalRange();
  if (currentRange) {
    // 保持时间范围不变，只是视觉提示
    // 可以通过闪烁效果来提示用户
    const idx = srLevels.value.indexOf(level);
    if (idx >= 0) {
      highlightedSR.value = idx;
      setTimeout(() => {
        highlightedSR.value = null;
      }, 1000);
    }
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
    let res: AnalysisResponse | null;
    
    if (useMockData.value) {
      // 使用前端本地计算引擎
      console.log('[测试模式] 使用前端分析引擎计算支撑阻力位和区间统计');
      const sr_levels = calculateSRLevels(klineData.value, 5, currentPeriod.value);
      const statistics = calculateRangeStats(klineData.value, startDate.value, endDate.value);
      
      res = {
        sr_levels,
        statistics: statistics || {
          max_rise: { pct: 0, start: '', end: '' },
          max_fall: { pct: 0, start: '', end: '' }
        }
      };
    } else {
      // 调用后端API：优先命中缓存
      // 注意: 分析结果里的"区间统计"依赖起止日期，缓存键必须包含日期区间，
      // 否则改了起止日期点"重新计算"会命中旧缓存、返回旧区间的统计(表现为"无反应")。
      // SR 支撑阻力位仅依赖 symbol+period(全量K线)，但键里带上日期只会让其随日期重算(结果一致)，不影响正确性。
      const aKey = `${querySymbol}_${currentPeriod.value}_${startDate.value}_${endDate.value}`;
      if (analysisCache.has(aKey)) {
        console.log(`[缓存命中] 直接复用 ${aKey} 的分析结果`);
        res = analysisCache.get(aKey)!;
      } else {
        res = await getStockAnalysis(querySymbol, startDate.value, endDate.value, klineData.value, currentPeriod.value);
        if (res) analysisCache.set(aKey, res);
      }
    }
    
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
    // 防御：确保按时间严格升序且无重复 time，
    // 否则 lightweight-charts 会渲染错位或对乱序数据报错
    const sorted = [...newData].sort((a, b) =>
      a.time < b.time ? -1 : a.time > b.time ? 1 : 0
    );
    const seen = new Set<string>();
    const clean = sorted.filter(d => {
      if (seen.has(d.time)) return false;
      seen.add(d.time);
      return true;
    });

    candlestickSeries.setData(clean.map(d => ({
      time: toChartTime(d.time),
      open: d.open,
      close: d.close,
      high: d.high,
      low: d.low,
    })));

    volumeSeries.setData(clean.map(d => ({
      time: toChartTime(d.time),
      value: d.volume,
      color: d.close >= d.open ? 'rgba(13, 148, 136, 0.2)' : 'rgba(225, 29, 72, 0.2)'
    })));

    // 恢复记忆的缩放比例：鼠标滚轮缩放 / 日期范围选择都会被记忆，
    // 并在切换股票、周期、数据模式时按比例还原，保持用户当前视角。
    const n = clean.length;
    if (zoomMemory && n > 1) {
      const from = zoomMemory.fromFrac * n;
      const to = zoomMemory.toFrac * n;
      if (to - from >= 1) {
        suppressRangeEvents = true;
        chartInstance?.timeScale().setVisibleLogicalRange({ from, to });
        suppressRangeEvents = false;
      } else {
        chartInstance?.timeScale().fitContent();
      }
    } else {
      chartInstance?.timeScale().fitContent();
    }
  }
});

// 切换测试/真实数据模式时，若已加载股票则自动重新拉取并重算
watch(useMockData, () => {
  if (currentSymbol.value) {
    console.log(`[模式切换] 切换到 ${useMockData.value ? '测试模式' : '真实数据模式'}，重新加载 ${currentSymbol.value}`);
    handleSearch();
  }
});

onMounted(() => {
  loadWatchlist();
  initDarkMode(); // 初始化深色模式

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
    // 窗口大小变化时不需要调整侧边栏宽度，它们有固定最小值
  });

  // 全局键盘快捷键
  window.addEventListener('keydown', handleGlobalKeydown);
  // 点击外部关闭时间范围下拉菜单
  document.addEventListener('click', handleClickOutside);
});

// 点击非下拉菜单区域时关闭菜单
const handleClickOutside = (e: MouseEvent) => {
  if (!showTimeRangeMenu.value) return;
  const target = e.target as HTMLElement;
  if (!target.closest('.relative')) {
    showTimeRangeMenu.value = false;
  }
};

// 全局键盘快捷键处理
const handleGlobalKeydown = (e: KeyboardEvent) => {
  // 忽略输入框内的按键
  const target = e.target as HTMLElement;
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

  // Ctrl+K / Cmd+K: 聚焦搜索框
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    const searchInput = document.querySelector('input[placeholder="搜索股票代码/名称"]') as HTMLInputElement;
    if (searchInput) searchInput.focus();
  }
  
  // R: 触发分析重算
  if (e.key === 'r' || e.key === 'R') {
    if (klineData.value.length > 0) {
      handleReCalculate();
    }
  }
};

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.timeScale().unsubscribeVisibleLogicalRangeChange(onVisibleLogicalRangeChanged);
    chartInstance.remove();
    chartInstance = null;
  }
  clearTimeout(searchDebounceTimer);
  window.removeEventListener('keydown', handleGlobalKeydown);
  document.removeEventListener('click', handleClickOutside);
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

/* 时间范围菜单过渡 */
.fade-scale-enter-active,
.fade-scale-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.fade-scale-enter-from,
.fade-scale-leave-to {
  opacity: 0;
  transform: scale(0.95) translateY(-4px);
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

/* ========== 骨架屏 shimmer 动画 ========== */
.skeleton {
  position: relative;
  overflow: hidden;
  background-color: #e2e8f0; /* slate-200 */
}
.dark .skeleton {
  background-color: #334155; /* slate-700 */
}
.skeleton::after {
  content: '';
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0) 0%,
    rgba(255, 255, 255, 0.55) 50%,
    rgba(255, 255, 255, 0) 100%
  );
  animation: skeleton-shimmer 1.5s ease-in-out infinite;
}
.dark .skeleton::after {
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0) 0%,
    rgba(255, 255, 255, 0.10) 50%,
    rgba(255, 255, 255, 0) 100%
  );
}
@keyframes skeleton-shimmer {
  100% {
    transform: translateX(100%);
  }
}
</style>
