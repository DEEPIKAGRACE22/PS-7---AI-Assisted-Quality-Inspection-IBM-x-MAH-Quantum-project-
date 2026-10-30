/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Dark charcoal/navy industrial palette
        charcoal: {
          950: '#080C14',
          900: '#0D1117',
          800: '#131C2E',
          700: '#1A2540',
          600: '#1E2D4A',
          500: '#243356',
        },
        steel: {
          400: '#8BA7C7',
          300: '#A8BDD5',
          200: '#C4D3E3',
          100: '#E2EBF4',
        },
        accent: {
          DEFAULT: '#00D4FF',
          hover: '#00BBDD',
          dim: 'rgba(0,212,255,0.15)',
        },
        success: {
          DEFAULT: '#22C55E',
          dim: 'rgba(34,197,94,0.15)',
        },
        warning: {
          DEFAULT: '#F59E0B',
          dim: 'rgba(245,158,11,0.15)',
        },
        danger: {
          DEFAULT: '#EF4444',
          dim: 'rgba(239,68,68,0.15)',
        },
        defect: {
          crazing: '#FF6B6B',
          inclusion: '#4ECDC4',
          patches: '#45B7D1',
          pitted: '#96CEB4',
          scale: '#FFEAA7',
          scratches: '#DDA0DD',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      backgroundImage: {
        'grid-pattern': "linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px)",
      },
      backgroundSize: {
        'grid': '40px 40px',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'shimmer': 'shimmer 2s infinite',
        'slide-in': 'slideIn 0.3s ease-out',
        'fade-in': 'fadeIn 0.4s ease-out',
        'conveyor': 'conveyor 8s linear infinite',
        'scan': 'scan 2s ease-in-out infinite',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        slideIn: {
          '0%': { transform: 'translateX(-20px)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        conveyor: {
          '0%': { backgroundPosition: '0 0' },
          '100%': { backgroundPosition: '200px 0' },
        },
        scan: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(80%)' },
        },
      },
      boxShadow: {
        'card': '0 1px 3px rgba(0,0,0,0.3), 0 8px 32px rgba(0,0,0,0.2)',
        'glow': '0 0 20px rgba(0,212,255,0.3)',
        'glow-success': '0 0 20px rgba(34,197,94,0.3)',
        'glow-danger': '0 0 20px rgba(239,68,68,0.3)',
        'inner-card': 'inset 0 1px 0 rgba(255,255,255,0.05)',
      },
    },
  },
  plugins: [],
}
