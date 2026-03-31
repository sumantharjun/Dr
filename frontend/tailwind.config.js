/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#fdf4ff",
          100: "#fae8ff",
          200: "#f3d0fe",
          300: "#e8a9fc",
          400: "#d872f8",
          500: "#c44bf0",
          600: "#a62cd4",
          700: "#8820ae",
          800: "#71218e",
          900: "#5c1d72",
        },
      },
    },
  },
  plugins: [],
};
