import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    // `lib/format.ts` holds complete class-name literals for the semantic tones,
    // so it must be scanned or those utilities will be purged.
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
        serif: ['ui-serif', 'Georgia', 'Cambria', 'Times New Roman', 'serif'],
        mono: [
          'ui-monospace',
          'SFMono-Regular',
          'SF Mono',
          'Menlo',
          'Consolas',
          'Liberation Mono',
          'monospace',
        ],
      },
      colors: {
        // Cool gray/slate palette for contrast against the warm newspaper texture
        paper: {
          50: '#EEF1F4',   // light gray canvas
          100: '#DDE3E8',  // secondary panels & footers
          200: '#C5CED6',  // borders & dividers
          300: '#9AA8B5',  // subtle borders / accents
        },
        ink: {
          300: '#8A99A6',
          400: '#647382',  // muted placeholder/counter text
          500: '#526170',  // muted text
          600: '#3F4D5B',  // secondary slate text
          700: '#2E3A46',  // body / secondary dark slate
          800: '#202B36',  // primary slate buttons & logo badge
          900: '#111A23',  // primary slate ink & headings
        },
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      keyframes: {
        'fade-rise': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'sweep': {
          from: { transform: 'translateX(-100%)' },
          to: { transform: 'translateX(100%)' },
        },
      },
      animation: {
        'fade-rise': 'fade-rise 320ms cubic-bezier(0.16, 1, 0.3, 1) both',
        sweep: 'sweep 1.6s cubic-bezier(0.4, 0, 0.2, 1) infinite',
      },
    },
  },
  plugins: [],
};

export default config;
