/** @type {import('tailwindcss').Config} */
// One palette for the whole app, taken from jklu.edu.in. Use these tokens, not Tailwind's built-in colours.
// Token names are kept from the first design: `navy` is now JKLU royal blue and `gold` is JKLU orange.
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Roboto", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Helvetica", "Arial", "sans-serif"],
        display: ["Roboto Condensed", "Roboto", "ui-sans-serif", "system-ui", "Arial Narrow", "sans-serif"],   // headings
      },
      colors: {
        // Neutrals
        canvas: "#F8F8F8",                      // page background (the site's section grey)
        surface: "#FFFFFF",                     // cards, panels
        subtle: "#F1F3F6",                      // table headers, kanban columns, hover
        line: { DEFAULT: "#E4E7EC", strong: "#D0D5DD" },
        ink: { DEFAULT: "#101828", secondary: "#475467", muted: "#667085" },   // muted text: not on `subtle`
        // Brand
        navy: { DEFAULT: "#0036A1", hover: "#002B80" },    // JKLU royal blue: primary buttons, sidebar, headings
        gold: { DEFAULT: "#F56C1F", soft: "#FEF0E7" },    // JKLU orange, sparingly: markers and the pending count, dark text only
        periwinkle: "#6686C6",                            // JKLU's section blue: decoration, never under small text
        // Status: text on its soft background, always with a label
        danger: { DEFAULT: "#B42318", soft: "#FEF3F2" },  // hot
        warning: { DEFAULT: "#B54708", soft: "#FFFAEB" }, // warm
        info: { DEFAULT: "#175CD3", soft: "#EFF8FF" },    // cold
        success: { DEFAULT: "#067647", soft: "#ECFDF3" },
        optout: { DEFAULT: "#6941C6", soft: "#F4F3FF" },
        chart: "#6686C6",                       // the one series colour (JKLU periwinkle)
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
