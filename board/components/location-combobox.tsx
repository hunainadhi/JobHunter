"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { MapPin, X } from "lucide-react";
import type { PlaceOption } from "@/lib/types";
import { RADIUS_OPTIONS } from "@/lib/types";

const MAX_SUGGESTIONS = 8;

function fold(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
}

/**
 * Prefix matches first, then substring — so "tor" puts Toronto above Peterborough,
 * and within each group the busiest place wins. Province code matches too, so
 * "waterloo on" works.
 */
function rankPlaces(places: PlaceOption[], term: string): PlaceOption[] {
  const needle = fold(term);
  if (!needle) return [];

  const prefix: PlaceOption[] = [];
  const contains: PlaceOption[] = [];

  for (const place of places) {
    const name = fold(place.name);
    const full = `${name} ${place.province.toLowerCase()}`;
    if (name.startsWith(needle) || full.startsWith(needle)) prefix.push(place);
    else if (name.includes(needle) || full.includes(needle)) contains.push(place);
  }

  const byCount = (a: PlaceOption, b: PlaceOption) => b.job_count - a.job_count;
  return [...prefix.sort(byCount), ...contains.sort(byCount)].slice(0, MAX_SUGGESTIONS);
}

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

export function LocationCombobox({
  places,
  selectedPlace,
  locationText,
  radius,
  includeRemote,
  onSelectPlace,
  onFreeText,
  onRadiusChange,
  onRemoteChange,
}: {
  places: PlaceOption[];
  selectedPlace: PlaceOption | null;
  locationText: string;
  radius: number;
  includeRemote: boolean;
  onSelectPlace: (place: PlaceOption | null) => void;
  onFreeText: (value: string) => void;
  onRadiusChange: (km: number) => void;
  onRemoteChange: (include: boolean) => void;
}) {
  const [term, setTerm] = useState(locationText);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const wrapRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const suggestions = useMemo(
    () => (open ? rankPlaces(places, term) : []),
    [places, term, open]
  );

  useEffect(() => {
    setTerm(locationText);
  }, [locationText]);

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  // Free text still filters, so typing "remote" or a city we don't have a place
  // for keeps working exactly as it did before.
  function scheduleFreeText(value: string) {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => onFreeText(value), 350);
  }

  function choose(place: PlaceOption) {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    setOpen(false);
    setTerm("");
    onSelectPlace(place);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || suggestions.length === 0) {
      if (event.key === "Escape") setOpen(false);
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((i) => (i + 1) % suggestions.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((i) => (i - 1 + suggestions.length) % suggestions.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      choose(suggestions[Math.min(active, suggestions.length - 1)]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  if (selectedPlace) {
    return (
      <div className="flex flex-wrap items-center" style={{ gap: 8 }}>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "9px 10px 9px 12px",
            borderRadius: 8,
            fontSize: 14,
            fontWeight: 500,
            background: "var(--bg-neutral-tertiary-medium)",
            border: "1px solid var(--border-default-medium)",
            color: "var(--text-heading)",
          }}
        >
          <MapPin size={14} aria-hidden="true" />
          {selectedPlace.name}, {selectedPlace.province}
          <button
            type="button"
            onClick={() => onSelectPlace(null)}
            aria-label={`Clear ${selectedPlace.name}`}
            style={{
              display: "inline-flex",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: "var(--text-body)",
              padding: 2,
              borderRadius: 4,
            }}
          >
            <X size={14} />
          </button>
        </span>

        <label style={{ fontSize: 14, color: "var(--text-body)" }}>
          <span style={{ marginRight: 6 }}>within</span>
          <select
            value={radius}
            onChange={(e) => onRadiusChange(parseInt(e.target.value, 10))}
            aria-label="Search radius"
            style={{
              background: "var(--bg-neutral-secondary-medium)",
              border: "1px solid var(--border-default-medium)",
              borderRadius: 8,
              padding: "9px 10px",
              fontSize: 14,
              color: "var(--text-heading)",
              cursor: "pointer",
            }}
          >
            {RADIUS_OPTIONS.map((km) => (
              <option key={km} value={km}>{km} km</option>
            ))}
          </select>
        </label>

        <label
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: 14,
            color: "var(--text-body)",
            cursor: "pointer",
          }}
        >
          <input
            type="checkbox"
            checked={includeRemote}
            onChange={(e) => onRemoteChange(e.target.checked)}
            style={{ cursor: "pointer" }}
          />
          Include remote
        </label>
      </div>
    );
  }

  return (
    <div ref={wrapRef} style={{ position: "relative", width: 220 }}>
      <input
        type="text"
        placeholder="Location or remote"
        value={term}
        role="combobox"
        aria-expanded={open && suggestions.length > 0}
        aria-controls="location-suggestions"
        aria-autocomplete="list"
        onChange={(e) => {
          setTerm(e.target.value);
          setOpen(true);
          setActive(0);
          scheduleFreeText(e.target.value);
        }}
        onFocus={(e) => {
          setOpen(true);
          e.currentTarget.style.borderColor = "var(--border-brand)";
          e.currentTarget.style.boxShadow = "0 0 0 1px var(--border-brand)";
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = "var(--border-default-medium)";
          e.currentTarget.style.boxShadow = "var(--shadow-xs)";
        }}
        onKeyDown={onKeyDown}
        style={{ ...inputStyle, width: "100%" }}
      />

      {open && suggestions.length > 0 && (
        <ul
          id="location-suggestions"
          role="listbox"
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            right: 0,
            zIndex: 30,
            margin: 0,
            padding: 4,
            listStyle: "none",
            background: "var(--bg-neutral-primary-medium, var(--bg-neutral-secondary-medium))",
            border: "1px solid var(--border-default-medium)",
            borderRadius: 8,
            boxShadow: "var(--shadow-md, 0 8px 24px rgba(0,0,0,0.18))",
            maxHeight: 300,
            overflowY: "auto",
          }}
        >
          {suggestions.map((place, index) => (
            <li key={place.slug} role="option" aria-selected={index === active}>
              <button
                type="button"
                onMouseEnter={() => setActive(index)}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => choose(place)}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  gap: 12,
                  width: "100%",
                  textAlign: "left",
                  padding: "8px 10px",
                  fontSize: 14,
                  border: "none",
                  borderRadius: 6,
                  cursor: "pointer",
                  color: "var(--text-heading)",
                  background:
                    index === active ? "var(--bg-neutral-tertiary-medium)" : "transparent",
                }}
              >
                <span>
                  {place.name}
                  <span style={{ color: "var(--text-body)" }}>, {place.province}</span>
                </span>
                <span
                  style={{
                    fontSize: 12,
                    color: "var(--text-body)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {place.job_count.toLocaleString()}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
