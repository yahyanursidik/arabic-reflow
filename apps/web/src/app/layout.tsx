import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Reflow — PDF to EPUB",
  description:
    "Open-source reconstruction engine for mixed Arabic-Latin PDFs to reflowable EPUB 3.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
