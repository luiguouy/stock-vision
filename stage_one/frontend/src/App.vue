<template>
  <div
    class="flex flex-col flex-1 h-screen overflow-hidden bg-slate-50 dark:bg-[#090d16] text-slate-800 dark:text-slate-200 antialiased font-sans select-none">

    <!-- 顶栏导航 (48px Header) -->
    <header class="h-12 bg-white/95 dark:bg-[#0f172a]/95 backdrop-blur-md border-b border-slate-200/80 dark:border-slate-800 px-3.5 flex items-center gap-3 shrink-0 z-[60]">
      <!-- 左：导航按钮 -->
      <div class="flex items-center gap-1 shrink-0">
        <button @click="navBack()" :disabled="navBackHistory.length === 0"
          class="btn-tactile p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-25 disabled:cursor-not-allowed transition-colors cursor-pointer" title="后退">
          <svg class="w-4 h-4 text-slate-500 dark:text-slate-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>
        </button>
        <button @click="navForward()" :disabled="navForwardHistory.length === 0"
          class="btn-tactile p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-25 disabled:cursor-not-allowed transition-colors cursor-pointer" title="前进">
          <svg class="w-4 h-4 text-slate-500 dark:text-slate-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>
        </button>
        <button @click="refreshCurrent()"
          class="btn-tactile p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer" title="刷新行情">
          <svg class="w-4 h-4 text-slate-500 dark:text-slate-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
        </button>
        <div class="h-4 w-px bg-slate-200 dark:bg-slate-800 mx-0.5"></div>
        <!-- 切换左侧边栏 (自选列表) -->
        <button @click="toggleLeftSidebar()"
          class="btn-tactile p-1.5 rounded-lg transition-colors cursor-pointer"
          :class="showLeftSidebar ? 'text-indigo-600 dark:text-indigo-400 bg-indigo-50/80 dark:bg-indigo-950/40 hover:bg-indigo-100 dark:hover:bg-indigo-900/50' : 'text-slate-400 dark:text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'"
          :title="showLeftSidebar ? '收起左侧自选栏 (快捷键 [ )' : '展开左侧自选栏 (快捷键 [ )'">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M9 3v18" />
          </svg>
        </button>
      </div>

      <!-- 中：全局证券搜索（系统入口） -->
      <div class="w-60 shrink-0">
        <GlobalSecuritySearch
          ref="searchComponentRef"
          :watchlist="watchlist"
          :placeholder="searchPlaceholder"
          @select="selectSuggestion"
          @add-watch="toggleWatchlist"
        />
      </div>

      <!-- 右：当前标的摘要 + 控制 -->
      <div class="flex items-center gap-2.5 shrink-0 ml-auto">
        <template v-if="currentSymbol">
          <div class="flex items-center gap-1.5">
            <span class="text-sm font-bold text-slate-900 dark:text-slate-100 font-sans tracking-tight">{{ formatSymbol(currentSymbol) }}</span>
            <span class="text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 font-mono">{{ MARKET_LABEL[marketOf(currentSymbol) || 'us'] }}</span>
          </div>
          <div v-if="displayPrice != null" class="flex items-center gap-2 pl-2 border-l border-slate-200 dark:border-slate-800">
            <span class="text-sm font-bold font-mono tabular-nums tracking-tight"
              :class="displayChange >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'">
              {{ currencyOf(currentSymbol) }}{{ displayPrice.toFixed(2) }}
            </span>
            <span class="text-[10px] font-bold font-mono tabular-nums px-1.5 py-0.5 rounded shadow-2xs leading-none"
              :class="displayChange >= 0 ? 'bg-emerald-500 text-white' : 'bg-rose-500 text-white'">
              {{ displayChange >= 0 ? '+' : '' }}{{ displayChange.toFixed(2) }}%
            </span>
            <div v-if="displayExtendedInfo" class="flex items-center gap-1 pl-2 border-l border-slate-200 dark:border-slate-800 text-[11px] font-mono">
              <span class="text-[9px] font-bold px-1 py-0.2 rounded bg-amber-500/15 text-amber-600 dark:text-amber-400">
                {{ displayExtendedInfo.label }}
              </span>
              <span class="font-bold text-slate-700 dark:text-slate-200">
                {{ currencyOf(currentSymbol) }}{{ displayExtendedInfo.price.toFixed(2) }}
              </span>
              <span :class="displayExtendedInfo.changePct >= 0 ? 'text-emerald-500' : 'text-rose-500'">
                {{ displayExtendedInfo.changePct >= 0 ? '+' : '' }}{{ displayExtendedInfo.changePct.toFixed(2) }}%
              </span>
            </div>
          </div>
          <button @click="toggleWatchlist(currentSymbol)"
            class="btn-tactile p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
            :title="isWatchlisted(currentSymbol) ? '取消自选' : '加入自选'">
            <svg class="w-4 h-4" :class="isWatchlisted(currentSymbol) ? 'text-amber-400 fill-amber-400' : 'text-slate-300 dark:text-slate-600 fill-none'"
              xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M11.48 3.499c.174-.383.72-.383.894 0l2.64 5.352 5.9 1.15c.422.082.59.59.282.895l-4.244 4.14 1.002 5.86c.071.423-.372.746-.75.545l-5.267-2.77-5.268 2.77c-.378.201-.821-.122-.75-.545l1.002-5.86-4.244-4.14c-.308-.305-.14-.813.282-.895l5.9-1.15 2.64-5.352z" />
            </svg>
          </button>
        </template>
        <!-- 数据连接状态 -->
        <button
          @click="!backendOnline && retryConnection()"
          class="flex items-center gap-1.5 text-[10px] font-semibold px-2 py-1 rounded-md bg-slate-100 dark:bg-slate-800 transition-colors"
          :class="backendOnline ? 'text-emerald-600 dark:text-emerald-400 cursor-default' : 'text-rose-600 dark:text-rose-400 hover:bg-rose-100 dark:hover:bg-rose-950/40 cursor-pointer'"
          :title="backendOnline ? delayFullOf(currentSymbol) : '后端未连接 (点击重新尝试连接)'">
          <span class="relative flex h-2 w-2">
            <span v-if="backendOnline" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2 w-2" :class="backendOnline ? 'bg-emerald-500' : 'bg-rose-500'"></span>
          </span>
          <span>{{ backendOnline ? 'LIVE' : 'OFFLINE' }}</span>
        </button>
        <!-- 拟物微质感跑道流光主题切换开关 -->
        <ThemeToggle :model-value="isDarkMode" @toggle="toggleDarkMode()" />
        <div class="h-4 w-px bg-slate-200 dark:bg-slate-800 mx-0.5"></div>
        <!-- 切换右侧边栏 (策略面板) -->
        <button @click="toggleRightSidebar()"
          class="btn-tactile p-1.5 rounded-lg transition-colors cursor-pointer"
          :class="showRightSidebar ? 'text-indigo-600 dark:text-indigo-400 bg-indigo-50/80 dark:bg-indigo-950/40 hover:bg-indigo-100 dark:hover:bg-indigo-900/50' : 'text-slate-400 dark:text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800'"
          :title="showRightSidebar ? '收起右侧策略面板 (快捷键 ] )' : '展开右侧策略面板 (快捷键 ] )'">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M15 3v18" />
          </svg>
        </button>
      </div>
    </header>

    <!-- 主交互区域 -->
    <main class="flex-1 flex overflow-hidden relative min-h-0 bg-white dark:bg-[#090d16]">

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

      <!-- 左侧边栏：自选股列表 (Swiss Modular 8pt Grid) -->
      <aside
        v-show="showLeftSidebar"
        :style="{ width: leftSidebarWidth + 'px' }"
        class="bg-white dark:bg-[#0f172a] border-r border-slate-200/80 dark:border-slate-800 flex flex-col shrink-0 overflow-y-auto scrollbar-thin">

        <!-- 自选分组 -->
        <div class="flex-1 overflow-y-auto">
          <!-- 顶部固定：标题 + 分组切换 Tab 栏 + 市场 Tab 栏 -->
          <div class="sticky top-0 z-20 bg-white/95 dark:bg-[#0f172a]/95 backdrop-blur-sm border-b border-slate-200/60 dark:border-slate-800">
            <!-- 标题栏 -->
            <div class="px-3.5 pt-2.5 pb-1 flex items-center justify-between">
              <h3 class="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                <span>自选标的</span>
                <span class="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 font-semibold">{{ filteredWatchlist.length }}/{{ watchlist.length }}</span>
              </h3>
              <!-- 收起左侧栏按钮 -->
              <button @click="toggleLeftSidebar()"
                class="btn-tactile p-1 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                title="收起左侧栏 (快捷键 [ )">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
                </svg>
              </button>
            </div>

            <!-- 分组切换 Tab 栏 (平铺核心 + 下拉分组) -->
            <div class="px-3 py-1.5 flex items-center gap-1.5 border-b border-slate-100 dark:border-slate-800/60">
              <!-- 全部 Tab -->
              <button @click="activeGroupId = 'all'"
                class="btn-tactile px-2.5 py-1 text-xs rounded-lg transition-all cursor-pointer font-semibold"
                :class="activeGroupId === 'all'
                  ? 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 border border-indigo-200/60 dark:border-indigo-800/60 shadow-2xs'
                  : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-300 border border-transparent'">
                全部
              </button>
              
              <!-- 特别关注 Tab (第一个分组) -->
              <button v-if="watchGroups.length > 0"
                @click="activeGroupId = watchGroups[0].id"
                class="btn-tactile px-2.5 py-1 text-xs rounded-lg transition-all cursor-pointer font-semibold truncate max-w-20"
                :class="activeGroupId === watchGroups[0].id
                  ? 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 border border-indigo-200/60 dark:border-indigo-800/60 shadow-2xs'
                  : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-300 border border-transparent'"
                :title="watchGroups[0].name">
                {{ watchGroups[0].name }}
              </button>

              <!-- 其他分组下拉框 -->
              <div class="relative group-dropdown-container flex-1">
                <button @click="toggleGroupDropdown"
                  class="btn-tactile w-full flex items-center justify-between gap-1 px-2 py-1 border border-slate-200 dark:border-slate-700/80 rounded-lg text-xs font-semibold bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600 cursor-pointer">
                  <span class="truncate">{{ activeGroupName }}</span>
                  <svg class="w-3 h-3 shrink-0 text-slate-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
                  </svg>
                </button>
                <transition name="dropdown">
                  <div v-if="showGroupDropdown"
                    class="absolute left-0 top-full mt-1 w-52 max-h-80 overflow-y-auto bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border border-slate-200 dark:border-slate-700 rounded-xl shadow-xl z-50 animate-fade-in-down py-1">
                    <!-- 列出已有的分组名 -->
                    <div class="max-h-56 overflow-y-auto divide-y divide-slate-100/40 dark:divide-slate-800/40">
                      <button v-for="g in watchGroups" :key="g.id"
                        @click="selectGroup(g.id)"
                        class="w-full text-left px-3.5 py-2 text-xs text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors flex items-center justify-between cursor-pointer">
                        <span class="truncate pr-2 font-medium">{{ g.name }}</span>
                        <span class="text-[9px] font-mono text-slate-400 shrink-0">({{ g.stocks.length }})</span>
                      </button>
                    </div>
                    
                    <!-- 底部分割线和操作入口 -->
                    <div class="border-t border-slate-100 dark:border-slate-800 mt-1 pt-1">
                      <button @click="triggerCreateGroup"
                        class="w-full text-left px-3.5 py-1.5 text-xs text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50/50 dark:hover:bg-indigo-950/30 transition-colors flex items-center gap-1.5 font-semibold cursor-pointer">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
                        </svg>
                        创建分组
                      </button>
                      <button @click="triggerManageGroups"
                        class="w-full text-left px-3.5 py-1.5 text-xs text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors flex items-center gap-1.5 font-medium cursor-pointer">
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
            <div class="flex items-center gap-1 px-3 pb-2 pt-0.5">
              <button v-for="t in MARKET_TABS" :key="t.key" @click="activeMarketTab = t.key"
                class="btn-tactile flex-1 text-xs font-semibold py-1 rounded-lg border transition-all cursor-pointer"
                :class="activeMarketTab === t.key
                  ? 'border-indigo-500 text-indigo-600 bg-indigo-50/70 dark:bg-indigo-950/40 dark:text-indigo-300 font-bold'
                  : 'border-slate-200 dark:border-slate-700/80 text-slate-500 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-600'">
                {{ t.label }}
              </button>
            </div>
          </div>

          <!-- 排序表头：点击 名称代码 / 最新价 / 涨跌幅 切换升降序 -->
          <div
            class="flex items-center px-3.5 py-1.5 bg-slate-50/80 dark:bg-slate-900/60 border-b border-slate-100 dark:border-slate-800 text-[10px] font-bold text-slate-400 dark:text-slate-500 select-none uppercase tracking-wider">
            <button @click="setSort('name')"
              class="flex-1 text-left flex items-center gap-0.5 transition-colors cursor-pointer"
              :class="sortBy === 'name' ? 'text-indigo-600 dark:text-indigo-400 font-bold' : 'hover:text-slate-600 dark:hover:text-slate-300'">
              名称代码
              <span v-if="sortBy === 'name'" class="text-[9px] font-mono">{{ sortDir === 'asc' ? '↑' : '↓' }}</span>
            </button>
            <div class="flex items-center gap-3 shrink-0">
              <button @click="setSort('price')"
                class="text-right transition-colors cursor-pointer"
                :class="sortBy === 'price' ? 'text-indigo-600 dark:text-indigo-400 font-bold' : 'hover:text-slate-600 dark:hover:text-slate-300'">
                最新价
                <span v-if="sortBy === 'price'" class="text-[9px] font-mono">{{ sortDir === 'asc' ? '↑' : '↓' }}</span>
              </button>
              <button @click="setSort('change')"
                class="text-right min-w-[46px] transition-colors cursor-pointer"
                :class="sortBy === 'change' ? 'text-indigo-600 dark:text-indigo-400 font-bold' : 'hover:text-slate-600 dark:hover:text-slate-300'">
                涨跌幅
                <span v-if="sortBy === 'change'" class="text-[9px] font-mono">{{ sortDir === 'asc' ? '↑' : '↓' }}</span>
              </button>
            </div>
          </div>

          <!-- 后端离线警告条 -->
          <div v-if="!backendOnline"
            class="px-3.5 py-1.5 bg-rose-500/10 border-b border-rose-500/20 flex items-center justify-between">
            <p class="text-[10px] text-rose-600 dark:text-rose-400 font-medium flex items-center gap-1.5">
              <svg class="w-3 h-3 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
              </svg>
              后端服务未连接 (127.0.0.1:8000)
            </p>
            <button @click="retryConnection()" class="text-[10px] text-rose-600 dark:text-rose-400 underline font-semibold hover:opacity-80 cursor-pointer">重试</button>
          </div>

          <!-- 空状态 -->
          <div v-if="!sortedFilteredWatchlist.length"
            class="p-8 text-center text-xs text-slate-400">
            <!-- 1. 当前激活分组为空分组的情况 -->
            <div v-if="isCurrentGroupEmpty" class="py-12 flex flex-col items-center">
              <svg class="w-12 h-12 text-slate-300 dark:text-slate-600 mb-2" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-19.5 0A2.25 2.25 0 004.5 15h15a2.25 2.25 0 002.25-2.25m-19.5 0v.25A2.25 2.25 0 004.5 17.5h15a2.25 2.25 0 002.25-2.25V12.75" />
              </svg>
              <div class="text-xs text-slate-400 dark:text-slate-500 mb-2">当前分组暂无标的</div>
              <button @click="showSearchModal = true; nextTick(() => { modalSearchInputRef?.focus(); })" 
                class="btn-tactile text-xs text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer font-semibold bg-transparent border-0 p-0">添加标的</button>
            </div>
            <!-- 2. 普通无任何自选股情况 -->
            <div v-else-if="!watchlist.length" class="py-12">
              <svg class="w-10 h-10 mx-auto mb-2 text-slate-300 dark:text-slate-600" xmlns="http://www.w3.org/2000/svg" fill="none"
                viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round"
                  d="M11.48 3.499c.174-.383.72-.383.894 0l2.64 5.352 5.9 1.15c.422.082.59.59.282.895l-4.244 4.14 1.002 5.86c.071.423-.372.746-.75.545l-5.267-2.77-5.268 2.77c-.378.201-.821-.122-.75-.545l1.002-5.86-4.244-4.14c-.308-.305-.14-.813.282-.895l5.9-1.15 2.64-5.352z" />
              </svg>
              <p class="font-medium">暂无自选股</p>
              <p class="mt-1 text-[10px] text-slate-400">在图表区或搜索栏点击星标添加</p>
            </div>
            <!-- 3. 条件过滤后的空结果 -->
            <div v-else class="py-12">
              <p>当前筛选条件下未匹配到标的</p>
            </div>
          </div>

          <!-- 过滤后的自选列表（扁平 + 市场Tab/分组交集筛选 + 表头排序） -->
          <div v-if="sortedFilteredWatchlist.length" class="divide-y divide-slate-100 dark:divide-slate-800/70">
            <div v-for="item in sortedFilteredWatchlist" :key="item" @click="selectWatchlist(item)"
              class="group px-3.5 py-2.5 hover:bg-slate-50 dark:hover:bg-slate-800/60 cursor-pointer transition-all"
              :class="currentSymbol === item ? 'bg-indigo-50/70 dark:bg-indigo-950/30 border-l-2 border-indigo-600 dark:border-indigo-400' : 'border-l-2 border-transparent'">
              <div class="flex items-center justify-between gap-2.5">
                <!-- 左侧：名称 + 星标 + 代码 + 市场标签 -->
                <div class="flex-1 min-w-0 overflow-hidden">
                  <div class="flex items-center gap-1.5 mb-0.5 min-w-0">
                    <span class="font-bold text-xs text-slate-900 dark:text-slate-100 truncate min-w-0">{{ getStockName(item) }}</span>
                    <button @click.stop="toggleWatchlist(item)" class="shrink-0 cursor-pointer p-0.5"
                      :title="isWatchlisted(item) ? '取消自选' : '加入自选'">
                      <svg class="w-3.5 h-3.5" :class="isWatchlisted(item) ? 'text-amber-400 fill-amber-400' : 'text-slate-300 dark:text-slate-600'"
                        fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499c.174-.383.72-.383.894 0l2.64 5.352 5.9 1.15c.422.082.59.59.282.895l-4.244 4.14 1.002 5.86c.071.423-.372.746-.75.545l-5.267-2.77-5.268 2.77c-.378.201-.821-.122-.75-.545l1.002-5.86-4.244-4.14c-.308-.305-.14-.813.282-.895l5.9-1.15 2.64-5.352z" />
                      </svg>
                    </button>
                  </div>
                  <div class="flex items-center gap-1.5 min-w-0">
                    <span class="text-[11px] text-slate-400 dark:text-slate-500 font-mono">{{ formatSymbol(item) }}</span>
                    <span class="text-[9px] font-bold px-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 font-mono">{{ MARKET_LABEL[marketOf(item) || 'us'] }}</span>
                  </div>
                </div>
                <!-- 右侧：最新价（涨绿跌红）+ 辅助行情信息（盘后/昨收）+ 涨跌百分比色块 -->
                <div class="flex items-center gap-2 shrink-0">
                  <div class="text-right">
                    <template v-if="rowInfoMap[item]?.price != null">
                      <!-- 第一行：当前价格（主信息） -->
                      <div class="text-xs font-bold font-mono tabular-nums leading-tight tracking-tight"
                        :class="rowInfoMap[item].isUp ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'">
                        {{ currencyOf(item) }}{{ rowInfoMap[item].formattedPrice }}
                      </div>
                      <!-- 第二行：辅助行情信息（扩展交易时段 / 昨收） -->
                      <div v-if="rowInfoMap[item].secondary"
                        class="flex items-center justify-end gap-1 text-[10px] font-mono tabular-nums leading-tight text-slate-400 dark:text-slate-500">
                        <span :class="rowInfoMap[item].secondary!.formattedChange != null
                          ? (rowInfoMap[item].secondary!.isUp ? 'text-emerald-500/80 dark:text-emerald-400/80' : 'text-rose-500/80 dark:text-rose-400/80')
                          : ''">
                          {{ rowInfoMap[item].secondary!.price }}
                          <template v-if="rowInfoMap[item].secondary!.formattedChange != null">
                            {{ rowInfoMap[item].secondary!.formattedChange }}
                          </template>
                        </span>
                        <span class="text-[9px] px-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-500 leading-tight">
                          {{ rowInfoMap[item].secondary!.label }}
                        </span>
                      </div>
                    </template>
                    <span v-else class="text-xs text-slate-400 font-mono" :title="rowInfoMap[item]?.reason || rowInfoMap[item]?.status || ''">--</span>
                  </div>
                  <!-- 右侧涨跌百分比色块（涨绿跌红，白底白字） -->
                  <div v-if="rowInfoMap[item]?.change != null"
                    class="text-[11px] font-bold font-mono tabular-nums px-1.5 py-0.5 rounded leading-tight text-white min-w-[46px] text-center shadow-2xs"
                    :class="rowInfoMap[item].isUp ? 'bg-emerald-500' : 'bg-rose-500'">
                    {{ rowInfoMap[item].formattedChange }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <!-- 比例调节拖拽条 (Left Resizer) -->
      <div v-if="showLeftSidebar" @mousedown="startResizeLeft"
        class="w-1 bg-slate-200/60 dark:bg-slate-800 hover:bg-indigo-500 active:bg-indigo-600 cursor-col-resize transition-colors shrink-0 z-50 group relative">
        <div class="absolute inset-y-0 -left-4 -right-4"></div>
        <!-- 拖拽指示器 -->
        <div class="absolute inset-y-0 -left-1 -right-1 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center pointer-events-none">
          <div class="w-1 h-8 rounded-full bg-indigo-500/50"></div>
        </div>
      </div>

      <!-- 中间：图表容器 (Swiss High-Density Trading Terminal) -->
      <div class="flex-1 flex flex-col min-h-0 min-w-0 bg-white dark:bg-[#090d16]">
        <!-- 图表工具栏：K线周期 + 时间范围（一行式，参考同花顺/TradingView 专业级排版） -->
        <div class="h-10 flex items-center justify-between px-3 border-b border-slate-200/80 dark:border-slate-800 bg-slate-50/70 dark:bg-[#0f172a]/70 backdrop-blur-sm shrink-0">
          <!-- 左侧：股票代码 + 周期选择（辅助信息，不抢焦点） -->
          <div class="flex items-center gap-2.5 shrink-0">
            <span v-if="currentSymbol" class="text-xs font-bold font-mono text-slate-900 dark:text-slate-100">{{ currentSymbol }}</span>
            <!-- 周期按钮组：分段式控件设计 -->
            <div class="flex items-center gap-0.5 bg-slate-200/50 dark:bg-slate-800/80 p-0.5 rounded-lg border border-slate-200/60 dark:border-slate-700/60">
              <button
                v-for="p in periodOptions"
                :key="p"
                @click="changePeriod(p)"
                class="btn-tactile px-2 py-0.5 text-[11px] font-semibold rounded-md transition-all cursor-pointer"
                :class="currentPeriod === p
                  ? 'text-indigo-600 dark:text-indigo-400 font-bold bg-white dark:bg-slate-700 shadow-2xs border border-slate-200/50 dark:border-slate-600/50'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-white/50 dark:hover:bg-slate-700/50'">
                {{ periodLabels[p] }}
              </button>
            </div>
            <!-- EMA / VWAP 指标开关 -->
            <div class="flex items-center gap-1 ml-1">
              <button
                @click="showEMA = !showEMA; updateIndicators(klineData)"
                class="btn-tactile px-2 py-0.5 text-[11px] font-semibold rounded-md border transition-all cursor-pointer"
                :class="showEMA ? 'border-purple-500 bg-purple-500/10 text-purple-600 dark:text-purple-400 font-bold' : 'border-slate-200 dark:border-slate-700 text-slate-500'"
              >
                EMA
              </button>
              <button
                @click="showVWAP = !showVWAP; updateIndicators(klineData)"
                class="btn-tactile px-2 py-0.5 text-[11px] font-semibold rounded-md border transition-all cursor-pointer"
                :class="showVWAP ? 'border-pink-500 bg-pink-500/10 text-pink-600 dark:text-pink-400 font-bold' : 'border-slate-200 dark:border-slate-700 text-slate-500'"
              >
                VWAP
              </button>
            </div>
          </div>

          <!-- 右侧：侧边栏 Toggle 按钮组 -->
          <div class="flex items-center gap-1.5 shrink-0">
            <!-- Toggle Left Sidebar -->
            <button @click="toggleLeftSidebar()"
              class="btn-tactile px-2 py-1 flex items-center gap-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer"
              :class="showLeftSidebar
                ? 'border-indigo-200 dark:border-indigo-800/60 bg-indigo-50/70 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 shadow-2xs'
                : 'border-slate-200 dark:border-slate-700/80 bg-white dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-600'"
              :title="showLeftSidebar ? '收起左侧自选栏 (快捷键 [ )' : '展开左侧自选栏 (快捷键 [ )'">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M9 3v18" />
              </svg>
              <span class="text-[11px]">自选栏</span>
            </button>

            <!-- Toggle Right Sidebar -->
            <button @click="toggleRightSidebar()"
              class="btn-tactile px-2 py-1 flex items-center gap-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer"
              :class="showRightSidebar
                ? 'border-indigo-200 dark:border-indigo-800/60 bg-indigo-50/70 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 shadow-2xs'
                : 'border-slate-200 dark:border-slate-700/80 bg-white dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-600'"
              :title="showRightSidebar ? '收起右侧策略面板 (快捷键 ] )' : '展开右侧策略面板 (快捷键 ] )'">
              <span class="text-[11px]">策略面板</span>
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M15 3v18" />
              </svg>
            </button>
          </div>
        </div>
        
        <!-- 数据完整性提示 -->
        <div v-if="dataWarning"
          class="px-4 py-2 bg-amber-500/10 border-b border-amber-500/20 text-amber-700 dark:text-amber-400 text-xs font-medium flex items-center gap-2">
          <span>⚠️</span><span>{{ dataWarning }}</span>
        </div>

        <!-- 实际图表绑定节点 -->
        <div ref="chartArea" class="flex-1 relative min-w-0 bg-white dark:bg-[#090d16]">
          <!-- 左侧边栏展开把手 (当左侧自选栏收起时在左边缘悬浮显示) -->
          <button
            v-if="!showLeftSidebar"
            @click="toggleLeftSidebar()"
            class="absolute top-1/2 -translate-y-1/2 left-0 z-30 bg-white/95 dark:bg-[#0f172a]/95 hover:bg-indigo-600 hover:text-white border border-l-0 border-slate-200/80 dark:border-slate-700 shadow-md py-3 px-1 rounded-r-lg text-slate-400 dark:text-slate-500 transition-all cursor-pointer group"
            title="展开自选标的 (快捷键 [ )"
          >
            <svg class="w-3.5 h-3.5 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>

          <!-- 右侧边栏展开把手 (当右侧策略面板收起时在右边缘悬浮显示) -->
          <button
            v-if="!showRightSidebar"
            @click="toggleRightSidebar()"
            class="absolute top-1/2 -translate-y-1/2 right-0 z-30 bg-white/95 dark:bg-[#0f172a]/95 hover:bg-indigo-600 hover:text-white border border-r-0 border-slate-200/80 dark:border-slate-700 shadow-md py-3 px-1 rounded-l-lg text-slate-400 dark:text-slate-500 transition-all cursor-pointer group"
            title="展开策略面板 (快捷键 ] )"
          >
            <svg class="w-3.5 h-3.5 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          <div ref="chartContainer" class="absolute inset-0 w-full h-full transition-opacity duration-300"
            :class="{ 'opacity-50': isLoading }"></div>

          <!-- 自定义K线悬停提示框 (Swiss Glassmorphic Tooltip) -->
          <div v-show="tooltipVisible" ref="tooltipEl"
            class="absolute z-40 pointer-events-none bg-white/95 dark:bg-[#0f172a]/95 backdrop-blur-md border border-slate-200/80 dark:border-slate-700/80 rounded-xl shadow-2xl py-3 px-4 text-xs font-mono animate-tooltip-in"
            :style="tooltipStyle">
            <!-- 日期 -->
            <div class="text-slate-400 dark:text-slate-500 mb-2 pb-2 border-b border-slate-100 dark:border-slate-800 font-sans text-[11px] font-bold">
              {{ tooltipData.date }}
            </div>
            <!-- OHLC 数据 -->
            <div class="space-y-1">
              <div class="flex justify-between gap-5">
                <span class="text-slate-400 dark:text-slate-500">开盘</span>
                <span class="text-slate-900 dark:text-slate-100 font-semibold tabular-nums">{{ tooltipData.open }}</span>
              </div>
              <div class="flex justify-between gap-5">
                <span class="text-slate-400 dark:text-slate-500">最高</span>
                <span class="text-rose-600 dark:text-rose-400 font-semibold tabular-nums">{{ tooltipData.high }}</span>
              </div>
              <div class="flex justify-between gap-5">
                <span class="text-slate-400 dark:text-slate-500">最低</span>
                <span class="text-emerald-600 dark:text-emerald-400 font-semibold tabular-nums">{{ tooltipData.low }}</span>
              </div>
              <div class="flex justify-between gap-5">
                <span class="text-slate-400 dark:text-slate-500">收盘</span>
                <span class="font-bold tabular-nums" :class="tooltipData.change >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'">
                  {{ tooltipData.close }}
                </span>
              </div>
            </div>
            <!-- 分隔 -->
            <div class="my-2 border-t border-slate-100 dark:border-slate-800"></div>
            <!-- 涨跌 & 振幅 -->
            <div class="space-y-1">
              <div class="flex justify-between gap-5 items-center">
                <span class="text-slate-400 dark:text-slate-500">涨跌幅</span>
                <span class="font-bold text-xs px-1.5 py-0.5 rounded tabular-nums"
                  :class="tooltipData.change >= 0 ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20'">
                  {{ tooltipData.changeStr }}
                </span>
              </div>
              <div class="flex justify-between gap-5 items-center">
                <span class="text-slate-400 dark:text-slate-500">振幅</span>
                <span class="font-semibold text-slate-700 dark:text-slate-300 tabular-nums">{{ tooltipData.amplitude }}%</span>
              </div>
              <div class="flex justify-between gap-5 items-center">
                <span class="text-slate-400 dark:text-slate-500">成交量</span>
                <span class="font-semibold text-slate-700 dark:text-slate-300 tabular-nums">{{ tooltipData.volumeStr }}</span>
              </div>
            </div>
          </div>

          <!-- 骨架屏加载状态 -->
          <div v-if="isLoading"
            class="absolute inset-0 flex bg-slate-50/60 dark:bg-slate-950/60 backdrop-blur-sm z-10 animate-fade-in">
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
            class="absolute inset-0 flex items-center justify-center bg-slate-50/50 dark:bg-[#090d16]/50">
            <div class="text-center animate-fade-in">
              <svg class="w-12 h-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" xmlns="http://www.w3.org/2000/svg" fill="none"
                viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
              <span class="text-slate-400 dark:text-slate-500 text-xs font-semibold">请在上方搜索美股代码载入行情</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 比例调节拖拽条（右侧 Resizer） -->
      <div v-if="showRightSidebar" @mousedown="startResizeRight"
        class="w-1 bg-slate-200/60 dark:bg-slate-800 hover:bg-indigo-500 active:bg-indigo-600 cursor-col-resize transition-colors shrink-0 z-50 group relative">
        <div class="absolute inset-y-0 -left-4 -right-4"></div>
        <!-- 拖拽指示器 -->
        <div class="absolute inset-y-0 -left-1 -right-1 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center pointer-events-none">
          <div class="w-1 h-8 rounded-full bg-indigo-500/50"></div>
        </div>
      </div>

      <!-- 右侧：技术分析面板 (Swiss Modular Analysis Drawer) -->
      <div
        v-show="showRightSidebar"
        :style="{ width: rightPanelWidth + 'px' }"
        class="bg-white dark:bg-[#0f172a] border-l border-slate-200/80 dark:border-slate-800 flex flex-col shrink-0 overflow-hidden">

        <div class="flex-1 overflow-y-auto scrollbar-thin p-4">
          <StrategyPanel
            :symbol="currentSymbol"
            :period="currentPeriod"
            :summary="strategySummary"
            :loading="strategyLoading"
            :sr-levels="srLevels"
            :highlighted-s-r="highlightedSR"
            @run="(mode) => handleRunStrategy(mode, true)"
            @clear="handleClearStrategy"
            @highlight-sr="highlightSRLevel"
            @scroll-to-sr="scrollToSRLevel"
            @highlight-time="(d) => chartAnnotations.highlightTimeLine(d)"
            @switch-symbol="(sym) => selectWatchlist(sym)"
            @toggle-collapse="toggleRightSidebar"
          />
        </div>
      </div>
    </main>

    <!-- 模态框组 (Swiss Impeccable Modals) -->
    
    <!-- 1. 添加自选分组 Modal -->
    <transition name="fade">
      <div v-if="showCreateGroupModal" 
        class="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/60 backdrop-blur-sm"
        @click.self="showCreateGroupModal = false">
        <div class="bg-white dark:bg-slate-800 rounded-2xl p-5 w-84 shadow-2xl border border-slate-200 dark:border-slate-700 animate-scale-in">
          <div class="flex justify-between items-center mb-4 pb-2.5 border-b border-slate-100 dark:border-slate-700/60">
            <h3 class="text-sm font-bold text-slate-900 dark:text-slate-100 tracking-tight">添加自选分组</h3>
            <button @click="showCreateGroupModal = false" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 font-bold cursor-pointer text-base">&times;</button>
          </div>
          <div class="mb-5">
            <label class="block text-xs font-semibold text-slate-400 dark:text-slate-500 mb-1.5 uppercase tracking-wider">分组名称</label>
            <input v-model="newGroupNameInput" ref="createGroupInputRef" type="text" placeholder="例如：半导体 / 核心持仓"
              class="w-full px-3 py-2 bg-slate-50 dark:bg-slate-700/60 border border-slate-200 dark:border-slate-600 rounded-lg text-xs text-slate-800 dark:text-slate-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/20 font-medium transition-all"
              @keydown.enter="handleCreateGroupSubmit" />
          </div>
          <div class="flex justify-end gap-2">
            <button @click="showCreateGroupModal = false" class="btn-tactile px-3.5 py-1.5 rounded-lg text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600 transition-colors font-semibold cursor-pointer">取消</button>
            <button @click="handleCreateGroupSubmit" class="btn-tactile px-3.5 py-1.5 rounded-lg text-xs bg-indigo-600 hover:bg-indigo-700 text-white font-semibold transition-colors cursor-pointer shadow-sm">确定</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 2. 分组管理 Modal -->
    <transition name="fade">
      <div v-if="showManageGroupsModal"
        class="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/60 backdrop-blur-sm"
        @click.self="showManageGroupsModal = false">
        <div class="bg-white dark:bg-slate-800 rounded-2xl p-5 w-96 shadow-2xl border border-slate-200 dark:border-slate-700 animate-scale-in">
          <div class="flex justify-between items-center mb-4 pb-2.5 border-b border-slate-100 dark:border-slate-700/60">
            <h3 class="text-sm font-bold text-slate-900 dark:text-slate-100 tracking-tight">分组管理</h3>
            <button @click="showManageGroupsModal = false" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 font-bold cursor-pointer text-base">&times;</button>
          </div>
          
          <div class="max-h-60 overflow-y-auto mb-4 divide-y divide-slate-100 dark:divide-slate-700/50">
            <div v-if="!watchGroups.length" class="py-8 text-center text-xs text-slate-400">暂无自定义分组</div>
            <div v-for="g in watchGroups" :key="g.id" class="py-2.5 flex items-center justify-between gap-3">
              <!-- 非编辑状态 -->
              <div v-if="editingGroupId !== g.id" class="flex-1 truncate text-xs text-slate-800 dark:text-slate-200 font-semibold">
                {{ g.name }} <span class="text-[10px] font-normal text-slate-400 font-mono">({{ g.stocks.length }} 只股票)</span>
              </div>
              <!-- 编辑状态 -->
              <input v-else v-model="editingGroupName" ref="manageRenameInputRef" type="text"
                class="flex-1 px-2 py-1 bg-slate-50 dark:bg-slate-700 border border-indigo-500 rounded text-xs text-slate-800 dark:text-slate-100 focus:outline-none"
                @keydown.enter="confirmRename(g.id)" @blur="confirmRename(g.id)" />
                
              <div class="flex items-center gap-2 shrink-0">
                <button v-if="editingGroupId !== g.id" @click="editingGroupId = g.id; editingGroupName = g.name" class="text-xs text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300 font-medium cursor-pointer">重命名</button>
                <button v-else @click="confirmRename(g.id)" class="text-xs text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300 font-medium cursor-pointer">保存</button>
                
                <button @click="deleteGroup(g.id)" class="text-xs text-rose-500 hover:text-rose-600 font-medium cursor-pointer">删除</button>
              </div>
            </div>
          </div>
          
          <div class="flex justify-end pt-2 border-t border-slate-100 dark:border-slate-700/60">
            <button @click="showManageGroupsModal = false" class="btn-tactile px-4 py-1.5 rounded-lg text-xs bg-indigo-600 text-white hover:bg-indigo-700 transition-all cursor-pointer font-semibold shadow-sm">完成</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 3. 添加自选搜索 Modal -->
    <transition name="fade">
      <div v-if="showSearchModal"
        class="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/60 backdrop-blur-sm"
        @click.self="showSearchModal = false">
        <div class="bg-white dark:bg-slate-800 rounded-2xl w-full max-w-md shadow-2xl border border-slate-200 dark:border-slate-700 overflow-hidden animate-scale-in">
          <div class="p-3.5 border-b border-slate-100 dark:border-slate-700/80 flex items-center gap-2.5">
            <svg class="w-4 h-4 text-slate-400 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input v-model="modalSearchQuery" ref="modalSearchInputRef" type="text" placeholder="输入代码 / 名称 / 拼音添加标的"
              class="flex-1 bg-transparent text-xs text-slate-800 dark:text-slate-100 focus:outline-none placeholder-slate-400 font-medium"
              @input="handleModalSearchInput" autocomplete="off" />
            <button @click="showSearchModal = false" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 font-bold cursor-pointer text-base">&times;</button>
          </div>
          <!-- 搜索结果列表 -->
          <div class="max-h-64 overflow-y-auto">
            <div v-if="modalSearchLoading" class="px-4 py-8 text-center text-xs text-slate-400">搜索中…</div>
            <div v-else-if="modalSearchQuery.trim() && !modalSearchResults.length" class="px-4 py-8 text-center text-xs text-slate-400">未找到匹配标的</div>
            <div v-else-if="!modalSearchQuery.trim()" class="px-4 py-6 text-center text-xs text-slate-400">输入关键词开始搜索</div>
            <div v-else class="divide-y divide-slate-100 dark:divide-slate-700/40">
              <button v-for="r in modalSearchResults" :key="r.symbol" @click="handleModalSearchSelect(r.symbol)"
                class="w-full text-left px-4 py-2.5 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-700/50 cursor-pointer transition-colors">
                <div class="flex items-center gap-2.5">
                  <span class="text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 font-mono w-14 text-center">{{ formatSymbol(r.symbol) }}</span>
                  <span class="text-xs font-semibold text-slate-800 dark:text-slate-100">{{ r.name }}</span>
                </div>
                <span class="text-xs text-indigo-600 dark:text-indigo-400 hover:underline font-semibold">点击添加</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue';
import GlobalSecuritySearch from './components/GlobalSecuritySearch.vue';
import StrategyPanel from './components/StrategyPanel.vue';
import ThemeToggle from './components/ThemeToggle.vue';
import {
  searchStocks,
  SUPPORTED_PERIODS,
  PERIOD_LABELS,
  BASE_URL,
  normalizeSymbol,
  stripPrefix,
  marketOf,
  formatSymbol,
  MARKET_LABEL,
  runPAStrategy,
  type Period,
} from './utils/api';
import { getChartOptions } from './utils/chartUtils';
import { useChartAnnotations, toChartTime as toChartTimeHelper } from './composables/useChartAnnotations';
import { useSmartThrottling } from './composables/useSmartThrottling';
import { useWebSocketControl } from './composables/useWebSocketControl';
import { useChartIndicators } from './composables/useChartIndicators';
import { useWatchlist, MARKET_TABS, canonSym, currencyOf } from './composables/useWatchlist';
import { useLiveQuoteSync } from './composables/useLiveQuoteSync';
import { useChartViewport } from './composables/useChartViewport';
import { useChartCore } from './composables/useChartCore';

const { showEMA, showVWAP, initIndicators, updateIndicators } = useChartIndicators();
const chartAnnotations = useChartAnnotations();
const { isWindowActive } = useSmartThrottling();

const searchComponentRef = ref<InstanceType<typeof GlobalSecuritySearch> | null>(null);
const symbolInput = ref('AAPL');
const currentSymbol = ref('');
const currentPeriod = ref<Period>('1d');
const periodOptions = SUPPORTED_PERIODS;
const periodLabels = PERIOD_LABELS;
const searchPlaceholder = '搜索代码或名称';

const backendOnline = ref(false);
const isDarkMode = ref(false);

// 浏览器风格导航历史
const navBackHistory = ref<string[]>([]);
const navForwardHistory = ref<string[]>([]);

// 图表实例与 DOM 引用
const chartContainer = ref<HTMLElement | null>(null);
const chartArea = ref<HTMLElement | null>(null);
const tooltipEl = ref<HTMLElement | null>(null);

const {
  chartInstance,
  candlestickSeries,
  volumeSeries,
  markersPlugin,
  chartReady,
  initChart: initChartCore,
  observeChartArea,
  syncChartSize: syncCoreChartSize,
  dispose: disposeChartCore,
} = useChartCore({
  chartArea,
  isDarkMode,
});

// 策略状态与竞态令牌
const strategySummary = ref<any>(null);
const strategyLoading = ref(false);
let activeStrategyRequestId = 0;
let activeStrategyAbortController: AbortController | null = null;

// 1. 组合图表视口与 K 线加载
const viewport = useChartViewport({
  isDarkMode,
  currentSymbol,
  currentPeriod,
  getChartInstance: () => chartInstance.value,
  getCandlestickSeries: () => candlestickSeries.value,
  getVolumeSeries: () => volumeSeries.value,
  getMarkersPlugin: () => markersPlugin.value,
  clearChartAnnotations: () => chartAnnotations.clearAnnotations(),
  updateIndicators,
  onBeforeLoad: () => {
    activeStrategyRequestId++;
    if (activeStrategyAbortController) {
      activeStrategyAbortController.abort();
      activeStrategyAbortController = null;
    }
    strategySummary.value = null;
  },
  onLoadSuccess: () => {
    wl.updateWatchlistPrices();
    liveSync.refreshEngineSymbols();
    handleRunStrategy('swing');
  },
  onLoadError: () => {
    strategySummary.value = null;
    wl.markAllLoadingFailed();
  },
});

const {
  klineData,
  isLoading,
  errorMsg,
  dataWarning,
  srLevels,
  highlightedSR,
  latestPrice,
  latestChange,
  highlightSRLevel,
  scrollToSRLevel,
  renderSRLevels,
  loadKlineData,
} = viewport;

// O(1) 前收盘价缓存索引表，杜绝 crosshairMove 逐帧 findIndex 遍历开销
let prevCloseMap = new Map<string, number>();

watch(
  klineData,
  (data) => {
    prevCloseMap = new Map<string, number>();
    if (!data || data.length < 2) return;
    for (let i = 1; i < data.length; i++) {
      const prevClose = data[i - 1].close;
      const curTime = data[i].time;
      prevCloseMap.set(String(curTime), prevClose);
      const ct = toChartTimeHelper(curTime);
      if (ct) {
        prevCloseMap.set(String(ct), prevClose);
      }
    }
  },
  { immediate: true }
);

// 2. 组合实时行情同步引擎
const liveSync = useLiveQuoteSync({
  currentSymbol,
  currentPeriod,
  klineData,
  latestPrice,
  latestChange,
  watchlist: { get value() { return wl.watchlist.value; } } as any,
  getChartInstance: () => chartInstance.value,
  getCandlestickSeries: () => candlestickSeries.value,
  setSuppressRangeEvents: viewport.setSuppressRangeEvents,
  onCacheUpdate: viewport.updateCache,
  onIndicatorsUpdate: updateIndicators,
  onPatchTailBar: viewport.patchTailBar,
  onSetKlineDataSilently: viewport.setKlineDataSilently,
});

const {
  quoteConfig,
  liveQuoteMap,
  displayPrice,
  displayChange,
  displayExtendedInfo,
  startQuoteEngine,
  pauseQuoteEngine,
  resumeQuoteEngine,
} = liveSync;

// 3. 组合自选分组与列表状态
const selectWatchlist = (sym: string) => {
  const target = canonSym(sym) || sym;
  if (currentSymbol.value && currentSymbol.value !== target) {
    navBackHistory.value.push(currentSymbol.value);
    navForwardHistory.value = [];
  }
  symbolInput.value = formatSymbol(target);
  loadKlineData(target, currentPeriod.value);
};

const wl = useWatchlist({
  liveQuoteMap,
  quoteConfig,
  currentSymbol,
  onSelectSymbol: selectWatchlist,
  onSymbolsChanged: () => liveSync.refreshEngineSymbols(),
});

const {
  watchGroups,
  watchlist,
  activeMarketTab,
  activeGroupId,
  showGroupDropdown,
  sortBy,
  sortDir,
  filteredWatchlist,
  sortedFilteredWatchlist,
  activeGroupName,
  isCurrentGroupEmpty,
  getStockName,
  delayFullOf,
  loadStockNameMap,
  rowInfoMap,
  loadWatchlist,
  isWatchlisted,
  toggleWatchlist,
  renameGroup,
  deleteGroup,
  selectGroup,
  toggleGroupDropdown,
  setSort,
} = wl;

// 导航与搜索
const navBack = () => {
  if (navBackHistory.value.length === 0) return;
  const prev = navBackHistory.value.pop()!;
  if (currentSymbol.value) navForwardHistory.value.push(currentSymbol.value);
  symbolInput.value = formatSymbol(prev);
  loadKlineData(prev, currentPeriod.value);
};

const navForward = () => {
  if (navForwardHistory.value.length === 0) return;
  const next = navForwardHistory.value.pop()!;
  if (currentSymbol.value) navBackHistory.value.push(currentSymbol.value);
  symbolInput.value = formatSymbol(next);
  loadKlineData(next, currentPeriod.value);
};

const refreshCurrent = () => {
  if (currentSymbol.value) {
    loadKlineData(currentSymbol.value, currentPeriod.value);
  }
};

const selectSuggestion = (symbol: string) => {
  symbolInput.value = symbol;
  handleSearch();
};

async function resolveSymbol(raw: string): Promise<string> {
  const s = (raw || '').trim();
  if (!s) return s;
  if (/^(us)/i.test(s)) return normalizeSymbol(s);
  try {
    const res = await searchStocks(s);
    if (res && res.length > 0) return res[0].symbol;
  } catch {}
  return normalizeSymbol(s);
}

const handleSearch = async () => {
  const raw = symbolInput.value.trim();
  if (!raw) return;
  const querySymbol = await resolveSymbol(raw);
  if (!querySymbol) return;
  await loadKlineData(querySymbol, currentPeriod.value);
};

const changePeriod = (period: Period) => {
  if (period === currentPeriod.value) return;
  activeStrategyRequestId++;
  if (activeStrategyAbortController) {
    activeStrategyAbortController.abort();
    activeStrategyAbortController = null;
  }
  currentPeriod.value = period;
  viewport.clearOverlays();
  strategySummary.value = null;
  if (currentSymbol.value) {
    loadKlineData(currentSymbol.value, period);
  }
};

// 后端连通性与自愈检测
let autoDetectTimer: any = null;

async function detectBackend(): Promise<boolean> {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 2000);
    const res = await fetch(`${BASE_URL}/health`, { signal: ctrl.signal, cache: 'no-store' });
    clearTimeout(timer);
    const online = res.ok;
    const wasOffline = !backendOnline.value;
    backendOnline.value = online;
    if (online && wasOffline) {
      wl.clearWatchlistCache();
      startQuoteEngine();
      if (chartReady.value && currentSymbol.value) {
        handleSearch();
      }
    }
    return online;
  } catch {
    backendOnline.value = false;
    return false;
  }
}

