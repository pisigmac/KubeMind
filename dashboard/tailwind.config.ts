import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        background: "#090D16",
        foreground: "#F8FAFC",
        primary: "#0066FF",
        accent: "#00D4B2",
        muted: "#94A3B8",
        border: "#1E293B",
        card: "#0F172A",
        surface: "#1E293B",
      },
      borderRadius: {
        DEFAULT: "12px",
        md: "14px",
        lg: "16px",
        xl: "20px",
      },
    },
  },
  plugins: [],
};

export default config;
