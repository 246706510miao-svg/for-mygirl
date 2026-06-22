/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        "bg-start": "var(--color-bg-start)",
        "bg-end": "var(--color-bg-end)",
        accent: {
          cool: "var(--color-accent-cool)",
          warm: "var(--color-accent-warm)",
        },
        surface: "var(--color-surface)",
        text: {
          primary: "var(--color-text-primary)",
          secondary: "var(--color-text-secondary)",
        },
      },
      borderRadius: {
        card: "var(--radius-large)",
      },
      fontFamily: {
        sans: ["Inter", "Manrope", "SF Pro Display", "Microsoft YaHei", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glass: "0 24px 70px rgba(0, 0, 0, 0.28)",
      },
    },
  },
  plugins: [],
};
