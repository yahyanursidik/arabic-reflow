import type { Metadata } from "next";
import { Inter, Source_Serif_4 } from "next/font/google";
import "./globals.css";

// NotionInter substitute (per style reference): Inter, weights 400-700.
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

// Lyon Text substitute: Source Serif 4 — editorial body moments + reading preview.
const lyon = Source_Serif_4({
  subsets: ["latin"],
  variable: "--font-lyon",
  weight: "400",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Reflow — PDF to EPUB",
  description:
    "Open-source reconstruction engine for mixed Arabic-Latin PDFs to reflowable EPUB 3.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="id" className={`${inter.variable} ${lyon.variable}`}>
      <body>{children}</body>
    </html>
  );
}
