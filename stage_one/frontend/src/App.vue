<template>
  <div
    class="flex flex-col flex-1 h-screen overflow-hidden bg-[#f8fafc] dark:bg-slate-900 text-slate-800 dark:text-slate-200 subpixel-antialiased font-sans select-none">

    <!-- 全局常驻风险提示：免费公开行情源存在刷新延迟，不构成任何投资交易依据 -->
    <div
      class="shrink-0 bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-[11px] font-medium px-4 py-1.5 flex items-center justify-center gap-2 text-center border-b border-amber-200/60 dark:border-amber-700/40">
      <svg class="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <span>本软件使用免费公开行情源，数据存在刷新延迟，不构成任何投资交易依据，请勿用于实盘交易。</span>
    </div>

    <!-- 浏览器风格导航栏 -->
    <header class="h-12 bg-white dark:bg-slate-800 border-b border-slate-200/60 dark:border-slate-700/60 px-3 flex items-center gap-2 shrink-0 z-[60]">
      <!-- 左：导航按钮 -->
      <div class="flex items-center gap-0.5 shrink-0">
        <button @click="navBack()" :disabled="navBackHistory.length === 0"
          class="p-1.5 rounded-md hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-25 disabled:cursor-not-allowed transition-colors cursor-pointer" title="后退">
          <svg class="w-4 h-4 text-slate-500 dark:text-slate-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>
        </button>
        <button @click="navForward()" :disabled="navForwardHistory.length === 0"
          class="p-1.5 rounded-md hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-25 disabled:cursor-not-allowed transition-colors cursor-pointer" title="前进">
          <svg class="w-4 h-4 text-slate-500 dark:text-slate-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
        </button>
        <button @click="refreshCurrent()"
          class="p-1.5 rounded-md hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors cursor-pointer" title="刷新行情">
          <svg class="w-4 h-4 text-slate-500 dark:text-slate-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
        </button>
      </div>

      <!-- 中：全局证券搜索（系统入口） -->
      <div class="flex-1 min-w-0 max-w-md">
        <GlobalSecuritySearch
          :watchlist="watchlist"
          :placeholder="searchPlaceholder"
          @select="selectSuggestion"
          @add-watch="toggleWatchlist"
        />
      </div>

      <!-- 右：当前标的摘要 + 控制 -->
      <div class="flex items-center gap-2 shrink-0">
        <template v-if="currentSymbol">
          <div class="flex items-center gap-1.5">
            <span class="text-sm font-bold text-slate-800 dark:text-slate-200">{{ formatSymbol(currentSymbol) }}</span>
            <span class="text-[9px] px-1 py-px rounded bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400">{{ MARKET_LABEL[marketOf(currentSymbol) || 'us'] }}</span>
          </div>
          <div v-if="displayPrice != null" class="flex items-center gap-1.5 pl-1.5 border-l border-slate-200/60 dark:border-slate-600/60">
            <span class="text-sm font-bold font-mono tabular-nums"
              :class="displayChange >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'">
              {{ currencyOf(currentSymbol) }}{{ displayPrice.toFixed(2) }}
            </span>
            <span class="text-[10px] font-semibold px-1 py-px rounded"
              :class="displayChange >= 0 ? 'bg-emerald-500 text-white' : 'bg-red-500 text-white'">
              {{ displayChange >= 0 ? '+' : '' }}{{ displayChange.toFixed(2) }}%
            </span>
          </div>
          <button @click="toggleWatchlist(currentSymbol)"
            class="p-1 rounded-md hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors cursor-pointer"
            :title="isWatchlisted(currentSymbol) ? '取消自选' : '加入自选'">
            <svg class="w-4 h-4" :class="isWatchlisted(currentSymbol) ? 'text-amber-400 fill-amber-400' : 'text-slate-300 fill-none'"
              xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M11.48 3.499c.174-.383.72-.383.894 0l2.64 5.352 5.9 1.15c.422.082.59.59.282.895l-4.244 4.14 1.002 5.86c.071.423-.372.746-.75.545l-5.267-2.77-5.268 2.77c-.378.201-.821-.122-.75-.545l1.002-5.86-4.244-4.14c-.308-.305-.14-.813.282-.895l5.9-1.15 2.64-5.352z" />
            </svg>
          </button>
        </template>
        <!-- 数据模式 -->
        <span class="flex items-center gap-1 text-[10px] font-medium cursor-help"
          :class="useMockData ? 'text-amber-500' : 'text-emerald-500'"
          :title="useMockData ? '纯前端随机数据生成' : delayFullOf(currentSymbol)">
          <span class="w-1.5 h-1.5 rounded-full" :class="useMockData ? 'bg-amber-400' : 'bg-emerald-400'"></span>
          {{ useMockData ? '演示' : '实时' }}
          <span v-if="!useMockData" class="text-[9px] text-slate-400 dark:text-slate-500">({{ delayLabelOf(currentSymbol) }})</span>
        </span>
        <!-- 深色模式 -->
        <button @click="toggleDarkMode()"
          class="p-1.5 rounded-md hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors cursor-pointer"
          :title="isDarkMode ? '切换到浅色模式' : '切换到深色模式'">
          <svg class="w-4 h-4" :class="isDarkMode ? 'text-amber-400' : 'text-slate-400'"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path v-if="!isDarkMode" stroke-linecap="round" stroke-linejoin="round"
              d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            <path v-else stroke-linecap="round" stroke-linejoin="round"
              d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
          </svg>
        </button>
      </div>
    </header>

    <!-- 主交互区域 -->
    <main class="flex-1 flex overflow-hidden relative min-h-0 bg-white dark:bg-slate-900">

      <!-- 降级/错误提示横幅 -->
      <transition name="fade">
        <div v-if="errorMsg"
          class="absolute top-4 left-1/2 -translate-x-1/2 z-20 bg-amber-50 border border-amber-200/60 text-amber-800 px-4 py-3 rounded-xl text-xs font-medium shadow-lg flex items-center gap-2 max-w-md animate-shake">
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

      <!-- 左侧边栏：自选股列表 -->
      <aside
        :style="{ width: leftSidebarWidth + 'px' }"
        class="bg-white dark:bg-slate-800 border-r border-slate-200/60 dark:border-slate-700/60 flex flex-col shrink-0 overflow-y-auto scrollbar-thin">

        <!-- 自选分组 -->
        <div class="flex-1 overflow-y-auto">
          <!-- 顶部固定：标题 + 分组切换 Tab 栏 + 市场 Tab 栏 -->
          <div class="sticky top-0 z-20 bg-white dark:bg-slate-800 border-b border-slate-100/80 dark:border-slate-700/60">
            <!-- 标题栏 -->
            <div class="px-4 pt-2.5 pb-1 flex items-center justify-between">
              <h3 class="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-2">
                <span>自选</span>
                <span class="text-[10px] font-normal text-slate-400 normal-case">{{ filteredWatchlist.length }} / {{ watchlist.length }}</span>
              </h3>
            </div>

            <!-- 分组切换 Tab 栏 (平铺核心 + 下拉分组) -->
            <div class="px-4 py-1.5 flex items-center gap-2 border-b border-slate-100/60 dark:border-slate-700/40">
              <!-- 全部 Tab -->
              <button @click="activeGroupId = 'all'"
                class="px-2.5 py-1 text-xs rounded-md transition-all cursor-pointer font-medium"
                :class="activeGroupId === 'all'
                  ? 'bg-slate-100 dark:bg-slate-700 text-teal-600 dark:text-teal-400 border border-slate-200/50 dark:border-slate-600/50'
                  : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'">
                全部
              </button>
              
              <!-- 特别关注 Tab (第一个分组) -->
              <button v-if="watchGroups.length > 0"
                @click="activeGroupId = watchGroups[0].id"
                class="px-2.5 py-1 text-xs rounded-md transition-all cursor-pointer font-medium truncate max-w-20"
                :class="activeGroupId === watchGroups[0].id
                  ? 'bg-slate-100 dark:bg-slate-700 text-teal-600 dark:text-teal-400 border border-slate-200/50 dark:border-slate-600/50'
                  : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'"
                :title="watchGroups[0].name">
                {{ watchGroups[0].name }}
              </button>

              <!-- 其他分组下拉框 -->
              <div class="relative group-dropdown-container flex-1">
                <button @click="toggleGroupDropdown"
                  class="w-full flex items-center justify-between gap-1 px-2 py-1 border border-slate-200 dark:border-slate-700 rounded-md text-xs font-medium bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600 cursor-pointer">
                  <span class="truncate">{{ activeGroupName }}</span>
                  <svg class="w-3 h-3 shrink-0 text-slate-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
                  </svg>
                </button>
                <transition name="dropdown">
                  <div v-if="showGroupDropdown"
                    class="absolute left-0 top-full mt-1 w-52 max-h-80 overflow-y-auto bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-xl z-50 animate-fade-in-down py-1">
                    <!-- 列出已有的分组名 -->
                    <div class="max-h-56 overflow-y-auto">
                      <button v-for="g in watchGroups" :key="g.id"
                        @click="selectGroup(g.id)"
                        class="w-full text-left px-3 py-2 text-xs text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700/60 transition-colors flex items-center justify-between">
                        <span class="truncate pr-2">{{ g.name }}</span>
                        <span class="text-[9px] text-slate-400 shrink-0">({{ g.stocks.length }})</span>
                      </button>
                    </div>
                    
                    <!-- 底部分割线和操作入口 -->
                    <div class="border-t border-slate-100 dark:border-slate-700/80 mt-1 pt-1">
                      <button @click="triggerCreateGroup"
                        class="w-full text-left px-3 py-1.5 text-xs text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700/60 transition-colors flex items-center gap-1.5 font-medium cursor-pointer">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
                        </svg>
                        创建分组
                      </button>
                      <button @click="triggerManageGroups"
                        class="w-full text-left px-3 py-1.5 text-xs text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700/60 transition-colors flex items-center gap-1.5 font-medium cursor-pointer">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                        </svg>
                        分组管理
                      </button>
                    </div>
                  </div>
                </transition>
              </div>
            </div>
            <!-- 市场 Tab 栏 -->
            <div class="flex items-center gap-1 px-3 pb-2.5">
              <button v-for="t in MARKET_TABS" :key="t.key" @click="activeMarketTab = t.key"
                class="flex-1 text-xs font-semibold py-1 rounded-md border transition-all cursor-pointer"
                :class="activeMarketTab === t.key
                  ? 'border-teal-500 text-teal-600 bg-teal-50 dark:bg-teal-900/30 dark:text-teal-300'
                  : 'border-slate-200 dark:border-slate-600 text-slate-500 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-500'">
                {{ t.label }}
              </button>
            </div>
          </div>

          <!-- 排序表头：点击 名称代码 / 最新价 / 涨跌幅 切换升降序 -->
          <div
            class="flex items-center px-4 py-1.5 bg-white dark:bg-slate-800 border-b border-slate-100/80 dark:border-slate-700/60 text-[10px] font-semibold text-slate-400 select-none">
            <button @click="setSort('name')"
              class="flex-1 text-left flex items-center gap-0.5 transition-colors cursor-pointer"
              :class="sortBy === 'name' ? 'text-teal-600 dark:text-teal-400' : 'hover:text-slate-600 dark:hover:text-slate-200'">
              名称代码
              <span v-if="sortBy === 'name'" class="text-[9px]">{{ sortDir === 'asc' ? '↑' : '↓' }}</span>
            </button>
            <div class="flex items-center gap-2 shrink-0">
              <button @click="setSort('price')"
                class="text-right transition-colors cursor-pointer"
                :class="sortBy === 'price' ? 'text-teal-600 dark:text-teal-400' : 'hover:text-slate-600 dark:hover:text-slate-200'">
                最新价
                <span v-if="sortBy === 'price'" class="text-[9px]">{{ sortDir === 'asc' ? '↑' : '↓' }}</span>
              </button>
              <button @click="setSort('change')"
                class="text-right min-w-[42px] transition-colors cursor-pointer"
                :class="sortBy === 'change' ? 'text-teal-600 dark:text-teal-400' : 'hover:text-slate-600 dark:hover:text-slate-200'">
                涨跌幅
                <span v-if="sortBy === 'change'" class="text-[9px]">{{ sortDir === 'asc' ? '↑' : '↓' }}</span>
              </button>
            </div>
          </div>

          <!-- 测试模式警告条 -->
          <div v-if="useMockData && watchlist.length"
            class="px-4 py-1.5 bg-amber-50/80 dark:bg-amber-900/20 border-b border-amber-200/60 dark:border-amber-700/40">
            <p class="text-[10px] text-amber-600 dark:text-amber-400 font-medium flex items-center gap-1">
              <svg class="w-3 h-3 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
              </svg>
              模拟数据，非真实行情
            </p>
          </div>

          <!-- 空状态 -->
          <div v-if="!sortedFilteredWatchlist.length"
            class="p-8 text-center text-xs text-slate-400">
            <!-- 1. 当前激活分组为空分组的情况 (图3样式) -->
            <div v-if="isCurrentGroupEmpty" class="py-12 flex flex-col items-center">
              <svg class="w-12 h-12 text-slate-300 dark:text-slate-600 mb-2" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-19.5 0A2.25 2.25 0 004.5 15h15a2.25 2.25 0 002.25-2.25m-19.5 0v.25A2.25 2.25 0 004.5 17.5h15a2.25 2.25 0 002.25-2.25V12.75" />
              </svg>
              <div class="text-xs text-slate-400 dark:text-slate-500 mb-1">暂无数据</div>
              <button @click="showSearchModal = true; nextTick(() => { modalSearchInputRef?.focus(); })" 
                class="text-xs text-blue-500 hover:text-blue-600 hover:underline cursor-pointer font-medium bg-transparent border-0 p-0">添加自选</button>
            </div>
            <!-- 2. 普通无任何自选股情况 -->
            <div v-else-if="!watchlist.length" class="py-12">
              <svg class="w-10 h-10 mx-auto mb-2 text-slate-300" xmlns="http://www.w3.org/2000/svg" fill="none"
                viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round"
                  d="M11.48 3.499c.174-.383.72-.383.894 0l2.64 5.352 5.9 1.15c.422.082.59.59.282.895l-4.244 4.14 1.002 5.86c.071.423-.372.746-.75.545l-5.267-2.77-5.268 2.77c-.378.201-.821-.122-.75-.545l1.002-5.86-4.244-4.14c-.308-.305-.14-.813.282-.895l5.9-1.15 2.64-5.352z" />
              </svg>
              <p>暂无自选股</p>
              <p class="mt-1 text-[10px] text-slate-400">在图表区点击星标添加</p>
            </div>
            <!-- 3. 条件过滤后的空结果 -->
            <div v-else class="py-12">
              <p>当前筛选条件下没有标的</p>
            </div>
          </div>

          <!-- 过滤后的自选列表（扁平 + 市场Tab/分组交集筛选 + 表头排序） -->
          <transition-group v-if="sortedFilteredWatchlist.length" name="list" tag="div" class="divide-y divide-slate-100/80 dark:divide-slate-700/60">
            <div v-for="item in sortedFilteredWatchlist" :key="item" @click="selectWatchlist(item)"
              class="group px-4 py-2.5 hover:bg-slate-50 dark:hover:bg-slate-700 cursor-pointer transition-all"
              :class="currentSymbol === item ? 'bg-teal-50/60 dark:bg-teal-900/20 border-l-2 border-teal-500' : 'border-l-2 border-transparent'">
              <div class="flex items-center justify-between gap-3">
                <!-- 左侧：名称 + 星标 + 代码 + 市场标签 -->
                <div class="flex-1 min-w-0 overflow-hidden">
                  <div class="flex items-center gap-1.5 mb-0.5 min-w-0">
                    <span class="font-bold text-sm text-slate-900 dark:text-slate-100 truncate min-w-0">{{ getStockName(item) }}</span>
                    <button @click.stop="toggleWatchlist(item)" class="shrink-0 cursor-pointer"
                      :title="isWatchlisted(item) ? '取消自选' : '加入自选'">
                      <svg class="w-3.5 h-3.5" :class="isWatchlisted(item) ? 'text-amber-400 fill-amber-400' : 'text-slate-300 dark:text-slate-600'"
                        fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499c.174-.383.72-.383.894 0l2.64 5.352 5.9 1.15c.422.082.59.59.282.895l-4.244 4.14 1.002 5.86c.071.423-.372.746-.75.545l-5.267-2.77-5.268 2.77c-.378.201-.821-.122-.75-.545l1.002-5.86-4.244-4.14c-.308-.305-.14-.813.282-.895l5.9-1.15 2.64-5.352z" />
                      </svg>
                    </button>
                  </div>
                  <div class="flex items-center gap-1.5 min-w-0">
                    <span class="text-[11px] text-slate-500 dark:text-slate-400 font-mono">{{ formatSymbol(item) }}</span>
                    <span class="text-[9px] px-1 rounded bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400">{{ MARKET_LABEL[marketOf(item) || 'us'] }}</span>
                  </div>
                </div>
                <!-- 右侧：最新价（涨绿跌红）+ 辅助行情信息（盘后/昨收）+ 涨跌百分比色块 -->
                <div class="flex items-center gap-2 shrink-0">
                  <div class="text-right">
                    <div v-if="watchPriceInfo(item).loading" class="h-4 w-14 bg-slate-200 dark:bg-slate-600 rounded animate-pulse"></div>
                    <template v-else-if="watchPriceInfo(item).price != null">
                      <!-- 第一行：当前价格（主信息） -->
                      <div class="text-sm font-bold font-mono tabular-nums leading-tight"
                        :class="watchPriceInfo(item).change! >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'">
                        {{ currencyOf(item) }}{{ watchPriceInfo(item).price!.toFixed(2) }}
                      </div>
                      <!-- 第二行：辅助行情信息（扩展交易时段 / 昨收） -->
                      <div v-if="secondaryLineInfo(item)"
                        class="flex items-center justify-end gap-1 text-[10px] font-mono tabular-nums leading-tight text-slate-500 dark:text-slate-400">
                        <span :class="secondaryLineInfo(item)!.changePct != null
                          ? (secondaryLineInfo(item)!.changePct! >= 0 ? 'text-emerald-500/70 dark:text-emerald-400/70' : 'text-red-500/70 dark:text-red-400/70')
                          : ''">
                          {{ secondaryLineInfo(item)!.price!.toFixed(2) }}
                          <template v-if="secondaryLineInfo(item)!.changePct != null">
                            {{ secondaryLineInfo(item)!.changePct! >= 0 ? '+' : '' }}{{ secondaryLineInfo(item)!.changePct!.toFixed(2) }}%
                          </template>
                        </span>
                        <span class="text-[9px] px-1 rounded bg-slate-100 dark:bg-slate-700/60 text-slate-400 dark:text-slate-500 leading-tight">
                          {{ secondaryLineInfo(item)!.label }}
                        </span>
                      </div>
                    </template>
                    <span v-else class="text-sm text-slate-400">--</span>
                  </div>
                  <!-- 右侧涨跌百分比色块（涨绿跌红，白底白字） -->
                  <div v-if="watchPriceInfo(item).change != null && !watchPriceInfo(item).loading"
                    class="text-[11px] font-bold px-1.5 py-1 rounded leading-none text-white min-w-[42px] text-center"
                    :class="watchPriceInfo(item).change! >= 0 ? 'bg-emerald-500' : 'bg-red-500'">
                    {{ watchPriceInfo(item).change! >= 0 ? '+' : '' }}{{ watchPriceInfo(item).change!.toFixed(2) }}%
                  </div>
                </div>
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
        <div class="h-9 flex items-center justify-between px-3 border-b border-slate-100/80 dark:border-slate-700/60 bg-slate-50/30 dark:bg-slate-800/30 shrink-0">
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
              <div v-if="showTimeRangeMenu" class="absolute right-0 top-full mt-1 z-50 min-w-[90px] bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200/60 dark:border-slate-600/60 py-1">
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
          class="px-4 py-2 bg-amber-50/80 dark:bg-amber-900/20 border-b border-amber-200/60 dark:border-amber-800/60 text-amber-700 dark:text-amber-300 text-xs font-medium flex items-center gap-2">
          <span>⚠️</span><span>{{ dataWarning }}</span>
        </div>

        <!-- 实际图表绑定节点 -->
        <div ref="chartArea" class="flex-1 relative min-w-0 bg-white dark:bg-slate-900">
          <div ref="chartContainer" class="absolute inset-0 w-full h-full transition-opacity duration-300"
            :class="{ 'opacity-50': isLoading }"></div>

          <!-- 自定义K线悬停提示框 -->
          <div v-show="tooltipVisible" ref="tooltipEl"
            class="absolute z-40 pointer-events-none bg-white/95 dark:bg-slate-800/95 backdrop-blur-sm border border-slate-200/60 dark:border-slate-700/60 rounded-xl shadow-xl py-3 px-4 text-xs font-mono animate-tooltip-in"
            :style="tooltipStyle">
            <!-- 日期 -->
            <div class="text-slate-400 dark:text-slate-500 mb-2 pb-2 border-b border-slate-100/80 dark:border-slate-700/60 font-sans text-[11px] font-semibold">
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
                <span class="font-semibold" :class="tooltipData.change >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'">
                  {{ tooltipData.close }}
                </span>
              </div>
            </div>
            <!-- 分隔 -->
            <div class="my-2 border-t border-slate-100/80 dark:border-slate-700/60"></div>
            <!-- 涨跌 & 振幅 -->
            <div class="space-y-1">
              <div class="flex justify-between gap-4 items-center">
                <span class="text-slate-400 dark:text-slate-500">涨跌幅</span>
                <span class="font-semibold text-xs px-1.5 py-0.5 rounded"
                  :class="tooltipData.change >= 0 ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400' : 'bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400'">
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
        class="bg-white dark:bg-slate-800 border-l border-slate-200/60 dark:border-slate-700/60 flex flex-col shrink-0 overflow-hidden">

        <!-- Tab 导航 -->
        <div class="flex border-b border-slate-200/60 dark:border-slate-700/60 bg-slate-50/50 dark:bg-slate-800/50 shrink-0">
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
            <div class="p-5 border-b border-slate-100/80 dark:border-slate-700/60">
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

            <!-- 快捷区间 -->
            <div class="flex flex-wrap gap-1.5 mb-3">
              <button
                v-for="p in rangePresets"
                :key="p.value"
                type="button"
                @click="applyRangePreset(p.value)"
                :class="[
                  'px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition-all active:scale-[0.97] cursor-pointer',
                  isPresetActive(p.value)
                    ? 'border-teal-500 bg-teal-50 dark:bg-teal-900/40 text-teal-700 dark:text-teal-300'
                    : 'border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-500',
                ]"
              >
                {{ p.label }}
              </button>
            </div>

            <!-- 时间选择表单（自定义丝滑日期选择器） -->
            <div class="mb-4">
              <DateRangePicker
                v-model:modelStart="inputStartDate"
                v-model:modelEnd="inputEndDate"
                :min-date="klineData.length ? klineData[0].time : ''"
                :max-date="klineData.length ? klineData[klineData.length - 1].time : ''"
              />
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
                class="bg-emerald-50/50 dark:bg-emerald-900/30 border border-emerald-100 dark:border-emerald-700 rounded-xl p-3.5 transition-all hover:shadow-md hover:-translate-y-0.5 hover:border-emerald-200 dark:hover:border-emerald-600 group">
                <div class="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400 font-bold text-xs mb-1">
                  <svg class="w-4 h-4 transition-transform group-hover:-translate-y-1" xmlns="http://www.w3.org/2000/svg"
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                  <span>最大连贯上涨</span>
                </div>
                <div class="text-lg font-extrabold text-emerald-600 dark:text-emerald-400 font-mono number-animate">
                  +{{ animatedRisePct.toFixed(2) }}%
                </div>
                <div class="text-[10px] text-slate-400 dark:text-slate-500 mt-1 font-medium font-mono">
                  {{ rangeStats.max_rise.start }} &rarr; {{ rangeStats.max_rise.end }}
                </div>
              </div>

              <!-- 下跌 -->
              <div
                class="bg-red-50/50 dark:bg-red-900/30 border border-red-100 dark:border-red-700 rounded-xl p-3.5 transition-all hover:shadow-md hover:-translate-y-0.5 hover:border-red-200 dark:hover:border-red-600 group">
                <div class="flex items-center gap-1.5 text-red-700 dark:text-red-400 font-bold text-xs mb-1">
                  <svg class="w-4 h-4 transition-transform group-hover:translate-y-1" xmlns="http://www.w3.org/2000/svg"
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M13 17h8m0 0v-8m0 8l-8-8-4 4-6-6" />
                  </svg>
                  <span>最大连贯下跌</span>
                </div>
                <div class="text-lg font-extrabold text-red-600 dark:text-red-400 font-mono number-animate">
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
    <footer class="h-7 bg-slate-50 dark:bg-slate-800/50 text-slate-500 dark:text-slate-400 text-[10px] flex items-center justify-between px-4 shrink-0 border-t border-slate-200/60 dark:border-slate-700/40">
      <div class="flex items-center gap-4">
        <span class="flex items-center gap-1">
          <span class="w-1.5 h-1.5 rounded-full" :class="useMockData ? 'bg-amber-400' : 'bg-green-400'"></span>
          {{ useMockData ? '演示模式 (模拟数据)' : '实时数据 (后端)' }}
        </span>
        <button v-if="useMockData" @click="retryConnection()"
          class="text-slate-400 hover:text-teal-400 transition-colors underline-offset-2 hover:underline">
          后端已启动？重试连接
        </button>
        <!-- 实时刷新状态：当前标的刷新周期 / 上次请求时间 / 接口状态 -->
        <span v-if="!useMockData && currentSymbol" class="flex items-center gap-1.5 font-mono">
          <span class="w-1.5 h-1.5 rounded-full"
            :class="quoteEngineStatus.cooling ? 'bg-orange-400 animate-pulse' : 'bg-teal-400'"></span>
          <span :class="quoteEngineStatus.cooling ? 'text-orange-400' : 'text-teal-400'">
            {{ quoteEngineStatus.cooling ? '接口限流冷却中' : '接口正常' }}
          </span>
          <span class="text-slate-500">· 刷新 {{ currentRefreshCycle }}s</span>
          <span class="text-slate-500">· 上次请求 {{ lastRequestText }}</span>
        </span>
        <span v-if="currentSymbol">{{ formatSymbol(currentSymbol) }} · {{ klineData.length }} 根K线</span>
      </div>
      <div class="flex items-center gap-4">
        <span>自选股: {{ watchlist.length }} 只</span>
        <span>Ctrl+K 搜索 | R 重算</span>
      </div>
    </footer>

    <!-- 模态框组 (Modals) -->
    
    <!-- 1. 添加自选分组 Modal (图二样式) -->
    <transition name="fade">
      <div v-if="showCreateGroupModal" 
        class="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm"
        @click.self="showCreateGroupModal = false">
        <div class="bg-white dark:bg-slate-800 rounded-xl p-5 w-80 shadow-2xl border border-slate-200 dark:border-slate-700 animate-scale-up animate-fade-in-down">
          <div class="flex justify-between items-center mb-4">
            <h3 class="text-sm font-bold text-slate-800 dark:text-slate-200">添加自选分组</h3>
            <button @click="showCreateGroupModal = false" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 font-bold cursor-pointer text-lg">&times;</button>
          </div>
          <div class="mb-5">
            <label class="block text-xs text-slate-400 dark:text-slate-500 mb-1">名称</label>
            <input v-model="newGroupNameInput" ref="createGroupInputRef" type="text" placeholder="请输入分组名称"
              class="w-full px-3 py-2 bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-teal-500"
              @keydown.enter="handleCreateGroupSubmit" />
          </div>
          <div class="flex justify-end gap-2">
            <button @click="showCreateGroupModal = false" class="px-4 py-1.5 rounded-lg text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600 transition-colors cursor-pointer">取消</button>
            <button @click="handleCreateGroupSubmit" class="px-4 py-1.5 rounded-lg text-xs bg-slate-900 hover:bg-slate-800 text-white dark:bg-teal-600 dark:hover:bg-teal-500 dark:text-white transition-colors cursor-pointer">确定</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 2. 分组管理 Modal -->
    <transition name="fade">
      <div v-if="showManageGroupsModal"
        class="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm"
        @click.self="showManageGroupsModal = false">
        <div class="bg-white dark:bg-slate-800 rounded-xl p-5 w-96 shadow-2xl border border-slate-200 dark:border-slate-700 animate-scale-up animate-fade-in-down">
          <div class="flex justify-between items-center mb-4">
            <h3 class="text-sm font-bold text-slate-800 dark:text-slate-200">分组管理</h3>
            <button @click="showManageGroupsModal = false" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 font-bold cursor-pointer text-lg">&times;</button>
          </div>
          
          <div class="max-h-60 overflow-y-auto mb-4 divide-y divide-slate-100 dark:divide-slate-700/50">
            <div v-if="!watchGroups.length" class="py-8 text-center text-xs text-slate-400">暂无自定义分组</div>
            <div v-for="g in watchGroups" :key="g.id" class="py-2.5 flex items-center justify-between gap-3">
              <!-- 非编辑状态 -->
              <div v-if="editingGroupId !== g.id" class="flex-1 truncate text-sm text-slate-700 dark:text-slate-200 font-medium">
                {{ g.name }} <span class="text-xs font-normal text-slate-400 dark:text-slate-500">({{ g.stocks.length }} 只股票)</span>
              </div>
              <!-- 编辑状态 -->
              <input v-else v-model="editingGroupName" ref="manageRenameInputRef" type="text"
                class="flex-1 px-2 py-1 bg-slate-50 dark:bg-slate-700 border border-teal-500 rounded text-sm text-slate-800 dark:text-slate-100 focus:outline-none"
                @keydown.enter="confirmRename(g.id)" @blur="confirmRename(g.id)" />
                
              <div class="flex items-center gap-1.5 shrink-0">
                <button v-if="editingGroupId !== g.id" @click="editingGroupId = g.id; editingGroupName = g.name" class="text-xs text-teal-600 hover:text-teal-700 dark:text-teal-400 dark:hover:text-teal-300 cursor-pointer">重命名</button>
                <button v-else @click="confirmRename(g.id)" class="text-xs text-teal-600 hover:text-teal-700 dark:text-teal-400 dark:hover:text-teal-300 cursor-pointer">保存</button>
                
                <button @click="deleteGroup(g.id)" class="text-xs text-rose-500 hover:text-rose-600 cursor-pointer">删除</button>
              </div>
            </div>
          </div>
          
          <div class="flex justify-end">
            <button @click="showManageGroupsModal = false" class="px-4 py-1.5 rounded-lg text-xs bg-slate-900 text-white dark:bg-teal-600 hover:opacity-90 transition-all cursor-pointer font-medium">完成</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 3. 添加自选搜索 Modal -->
    <transition name="fade">
      <div v-if="showSearchModal"
        class="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm"
        @click.self="showSearchModal = false">
        <div class="bg-white dark:bg-slate-800 rounded-xl w-full max-w-md shadow-2xl border border-slate-200 dark:border-slate-700 overflow-hidden animate-scale-up animate-fade-in-down">
          <div class="p-3 border-b border-slate-100 dark:border-slate-700/80 flex items-center gap-2">
            <svg class="w-4 h-4 text-slate-400 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input v-model="modalSearchQuery" ref="modalSearchInputRef" type="text" placeholder="输入代码 / 名称 / 拼音添加标的"
              class="flex-1 bg-transparent text-sm text-slate-800 dark:text-slate-100 focus:outline-none placeholder-slate-400"
              @input="handleModalSearchInput" autocomplete="off" />
            <button @click="showSearchModal = false" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 font-bold cursor-pointer text-lg">&times;</button>
          </div>
          <!-- 搜索结果列表 -->
          <div class="max-h-64 overflow-y-auto">
            <div v-if="modalSearchLoading" class="px-4 py-8 text-center text-xs text-slate-400">搜索中…</div>
            <div v-else-if="modalSearchQuery.trim() && !modalSearchResults.length" class="px-4 py-8 text-center text-xs text-slate-400">未找到匹配标的</div>
            <div v-else-if="!modalSearchQuery.trim()" class="px-4 py-6 text-center text-xs text-slate-400">输入关键词开始搜索</div>
            <div v-else>
              <button v-for="r in modalSearchResults" :key="r.symbol" @click="handleModalSearchSelect(r.symbol)"
                class="w-full text-left px-4 py-2.5 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-700/50 border-b border-slate-100 dark:border-slate-700/40 last:border-0 cursor-pointer">
                <div class="flex items-center gap-2">
                  <span class="text-[9px] px-1 rounded bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 font-mono w-14 text-center">{{ formatSymbol(r.symbol) }}</span>
                  <span class="text-sm font-medium text-slate-800 dark:text-slate-100">{{ r.name }}</span>
                </div>
                <span class="text-xs text-teal-600 dark:text-teal-400 hover:underline">点击添加</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch, computed } from 'vue';
