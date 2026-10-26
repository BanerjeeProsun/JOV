import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: '#f5f5f7', surface: '#ffffff', ash: '#e8e8ed',
        'text-primary': '#1d1d1f', 'text-secondary': '#707070', 'text-tertiary': '#86868b',
        'border-subtle': '#d6d6d6', 'border-strong': '#b9b9bf',
        'apple-blue': '#0071e3', 'apple-blue-hover': '#0077ed', 'apple-blue-subtle': '#eef6ff',
        'link-blue': '#0066cc',
        'success-green': '#3c7a57', 'success-subtle': '#eef6f0',
        'warning-amber': '#946b16', 'warning-subtle': '#faf5e7',
        'danger-red': '#b4473d', 'danger-subtle': '#fbefed',
        // Compatibility aliases for existing functional screen markup.
        'apple-canvas': '#f5f5f7', 'apple-charcoal': '#1d1d1f', 'apple-subtle': '#86868b',
        'apple-border': '#d6d6d6', 'apple-accent': '#0066cc',
        'surface-subtle': '#ffffff', 'surface-hover': '#e8e8ed',
      },
      fontFamily: {
        sans: ['"SF Pro Text"', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Inter', 'system-ui', 'sans-serif'],
        display: ['"SF Pro Display"', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['SFMono-Regular', 'Consolas', '"Liberation Mono"', 'monospace'],
      },
      borderRadius: {
        sm: '18px', md: '24px', lg: '28px', xl: '28px', '2xl': '28px',
        'apple-sm': '18px', 'apple-md': '24px', 'apple-lg': '28px', 'apple-xl': '32px',
        'apple-2xl': '36px', card: '28px', 'card-lg': '28px', input: '980px', btn: '980px',
      },
      boxShadow: { sm: 'none', 'apple-card': 'none', 'apple-floating': 'none', 'apple-button': 'none', subtle: 'none' },
      keyframes: {
        'page-in': { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        'soft-pulse': { '0%, 100%': { opacity: '1' }, '50%': { opacity: '.58' } },
      },
      animation: { 'page-in': 'page-in 360ms cubic-bezier(.22,1,.36,1) both', 'soft-pulse': 'soft-pulse 1.6s ease-in-out infinite' },
    },
  },
  plugins: [],
} satisfies Config
