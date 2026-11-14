/** @type {import('tailwindcss').Config} */
// One palette for the whole app. Use these tokens, not Tailwind's built-in colours.
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica", "Arial", "sans-serif"],
      },
      colors: {
        // Neutrals
        canvas: "#F7F8FA",                      // page background
        surface: "#FFFFFF",                     // cards, panels
        subtle: "#F1F3F6",                      // table headers, kanban columns, hover
        line: { DEFAULT: "#E4E7EC", strong: "#D0D5DD" },
        ink: { DEFAULT: "#101828", secondary: "#475467", muted: "#667085" },   // muted text: not on `subtle`
        // Brand
        navy: { DEFAULT: "#0A2540", hover: "#13355A" },
        gold: { DEFAULT: "#C9A227", soft: "#FBF3DC" },    // sparingly: active nav marker, pending count
        // Status: text on its soft background, always with a label
        danger: { DEFAULT: "#B42318", soft: "#FEF3F2" },  // hot
        warning: { DEFAULT: "#B54708", soft: "#FFFAEB" }, // warm
        info: { DEFAULT: "#175CD3", soft: "#EFF8FF" },    // cold
        success: { DEFAULT: "#067647", soft: "#ECFDF3" },
        optout: { DEFAULT: "#6941C6", soft: "#F4F3FF" },
        chart: "#2E5A88",                       // the one series colour
      },
      fontSize: {
        "13": ["13px", { lineHeight: "20px" }],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16, 24, 40, 0.05)",
      },
      borderRadius: {
        lg: "8px",     // inputs and buttons
        xl: "12px",    // cards
      },
    },
  },
  plugins: [],
}