import { createChart, CandlestickSeries, HistogramSeries, createSeriesMarkers } from 'lightweight-charts';
import type { IChartApi } from 'lightweight-charts';
import GlobalSecuritySearch from './components/GlobalSecuritySearch.vue';
import { getKLines, getStockAnalysis, searchStocks, generateMockKLines, getWatchlist, saveWatchlist, SUPPORTED_PERIODS, PERIOD_LABELS, BASE_URL, normalizeSymbol, stripPrefix, marketOf, formatSymbol, MARKET_LABEL } from './utils/api';
import type { KLinePoint, SRLevel, AnalysisResponse, Period, WatchGroup } from './utils/api';
import { getChartOptions } from './utils/chartUtils';
import { calculateSRLevels, calculateRangeStats, resampleMockKLines } from './utils/mockEngine';
import DateRangePicker from './components/DateRangePicker.vue';
// 实时行情引擎（多市场：美股/A股/港股），负责分层刷新与限流防护
import { quoteEngine, type Quote, type SymbolMeta, type QuoteConfig } from './utils/quote';

const symbolInput = ref('AAPL');
const currentSymbol = ref('');

// 浏览器风格导航历史
const navBackHistory = ref<string[]>([]);
const navForwardHistory = ref<string[]>([]);

/** 后退到上一个浏览的标的 */
const navBack = () => {
  if (navBackHistory.value.length === 0) return;
  const prev = navBackHistory.value.pop()!;
  if (currentSymbol.value) navForwardHistory.value.push(currentSymbol.value);
  symbolInput.value = stripPrefix(prev);
  handleSearch();
};

