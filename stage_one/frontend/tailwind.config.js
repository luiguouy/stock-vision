/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        darkBg: '#0e1118',
        cardBg: '#FFFFFF',       // 重定义 cardBg 为纯白
        borderGray: '#E2E8F0',   // 重定义 borderGray 为浅灰
        lightBg: '#F8F9FA',      // 新增主体背景
        textMain: '#1A1A1A',     // 新增主标题字色
        textSub: '#4A4A4A',      // 新增正文辅助字色
      }
    },
  },
  plugins: [],
}
