export default function Loading() {
  return (
    <main style={{ minHeight: "100dvh", padding: "48px 24px" }}>
      <div style={{ maxWidth: 1152, margin: "0 auto" }}>
        {/* Header skeleton */}
        <div style={{ marginBottom: 48 }}>
          <div
            className="animate-pulse"
            style={{
              width: 200,
              height: 32,
              borderRadius: 8,
              background: "var(--bg-neutral-secondary-medium)",
              marginBottom: 16,
            }}
          />
          <div
            className="animate-pulse"
            style={{
              width: 360,
              height: 20,
              borderRadius: 8,
              background: "var(--bg-neutral-secondary-medium)",
            }}
          />
        </div>

        {/* Filter bar skeleton */}
        <div className="flex flex-wrap gap-3" style={{ marginBottom: 24 }}>
          <div
            className="animate-pulse flex-1"
            style={{
              minWidth: 200,
              height: 42,
              borderRadius: 8,
              background: "var(--bg-neutral-secondary-medium)",
            }}
          />
          <div
            className="animate-pulse"
            style={{ width: 140, height: 42, borderRadius: 8, background: "var(--bg-neutral-secondary-medium)" }}
          />
          <div
            className="animate-pulse"
            style={{ width: 180, height: 42, borderRadius: 8, background: "var(--bg-neutral-secondary-medium)" }}
          />
        </div>

        {/* Table skeleton */}
        <div
          style={{
            background: "var(--bg-neutral-primary-soft)",
            border: "1px solid var(--border-default)",
            borderRadius: 8,
            boxShadow: "var(--shadow-xs)",
            overflow: "hidden",
          }}
        >
          {Array.from({ length: 10 }).map((_, i) => (
            <div
              key={i}
              className="animate-pulse"
              style={{
                height: 56,
                borderBottom: i < 9 ? "1px solid var(--border-default)" : "none",
                background: i === 0 ? "var(--bg-neutral-secondary-soft)" : "transparent",
              }}
            />
          ))}
        </div>
      </div>
    </main>
  );
}