/** 前进到下一个浏览的标的 */
const navForward = () => {
  if (navForwardHistory.value.length === 0) return;
  const next = navForwardHistory.value.pop()!;
  if (currentSymbol.value) navBackHistory.value.push(currentSymbol.value);
  symbolInput.value = stripPrefix(next);
  handleSearch();
};

/** 刷新当前标的行情（重新加载K线） */
const refreshCurrent = () => {
  if (currentSymbol.value) {
    symbolInput.value = stripPrefix(currentSymbol.value);
    handleSearch();
  }
};

// 根据代码所属市场返回计价货币符号 (美股 $, 港股 HK$, A股 ¥)
const currencyOf = (sym: string): string => {
  const m = marketOf(sym);
  if (m === 'hk') return 'HK$';
  if (m === 'ash' || m === 'asz') return '¥';
  return '$';
};

// ================== 实时行情引擎（多市场）集成 ==================
// 引擎生命周期：真实模式启动轮询，演示模式停用（复用 K 线末根作为价格来源）。
// 以下响应式状态由引擎的订阅回调驱动更新。
const quoteConfig = ref<QuoteConfig | null>(null);
// 去重后的最新行情（仅价格/涨跌幅变化时才更新）
const liveQuoteMap = ref<Record<string, Quote>>({});
// 每只标的的轮询元数据（刷新周期/上次请求时间等，每 tick 同步）
const liveMetaMap = ref<Record<string, SymbolMeta>>({});
// 引擎是否处于冷却（限流/异常）
const engineCooling = ref(false);

