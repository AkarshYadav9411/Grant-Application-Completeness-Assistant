/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172033",
        line: "#d9e1ec",
        panel: "#f7f9fc",
        brand: "#2563eb",
        mint: "#0f766e",
        amber: "#b45309",
        danger: "#b91c1c"
      },
      boxShadow: {
        soft: "0 12px 30px rgba(23, 32, 51, 0.08)"
      }
    }
  },
  plugins: []
};
