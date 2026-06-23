import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "1rem",
      screens: { "2xl": "1280px" },
    },
    extend: {
      colors: {
        background: "hsl(0 0% 4%)",
        foreground: "hsl(0 0% 98%)",
        muted: "hsl(0 0% 12%)",
        "muted-foreground": "hsl(0 0% 70%)",
        primary: "hsl(15 90% 55%)",
        "primary-foreground": "hsl(0 0% 100%)",
        accent: "hsl(50 90% 55%)",
        border: "hsl(0 0% 18%)",
        card: "hsl(0 0% 8%)",
        destructive: "hsl(0 70% 55%)",
      },
      borderRadius: {
        lg: "0.75rem",
        md: "0.5rem",
        sm: "0.25rem",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