// 股票名称映射表（symbol -> name），从后端股票池加载
const stockNameMap = ref<Record<string, string>>({});

/** 获取股票显示名称：优先从名称映射表取，无匹配则返回去前缀后的代码 */
const getStockName = (sym: string): string => {
  const normalized = canonSym(sym);
  return stockNameMap.value[normalized] || stockNameMap.value[sym] || formatSymbol(sym);
};

/** 从后端拉取全部股票池，构建名称映射（演示模式下使用本地兜底名称） */
async function loadStockNameMap() {
  try {
    const res = await fetch(`${BASE_URL}/search`, { cache: 'no-store' });
    if (res.ok) {
      const pool = await res.json();
      if (Array.isArray(pool)) {
        const map: Record<string, string> = {};
        for (const s of pool) {
          if (s.symbol && s.name) {
            map[canonSym(s.symbol)] = s.name;
          }
        }
        stockNameMap.value = { ...stockNameMap.value, ...map };
      }
    }
  } catch {
    // 后端不可用时静默失败，模板会回退显示代码
  }
}

/** 各市场延迟标注兜底（配置未加载/演示模式下也能固定展示） */
const DELAY_LABEL_FALLBACK: Record<string, { label: string; full: string }> = {
  ash: { label: '无延迟 LV1', full: 'A股【无延迟 LV1】' },
  asz: { label: '无延迟 LV1', full: 'A股【无延迟 LV1】' },
  hk: { label: '秒级轻微延迟', full: '港股【秒级轻微延迟】' },
  us: { label: '延迟 15 分钟，仅供参考，不可实盘交易', full: '美股【延迟 15 分钟，仅供参考，不可实盘交易】' },
};
/** 读取某标的延迟标注（精简） */
const delayLabelOf = (sym: string): string => {
  const m = marketOf(sym) || 'us';
  return quoteConfig.value?.markets[m]?.delayLabel ?? DELAY_LABEL_FALLBACK[m].label;
};
/** 读取某标的延迟完整提示语（悬浮标题） */
const delayFullOf = (sym: string): string => {
  const m = marketOf(sym) || 'us';
  return quoteConfig.value?.markets[m]?.delayFull ?? DELAY_LABEL_FALLBACK[m].full;
};

