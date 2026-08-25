import { ImageResponse } from "next/og";

export const alt = "JobHunter — AI job search across every ATS";
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
            AI job search across every ATS
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
            Semantic search over 25,000+ postings, powered by vector embeddings.
          </div>
        </div>

        <div style={{ display: "flex", gap: "56px", alignItems: "flex-end" }}>
          {[
            ["12", "ATS sources"],
            ["25,000+", "postings"],
            ["$0", "per month"],
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
