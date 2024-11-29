/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html", 
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        rubik: ['Rubik', 'sans-serif'],
      },
      colors: {
        almostBlack: '#222831',
        almostGray: '#31363F',
        almostBlue: '#2C4081',
        almostWhite: '#EEEEEE',
      },
    },
  },
  plugins: [],
}