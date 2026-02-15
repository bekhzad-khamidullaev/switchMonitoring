tailwind.config = {
  theme: {
    extend: {
      fontFamily: {
        sans: ['Manrope', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Sora', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        brand: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          900: '#0c4a6e',
        },
        success: {
          100: '#dcfce7',
          600: '#16a34a',
          700: '#15803d',
        },
        warning: {
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          600: '#d97706',
          700: '#b45309',
        },
        info: {
          100: '#e0e7ff',
          300: '#a5b4fc',
          600: '#4f46e5',
          700: '#4338ca',
        },
        danger: {
          100: '#fee2e2',
          600: '#dc2626',
          700: '#b91c1c',
        },
        surface: {
          0: '#ffffff',
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          600: '#475569',
          700: '#334155',
          900: '#0f172a',
        },
      },
      boxShadow: {
        soft: '0 6px 24px rgba(15, 23, 42, 0.08)',
      },
      borderRadius: {
        panel: '0.875rem',
      },
    },
  },
};
