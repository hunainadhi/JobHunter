import { ImageResponse } from "next/og";

export const alt = "JobHunter — every job in Canada, searched by meaning";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#09090b",
          padding: "72px",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div
            style={{
              display: "flex",
              fontSize: 26,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "#a1a1aa",
            }}
          >
            JobHunter
          </div>
          <div
            style={{
              display: "flex",
              marginTop: 28,
              fontSize: 84,
              fontWeight: 700,
              color: "#fafafa",
              lineHeight: 1.05,
              maxWidth: 900,
            }}
          >
            Every job in Canada, searched by meaning
          </div>
          <div
            style={{
              display: "flex",
              marginTop: 28,
              fontSize: 32,
              color: "#a1a1aa",
              maxWidth: 940,
              lineHeight: 1.35,
            }}
          >
            Scraped straight from company career pages, every single day.
          </div>
        </div>

        <div style={{ display: "flex", gap: "56px", alignItems: "flex-end" }}>
          {[
            ["12", "hiring platforms"],
            ["10,000+", "live postings"],
            ["Free", "no account"],
          ].map(([value, label]) => (
            <div key={label} style={{ display: "flex", flexDirection: "column" }}>
              <div style={{ display: "flex", fontSize: 46, fontWeight: 700, color: "#fafafa" }}>
                {value}
              </div>
              <div style={{ display: "flex", fontSize: 24, color: "#71717a", marginTop: 6 }}>
                {label}
              </div>
            </div>
          ))}
        </div>
      </div>
    ),
    { ...size }
  );
}
