// useSmartThrottling.ts
// 智能后台节流与超低待机 CPU 控制机制
import { ref, onMounted, onUnmounted } from 'vue';

export function useSmartThrottling() {
  const isWindowActive = ref(true);
  const isDocumentVisible = ref(!document.hidden);

  type Poller = {
    fn: () => void | Promise<void>;
    intervalMs: number;
    timerId: any;
  };
  const pollers: Poller[] = [];

  function handleVisibilityChange() {
    const visible = document.visibilityState === 'visible';
    isDocumentVisible.value = visible;
    updateActiveState();
  }

  function handleFocus() {
    isWindowActive.value = true;
    updateActiveState();
  }

  function handleBlur() {
    // 焦点离开时可能仍在可见视口，故以 document.hidden 综合判断
    if (document.hidden) {
      isWindowActive.value = false;
      updateActiveState();
    }
  }

  function updateActiveState() {
    const active = !document.hidden;
    isWindowActive.value = active;

    if (active) {
      // 唤醒：立即执行一次所有轮询任务，并按正常高频节奏恢复
      for (const p of pollers) {
        clearInterval(p.timerId);
        try {
          p.fn();
        } catch (e) {
          console.warn('Waking poll error:', e);
        }
        p.timerId = setInterval(p.fn, p.intervalMs);
      }
    } else {
      // 休眠：挂起高频轮询，暂停或降级到 60 秒最低心跳防断连，彻底消除待机 CPU 消耗
      for (const p of pollers) {
        clearInterval(p.timerId);
        p.timerId = setInterval(p.fn, Math.max(60000, p.intervalMs * 10));
      }
    }
  }

  /**
   * 注册受节流保护的轮询任务
   */
  function registerPoll(fn: () => void | Promise<void>, intervalMs: number) {
    const poller: Poller = {
      fn,
      intervalMs,
      timerId: null,
    };
    if (isWindowActive.value) {
      poller.timerId = setInterval(fn, intervalMs);
    } else {
      poller.timerId = setInterval(fn, Math.max(60000, intervalMs * 10));
    }
    pollers.push(poller);

    return () => {
      clearInterval(poller.timerId);
      const idx = pollers.indexOf(poller);
      if (idx !== -1) pollers.splice(idx, 1);
    };
  }

  onMounted(() => {
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleFocus);
    window.addEventListener('blur', handleBlur);
  });

  onUnmounted(() => {
    document.removeEventListener('visibilitychange', handleVisibilityChange);
    window.removeEventListener('focus', handleFocus);
    window.removeEventListener('blur', handleBlur);
    for (const p of pollers) {
      clearInterval(p.timerId);
    }
    pollers.length = 0;
  });

  return {
    isWindowActive,
    isDocumentVisible,
    registerPoll,
  };
}