async function retryConnection() {
  errorMsg.value = '';
  const online = await detectBackend();
  if (online && chartReady.value && currentSymbol.value) {
    wl.clearWatchlistCache();
    handleSearch();
  } else if (!online) {
    errorMsg.value = '仍未检测到后端服务，请确认已启动后端 (FastAPI @ http://127.0.0.1:8000)。';
  }
}

// 策略执行与 WebSocket 控制面
const handleRunStrategy = async (mode: string = 'swing', isManual: boolean = false) => {
  if (!currentSymbol.value) return;
  const targetSymbol = currentSymbol.value;
  const targetPeriod = currentPeriod.value;
  const reqId = ++activeStrategyRequestId;

  if (activeStrategyAbortController) {
    activeStrategyAbortController.abort();
    activeStrategyAbortController = null;
  }
  const controller = new AbortController();
  activeStrategyAbortController = controller;

  try {
    strategyLoading.value = true;
    if (!srLevels.value.length && klineData.value.length) {
      renderSRLevels();
    }
    if (reqId !== activeStrategyRequestId || currentSymbol.value !== targetSymbol || currentPeriod.value !== targetPeriod) {
      return;
    }

    const res = await runPAStrategy(targetSymbol, targetPeriod, mode, klineData.value, controller.signal);
    if (reqId !== activeStrategyRequestId || currentSymbol.value !== targetSymbol || currentPeriod.value !== targetPeriod) {
      return;
    }
    strategySummary.value = res.summary;
    if (res.annotations) {
      chartAnnotations.setAllAnnotations(res.annotations);
    }
    renderSRLevels(undefined, res.summary);
  } catch (e: any) {
    if (e.name === 'AbortError') return;
    if (reqId === activeStrategyRequestId && currentSymbol.value === targetSymbol && currentPeriod.value === targetPeriod) {
      if (isManual) errorMsg.value = e.message || '策略执行失败，请检查K线数据';
    }
  } finally {
    if (activeStrategyAbortController === controller) {
      activeStrategyAbortController = null;
    }
    if (reqId === activeStrategyRequestId && currentSymbol.value === targetSymbol && currentPeriod.value === targetPeriod) {
      strategyLoading.value = false;
    }
  }
};

