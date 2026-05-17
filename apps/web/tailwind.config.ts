import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        board: {
          base: "#0f1115",
          card: "#1b1f27",
          accent: "#f0c674",
          grid: "rgba(255,255,255,0.04)",
        },
      },
      boxShadow: {
        card: "0 10px 40px rgba(0,0,0,0.35)",
      },
      backgroundImage: {
        grain: "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.05) 1px, transparent 0)",
      },
      fontFamily: {
        display: ["'Manrope'", "'Segoe UI'", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;

