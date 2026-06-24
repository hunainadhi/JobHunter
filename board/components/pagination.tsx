import Link from "next/link";

type PaginationProps = {
  currentPage: number;
  totalPages: number;
  searchParams: Record<string, string>;
};

function buildHref(page: number, searchParams: Record<string, string>): string {
  const params = new URLSearchParams(searchParams);
  if (page > 1) {
    params.set("page", String(page));
  } else {
    params.delete("page");
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "/";
}

function getPageNumbers(current: number, total: number): (number | "ellipsis")[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: (number | "ellipsis")[] = [1];

  if (current > 3) pages.push("ellipsis");

  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);
  for (let i = start; i <= end; i++) {
    pages.push(i);
  }

  if (current < total - 2) pages.push("ellipsis");

  pages.push(total);
  return pages;
}

const itemBase: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  minWidth: 36,
  height: 36,
  fontSize: 14,
  fontWeight: 500,
  background: "var(--bg-neutral-secondary-medium)",
  border: "1px solid var(--border-default-medium)",
  color: "var(--text-body)",
  textDecoration: "none",
  marginLeft: -1,
  transition: "background 150ms, color 150ms",
};

export function Pagination({ currentPage, totalPages, searchParams }: PaginationProps) {
  if (totalPages <= 1) return null;

  const pages = getPageNumbers(currentPage, totalPages);

  return (
    <nav
      aria-label="Pagination"
      className="flex justify-center"
      style={{ marginTop: 24 }}
    >
      <div className="flex">
        {/* Previous */}
        {currentPage > 1 ? (
          <Link
            href={buildHref(currentPage - 1, searchParams)}
            style={{
              ...itemBase,
              padding: "0 12px",
              borderRadius: "8px 0 0 8px",
            }}
          >
            Previous
          </Link>
        ) : (
          <span
            style={{
              ...itemBase,
              padding: "0 12px",
              borderRadius: "8px 0 0 8px",
              color: "var(--text-fg-disabled)",
              cursor: "not-allowed",
            }}
          >
            Previous
          </span>
        )}

        {/* Page numbers */}
        {pages.map((p, i) =>
          p === "ellipsis" ? (
            <span key={`e${i}`} style={{ ...itemBase, cursor: "default" }}>
              ...
            </span>
          ) : p === currentPage ? (
            <span
              key={p}
              style={{
                ...itemBase,
                color: "var(--text-fg-brand)",
                background: "var(--bg-neutral-tertiary-medium)",
              }}
            >
              {p}
            </span>
          ) : (
            <Link key={p} href={buildHref(p, searchParams)} style={itemBase}>
              {p}
            </Link>
          )
        )}

        {/* Next */}
        {currentPage < totalPages ? (
          <Link
            href={buildHref(currentPage + 1, searchParams)}
            style={{
              ...itemBase,
              padding: "0 12px",
              borderRadius: "0 8px 8px 0",
            }}
          >
            Next
          </Link>
        ) : (
          <span
            style={{
              ...itemBase,
              padding: "0 12px",
              borderRadius: "0 8px 8px 0",
              color: "var(--text-fg-disabled)",
              cursor: "not-allowed",
            }}
          >
            Next
          </span>
        )}
      </div>
    </nav>
  );
}
