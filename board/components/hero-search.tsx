"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";

const EXAMPLE_QUERIES = [
  "early-stage AI infra role",
  "senior backend, remote-friendly",
  "junior frontend, no leetcode",
];

export function HeroSearch() {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const timer = setInterval(() => {
      setPlaceholderIndex((i) => (i + 1) % EXAMPLE_QUERIES.length);
    }, 3200);
    return () => clearInterval(timer);
  }, []);

  function submit() {
    const q = value.trim();
    router.push(q ? `/jobs?q=${encodeURIComponent(q)}` : "/jobs");
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        maxWidth: 520,
        margin: "0 auto",
        background: "var(--bg-neutral-primary-soft)",
        border: "1px solid var(--border-default-medium)",
        borderRadius: 10,
        padding: "6px 6px 6px 16px",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <Search size={18} color="var(--text-body-subtle)" style={{ flexShrink: 0 }} />
      <input
        ref={inputRef}
        type="text"
        className="hero-search-input"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={`Try “${EXAMPLE_QUERIES[placeholderIndex]}”`}
        aria-label="Search jobs by meaning"
        style={{
          flex: 1,
          border: "none",
          outline: "none",
          background: "transparent",
          fontSize: 16,
          color: "var(--text-heading)",
          padding: "10px 0",
          minWidth: 0,
        }}
      />
      <button type="submit" className="btn-primary" style={{ padding: "12px 20px", fontSize: 15 }}>
        Search
      </button>
    </form>
  );
}
