/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Theme-driven palette — actual values come from CSS variables set on
        // <html data-theme="blue"> or data-theme="pink" (see index.css).
        primary: {
          50:  "rgb(var(--p-50)  / <alpha-value>)",
          100: "rgb(var(--p-100) / <alpha-value>)",
          200: "rgb(var(--p-200) / <alpha-value>)",
          300: "rgb(var(--p-300) / <alpha-value>)",
          400: "rgb(var(--p-400) / <alpha-value>)",
          500: "rgb(var(--p-500) / <alpha-value>)",
          600: "rgb(var(--p-600) / <alpha-value>)",
          700: "rgb(var(--p-700) / <alpha-value>)",
          800: "rgb(var(--p-800) / <alpha-value>)",
          900: "rgb(var(--p-900) / <alpha-value>)",
        },
        // UNOSOL brand accents — fixed, do not flip with theme.
        cream: {
          50:  "#FDFAEC",
          100: "#F8F1D6",
          200: "#F2E6B8",
        },
        sky: {
          brand: "#B2E6F3",
        },
      },
    },
  },
  plugins: [],
};