const handleClearStrategy = () => {
  activeStrategyRequestId++;
  if (activeStrategyAbortController) {
    activeStrategyAbortController.abort();
    activeStrategyAbortController = null;
  }
  chartAnnotations.clearAnnotations();
  strategySummary.value = null;
  renderSRLevels();
  try {
    chartInstance.value?.priceScale('right').setAutoScale(true);
  } catch {}
};

const wsControl = useWebSocketControl({
  onRefreshWatchlist: () => loadWatchlist(),
  onOpenChart(symbol, period) {
    currentSymbol.value = symbol;
    symbolInput.value = stripPrefix(symbol);
    if (period && (periodOptions as readonly string[]).includes(period)) {
      currentPeriod.value = period as any;
    }
    handleSearch();
  },
  onAddMarkers(markers, sym) {
    if (!sym || normalizeSymbol(sym) !== normalizeSymbol(currentSymbol.value)) return;
    chartAnnotations.setMarkers(markers);
  },
  onDrawLines(lines, sym) {
    if (!sym || normalizeSymbol(sym) !== normalizeSymbol(currentSymbol.value)) return;
    chartAnnotations.setPriceLines(lines);
  },
  onDrawBoxes(boxes, sym) {
    if (!sym || normalizeSymbol(sym) !== normalizeSymbol(currentSymbol.value)) return;
    chartAnnotations.setBoxes(boxes);
  },
  onDrawChannelLines(channelLines, sym) {
    if (!sym || normalizeSymbol(sym) !== normalizeSymbol(currentSymbol.value)) return;
    chartAnnotations.setChannelLines(channelLines);
  },
  onDrawWaveLines(waveLines, sym) {
    if (!sym || normalizeSymbol(sym) !== normalizeSymbol(currentSymbol.value)) return;
    chartAnnotations.setWaveLines(waveLines);
  },
  onDrawTimeLines(timeLines, sym) {
    if (!sym || normalizeSymbol(sym) !== normalizeSymbol(currentSymbol.value)) return;
    chartAnnotations.setTimeLines(timeLines);
  },
  onDrawFibLines(fibLines, sym) {
    if (!sym || normalizeSymbol(sym) !== normalizeSymbol(currentSymbol.value)) return;
    chartAnnotations.setFibLines(fibLines);
  },
  onDrawGapBoxes(gapBoxes, sym) {
    if (!sym || normalizeSymbol(sym) !== normalizeSymbol(currentSymbol.value)) return;
    chartAnnotations.setGapBoxes(gapBoxes);
  },
  onDrawEma200(ema200Data, sym) {
    if (!sym || normalizeSymbol(sym) !== normalizeSymbol(currentSymbol.value)) return;
    chartAnnotations.setEma200Data(ema200Data);
  },
  onClearAnnotations(kind, sym) {
    if (sym && normalizeSymbol(sym) !== normalizeSymbol(currentSymbol.value)) return;
    if (kind === 'marker') chartAnnotations.setMarkers([]);
    else if (kind === 'line') chartAnnotations.setPriceLines([]);
    else if (kind === 'box') chartAnnotations.setBoxes([]);
    else if (kind === 'channel') chartAnnotations.setChannelLines([]);
    else if (kind === 'wave') chartAnnotations.setWaveLines(null);
    else if (kind === 'time_line') chartAnnotations.setTimeLines([]);
    else if (kind === 'fib_line') chartAnnotations.setFibLines([]);
    else if (kind === 'gap_box') chartAnnotations.setGapBoxes([]);
    else if (kind === 'ema200') chartAnnotations.setEma200Data([]);
    else chartAnnotations.clearAnnotations();
  },
  onRunStrategy: async (mode) => handleRunStrategy(mode, true),
  onCaptureChart() {
    if (chartInstance.value && typeof (chartInstance.value as any).takeScreenshot === 'function') {
      try {
        const canvas = (chartInstance.value as any).takeScreenshot();
        if (canvas) return canvas.toDataURL('image/png');
      } catch {}
    }
    const canvas = chartContainer.value?.querySelector('canvas');
    return canvas ? canvas.toDataURL('image/png') : null;
  },
});

