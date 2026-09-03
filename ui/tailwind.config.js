/** @type {import('tailwindcss').Config} */

/**
 * Colors resolve to the CSS variables declared in `src/assets/css/tokens.css`,
 * so every utility follows the active theme. `<alpha-value>` keeps Tailwind's
 * opacity modifiers (`bg-panel/60`) working.
 */
const token = (name) => `rgb(var(--c-${name}) / <alpha-value>)`

export default {
  darkMode: ['class', '[data-theme="dark"]'],
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Semantic tokens — what redesigned markup should use.
        app: {
          DEFAULT: token('bg'),
          sub: token('bg-sub')
        },
        panel: {
          DEFAULT: token('panel'),
          sub: token('panel-sub')
        },
        line: {
          DEFAULT: token('line'),
          soft: token('line-soft')
        },
        ink: {
          DEFAULT: token('tx'),
          2: token('tx2'),
          3: token('tx3'),
          4: token('tx4')
        },
        accent: {
          DEFAULT: token('ac'),
          on: token('ac-on'),
          soft: token('ac-soft')
        },
        ok: {
          DEFAULT: token('ok'),
          soft: token('ok-soft')
        },
        warn: {
          DEFAULT: token('warn'),
          soft: token('warn-soft')
        },
        bad: {
          DEFAULT: token('bad'),
          soft: token('bad-soft')
        },
        chip: token('chip'),

        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a'
        },

        // Legacy ramp: pages not yet redesigned keep their `gray-*` classes,
        // which now follow the theme because the ramp inverts in dark mode.
        gray: {
          50: token('n50'),
          100: token('n100'),
          200: token('n200'),
          300: token('n300'),
          400: token('n400'),
          500: token('n500'),
          600: token('n600'),
          700: token('n700'),
          800: token('n800'),
          900: token('n900')
        }
      },
      fontFamily: {
        sans: [
          'Noto Sans SC',
          '-apple-system',
          'PingFang SC',
          'Microsoft YaHei',
          'system-ui',
          'sans-serif'
        ],
        display: ['Space Grotesk', 'Noto Sans SC', 'system-ui', 'sans-serif'],
        mono: ['IBM Plex Mono', 'ui-monospace', 'Menlo', 'monospace']
      },
      // The canvas works in three radius tiers — 3/4 on badges, 7/8 on
      // controls, 9/10/11 on cards — so the named steps carry those rather
      // than the 16/20/24 the old rounded look was built on.
      borderRadius: {
        DEFAULT: '8px',
        sm: '4px',
        md: '7px',
        lg: '10px',
        xl: '12px',
        '2xl': '16px'
      },
      boxShadow: {
        soft: '0 2px 8px rgba(0, 0, 0, 0.08)',
        'soft-md': '0 4px 12px rgba(0, 0, 0, 0.10)',
        'soft-lg': '0 8px 16px rgba(0, 0, 0, 0.12)'
      },
      container: {
        center: true,
        padding: '1rem',
        screens: {
          sm: '640px',
          md: '768px',
          lg: '1024px',
          xl: '1280px',
          '2xl': '1400px'
        }
      }
    }
  },
  plugins: []
}
