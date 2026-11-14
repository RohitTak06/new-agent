/** @type {import('tailwindcss').Config} */
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
        jklu: {
          blue: "#0A2540",       // brand navy: headings, primary buttons, sidebar
          navy: "#0A2540",
          ink: "#122F4F",        // sidebar hover and raised surfaces on navy
          line: "#1E3D60",       // dividers on navy
          gold: "#D4AF37",
          goldsoft: "#F6EBC4",
          maroon: "#800000",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(16, 24, 40, 0.04), 0 1px 3px rgba(16, 24, 40, 0.06)",
        raised: "0 4px 12px rgba(16, 24, 40, 0.08)",
      },
    },
  },
  plugins: [],
}
