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
        // Cool grayscale neutrals replacing warm paper/ink palette
        paper: {
          50: '#F3F4F6',   // canvas fallback
          100: '#E5E7EB',  // secondary / muted panels & footers
          200: '#D1D5DB',  // borders & dividers
          300: '#9CA3AF',  // subtle borders / accents
        },
        ink: {
          300: '#9CA3AF',
          400: '#6B7280',  // muted placeholder/counter text
          500: '#6B7280',  // muted text
          600: '#4B5563',  // secondary slate gray text
          700: '#374151',  // body / secondary dark gray
          800: '#1F2937',  // primary dark gray buttons & logo badge
          900: '#111827',  // primary dark gray ink & headings
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