// 主题切换
const toChartTime = (timeStr: any): any => toChartTimeHelper(timeStr);

const applyChartTheme = (isDark: boolean) => {
  chartAnnotations.setDarkMode(isDark);
  if (!chartInstance.value) return;
  chartInstance.value.applyOptions(getChartOptions(isDark));
  if (candlestickSeries.value) {
    const upColor = isDark ? '#34d399' : '#10b981';
    const downColor = isDark ? '#fb7185' : '#f43f5e';
    candlestickSeries.value.applyOptions({ upColor, downColor, wickUpColor: upColor, wickDownColor: downColor });
  }
  if (volumeSeries.value && klineData.value.length > 0) {
    const upVol = isDark ? 'rgba(52, 211, 153, 0.35)' : 'rgba(16, 185, 129, 0.25)';
    const downVol = isDark ? 'rgba(251, 113, 133, 0.35)' : 'rgba(244, 63, 94, 0.25)';
    volumeSeries.value.setData(
      klineData.value.map((d) => ({
        time: toChartTime(d.time),
        value: d.volume,
        color: d.close >= d.open ? upVol : downVol,
      }))
    );
  }
};

const toggleDarkMode = () => {
  isDarkMode.value = !isDarkMode.value;
  document.documentElement.classList.toggle('dark', isDarkMode.value);
  localStorage.setItem('darkMode', isDarkMode.value ? 'true' : 'false');
  applyChartTheme(isDarkMode.value);
};

