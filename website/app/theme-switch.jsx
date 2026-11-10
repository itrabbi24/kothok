"use client";

import { useEffect, useState } from "react";

const options = [
  { id: "system", label: "ডিভাইস" },
  { id: "light", label: "লাইট" },
  { id: "dark", label: "ডার্ক" },
];

function apply(theme) {
  if (theme === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", theme);
}

export default function ThemeSwitch() {
  const [theme, setTheme] = useState("system");

  useEffect(() => {
    try {
      setTheme(localStorage.getItem("theme") || "system");
    } catch {}
  }, []);

  const choose = (id) => {
    setTheme(id);
    apply(id);
    try {
      localStorage.setItem("theme", id);
    } catch {}
  };

  return (
    <div className="theme" role="group" aria-label="থিম">
      {options.map((o) => (
        <button key={o.id} className={theme === o.id ? "on" : ""} onClick={() => choose(o.id)} aria-pressed={theme === o.id}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
