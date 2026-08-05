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
        <Link href="/jobs" className="btn-primary" style={{ padding: "8px 18px", fontSize: 14 }}>
          Browse jobs
        </Link>
      </div>
    </header>
  );
}