const initDarkMode = () => {
  if (localStorage.getItem('darkMode') === 'true') {
    isDarkMode.value = true;
    document.documentElement.classList.add('dark');
  }
};

// 模态框与分组管理 UI 状态
const showCreateGroupModal = ref(false);
const showManageGroupsModal = ref(false);
const showSearchModal = ref(false);
const newGroupNameInput = ref('');
const modalSearchQuery = ref('');
const modalSearchResults = ref<any[]>([]);
const modalSearchLoading = ref(false);
const createGroupInputRef = ref<HTMLInputElement | null>(null);
const modalSearchInputRef = ref<HTMLInputElement | null>(null);
const editingGroupId = ref<string | null>(null);
const editingGroupName = ref('');

const triggerCreateGroup = () => {
  showGroupDropdown.value = false;
  showCreateGroupModal.value = true;
  nextTick(() => createGroupInputRef.value?.focus());
};

const triggerManageGroups = () => {
  showGroupDropdown.value = false;
  showManageGroupsModal.value = true;
};

const handleCreateGroupSubmit = () => {
  wl.createGroup(newGroupNameInput.value);
  newGroupNameInput.value = '';
  showCreateGroupModal.value = false;
};

const confirmRename = (id: string) => {
  if (editingGroupId.value !== id) return;
  renameGroup(id, editingGroupName.value);
  editingGroupId.value = null;
};

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
      modalSearchResults.value = (await searchStocks(q)) || [];
    } catch {
      modalSearchResults.value = [];
    } finally {
      modalSearchLoading.value = false;
    }
  }, 250);
};

