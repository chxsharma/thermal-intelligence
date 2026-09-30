import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./features/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0b0d10",
          900: "#111418",
          800: "#171b20",
          700: "#1e242b",
          600: "#2a323b",
        },
        mist: {
          100: "#e8eef2",
          400: "#8b98a5",
          500: "#6b7784",
        },
        teal: {
          300: "#7ecfc4",
          400: "#5fb3a8",
        },
        signal: {
          red: "#d4655a",
          orange: "#d08a4a",
          green: "#6ea56e",
          amber: "#c9a227",
          gray: "#8a93a0",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