// 头部展示价格：真实模式取实时引擎，演示模式取 K 线末根（latestPrice/latestChange）
const displayPrice = computed<number | null>(() => {
  if (useMockData.value) return latestPrice.value;
  const q = currentSymbol.value ? liveQuoteMap.value[currentSymbol.value] : null;
  return q && q.price != null ? q.price : latestPrice.value;
});
const displayChange = computed<number>(() => {
  if (useMockData.value) return latestChange.value;
  const q = currentSymbol.value ? liveQuoteMap.value[currentSymbol.value] : null;
  return q && q.changePct != null ? q.changePct : latestChange.value;
});

/** 自选行统一价格信息：真实模式取引擎实时行情，演示模式取 K 线末根缓存 */
function watchPriceInfo(item: string): {
  price: number | null;
  change: number | null;
  loading: boolean;
  extendedPrice: number | null;
  extendedLabel: string;
  prevClose: number | null;
} {
  if (!useMockData.value) {
    const q = liveQuoteMap.value[item];
    if (q && q.status === 'ok' && q.price != null && q.changePct != null) {
      return {
        price: q.price,
        change: q.changePct,
        loading: false,
        extendedPrice: q.extendedPrice ?? null,
        extendedLabel: q.extendedLabel ?? '',
        prevClose: q.prevClose ?? null,
      };
    }
    // 真实模式尚未取到首值 → 视为加载中
    return { price: null, change: null, loading: true, extendedPrice: null, extendedLabel: '', prevClose: null };
  }
  const w = watchlistPriceMap.value[item] || {};
  return { price: w.price ?? null, change: w.change ?? null, loading: !!w.loading, extendedPrice: null, extendedLabel: '', prevClose: null };
}

/** 第二行辅助行情信息：优先展示扩展交易时段价格，否则展示昨收价 */
function secondaryLineInfo(item: string): {
  price: number | null;
  changePct: number | null;
  label: string;
} | null {
  const info = watchPriceInfo(item);
  if (info.loading || info.price == null) return null;

  // 优先：扩展交易时段价格（盘后/夜盘），需与当前价格不同才有展示价值
  if (info.extendedPrice != null && info.prevClose != null && info.prevClose > 0) {
    if (Math.abs(info.extendedPrice - info.price) >= 0.01) {
      const chg = ((info.extendedPrice - info.prevClose) / info.prevClose) * 100;
      return { price: info.extendedPrice, changePct: chg, label: info.extendedLabel || '盘后' };
    }
  }

  // 兜底：展示昨收价（提供辅助参考信息）
  if (info.prevClose != null && info.prevClose > 0) {
    return { price: info.prevClose, changePct: null, label: '昨收' };
  }

  return null;
}

// 当前标的刷新周期（秒）= 市场最低间隔 × 自适应倍率（向上取整）
const currentRefreshCycle = computed<number>(() => {
  const meta = currentSymbol.value ? liveMetaMap.value[currentSymbol.value] : null;
  const base = marketOf(currentSymbol.value) === 'us' ? 10 : 2; // 兜底
  const min = quoteConfig.value?.markets[marketOf(currentSymbol.value) || 'us']?.minInterval ?? base;
  return Math.max(1, Math.round(min * (meta?.intervalMul ?? 1)));
});

// 上次请求时间（mm:ss 形式，相对当前）
const lastRequestText = computed<string>(() => {
  const meta = currentSymbol.value ? liveMetaMap.value[currentSymbol.value] : null;
  if (!meta || !meta.lastRequest) return '—';
  const sec = Math.floor((Date.now() - meta.lastRequest) / 1000);
  if (sec < 60) return `${sec}s前`;
  const m = Math.floor(sec / 60);
  return `${m}m${sec % 60}s前`;
});

// 引擎状态（供头部/底部状态展示）
const quoteEngineStatus = computed<{ cooling: boolean; reason: string }>(() => ({
  cooling: engineCooling.value,
  reason: engineCooling.value ? 'cooling' : '',
}));

/** 刷新引擎需要轮询的标的集合（当前股票 + 自选股） */
function refreshEngineSymbols() {
  const syms = [currentSymbol.value, ...watchlist.value].filter(Boolean);
  quoteEngine.setSymbols(syms);
}

// 搜索框占位符（全市场统一，不再前置拆分市场）
// @ts-ignore
const searchPlaceholder = computed(() => '搜索股票代码 / 名称 / 拼音（美股 · A股 · 港股 全市场）');
const klineData = ref<KLinePoint[]>([]);
// 按 "symbol_period" 缓存K线和分析结果，避免切换周期时重复网络请求
const klineCache = new Map<string, KLinePoint[]>();
const analysisCache = new Map<string, AnalysisResponse>();
const cacheKey = (symbol: string, period: Period) => `${symbol}_${period}`;
const isLoading = ref(false);
const errorMsg = ref('');
const starBounce = ref(false);

// 数据模式：由后端探测自动决定。默认 true=演示模式(模拟数据)，
// 后端可用时自动切换为 false=实时数据。无需手动切换按钮。
const useMockData = ref(true);
// 图表是否已完成初始化（避免在图表就绪前触发重算导致崩溃）
const chartReady = ref(false);
// 后端是否在线（仅用于状态展示）
const backendOnline = ref(false);

/**
 * 探测后端可用性：
 *  - 可达 ( /api/health 返回 200 ) → 实时数据 (useMockData=false)
 *  - 不可达 / 超时                → 演示模式 (useMockData=true, 模拟数据)
 * 这样单独启动前端(无后端)即自动进入演示模式便于测试页面；
 * 启动后端后刷新或点"重试连接"即自动切回实时数据。
 */
async function detectBackend(): Promise<boolean> {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 2000);
    const res = await fetch(`${BASE_URL}/health`, { signal: ctrl.signal, cache: 'no-store' });
    clearTimeout(timer);
    const online = res.ok;
    backendOnline.value = online;
    if (online !== !useMockData.value) {
      useMockData.value = !online; // 后端在线=真实(false)，离线=演示(true)
    }
    return online;
  } catch {
    backendOnline.value = false;
    if (!useMockData.value) useMockData.value = true; // 探测失败 → 演示模式
    return false;
  }
}

/** 后端启动后手动重试连接（非模式切换按钮，仅重新探测并刷新） */
async function retryConnection() {
  errorMsg.value = '';
  const online = await detectBackend();
  if (online && chartReady.value && currentSymbol.value) {
    watchlistKlineCache.clear();
    watchlistPriceMap.value = {};
    handleSearch();
  } else if (!online) {
    errorMsg.value = '仍未检测到后端服务，请确认已启动后端 (python main.py)，或继续在演示模式下浏览前端页面。';
  }
}

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

// ================== 自选股价格与区间涨跌幅 ==================
interface WatchlistPriceInfo {
  price: number | null;      // 最新(实时)收盘价
  change: number | null;     // 当日涨跌幅 % (最新close vs 前一日close)
  loading: boolean;          // 是否正在加载中
}
const watchlistPriceMap = ref<Record<string, WatchlistPriceInfo>>({});
// 缓存已拉取的自选股K线（切换日期范围时复用，避免重复请求）
const watchlistKlineCache = new Map<string, KLinePoint[]>();

/**
 * 从日线 K 线中取「最新(实时)收盘价」与「当日涨跌幅%」(最新close vs 前一日close)。
 * 注意: 此处一律使用日线数据，与图表当前周期无关，也不依赖用户选中的日期区间，
 *       因此点击切换股票 / 修改区间时，自选栏数值保持稳定，不会跳动。
 */
function calcLatestPrice(klines: KLinePoint[]): { price: number | null; change: number | null } {
  if (!klines || klines.length === 0) return { price: null, change: null };
  const last = klines[klines.length - 1];
  const price = last.close;
  if (klines.length > 1) {
    const prevClose = klines[klines.length - 2].close;
    if (prevClose && prevClose !== 0) {
      const change = ((price - prevClose) / prevClose) * 100;
      return { price, change };
    }
  }
  // 仅有第一根 K 线，无法算涨跌
  return { price, change: null };
}

/** 测试模式各股票基准价（与 loadStock 中一致） */
const MOCK_BASE_PRICES: Record<string, number> = {
  'AAPL': 180, 'NVDA': 450, 'TSLA': 250, 'MSFT': 370,
  'GOOGL': 140, 'AMZN': 175, 'META': 480, 'AMD': 160, 'MU': 130, 'SNDK': 95,
};

/** 更新所有自选股的实时价格与当日涨跌幅（始终基于日线，与图表周期/选中区间解耦，故点击切换不跳动）
 *  注：仅演示模式使用。真实模式改由实时行情引擎(quoteEngine)批量拉取实时报价，
 *      避免每切一只股票就对每只自选股各发一次 K 线请求（浪费限流额度）。 */
async function updateWatchlistPrices() {
  if (!useMockData.value) return; // 真实模式：行情由引擎负责，此处跳过
  const symbols = watchlist.value.slice();
  if (!symbols.length) return;

  // 先标记所有股票为 loading
  const newMap: Record<string, WatchlistPriceInfo> = {};
  for (const sym of symbols) {
    const prev = watchlistPriceMap.value[sym];
    newMap[sym] = prev ? { ...prev, loading: true } : { price: null, change: null, loading: true };
  }
  watchlistPriceMap.value = newMap;

  // 并行获取每只股票的日线数据（自选栏只看「实时价 + 当日涨跌」，故固定用 1d，不随图表周期变化）
  await Promise.allSettled(symbols.map(async (sym) => {
    try {
      let klines: KLinePoint[];
      if (useMockData.value) {
        // 测试模式：生成模拟日线（缓存，避免每次调用都重新随机生成导致数值跳动）
        const mockKey = 'mock_' + sym;
        if (watchlistKlineCache.has(mockKey)) {
          klines = watchlistKlineCache.get(mockKey)!;
        } else {
          klines = generateMockKLines(stripPrefix(sym), 4500, MOCK_BASE_PRICES[stripPrefix(sym)] || 150);
          watchlistKlineCache.set(mockKey, klines);
        }
      } else {
        // 真实数据模式：优先用缓存，未命中则请求后端日线。
        // 统一用 normalizeSymbol 补全市场前缀 (与 loadStock 完全一致，避免漏加前缀导致后端 404)。
        const querySym = normalizeSymbol(sym);
        const key = 'real_' + querySym + '_1d';
        if (watchlistKlineCache.has(key)) {
          klines = watchlistKlineCache.get(key)!;
        } else {
          klines = await getKLines(querySym, '1d');
          watchlistKlineCache.set(key, klines); // 写入自选股专用缓存
        }
      }
      const result = calcLatestPrice(klines);
      watchlistPriceMap.value[sym] = { price: result.price, change: result.change, loading: false };
    } catch (e) {
      console.warn(`[自选股价格] ${sym} 获取失败:`, e);
      watchlistPriceMap.value[sym] = { price: null, change: null, loading: false };
    }
  }));
}

