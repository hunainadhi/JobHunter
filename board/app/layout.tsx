import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { SiteNav } from "@/components/site-nav";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "JobHunter — AI job search across every ATS",
  description:
    "JobHunter scrapes Greenhouse, Lever, Ashby, and 9 other ATS platforms daily, then uses vector embeddings to power semantic job search across Canada.",
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
