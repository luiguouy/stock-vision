<template>
  <button
    type="button"
    role="switch"
    :aria-checked="modelValue"
    :title="modelValue ? '切换到浅色模式' : '切换到深色模式'"
    @click="handleClick"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerCancel"
    class="theme-switch relative inline-flex items-center w-16 h-8 p-[3px] rounded-full select-none focus:outline-none shrink-0 touch-none overflow-hidden"
    :class="isDragging ? 'cursor-grabbing' : 'cursor-grab'"
  >
    <!-- 底座基础暗底，防止半透明混合时漏光 -->
    <span class="absolute inset-0 rounded-full bg-[#151821] pointer-events-none" />

    <!-- 跑道底座：夜间渐变背景与内阴影 -->
    <span
      class="theme-switch-bg theme-switch-bg--dark absolute inset-0 rounded-full pointer-events-none will-change-[opacity]"
      :style="{ opacity: 1 - currentProgress }"
    />

    <!-- 跑道底座：日间渐变背景与内阴影 -->
    <span
      class="theme-switch-bg theme-switch-bg--light absolute inset-0 rounded-full pointer-events-none will-change-[opacity]"
      :style="{ opacity: currentProgress }"
    />

    <!-- 滑动圆角矩形 Thumb -->
    <span
      class="theme-thumb relative w-[26px] h-[26px] rounded-[8px] flex items-center justify-center will-change-transform"
      :style="{ transform: `translateX(${currentProgress * 32}px)` }"
    >
      <!-- 滑块基础暗底 -->
      <span class="absolute inset-0 rounded-[8px] bg-[#1e2230] pointer-events-none" />

      <!-- 滑块：夜间金属暗色质感与紫蓝微光 -->
      <span
        class="theme-thumb-bg theme-thumb-bg--dark absolute inset-0 rounded-[8px] pointer-events-none will-change-[opacity]"
        :style="{ opacity: 1 - currentProgress }"
      />

      <!-- 滑块：日间暖白瓷质感与金色琥珀微光 -->
      <span
        class="theme-thumb-bg theme-thumb-bg--light absolute inset-0 rounded-[8px] pointer-events-none will-change-[opacity]"
        :style="{ opacity: currentProgress }"
      />

      <!-- 边缘游走流光边框 (SVG 随进度实时巡游) -->
      <svg
        class="absolute inset-0 w-full h-full pointer-events-none overflow-visible z-10"
        viewBox="0 0 26 26"
      >
        <rect
          x="0.75"
          y="0.75"
          width="24.5"
          height="24.5"
          rx="7.5"
          fill="none"
          stroke-width="1.6"
          stroke-linecap="round"
          pathLength="100"
          class="rim-arc"
          :style="rimArcStyle"
        />
      </svg>

      <!-- 点阵像素图标 & 粒子重组画布 -->
      <canvas
        ref="canvasRef"
        class="w-[22px] h-[22px] pointer-events-none relative z-20"
      />
    </span>
  </button>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';

const props = defineProps<{
  modelValue: boolean; // true = 夜间模式 (Dark, 对应进度 0), false = 白天模式 (Light, 对应进度 1)
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void;
  (e: 'toggle'): void;
}>();

const canvasRef = ref<HTMLCanvasElement | null>(null);

// 进度：0.0 代表完全的夜间模式 (Moon)，1.0 代表完全的日间模式 (Sun)
const currentProgress = ref<number>(props.modelValue ? 0 : 1);
const isDragging = ref<boolean>(false);

interface PixelDot {
  gx: number;
  gy: number;
  alpha: number;
  twinkle?: boolean;
}

interface MorphParticle {
  // 月亮端配置
  mx: number;
  my: number;
  mAlpha: number;
  twinkle: boolean;
  // 太阳端配置
  sx: number;
  sy: number;
  sAlpha: number;
  // 变换中的离散飞散参数
  ox: number;
  oy: number;
  delay: number;
}