// 自选分组：用户自创，用来自由归类标的（不再由系统硬分市场）
const watchGroups = ref<WatchGroup[]>([]);
// 规范化为「小写前缀」统一形态 (usAAPL / hk00700)，避免存储值大小写不一导致比较错位
const canonSym = (s: string): string => {
  const n = normalizeSymbol(s);
  if (!n) return n;
  return n.replace(/^(US|SH|SZ|HK)/i, (m) => m.toLowerCase());
};
// 扁平并集（供实时行情引擎 / 演示模式 / 自动加载使用），与分组保持同步派生
const watchlist = computed<string[]>(() => {
  const set = new Set<string>();
  for (const g of watchGroups.value) {
    for (const s of g.stocks) {
      const n = canonSym(s);
      if (n) set.add(n);
    }
  }
  return [...set];
});

// ================== 自选列表：市场 Tab 过滤 + 分组多选筛选（交集） ==================
type MarketTabKey = 'all' | 'ash' | 'hk' | 'us' | 'futures';
const MARKET_TABS: { key: MarketTabKey; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'ash', label: 'A股' },
  { key: 'hk', label: '港股' },
  { key: 'us', label: '美股' },
  { key: 'futures', label: '期货' },
];
// 当前激活的市场 Tab（默认全部）；切换 Tab 仅过滤视图，不影响分组勾选状态
const activeMarketTab = ref<MarketTabKey>('all');
// 当前激活的分组 ID（'all' = 全部自选，或具体的 g.id）
const activeGroupId = ref<string>('all');
// 分组下拉面板开关
const showGroupDropdown = ref(false);

// 新建分组、添加自选及分组管理 Modals
const showCreateGroupModal = ref(false);
const showManageGroupsModal = ref(false);
const showSearchModal = ref(false);

const newGroupNameInput = ref('');
const modalSearchQuery = ref('');
const modalSearchResults = ref<any[]>([]);
const modalSearchLoading = ref(false);

const createGroupInputRef = ref<HTMLInputElement | null>(null);
const modalSearchInputRef = ref<HTMLInputElement | null>(null);

// ================== 自选列表排序：点击 名称代码 / 最新价 / 涨跌幅 表头切换 ==================
type SortKey = 'name' | 'price' | 'change';
// 当前排序字段（null = 不排序，保持分组原始顺序）；方向 asc 升序 / desc 降序
const sortBy = ref<SortKey | null>(null);
const sortDir = ref<'asc' | 'desc'>('desc');
const setSort = (key: SortKey) => {
  if (sortBy.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc';
  } else {
    sortBy.value = key;
    // 名称默认按代码升序；价格 / 涨跌幅默认降序（数值大者在前）
    sortDir.value = key === 'name' ? 'asc' : 'desc';
  }
};

// 市场 Tab 命中判断：期货按代码以 main 结尾识别，其余按前缀
const matchMarketTab = (sym: string, tab: MarketTabKey): boolean => {
  if (tab === 'all') return true;
  if (tab === 'futures') return sym.toLowerCase().endsWith('main');
  const m = marketOf(sym);
  if (tab === 'ash') return m === 'ash' || m === 'asz';
  if (tab === 'hk') return m === 'hk';
  if (tab === 'us') return m === 'us';
  return false;
};

// 过滤后的自选列表 = 市场 Tab 过滤 ∩ 当前选中的单选分组（实时刷新）
const filteredWatchlist = computed<string[]>(() => {
  const gid = activeGroupId.value;
  return watchlist.value.filter((sym) => {
    const okMarket = matchMarketTab(sym, activeMarketTab.value);
    let okGroup = true;
    if (gid !== 'all') {
      const g = watchGroups.value.find((x) => x.id === gid);
      okGroup = g ? g.stocks.some((s) => canonSym(s) === canonSym(sym)) : false;
    }
    return okMarket && okGroup;
  });
});

// 在「市场 Tab ∩ 分组」过滤结果之上，再按表头选择排序（无数据项恒置末尾）
const sortedFilteredWatchlist = computed<string[]>(() => {
  const arr = filteredWatchlist.value.slice();
  if (!sortBy.value) return arr;
  const dir = sortDir.value === 'asc' ? 1 : -1;
  const k = sortBy.value;
  arr.sort((a, b) => {
    if (k === 'name') return a.localeCompare(b) * dir;
    const va = k === 'price' ? watchPriceInfo(a).price : watchPriceInfo(a).change;
    const vb = k === 'price' ? watchPriceInfo(b).price : watchPriceInfo(b).change;
    const na = va == null;
    const nb = vb == null;
    if (na && nb) return 0;
    if (na) return 1; // 无数据恒排末尾
    if (nb) return -1;
    return (va - vb) * dir;
  });
  return arr;
});

const selectGroup = (id: string) => {
  activeGroupId.value = id;
  showGroupDropdown.value = false;
};
const toggleGroupDropdown = () => {
  showGroupDropdown.value = !showGroupDropdown.value;
};
const activeGroupName = computed(() => {
  if (activeGroupId.value === 'all') return '选择分组';
  const g = watchGroups.value.find((x) => x.id === activeGroupId.value);
  return g ? g.name : '选择分组';
});
const triggerCreateGroup = () => {
  showGroupDropdown.value = false;
  showCreateGroupModal.value = true;
  nextTick(() => {
    createGroupInputRef.value?.focus();
  });
};
const triggerManageGroups = () => {
  showGroupDropdown.value = false;
  showManageGroupsModal.value = true;
};

// 分析数据状态
const srLevels = ref<SRLevel[]>([]);
const startDate = ref('');
const endDate = ref('');
const inputStartDate = ref('');
const inputEndDate = ref('');
const rangeStats = ref<any>(null);

// 每支股票的区间选择记忆（localStorage 持久化）
interface RangePref { start: string; end: string; }
const RANGE_PREFS_KEY = 'stockvision_range_prefs';
const rangePrefs = ref<Record<string, RangePref>>(loadRangePrefs());

function loadRangePrefs(): Record<string, RangePref> {
  try {
    const raw = localStorage.getItem(RANGE_PREFS_KEY);
    return raw ? (JSON.parse(raw) as Record<string, RangePref>) : {};
  } catch {
    return {};
  }
}
function saveRangePrefs() {
  try {
    localStorage.setItem(RANGE_PREFS_KEY, JSON.stringify(rangePrefs.value));
  } catch {
    /* 忽略写入失败（如隐私模式） */
  }
}
function clampDate(d: string, min: string, max: string): string {
  if (min && d < min) return min;
  if (max && d > max) return max;
  return d;
}
// 把"当前生效的区间"记到对应股票下，下次切回该股票时恢复
function persistCurrentRange() {
  const sym = currentSymbol.value;
  if (!sym || !startDate.value || !endDate.value || startDate.value > endDate.value) return;
  const next = { ...rangePrefs.value, [sym]: { start: startDate.value, end: endDate.value } };
  rangePrefs.value = next;
  saveRangePrefs();
}

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
const leftSidebarWidth = ref(320); // 左侧边栏固定宽度
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



const selectSuggestion = (symbol: string) => {
  symbolInput.value = symbol;
  handleSearch();
};