const handleModalSearchSelect = (sym: string) => {
  const target = wl.addToActiveGroup(sym);
  selectWatchlist(target);
  showSearchModal.value = false;
  modalSearchQuery.value = '';
  modalSearchResults.value = [];
};

// 侧边栏展开/收起状态与持久化
const showLeftSidebar = ref(localStorage.getItem('app_show_left_sidebar') !== 'false');
const showRightSidebar = ref(localStorage.getItem('app_show_right_sidebar') !== 'false');

const toggleLeftSidebar = () => {
  showLeftSidebar.value = !showLeftSidebar.value;
  try {
    localStorage.setItem('app_show_left_sidebar', String(showLeftSidebar.value));
  } catch {}
  nextTick(() => {
    syncChartSize();
  });
};

const toggleRightSidebar = () => {
  showRightSidebar.value = !showRightSidebar.value;
  try {
    localStorage.setItem('app_show_right_sidebar', String(showRightSidebar.value));
  } catch {}
  nextTick(() => {
    syncChartSize();
  });
};

// 左右栏拖拽调宽
const leftSidebarWidth = ref(320);
const rightPanelWidth = ref(340);
let resizeRaf: number | null = null;

const syncChartSize = () => {
  requestAnimationFrame(() => {
    syncCoreChartSize(chartArea.value);
  });
};

