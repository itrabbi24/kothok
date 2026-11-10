"use client";

import { useEffect, useState } from "react";

// Shows the latest version from GitHub; the download link itself always points at the latest release.
export default function ReleaseInfo() {
  const [info, setInfo] = useState(null);

  useEffect(() => {
    fetch("https://api.github.com/repos/itrabbi24/kothok/releases/latest")
      .then((r) => (r.ok ? r.json() : null))
      .then((rel) => {
        if (!rel) return;
        const zip = (rel.assets || []).find((a) => a.name === "Kothok-portable.zip");
        setInfo({
          version: rel.tag_name,
          size: zip ? Math.round(zip.size / 1048576) : null,
          date: new Date(rel.published_at).toLocaleDateString("bn-BD", { year: "numeric", month: "long", day: "numeric" }),
        });
      })
      .catch(() => {});
  }, []);

  return (
    <p className="release">
      {info ? (
        <>
          সর্বশেষ ভার্সন <b>{info.version}</b> · {info.date}
          {info.size ? ` · ${info.size} MB` : ""}
        </>
      ) : (
        "Windows 10/11 · 64-bit · ভয়েস মডেলসহ portable zip"
      )}
    </p>
  );
}