// ================== 自选分组方法 ==================
// 生成分组 id（优先 crypto.randomUUID，回退到随机串）
const genGroupId = (): string =>
  (typeof crypto !== 'undefined' && crypto.randomUUID)
    ? crypto.randomUUID()
    : `g${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;

// 默认分组（首次启动示例，用户可自由改名/删除/另建）
const defaultGroups = (): WatchGroup[] => ([
  { id: genGroupId(), name: '我的自选', stocks: ['usAAPL', 'usNVDA', 'sh600519', 'hk00700'] },
]);

const loadWatchlist = async () => {
  // 优先从后端加载 (跨浏览器 / 跨 origin / 跨预览会话持久)
  try {
    const remote = await getWatchlist();
    if (Array.isArray(remote) && remote.length) {
      watchGroups.value = remote.map((g: WatchGroup) => ({
        id: g.id || genGroupId(),
        name: g.name || '未命名分组',
        stocks: g.stocks.map((s: string) => canonSym(s) || s),
      }));
      persistWatchlistLocal(); // 同步本地兜底
    }
  } catch {
    // 后端不可用时忽略，回退本地
  }
  // 回退：本地 localStorage（兼容旧版扁平 list）
  if (!watchGroups.value.length) {
    const local = localStorage.getItem('stock_watchlist');
    if (local) {
      try {
        const parsed = JSON.parse(local);
        if (Array.isArray(parsed)) {
          // 旧版扁平 list -> 归入默认分组
          watchGroups.value = [{ id: genGroupId(), name: '我的自选', stocks: parsed.map((s: string) => canonSym(s) || s) }];
        } else if (parsed && Array.isArray(parsed.groups)) {
          watchGroups.value = parsed.groups as WatchGroup[];
        } else {
          watchGroups.value = defaultGroups();
        }
      } catch {
        watchGroups.value = defaultGroups();
      }
    } else {
      watchGroups.value = defaultGroups();
      persistWatchlistLocal();
    }
  }
  // 初始化价格地图为 loading 态：updateWatchlistPrices 要等 loadStock 完成后才调用，
  // 此间 watchlist 已有值但 watchlistPriceMap 为空 → 模板取到 undefined 会崩溃。
  // 预先填 loading 条目，既防崩溃又让初始显示骨架屏而非 "--" 闪烁。
  const initMap: Record<string, WatchlistPriceInfo> = {};
  for (const s of watchlist.value) {
    initMap[s] = { price: null, change: null, loading: true };
  }
  watchlistPriceMap.value = initMap;
  // 真实模式：同步引擎需轮询的标的（当前股票 + 自选股）
  if (!useMockData.value) refreshEngineSymbols();
  // 竞态保护: onMounted 中 loadWatchlist(async, await getWatchlist) 与
  // handleSearch→loadStock 并发执行。若 loadStock 先完成, 它末尾调用的
  // updateWatchlistPrices 会因 watchlist 仍为空而 return; 等 loadWatchlist
  // 在此设好 watchlist 后, 无人再触发更新 → 自选股永卡 loading。故此处补调一次。
  if (!currentSymbol.value && watchlist.value.length) {
    // 启动后自动加载第一只自选，确保图表与自选栏价格立即有数据
    selectWatchlist(watchlist.value[0]);
  } else if (currentSymbol.value && startDate.value && endDate.value) {
    updateWatchlistPrices();
  }
};

// 同时写后端 + 本地兜底
const persistWatchlistLocal = () => {
  localStorage.setItem('stock_watchlist', JSON.stringify({ groups: watchGroups.value }));
};
const persistWatchlist = () => {
  persistWatchlistLocal();
  saveWatchlist(watchGroups.value); // 异步写后端，不阻塞 UI
};

const isWatchlisted = (sym: string): boolean => {
  const target = canonSym(sym);
  return watchGroups.value.some((g) => g.stocks.some((s) => canonSym(s) === target));
};

const toggleWatchlist = (sym: string) => {
  if (!sym) return;
  const target = canonSym(sym);

  // 触发弹跳动画
  starBounce.value = true;
  setTimeout(() => {
    starBounce.value = false;
  }, 500);

  if (isWatchlisted(target)) {
    removeFromWatchlist(target);
  } else {
    // 未自选 -> 加入当前激活的分组，如果是 all 则加入第一个分组
    if (!watchGroups.value.length) watchGroups.value = defaultGroups();
    const targetGroupId = activeGroupId.value !== 'all' ? activeGroupId.value : watchGroups.value[0].id;
    const targetGroup = watchGroups.value.find(g => g.id === targetGroupId) || watchGroups.value[0];
    if (!targetGroup.stocks.some((s) => canonSym(s) === target)) {
      targetGroup.stocks.push(target);
      watchlistPriceMap.value[target] = { price: null, change: null, loading: true };
    }
    persistWatchlist();
    if (!useMockData.value) refreshEngineSymbols();
  }
  updateWatchlistPrices();
};

// 从指定分组移除股票 (不传 groupId 则从所有分组移除)
const removeFromWatchlist = (sym: string, groupId?: string) => {
  const target = canonSym(sym);
  for (const g of watchGroups.value) {
    if (groupId && g.id !== groupId) continue;
    const idx = g.stocks.findIndex((s) => canonSym(s) === target);
    if (idx > -1) g.stocks.splice(idx, 1);
  }
  const stillAny = watchGroups.value.some((g) => g.stocks.some((s) => canonSym(s) === target));
  if (!stillAny) delete watchlistPriceMap.value[target];
  persistWatchlist();
  if (!useMockData.value) refreshEngineSymbols();
};

const selectWatchlist = (sym: string) => {
  // 记录导航历史：当前标的压入后退栈，清空前进栈
  if (currentSymbol.value && currentSymbol.value !== sym) {
    navBackHistory.value.push(currentSymbol.value);
    navForwardHistory.value = [];
  }
  // 搜索框显示纯净代码，handleSearch 会自动按前缀识别市场
  symbolInput.value = stripPrefix(sym);
  handleSearch();
};

// ================== 自选分组 CRUD ==================
const handleCreateGroupSubmit = () => {
  const name = (newGroupNameInput.value || '').trim();
  if (name) {
    const newId = genGroupId();
    watchGroups.value.push({ id: newId, name, stocks: [] });
    persistWatchlist();
    // 自动在自选栏打开新建分组的列表
    activeGroupId.value = newId;
  }
  newGroupNameInput.value = '';
  showCreateGroupModal.value = false;
};
const editingGroupId = ref<string | null>(null);
const editingGroupName = ref('');
const confirmRename = (id: string) => {
  if (editingGroupId.value !== id) return;
  renameGroup(id, editingGroupName.value);
  editingGroupId.value = null;
};

const renameGroup = (id: string, name: string) => {
  const g = watchGroups.value.find((x) => x.id === id);
  if (g) {
    g.name = (name || '').trim() || g.name;
    persistWatchlist();
  }
};
const deleteGroup = (id: string) => {
  const i = watchGroups.value.findIndex((x) => x.id === id);
  if (i > -1) {
    watchGroups.value.splice(i, 1);
    // 删除分组时如果刚好被选中，切回全部
    if (activeGroupId.value === id) {
      activeGroupId.value = 'all';
    }
    persistWatchlist();
    if (!useMockData.value) refreshEngineSymbols();
  }
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
    const minL = 260;
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

const isCurrentGroupEmpty = computed(() => {
  if (activeGroupId.value === 'all') return false;
  const g = watchGroups.value.find((x) => x.id === activeGroupId.value);
  return g ? g.stocks.length === 0 : false;
});

let modalSearchDebounceTimer: ReturnType<typeof setTimeout> | null = null;
const handleModalSearchInput = () => {
  const q = modalSearchQuery.value.trim();
  if (modalSearchDebounceTimer) clearTimeout(modalSearchDebounceTimer);
  if (!q) {
    modalSearchResults.value = [];
    modalSearchLoading.value = false;
    return;
  }
  modalSearchLoading.value = true;
  modalSearchDebounceTimer = setTimeout(async () => {
    try {
      const res = await searchStocks(q);
      modalSearchResults.value = res || [];
    } catch (e) {
      console.error(e);
      modalSearchResults.value = [];
    } finally {
      modalSearchLoading.value = false;
    }
  }, 250);
};

const handleModalSearchSelect = (sym: string) => {
  const target = canonSym(sym);
  if (!watchGroups.value.length) watchGroups.value = defaultGroups();
  const currentGroup = watchGroups.value.find(g => g.id === activeGroupId.value);
  if (currentGroup) {
    if (!currentGroup.stocks.some(s => canonSym(s) === target)) {
      currentGroup.stocks.push(target);
    }
    if (!watchlistPriceMap.value[target]) {
      watchlistPriceMap.value[target] = { price: null, change: null, loading: true };
    }
    persistWatchlist();
    updateWatchlistPrices();
    if (!useMockData.value) refreshEngineSymbols();
    
    // 选中新添加的股票以直接展示 K 线
    selectWatchlist(target);
  }
  
  showSearchModal.value = false;
  modalSearchQuery.value = '';
  modalSearchResults.value = [];
};

// ================== 行情搜索 ==================
/**
 * 把用户输入解析为带市场前缀的统一代码。
 *  - 已带前缀 (us/hk/sh/sz)         -> 原样归一返回
 *  - 纯数字代码                     -> 按当前市场标签补全 (5位自动判港股, 6位自动判沪深)
 *  - 名称 / 拼音 (含中文或字母混合) -> 全局搜索解析, 避免被当前市场标签误判
 *                                     例如「小米」属港股, 在沪A标签下也应正确解析为 hk01810,
 *                                     而不是被强制拼成 SH小米 导致加载失败
 */
async function resolveSymbol(raw: string): Promise<string> {
  const s = (raw || '').trim();
  if (!s) return s;
  // 1) 已带市场前缀 -> 直接归一
  if (/^(us|hk|sh|sz)/i.test(s)) return normalizeSymbol(s);
  // 2) 纯数字代码 -> 自动识别市场补全 (6位沪深 / ≤5位港股 / 其它按美股)
  if (/^\d+$/.test(s)) return normalizeSymbol(s);
  // 3) 名称 / 拼音 -> 全局搜索解析 (跨市场)
  try {
    const res = await searchStocks(s);
    if (res && res.length > 0) return res[0].symbol;
  } catch {
    /* 后端不可达时走下方兜底 */
  }
  // 4) 兜底: 自动识别市场补全 (演示模式 / 后端挂了)
  return normalizeSymbol(s);
}

const handleSearch = async () => {
  const raw = symbolInput.value.trim();
  if (!raw) return;
  // 解析为带前缀代码: 名称/拼音走全局搜索, 不盲目套用当前市场前缀
  const querySymbol = await resolveSymbol(raw);
  if (!querySymbol) return;
  const code = querySymbol; // 供下方模拟数据基准价取纯净代码 (stripPrefix)

  isLoading.value = true;
  errorMsg.value = '';
  srLevels.value = [];
  rangeStats.value = null;
  activeTimeRange.value = 'ALL'; // 重置时间范围

  // 记录开始时间，用于保证骨架屏最短展示时长
  const startedAt = performance.now();

  try {
    let klines: KLinePoint[];

    if (useMockData.value) {
      // 使用测试数据模式
      console.log(`[测试模式] 生成 ${querySymbol} 的模拟K线数据`);
      const basePriceMap: Record<string, number> = {
        'AAPL': 180, 'NVDA': 450, 'TSLA': 250, 'MSFT': 370,
        'GOOGL': 140, 'AMZN': 175, 'META': 480, 'AMD': 160,
        'MU': 130, 'SNDK': 95,
        '600519': 1700, '601318': 55, '600036': 40, '600276': 50, '600900': 30,
        '000001': 12, '000858': 150, '300750': 250, '002594': 280, '000333': 70,
        '00700': 400, '09988': 90, '03690': 180, '01810': 25, '00939': 7,
      };
      // 模拟数据按去前缀后的纯净代码取基准价
      const basePrice = basePriceMap[stripPrefix(code)] || 150;
      // 测试模式也生成"上市以来"的长历史 (约 4500 交易日 ≈ 18 年)，便于直观查看全量K线
      klines = generateMockKLines(stripPrefix(code), 4500, basePrice);
      // 按当前周期重采样：否则周K/月K/季K等会把 4500 根日线直接渲染出来（"成了日K的显示"）
      klines = resampleMockKLines(klines, currentPeriod.value);
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
    // currentSymbol 存带前缀代码 (如 usAAPL / sh600519)，作为标的唯一身份；
    // UI 展示时通过 formatSymbol 去掉前缀，保持清晰。
    const prevSym = currentSymbol.value;
    currentSymbol.value = querySymbol;
    // 导航历史：切换标的时记录（selectWatchlist 已推入的情况不重复推）
    if (prevSym && prevSym !== querySymbol && navBackHistory.value[navBackHistory.value.length - 1] !== prevSym) {
      navBackHistory.value.push(prevSym);
      navForwardHistory.value = [];
    }

    // 真实模式下，若返回根数过少，提示数据可能不完整
    // - 日K <400 根：可能被限流/退回腾讯上限
    // - 聚合周期(季/半年/年) 根数少：该股票历史长度不足(如退市股 SNDK 只有 ~1.4 年日线)
    if (!useMockData.value && klines.length > 0) {
      const p = currentPeriod.value;
      const n = klines.length;
      if (p === '1d' && n < 400) {
        dataWarning.value = `⚠️ 当前仅返回 ${n} 根日K线，可能不是该股票的完整历史（数据源被限流或网络异常时会发生）。请稍后重试，或确认后端数据源可用。`;
      } else if ((p === '3M' && n < 4) || (p === '6M' && n < 2) || (p === '1Y' && n < 2)) {
        const labels: Record<string, string> = { '3M': '季K', '6M': '半年K', '1Y': '年K' };
        dataWarning.value = `⚠️ 该股票历史数据较短，当前仅 ${n} 根${labels[p] || p}（可能是退市/新上市股票）。建议切换到更短周期（如日K）查看更多细节。`;
      } else {
        dataWarning.value = '';
      }
    } else {
      dataWarning.value = '';
    }

    // 重置绘图线与标记
    priceLines.forEach(line => candlestickSeries?.removePriceLine(line));
    priceLines = [];
    markersPlugin?.setMarkers([]);

    if (klines.length > 0) {
      const minD = klines[0].time;
      const maxD = klines[klines.length - 1].time;
      // 恢复该股票上次记住的区间；没有记录则用全量历史
      const saved = rangePrefs.value[code];
      let s = minD;
      let e = maxD;
      if (saved && saved.start && saved.end && saved.start <= saved.end) {
        s = clampDate(saved.start, minD, maxD);
        e = clampDate(saved.end, minD, maxD);
        if (s > e) {
          s = minD;
          e = maxD;
        }
      }
      startDate.value = s;
      endDate.value = e;
      inputStartDate.value = s;
      inputEndDate.value = e;
    }

    await runAnalysis();
    // 更新自选股列表中每只股票的价格与区间涨跌幅（不阻塞 UI，后台静默更新）
    updateWatchlistPrices();
    // 真实模式：把当前股票加入引擎轮询集合（切换标的后立即开始拉取实时行情）
    if (!useMockData.value) refreshEngineSymbols();
  } catch (err: any) {
    errorMsg.value = err.message || '网络连接失败，无法加载行情图';
    klineData.value = [];
    currentSymbol.value = '';
    // 加载失败：清除自选股 loading 态，避免骨架屏永转（显示 "--"）
    for (const s of watchlist.value) {
      if (watchlistPriceMap.value[s]) watchlistPriceMap.value[s].loading = false;
    }
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
  updateWatchlistPrices();
};

// 快捷区间预设：一键设定起止日期并重新计算，免去抠原生日历
const rangePresets = [
  { label: '近1周', value: 'r1w' },
  { label: '近1月', value: 'r1m' },
  { label: '近3月', value: 'r3m' },
  { label: '近6月', value: 'r6m' },
  { label: '近1年', value: 'r1y' },
  { label: '全部', value: 'all' },
];
// 各预设相对"最新交易日"的回溯偏移（支持按天或按月）
const PRESET_OFFSETS: Record<string, { months?: number; days?: number }> = {
  r1w: { days: 7 },
  r1m: { months: 1 },
  r3m: { months: 3 },
  r6m: { months: 6 },
  r1y: { months: 12 },
};

function presetRange(value: string): { start: string; end: string } | null {
  if (!klineData.value.length) return null;
  const maxD = klineData.value[klineData.value.length - 1].time;
  const minD = klineData.value[0].time;
  if (value === 'all') return { start: minD, end: maxD };
  const off = PRESET_OFFSETS[value];
  if (!off) return null;
  const d = new Date(maxD + 'T00:00:00');
  if (off.months) d.setMonth(d.getMonth() - off.months);
  if (off.days) d.setDate(d.getDate() - off.days);
  let start = toLocalDateStr(d);
  if (start < minD) start = minD;
  return { start, end: maxD };
}

function applyRangePreset(value: string) {
  const r = presetRange(value);
  if (!r) return;
  inputStartDate.value = r.start;
  inputEndDate.value = r.end;
  handleReCalculate();
}

// 高亮当前生效的预设（用于按钮 active 态）
function isPresetActive(value: string): boolean {
  const r = presetRange(value);
  if (!r) return false;
  return r.start === inputStartDate.value && r.end === inputEndDate.value;
}

// ================== 计算技术分析 ==================
const runAnalysis = async () => {
  if (!klineData.value.length || !currentSymbol.value) return;

  const querySymbol = normalizeSymbol(currentSymbol.value);

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

    // 记住当前股票的分析区间（切回时恢复）
    persistCurrentRange();

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
    // 关键: 仅当数据足够长(n>10)才按比例还原缩放。短历史股票(退市/新上市/分拆股,
    // 如 SNDK 半年K 仅 3-4 根、年K 仅 2 根)若套用长股票(如 AAPL 4500 根)留下的
    // 高比例缩放记忆, 会把仅有的几根 K 线推到屏幕外 → 看似"无法显示"。
    // 短数据集一律 fitContent 全量展示。
    if (zoomMemory && n > 1 && n > 10) {
      const from = Math.max(0, Math.min(n, zoomMemory.fromFrac * n));
      const to = Math.max(0, Math.min(n, zoomMemory.toFrac * n));
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

// 模式由后端探测自动切换：清空自选股缓存并重新拉取，避免两种数据源混合显示。
// 图表未就绪(chartReady=false)时不触发，避免未初始化图表时调用 runAnalysis 崩溃。
// ================== 实时行情引擎：启动 / 停止 ==================
let quoteWired = false; // 订阅回调只注册一次，避免模式来回切换导致重复绑定

/** 启动实时行情引擎（真实模式）：加载配置、绑定订阅、开始分层轮询 */
async function startQuoteEngine() {
  await quoteEngine.loadConfig();
  quoteConfig.value = quoteEngine.config;
  if (!quoteWired) {
    // 行情变化才更新去重映射（UI 仅在此刻重渲染）
    quoteEngine.subscribe((sym, q) => {
      liveQuoteMap.value = { ...liveQuoteMap.value, [sym]: q };
    });
    // 每轮 tick 同步元数据与冷却状态（状态面板用，不受价格是否变化影响）
    quoteEngine.onTick(() => {
      liveMetaMap.value = quoteEngine.snapshotMetas();
      engineCooling.value = quoteEngine.getEngineStatus().cooling;
    });
    quoteWired = true;
  }
  refreshEngineSymbols();
  quoteEngine.start();
}

/** 停止并清理引擎（切回演示模式时调用） */
function stopQuoteEngine() {
  quoteEngine.stop();
  liveQuoteMap.value = {};
  liveMetaMap.value = {};
  engineCooling.value = false;
}

watch(useMockData, () => {
  watchlistKlineCache.clear();
  watchlistPriceMap.value = {};
  // 模式切换：真实模式启动实时行情引擎，演示模式停止并清理
  if (!useMockData.value) {
    startQuoteEngine();
  } else {
    stopQuoteEngine();
  }
  if (chartReady.value && currentSymbol.value) {
    console.log(`[模式切换] 切换到 ${useMockData.value ? '演示模式' : '实时数据模式'}，重新加载 ${currentSymbol.value}`);
    handleSearch();
  }
});

onMounted(async () => {
  loadStockNameMap(); // 先拉取股票名称映射，供自选栏显示名称
  loadWatchlist();
  initDarkMode(); // 初始化深色模式

  // 先探测后端是否可用，决定"演示/实时"模式，避免先加载模拟数据再刷新
  await detectBackend();

  // 真实模式：启动实时行情引擎（配置/订阅/轮询）
  if (!useMockData.value) {
    startQuoteEngine();
  }

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
        chartReady.value = true;
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
  const target = e.target as HTMLElement;
  
  // 关闭时间范围菜单
  if (showTimeRangeMenu.value && !target.closest('.relative')) {
    showTimeRangeMenu.value = false;
  }
  
  // 关闭分组筛选/管理菜单
  if (showGroupDropdown.value && !target.closest('.group-dropdown-container')) {
    showGroupDropdown.value = false;
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