// 11x11 像素矩阵：夜间月亮（含暗面轮廓 + 右上角星光）
const MOON_DOTS: PixelDot[] = [
  // 亮部弯月
  { gx: 4, gy: 2, alpha: 1 }, { gx: 5, gy: 2, alpha: 1 },
  { gx: 3, gy: 3, alpha: 1 }, { gx: 4, gy: 3, alpha: 1 },
  { gx: 2, gy: 4, alpha: 1 }, { gx: 3, gy: 4, alpha: 1 }, { gx: 4, gy: 4, alpha: 1 },
  { gx: 2, gy: 5, alpha: 1 }, { gx: 3, gy: 5, alpha: 1 }, { gx: 4, gy: 5, alpha: 1 },
  { gx: 2, gy: 6, alpha: 1 }, { gx: 3, gy: 6, alpha: 1 }, { gx: 4, gy: 6, alpha: 1 }, { gx: 5, gy: 6, alpha: 1 },
  { gx: 3, gy: 7, alpha: 1 }, { gx: 4, gy: 7, alpha: 1 }, { gx: 5, gy: 7, alpha: 1 }, { gx: 6, gy: 7, alpha: 1 }, { gx: 7, gy: 7, alpha: 1 },
  { gx: 4, gy: 8, alpha: 1 }, { gx: 5, gy: 8, alpha: 1 }, { gx: 6, gy: 8, alpha: 1 },
  // 月球暗面微光点阵
  { gx: 6, gy: 2, alpha: 0.22 },
  { gx: 5, gy: 3, alpha: 0.22 }, { gx: 6, gy: 3, alpha: 0.22 }, { gx: 7, gy: 3, alpha: 0.22 },
  { gx: 5, gy: 4, alpha: 0.22 }, { gx: 6, gy: 4, alpha: 0.22 }, { gx: 7, gy: 4, alpha: 0.22 },
  { gx: 5, gy: 5, alpha: 0.22 }, { gx: 6, gy: 5, alpha: 0.22 }, { gx: 7, gy: 5, alpha: 0.22 },
  { gx: 6, gy: 6, alpha: 0.22 }, { gx: 7, gy: 6, alpha: 0.22 },
  // 右上角微星
  { gx: 8, gy: 1, alpha: 0.85, twinkle: true },
  { gx: 9, gy: 3, alpha: 0.75, twinkle: true },
];

// 11x11 像素矩阵：日间太阳（切角核心 + 八向光芒）
const SUN_DOTS: PixelDot[] = [
  // 太阳核心 (切角 5x5)
  { gx: 4, gy: 3, alpha: 1 }, { gx: 5, gy: 3, alpha: 1 }, { gx: 6, gy: 3, alpha: 1 },
  { gx: 3, gy: 4, alpha: 1 }, { gx: 4, gy: 4, alpha: 1 }, { gx: 5, gy: 4, alpha: 1 }, { gx: 6, gy: 4, alpha: 1 }, { gx: 7, gy: 4, alpha: 1 },
  { gx: 3, gy: 5, alpha: 1 }, { gx: 4, gy: 5, alpha: 1 }, { gx: 5, gy: 5, alpha: 1 }, { gx: 6, gy: 5, alpha: 1 }, { gx: 7, gy: 5, alpha: 1 },
  { gx: 3, gy: 6, alpha: 1 }, { gx: 4, gy: 6, alpha: 1 }, { gx: 5, gy: 6, alpha: 1 }, { gx: 6, gy: 6, alpha: 1 }, { gx: 7, gy: 6, alpha: 1 },
  { gx: 4, gy: 7, alpha: 1 }, { gx: 5, gy: 7, alpha: 1 }, { gx: 6, gy: 7, alpha: 1 },
  // 上下左右主射线
  { gx: 5, gy: 0, alpha: 0.9 }, { gx: 5, gy: 1, alpha: 0.95 },
  { gx: 5, gy: 9, alpha: 0.95 }, { gx: 5, gy: 10, alpha: 0.9 },
  { gx: 0, gy: 5, alpha: 0.9 }, { gx: 1, gy: 5, alpha: 0.95 },
  { gx: 9, gy: 5, alpha: 0.95 }, { gx: 10, gy: 5, alpha: 0.9 },
  // 四角斜向光芒
  { gx: 2, gy: 2, alpha: 0.85 },
  { gx: 8, gy: 2, alpha: 0.85 },
  { gx: 2, gy: 8, alpha: 0.85 },
  { gx: 8, gy: 8, alpha: 0.85 },
];

