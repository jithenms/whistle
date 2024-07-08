"use client";
import React from "react";
import { useTheme } from "next-themes";

const ThemeToggle = () => {
  const { theme, setTheme } = useTheme();

  return (
    <button
      onClick={() => (theme == "dark" ? setTheme("light") : setTheme("dark"))}
      className="bottom-0 left-0 absolute z-50"
    >
      toggle
    </button>
  );
};

export default ThemeToggle;
