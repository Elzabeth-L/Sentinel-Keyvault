import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#07111f",
        panel: "#0d1b2e",
        border: "#203652",
        primary: "#32b5ff",
        muted: "#8fa7c2",
        success: "#2dd4a3",
        warning: "#f7b955",
        danger: "#ff6b7a"
      },
      boxShadow: {
        panel: "0 20px 60px rgba(0, 0, 0, 0.28)"
      }
    }
  },
  plugins: []
} satisfies Config;