const SIZE = 22;
const GRID = 11;
const STEP = SIZE / GRID; // 每格 2px
const DOT_SIZE = 1.45;

// 生成确定性映射的粒子群，拖动来回时粒子轨迹稳定连续
function createParticles(): MorphParticle[] {
  let seed = 42;
  const rnd = () => {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    return seed / 4294967296;
  };

  const count = Math.max(MOON_DOTS.length, SUN_DOTS.length);
  const list: MorphParticle[] = [];

  for (let i = 0; i < count; i++) {
    const m = MOON_DOTS[i % MOON_DOTS.length];
    const s = SUN_DOTS[i % SUN_DOTS.length];
    const angle = rnd() * Math.PI * 2;
    const radius = 3.2 + rnd() * 5.2;

    list.push({
      mx: m.gx * STEP + (STEP - DOT_SIZE) / 2,
      my: m.gy * STEP + (STEP - DOT_SIZE) / 2,
      mAlpha: i < MOON_DOTS.length ? m.alpha : 0,
      twinkle: Boolean(i < MOON_DOTS.length && m.twinkle),
      sx: s.gx * STEP + (STEP - DOT_SIZE) / 2,
      sy: s.gy * STEP + (STEP - DOT_SIZE) / 2,
      sAlpha: i < SUN_DOTS.length ? s.alpha : 0,
      ox: Math.cos(angle) * radius,
      oy: Math.sin(angle) * radius,
      delay: rnd() * 0.14,
    });
  }
  return list;
}

const particles = createParticles();

function easeInOutCubic(t: number): number {
  const clamped = Math.max(0, Math.min(1, t));
  return clamped < 0.5 ? 4 * clamped * clamped * clamped : 1 - Math.pow(-2 * clamped + 2, 3) / 2;
}

// 边缘游走流光边框样式：随着拖动实时变换位置、颜色与阴影
const rimArcStyle = computed(() => {
  const p = currentProgress.value;
  // offset 从 -42 (夜间左下) 平滑游走到 8 (白天右上)
  const offset = -42 + p * 50;

  // 描边色彩插值：#a5b4fc (165, 180, 252) -> #f59e0b (245, 158, 11)
  const r = Math.round(165 + (245 - 165) * p);
  const g = Math.round(180 + (158 - 180) * p);
  const b = Math.round(252 + (11 - 252) * p);

  // 阴影色彩插值：rgba(129, 140, 248, 0.95) -> rgba(245, 158, 11, 0.9)
  const sr = Math.round(129 + (245 - 129) * p);
  const sg = Math.round(140 + (158 - 140) * p);
  const sb = Math.round(248 + (11 - 248) * p);
  const sa = (0.95 + (0.9 - 0.95) * p).toFixed(2);

  return {
    strokeDashoffset: `${offset}`,
    stroke: `rgb(${r}, ${g}, ${b})`,
    filter: `drop-shadow(0 0 3.5px rgba(${sr}, ${sg}, ${sb}, ${sa}))`,
  };
});

