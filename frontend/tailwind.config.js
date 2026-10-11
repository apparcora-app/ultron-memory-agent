/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Legacy cyber tokens (backward compat)
        cyber: {
          950: '#090a0f',
          900: '#10121a',
          800: '#181b26',
          700: '#232738',
          cyan: '#00f0ff',
          neon: '#00ffa3',
          crimson: '#ff003c',
          amber: '#ffb800',
        },
        // Stitch Design System — Matte Dark Sidebar
        brand: {
          matteDark:   '#0f0f11',
          matteBorder: '#232328',
          matteCard:   '#18181c',
        },
        // Stitch Design System — Sky Blue Canvas
        canvas: {
          bg:      '#f8f9fa',
          white:   '#ffffff',
          border:  '#e2e8f0',
          text:    '#0f172a',
          subtext: '#64748b',
        },
        // Stitch Accent Colors
        skyblue: {
          DEFAULT: '#38bdf8',
          dark:    '#0284c7',
          light:   '#7dd3fc',
          subtle:  '#f0f9ff',
          border:  '#bae6fd',
        },
      },
      fontFamily: {
        // Stitch: Nunito Sans for UI, Roboto Mono for code
        sans:  ['"Nunito Sans"', 'system-ui', 'sans-serif'],
        mono:  ['"Roboto Mono"', 'monospace'],
        // Legacy
        display: ['"Nunito Sans"', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: '0.5rem',
        lg: '1rem',
        xl: '1.5rem',
        '2xl': '1.5rem',
        '3xl': '2rem',
        full: '9999px',
      },
      animation: {
        'pulse-glow': 'pulseGlow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scanline': 'scanline 8s linear infinite',
        'aura-pulse': 'auraPulseRing 3s ease-out infinite',
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { opacity: '1', filter: 'drop-shadow(0 0 12px rgba(14, 165, 233, 0.6))' },
          '50%':       { opacity: '0.6', filter: 'drop-shadow(0 0 4px rgba(14, 165, 233, 0.2))' },
        },
        scanline: {
          '0%':   { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(1000%)' },
        },
        auraPulseRing: {
          '0%':   { transform: 'scale(0.8)', opacity: '0.7' },
          '50%':  { opacity: '0.35' },
          '100%': { transform: 'scale(1.5)', opacity: '0' },
        },
      },
      boxShadow: {
        'card': '0 4px 18px rgba(30, 27, 46, 0.04)',
        'canvas': '0 20px 60px rgba(0,0,0,0.12)',
        'sky-glow': '0 0 12px rgba(14, 165, 233, 0.3)',
      },
    },
  },
  plugins: [],
};