const createColumnResizer = (getStartWidth: () => number, setWidth: (w: number) => void, sign: 1 | -1) => {
  return (e: MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = getStartWidth();
    let latestWidth = startWidth;

    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const deltaX = (moveEvent.clientX - startX) * sign;
      const maxL = Math.floor(window.innerWidth / 3);
      latestWidth = Math.max(260, Math.min(startWidth + deltaX, maxL));
      if (resizeRaf === null) {
        resizeRaf = requestAnimationFrame(() => {
          setWidth(latestWidth);
          syncChartSize();
          resizeRaf = null;
        });
      }
    };

    const cleanup = () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', cleanup);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      if (resizeRaf !== null) {
        cancelAnimationFrame(resizeRaf);
        resizeRaf = null;
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', cleanup);
  };
};

const startResizeLeft = createColumnResizer(() => leftSidebarWidth.value, (w) => (leftSidebarWidth.value = w), 1);
const startResizeRight = createColumnResizer(() => rightPanelWidth.value, (w) => (rightPanelWidth.value = w), -1);

// 十字准线悬停 Tooltip
const tooltipVisible = ref(false);
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

const skeletonCandles = Array.from({ length: 56 }, () => 28 + Math.floor(Math.random() * 68));
const skeletonVol = Array.from({ length: 56 }, () => 18 + Math.floor(Math.random() * 62));