// Canvas 渲染函数：精确根据 progress (0~1) 绘制粒子形态
function renderCanvas(t: number, now = performance.now()) {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, SIZE, SIZE);

  // 颜色插值：夜间月光纯白 (255,255,255) <-> 日间深炭灰 (30,32,40)
  const colorT = easeInOutCubic(t);
  const r = Math.round(255 + (30 - 255) * colorT);
  const g = Math.round(255 + (32 - 255) * colorT);
  const b = Math.round(255 + (40 - 255) * colorT);

  for (const p of particles) {
    const localT = Math.max(0, Math.min(1, (t - p.delay) / (1 - p.delay)));
    const moveT = easeInOutCubic(localT);
    // 飞散包络线：在动画中点 (0.5) 达到最大离散度，随后收拢
    const scatter = Math.sin(localT * Math.PI);

    const x = p.mx + (p.sx - p.mx) * moveT + p.ox * scatter;
    const y = p.my + (p.sy - p.my) * moveT + p.oy * scatter;
    let alpha = p.mAlpha + (p.sAlpha - p.mAlpha) * moveT;

    // 夜间形态下星光微闪呼吸效果
    if (t < 0.1 && p.twinkle) {
      alpha *= 0.65 + 0.35 * Math.sin(now * 0.004 + p.mx);
    }

    if (alpha <= 0.02) continue;

    ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha.toFixed(3)})`;
    if (t < 0.5 && alpha > 0.8) {
      const glowAlpha = ((1 - t * 2) * 0.75).toFixed(2);
      ctx.shadowColor = `rgba(199, 210, 254, ${glowAlpha})`;
      ctx.shadowBlur = 3;
    } else {
      ctx.shadowBlur = 0;
    }
    ctx.fillRect(x, y, DOT_SIZE, DOT_SIZE);
  }
}

// 动画与微闪循环控制器
let animRafId: number | null = null;
let idleRafId: number | null = null;
let currentAnimTarget: number | null = null;

function idleLoop(now: number) {
  if (currentProgress.value === 0 && !isDragging.value && animRafId === null) {
    renderCanvas(0, now);
    idleRafId = requestAnimationFrame(idleLoop);
  } else {
    idleRafId = null;
  }
}

function startIdleLoopIfNeeded() {
  if (currentProgress.value === 0 && idleRafId === null && animRafId === null) {
    idleRafId = requestAnimationFrame(idleLoop);
  }
}

function stopIdleLoop() {
  if (idleRafId !== null) {
    cancelAnimationFrame(idleRafId);
    idleRafId = null;
  }
}

// 平滑弹性过渡到目标值 (0 或 1)
function animateTo(targetP: number, duration = 480) {
  stopIdleLoop();
  if (animRafId !== null) {
    cancelAnimationFrame(animRafId);
    animRafId = null;
  }

  const fromP = currentProgress.value;
  currentAnimTarget = targetP;

  if (Math.abs(fromP - targetP) < 0.002) {
    currentProgress.value = targetP;
    currentAnimTarget = null;
    renderCanvas(targetP);
    startIdleLoopIfNeeded();
    return;
  }

  const startTime = performance.now();
  // 按照剩余行程比例动态调整时长，保持自然的物理反馈速度
  const actualDuration = Math.max(180, Math.min(duration, Math.abs(targetP - fromP) * duration));

  function step(now: number) {
    const elapsed = now - startTime;
    const progressRatio = Math.min(1, elapsed / actualDuration);
    const ease = easeInOutCubic(progressRatio);

    currentProgress.value = fromP + (targetP - fromP) * ease;
    renderCanvas(currentProgress.value, now);

    if (progressRatio < 1) {
      animRafId = requestAnimationFrame(step);
    } else {
      currentProgress.value = targetP;
      currentAnimTarget = null;
      animRafId = null;
      renderCanvas(targetP, now);
      startIdleLoopIfNeeded();
    }
  }

  animRafId = requestAnimationFrame(step);
}

// 拖动与手势状态
let startClientX = 0;
let startProgress = 0;
let isPointerDown = false;
let wasDragged = false;

function onPointerDown(e: PointerEvent) {
  if (e.button !== 0) return; // 仅响应主按键
  isPointerDown = true;
  wasDragged = false;
  startClientX = e.clientX;
  startProgress = currentProgress.value;

  stopIdleLoop();
  if (animRafId !== null) {
    cancelAnimationFrame(animRafId);
    animRafId = null;
    currentAnimTarget = null;
  }

  const el = e.currentTarget as HTMLElement;
  if (el && el.setPointerCapture) {
    try {
      el.setPointerCapture(e.pointerId);
    } catch (_) {}
  }
}

function onPointerMove(e: PointerEvent) {
  if (!isPointerDown) return;

  const dx = e.clientX - startClientX;
  if (!isDragging.value && Math.abs(dx) > 3) {
    isDragging.value = true;
  }

  if (isDragging.value) {
    // 轨迹总有效行程为 32px
    const deltaProgress = dx / 32;
    const nextProgress = Math.max(0, Math.min(1, startProgress + deltaProgress));
    currentProgress.value = nextProgress;
    renderCanvas(nextProgress, performance.now());
  }
}

function onPointerUp(e: PointerEvent) {
  if (!isPointerDown) return;
  isPointerDown = false;

  const el = e.currentTarget as HTMLElement;
  if (el && el.releasePointerCapture) {
    try {
      el.releasePointerCapture(e.pointerId);
    } catch (_) {}
  }

  if (isDragging.value) {
    isDragging.value = false;
    wasDragged = true;

    // 拖动结束：根据停靠位置是否过半决定切换或是回弹
    const targetDark = currentProgress.value <= 0.5;
    const targetProgress = targetDark ? 0 : 1;

    if (targetDark !== props.modelValue) {
      emit('update:modelValue', targetDark);
      emit('toggle');
    }
    animateTo(targetProgress);
  }
}

function onPointerCancel(e: PointerEvent) {
  if (!isPointerDown) return;
  isPointerDown = false;
  isDragging.value = false;

  const el = e.currentTarget as HTMLElement;
  if (el && el.releasePointerCapture) {
    try {
      el.releasePointerCapture(e.pointerId);
    } catch (_) {}
  }

  const targetDark = currentProgress.value <= 0.5;
  animateTo(targetDark ? 0 : 1);
}

// 保留原有的点击切换逻辑，并兼容键盘回车/空格等点击事件
function handleClick() {
  if (wasDragged) {
    wasDragged = false;
    return;
  }

  const nextDark = !props.modelValue;
  emit('update:modelValue', nextDark);
  emit('toggle');
  animateTo(nextDark ? 0 : 1);
}

watch(
  () => props.modelValue,
  (newVal) => {
    const target = newVal ? 0 : 1;
    // 如果不是正在拖动且尚未处于或朝向该目标，则执行动画
    if (!isDragging.value && currentAnimTarget !== target && Math.abs(currentProgress.value - target) > 0.001) {
      animateTo(target);
    }
  }
);

onMounted(() => {
  const canvas = canvasRef.value;
  if (canvas) {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = SIZE * dpr;
    canvas.height = SIZE * dpr;
  }

  currentProgress.value = props.modelValue ? 0 : 1;
  renderCanvas(currentProgress.value);
  startIdleLoopIfNeeded();
});

onUnmounted(() => {
  stopIdleLoop();
  if (animRafId !== null) {
    cancelAnimationFrame(animRafId);
    animRafId = null;
  }
});
</script>

<style scoped>
/* 外层跑道底座 - 夜间暗底 */
.theme-switch-bg--dark {
  background: linear-gradient(180deg, #0d0f15 0%, #171a24 100%);
  box-shadow:
    inset 0 2px 5px rgba(0, 0, 0, 0.85),
    inset 0 -1px 1px rgba(255, 255, 255, 0.08),
    0 1px 2px rgba(0, 0, 0, 0.4);
}

/* 外层跑道底座 - 日间暖亮底 */
.theme-switch-bg--light {
  background: linear-gradient(180deg, #e5e1d8 0%, #f5f2eb 100%);
  box-shadow:
    inset 0 2px 4px rgba(0, 0, 0, 0.1),
    inset 0 -1px 1px rgba(255, 255, 255, 0.9),
    0 1px 2px rgba(0, 0, 0, 0.05);
}

/* 滑动圆角矩形滑块背景 - 夜间模式 */
.theme-thumb-bg--dark {
  background: radial-gradient(circle at 25% 85%, rgba(129, 140, 248, 0.25), rgba(30, 34, 48, 0.95) 65%),
    linear-gradient(145deg, #272b3a 0%, #171923 100%);
  box-shadow:
    -2px 3px 8px rgba(99, 102, 241, 0.35),
    0 2px 4px rgba(0, 0, 0, 0.6),
    inset 0 1px 1px rgba(255, 255, 255, 0.15);
}

/* 滑动圆角矩形滑块背景 - 白天模式 */
.theme-thumb-bg--light {
  background: radial-gradient(circle at 80% 20%, rgba(251, 191, 36, 0.28), rgba(255, 255, 255, 0.96) 65%),
    linear-gradient(145deg, #ffffff 0%, #f2ece1 100%);
  box-shadow:
    2px -2px 8px rgba(245, 158, 11, 0.3),
    0 2px 5px rgba(0, 0, 0, 0.12),
    inset 0 1px 1px rgba(255, 255, 255, 1);
}

/* 边缘游走流光描边 (虚线段长度 36，间距 64) */
.rim-arc {
  stroke-dasharray: 36 64;
}
</style>
