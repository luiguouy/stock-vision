/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 基础主题色
        darkBg: '#0e1118',
        cardBg: '#FFFFFF',
        borderGray: '#E2E8F0',
        lightBg: '#F8F9FA',
        textMain: '#1A1A1A',
        textSub: '#4A4A4A',
        
        // 金融专业配色 - 涨跌色
        rising: {
          DEFAULT: '#22c55e',
          light: '#86efac',
          dark: '#16a34a',
          bg: '#f0fdf4',
        },
        falling: {
          DEFAULT: '#ef4444',
          light: '#fca5a5',
          dark: '#dc2626',
          bg: '#fef2f2',
        },
        
        // 面板背景色变量
        panel: {
          header: '#ffffff',
          sidebar: '#fafbfc',
          main: '#ffffff',
          footer: '#1e293b',
        },
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
