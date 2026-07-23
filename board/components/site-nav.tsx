import Link from "next/link";

export function SiteNav() {
  return (
    <header
      style={{
        borderBottom: "1px solid var(--border-default)",
        background: "var(--bg-neutral-primary-soft)",
      }}
    >
      <div
        className="flex items-center justify-between"
        style={{ maxWidth: 1152, margin: "0 auto", padding: "16px 24px" }}
      >
        <Link
          href="/"
          style={{
            fontSize: 18,
            fontWeight: 700,
            color: "var(--text-heading)",
            textDecoration: "none",
            letterSpacing: "-0.01em",
          }}
        >
          JobHunter
        </Link>
        <Link
          href="/jobs"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "8px 16px",
            fontSize: 14,
            fontWeight: 500,
            borderRadius: 8,
            background: "var(--bg-brand)",
            color: "var(--text-white)",
            textDecoration: "none",
            boxShadow: "var(--shadow-xs)",
          }}
        >
          Browse jobs
        </Link>
      </div>
    </header>
  );
}
