import type { Config } from "tailwindcss";

/**
 * Avenoir design tokens, matched to the Avenoir pitch-deck brand:
 * white / black / crimson, with the deep-maroon depth tone.
 * Color still maps to epistemic meaning in charts:
 *   crimson = the central estimate, mist = the range, ochre = the adverse tail.
 */
const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#141110",
        black: "#0B0A0A",
        // Primary brand red (deck title red). Kept under `bordeaux` so existing
        // usages recolor to the deck crimson in one place.
        bordeaux: {
          DEFAULT: "#8F0F24",
          deep: "#5E0118",
          soft: "#B21E39",
        },
        // Brighter crimson for the dotted-wave motifs and bright accents.
        crimson: {
          DEFAULT: "#C11530",
          bright: "#D21F3C",
        },
        paper: "#FBFAF9",
        surface: "#FFFFFF",
        mist: "#EAE6E3",
        "mist-deep": "#D8D1CC",
        ochre: {
          DEFAULT: "#B45309",
          soft: "#C9791F",
        },
        muted: "#6B625E",
      },
      fontFamily: {
        display: ["var(--font-poppins)", "Poppins", "system-ui", "sans-serif"],
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        "display-lg": ["clamp(2.75rem, 6.2vw, 5rem)", { lineHeight: "1.0", letterSpacing: "-0.02em" }],
        display: ["clamp(2rem, 4vw, 3.25rem)", { lineHeight: "1.04", letterSpacing: "-0.02em" }],
      },
      maxWidth: {
        content: "1200px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(20,17,16,0.04), 0 8px 24px -14px rgba(20,17,16,0.10)",
        lift: "0 2px 4px rgba(20,17,16,0.05), 0 26px 60px -24px rgba(94,1,24,0.22)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "wave-drift": {
          "0%,100%": { transform: "translate3d(0,0,0)" },
          "50%": { transform: "translate3d(-10px,6px,0)" },
        },
        "spin-slow": {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.5s cubic-bezier(0.16,1,0.3,1) both",
        "wave-drift": "wave-drift 14s ease-in-out infinite",
        "spin-slow": "spin-slow 26s linear infinite",
      },
    },
  },
  plugins: [],
};
export default config;