const formatVolumeNum = (vol: number): string => {
  if (vol >= 1e9) return (vol / 1e9).toFixed(2) + 'B';
  if (vol >= 1e6) return (vol / 1e6).toFixed(2) + 'M';
  if (vol >= 1e3) return (vol / 1e3).toFixed(2) + 'K';
  return vol.toString();
};

const findPrevClose = (time: any): number | null => {
  if (time == null) return null;
  if (typeof time === 'object' && time.year) {
    const y = time.year;
    const m = String(time.month).padStart(2, '0');
    const d = String(time.day).padStart(2, '0');
    const dateStr = `${y}-${m}-${d}`;
    return prevCloseMap.get(dateStr) ?? null;
  }
  const s = String(time);
  return prevCloseMap.get(s) ?? null;
};

const formatDate = (input: Date | string): string => {
  try {
    const date = input instanceof Date ? input : new Date(input);
    if (isNaN(date.getTime())) return String(input);
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    return `${date.getFullYear()}/${String(date.getMonth() + 1).padStart(2, '0')}/${String(date.getDate()).padStart(2, '0')} ${weekdays[date.getDay()]}`;
  } catch {
    return String(input);
  }
};

const updateTooltipPosition = (relX: number) => {
  if (!chartArea.value || !tooltipEl.value) return;
  const areaRect = chartArea.value.getBoundingClientRect();
  const tipRect = tooltipEl.value.getBoundingClientRect();
  const padding = 8;
  const left = relX > areaRect.width / 2 ? padding : areaRect.width - tipRect.width - padding;
  tooltipStyle.value = { left: `${left}px`, top: `${padding}px` };
};

// 初始化图表面板
const initChart = () => {
  if (!chartContainer.value) return;

  initChartCore(chartContainer.value, {
    isDark: isDarkMode.value,
    onRangeChange: viewport.onVisibleLogicalRangeChanged,
    onCrosshairMove: (param) => {
      if (!param.point || !param.time || !param.seriesData) {
        tooltipVisible.value = false;
        return;
      }
      const candleData = param.seriesData.get(candlestickSeries.value) as any;
      if (!candleData) {
        tooltipVisible.value = false;
        return;
      }
      const timeStr = String(param.time);
      const prevClose = findPrevClose(param.time as any);
      const change = prevClose !== null ? ((candleData.close - prevClose) / prevClose) * 100 : 0;
      const amplitude = prevClose !== null ? ((candleData.high - candleData.low) / prevClose) * 100 : 0;
      const volData = param.seriesData.get(volumeSeries.value) as any;

      tooltipData.value = {
        date: formatDate(timeStr),
        open: candleData.open.toFixed(2),
        high: candleData.high.toFixed(2),
        low: candleData.low.toFixed(2),
        close: candleData.close.toFixed(2),
        change,
        changeStr: `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`,
        amplitude: +amplitude.toFixed(2),
        volumeStr: formatVolumeNum(volData?.value ?? 0),
      };

      tooltipVisible.value = true;
      nextTick(() => updateTooltipPosition(param.point!.x));
    },
  });

  chartAnnotations.init(chartInstance.value!, candlestickSeries.value!, markersPlugin.value!);
  chartAnnotations.clearAnnotations();
  chartAnnotations.setDarkMode(isDarkMode.value);
  initIndicators(chartInstance.value!);
  applyChartTheme(isDarkMode.value);
};

// 生命周期与全局事件
watch(isWindowActive, (active) => {
  if (active) {
    if (backendOnline.value) resumeQuoteEngine();
  } else {
    pauseQuoteEngine();
  }
});

watch([showEMA, showVWAP], () => {
  if (klineData.value.length > 0) updateIndicators(klineData.value);
});

watch([currentSymbol, currentPeriod, klineData], () => {
  const lastBar = klineData.value.length ? klineData.value[klineData.value.length - 1] : null;
  wsControl.sendState({
    symbol: currentSymbol.value,
    period: currentPeriod.value,
    current_price: lastBar ? lastBar.close : 0,
  });
});

const handleClickOutside = (e: MouseEvent) => {
  const target = e.target as HTMLElement;
  if (showGroupDropdown.value && !target.closest('.group-dropdown-container')) showGroupDropdown.value = false;
};

const PERIOD_KEY_MAP: Record<string, Period> = {
  '1': '5m',
  '2': '15m',
  '3': '1h',
  '4': '4h',
  '5': '1d',
  '6': '1w',
  '7': '1M',
  '8': '3M',
};

const handleGlobalKeydown = (e: KeyboardEvent) => {
  const target = e.target as HTMLElement;
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    searchComponentRef.value?.focus();
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
    e.preventDefault();
    toggleLeftSidebar();
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'j') {
    e.preventDefault();
    toggleRightSidebar();
    return;
  }
  if (e.key === '[' && !e.ctrlKey && !e.metaKey && !e.altKey) {
    e.preventDefault();
    toggleLeftSidebar();
    return;
  }
  if (e.key === ']' && !e.ctrlKey && !e.metaKey && !e.altKey) {
    e.preventDefault();
    toggleRightSidebar();
    return;
  }
  if (PERIOD_KEY_MAP[e.key]) {
    e.preventDefault();
    changePeriod(PERIOD_KEY_MAP[e.key]);
    return;
  }
  if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
    e.preventDefault();
    const list = sortedFilteredWatchlist.value;
    if (!list.length) return;
    const current = canonSym(currentSymbol.value);
    const currIdx = list.findIndex((s) => canonSym(s) === current);
    const nextIdx =
      e.key === 'ArrowDown'
        ? currIdx < list.length - 1
          ? currIdx + 1
          : 0
        : currIdx > 0
          ? currIdx - 1
          : list.length - 1;
    selectWatchlist(list[nextIdx]);
    return;
  }
  if (e.code === 'Space' || e.key === ' ') {
    e.preventDefault();
    if (currentSymbol.value && klineData.value.length > 0) handleRunStrategy('swing');
  }
};

// 首屏 K 线与自选行情均就绪后，平滑关闭开屏动画并销毁监听
const stopSplashWatch = watch(
  [klineData, liveQuoteMap],
  ([klines, quotes]) => {
    if (klines.length > 0 || Object.keys(quotes).length > 0) {
      (window as any).__dismissSplash?.();
      stopSplashWatch();
    }
  }
);

onMounted(async () => {
  loadStockNameMap();
  initDarkMode();

  // 关键优化：优先加载本地与远程自选列表，保证 quoteEngine 启动瞬间就拥有完整的标的集合，消除多轮串行排队与标的遗漏
  await loadWatchlist();

  startQuoteEngine();
  await detectBackend();
  autoDetectTimer = setInterval(async () => {
    if (!backendOnline.value) {
      await detectBackend();
    }
  }, 2000);

  nextTick(() => {
    if (!chartContainer.value) return;
    const observer = new ResizeObserver((entries) => {
      if (entries[0] && entries[0].contentRect.height > 1) {
        observer.disconnect();
        initChart();
        chartReady.value = true;
        handleSearch();

        // 持续监听 chartArea 尺寸变动，在侧边栏折叠/展开或窗口变化时自适应图表
        if (chartArea.value) {
          observeChartArea(chartArea.value);
        }
      }
    });
    observer.observe(chartContainer.value);
  });

  window.addEventListener('keydown', handleGlobalKeydown);
  document.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  if (autoDetectTimer) {
    clearInterval(autoDetectTimer);
    autoDetectTimer = null;
  }
  chartAnnotations.dispose();
  disposeChartCore();
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
