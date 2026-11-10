"use client";

import { useEffect, useState } from "react";

// A small looping animation of what dictation feels like: key held -> listening -> text appears.
const lines = ["আমি আজকে অফিসে একটু দেরি করে আসব।", "আমি আজকে I want to make a coffee", "ধন্যবাদ, মিটিংটা কালকে সকাল দশটায় হবে।"];

export default function Demo() {
  const [line, setLine] = useState(0);
  const [phase, setPhase] = useState("idle"); // idle | listening | typing | done
  const [shown, setShown] = useState("");

  useEffect(() => {
    let timer;
    const text = Array.from(lines[line]);
    if (phase === "idle") timer = setTimeout(() => setPhase("listening"), 900);
    else if (phase === "listening") timer = setTimeout(() => setPhase("typing"), 1900);
    else if (phase === "typing") {
      if (shown.length < text.length) timer = setTimeout(() => setShown(text.slice(0, Array.from(shown).length + 1).join("")), 38);
      else timer = setTimeout(() => setPhase("done"), 100);
    } else
      timer = setTimeout(() => {
        setShown("");
        setLine((line + 1) % lines.length);
        setPhase("idle");
      }, 2600);
    return () => clearTimeout(timer);
  }, [phase, shown, line]);

  return (
    <div className="demo" aria-hidden="true">
      <div className="win">
        <div className="win-bar">
          <span /> <span /> <span />
          <em>নতুন ডকুমেন্ট</em>
        </div>
        <div className="win-body">
          {shown}
          <i className="caret" />
        </div>
      </div>
      <div className="keys">
        <kbd className={phase === "listening" ? "down" : ""}>Alt</kbd>
        <b>+</b>
        <kbd className={phase === "listening" ? "down" : ""}>R</kbd>
      </div>
      <div className={`overlay ${phase === "listening" || phase === "typing" ? "show" : ""}`}>
        <span className={`dot ${phase === "typing" ? "busy" : ""}`} />
        {phase === "typing" ? "লিখছি…" : "শুনছি…"}
        {phase === "listening" && (
          <span className="wave">
            <i /> <i /> <i /> <i /> <i />
          </span>
        )}
      </div>
    </div>
  );
}
