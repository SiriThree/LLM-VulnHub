import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "#d7dde5",
        background: "#f7f8fb",
        foreground: "#17202a",
        muted: "#eef2f6",
        primary: "#176b87",
        accent: "#7d4f50",
        success: "#276749",
        warning: "#a16207",
        danger: "#b42318"
      },
      boxShadow: {
        soft: "0 10px 30px rgba(23,32,42,0.08)"
      }
    }
  },
  plugins: []
};

export default config;
