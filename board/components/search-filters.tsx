"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useState, useEffect, useCallback } from "react";
import { Search, X } from "lucide-react";
import { CATEGORIES, LEVELS, PLATFORMS } from "@/lib/types";

const selectStyle: React.CSSProperties = {
  background: "var(--bg-neutral-secondary-medium)",
  border: "1px solid var(--border-default-medium)",
  borderRadius: 8,
  padding: "10px 12px",
  fontSize: 14,
  color: "var(--text-heading)",
  boxShadow: "var(--shadow-xs)",
  outline: "none",
  cursor: "pointer",
};

const inputStyle: React.CSSProperties = {
  background: "var(--bg-neutral-secondary-medium)",
  border: "1px solid var(--border-default-medium)",
  borderRadius: 8,
  padding: "10px 12px",
  fontSize: 14,
  color: "var(--text-heading)",
  boxShadow: "var(--shadow-xs)",
  outline: "none",
  transition: "all 200ms",
};

function useFocusHandlers() {
  return {
    onFocus: (e: React.FocusEvent<HTMLInputElement>) => {
      e.currentTarget.style.borderColor = "var(--border-brand)";
      e.currentTarget.style.boxShadow = "0 0 0 1px var(--border-brand)";
    },
    onBlur: (e: React.FocusEvent<HTMLInputElement>) => {
      e.currentTarget.style.borderColor = "var(--border-default-medium)";
      e.currentTarget.style.boxShadow = "var(--shadow-xs)";
    },
  };
}

export function SearchFilters() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const focus = useFocusHandlers();

  const currentQ = searchParams.get("q") || "";
  const currentLocation = searchParams.get("location") || "";
  const currentCompany = searchParams.get("company") || "";
  const currentDate = searchParams.get("date") || "all";
  const currentSort = searchParams.get("sort") || "posted_at";
  const currentCategory = searchParams.get("category") || "";
  const currentLevel = searchParams.get("level") || "";
  const currentPlatform = searchParams.get("platform") || "";

  const [q, setQ] = useState(currentQ);
  const [location, setLocation] = useState(currentLocation);
  const [company, setCompany] = useState(currentCompany);

  useEffect(() => { setQ(currentQ); }, [currentQ]);
  useEffect(() => { setLocation(currentLocation); }, [currentLocation]);
  useEffect(() => { setCompany(currentCompany); }, [currentCompany]);

  const updateParams = useCallback((updates: Record<string, string>) => {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(updates)) {
      if (value) {
        params.set(key, value);
      } else {
        params.delete(key);
      }
    }
    params.delete("page");
    router.replace(`?${params.toString()}`);
  }, [searchParams, router]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (q !== currentQ) updateParams({ q });
    }, 300);
    return () => clearTimeout(timer);
  }, [q, currentQ, updateParams]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (location !== currentLocation) updateParams({ location });
    }, 300);
    return () => clearTimeout(timer);
  }, [location, currentLocation, updateParams]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (company !== currentCompany) updateParams({ company });
    }, 300);
    return () => clearTimeout(timer);
  }, [company, currentCompany, updateParams]);

  const hasFilters =
    currentQ || currentLocation || currentCompany ||
    currentDate !== "all" || currentSort !== "posted_at" ||
    currentCategory || currentLevel || currentPlatform;

  const clearAll = () => {
    setQ("");
    setLocation("");
    setCompany("");
    router.replace("?");
  };

  return (
    <div style={{ marginBottom: 24, display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Row 1 */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1" style={{ minWidth: 200 }}>
          <Search
            size={16}
            className="absolute top-1/2 -translate-y-1/2"
            style={{ left: 12, color: "var(--text-body)" }}
          />
          <input
            type="text"
            placeholder="Search jobs or companies..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ ...inputStyle, width: "100%", paddingLeft: 36 }}
            {...focus}
          />
        </div>

        <select
          value={currentDate}
          onChange={(e) => updateParams({ date: e.target.value === "all" ? "" : e.target.value })}
          style={selectStyle}
        >
          <option value="all">All time</option>
          <option value="24h">Last 24 hours</option>
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
        </select>

        <input
          type="text"
          placeholder="Location or remote"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          style={{ ...inputStyle, width: 180 }}
          {...focus}
        />

        <div className="flex" style={{ gap: 0 }}>
          <button
            onClick={() => updateParams({ sort: "" })}
            style={{
              padding: "10px 16px",
              fontSize: 14,
              fontWeight: 500,
              borderRadius: "8px 0 0 8px",
              border: "1px solid var(--border-default-medium)",
              background: currentSort === "posted_at" ? "var(--bg-neutral-tertiary-medium)" : "var(--bg-neutral-secondary-medium)",
              color: currentSort === "posted_at" ? "var(--text-heading)" : "var(--text-body)",
              cursor: "pointer",
              boxShadow: "var(--shadow-xs)",
              transition: "color 200ms",
            }}
          >
            Newest
          </button>
          <button
            onClick={() => updateParams({ sort: "title" })}
            style={{
              padding: "10px 16px",
              fontSize: 14,
              fontWeight: 500,
              borderRadius: "0 8px 8px 0",
              border: "1px solid var(--border-default-medium)",
              borderLeft: "none",
              background: currentSort === "title" ? "var(--bg-neutral-tertiary-medium)" : "var(--bg-neutral-secondary-medium)",
              color: currentSort === "title" ? "var(--text-heading)" : "var(--text-body)",
              cursor: "pointer",
              boxShadow: "var(--shadow-xs)",
              transition: "color 200ms",
            }}
          >
            A–Z
          </button>
        </div>

        {hasFilters && (
          <button
            onClick={clearAll}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "10px 16px",
              fontSize: 14,
              fontWeight: 500,
              background: "transparent",
              border: "1px solid transparent",
              borderRadius: 8,
              color: "var(--text-heading)",
              cursor: "pointer",
              transition: "background 200ms",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--bg-neutral-secondary-medium)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            <X size={14} />
            Clear
          </button>
        )}
      </div>

      {/* Row 2 */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={currentCategory}
          onChange={(e) => updateParams({ category: e.target.value })}
          style={selectStyle}
        >
          <option value="">All Categories</option>
          {CATEGORIES.map((cat) => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>

        <select
          value={currentLevel}
          onChange={(e) => updateParams({ level: e.target.value })}
          style={selectStyle}
        >
          <option value="">All Levels</option>
          {LEVELS.map((lvl) => (
            <option key={lvl.value} value={lvl.value}>{lvl.label}</option>
          ))}
        </select>

        <select
          value={currentPlatform}
          onChange={(e) => updateParams({ platform: e.target.value })}
          style={selectStyle}
        >
          <option value="">All Platforms</option>
          {PLATFORMS.map((p) => (
            <option key={p.value} value={p.value}>{p.label}</option>
          ))}
        </select>

        <input
          type="text"
          placeholder="Filter by company..."
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          style={{ ...inputStyle, width: 200 }}
          {...focus}
        />
      </div>
    </div>
  );
}
