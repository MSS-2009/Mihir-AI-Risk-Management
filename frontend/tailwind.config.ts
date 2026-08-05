import type { Config } from "tailwindcss";

/**
 * Avenoir tokens. Light-first with a dark toggle, because the buyer pastes
 * output into a light board deck; dark exists for the dim demo room.
 *
 * Colour carries epistemic meaning, not decoration:
 *   brand   the central estimate
 *   rule    the range
 *   amber   the adverse tail, and only that
 *
 * There is deliberately no green/amber severity ramp. A traffic light is the
 * exact "dashboard says High" language this product exists to replace.
 */
const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Semantic tokens driven by CSS variables so the dark toggle is one class.
        canvas: "rgb(var(--canvas) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        raised: "rgb(var(--raised) / <alpha-value>)",
        ink: "rgb(var(--ink) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        rule: "rgb(var(--rule) / <alpha-value>)",
        brand: "rgb(var(--brand) / <alpha-value>)",
        "brand-deep": "rgb(var(--brand-deep) / <alpha-value>)",
        // The one semantic pair, reserved strictly for risk direction.
        amber: "rgb(var(--amber) / <alpha-value>)",
        emerald: "rgb(var(--emerald) / <alpha-value>)",
        // Legacy aliases so existing components keep compiling.
        bordeaux: {
          DEFAULT: "rgb(var(--brand) / <alpha-value>)",
          deep: "rgb(var(--brand-deep) / <alpha-value>)",
        },
        mist: "rgb(var(--rule) / <alpha-value>)",
        "mist-deep": "rgb(var(--rule-strong) / <alpha-value>)",
        paper: "rgb(var(--canvas) / <alpha-value>)",
        ochre: "rgb(var(--amber) / <alpha-value>)",
        crimson: "rgb(var(--brand) / <alpha-value>)",
      },
      fontFamily: {
        display: ["var(--font-poppins)", "system-ui", "sans-serif"],
        serif: ["var(--font-fraunces)", "Georgia", "serif"],
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        "display-lg": ["clamp(2.5rem, 5.5vw, 4.25rem)", { lineHeight: "1.02", letterSpacing: "-0.02em" }],
        display: ["clamp(1.9rem, 3.6vw, 2.9rem)", { lineHeight: "1.06", letterSpacing: "-0.02em" }],
      },
      maxWidth: { content: "1200px" },
      boxShadow: {
        card: "0 1px 2px rgb(var(--shadow) / 0.05), 0 8px 24px -14px rgb(var(--shadow) / 0.12)",
        lift: "0 2px 4px rgb(var(--shadow) / 0.06), 0 24px 56px -24px rgb(var(--shadow) / 0.22)",
      },
      keyframes: {
        "fade-up": { "0%": { opacity: "0", transform: "translateY(10px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
      },
      animation: { "fade-up": "fade-up 0.5s cubic-bezier(0.16,1,0.3,1) both" },
    },
  },
  plugins: [],
};
export default config;
