import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { SiteNav } from "@/components/site-nav";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const title = "JobHunter — every job in Canada, searched by meaning";
const description =
  "Search every live job posting in Canada, scraped straight from company career pages across Greenhouse, Lever, Ashby, and 9 other hiring platforms every day. Free, no account needed.";

export const metadata: Metadata = {
  metadataBase: new URL("https://jobhunter.hunainadhikari.com"),
  title,
  description,
  openGraph: {
    title,
    description,
    url: "https://jobhunter.hunainadhikari.com",
    siteName: "JobHunter",
    type: "website",
    locale: "en_CA",
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-dvh flex flex-col" style={{ fontFamily: "var(--font-inter), sans-serif" }}>
        <SiteNav />
        {children}
      </body>
    </html>
  );
}
