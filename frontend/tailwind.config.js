import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: "#165DFF",
        "brand-dark": "#044AE9",
        "text-main": "#151515",
        "text-sub": "#6C6F7D",
        line: "#E8ECFF",
        page: "#F8FAFF",
        ok: "#10B981",
        warn: "#FF6B6B",
        topic: "#8B5CF6",
      },
      boxShadow: {
        card: "0 4px 16px rgba(22, 93, 255, 0.08)",
        cardHover: "0 12px 32px rgba(22, 93, 255, 0.15)",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "PingFang SC",
          "Hiragino Sans GB",
          "Microsoft YaHei",
          "sans-serif",
        ],
        serif: ["Noto Serif SC", "Songti SC", "serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
