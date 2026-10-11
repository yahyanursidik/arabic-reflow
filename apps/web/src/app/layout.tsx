import type { Metadata } from "next";
import Link from "next/link";
import { Inter, Source_Serif_4 } from "next/font/google";
import { Brand } from "@/components/Brand";
import { APP_VERSION } from "@/lib/version";
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
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: { default: "Arabic Reflow — PDF to EPUB", template: "%s | Arabic Reflow" },
  applicationName: "Arabic Reflow",
  description:
    "Open-source reconstruction engine for mixed Arabic-Latin PDFs to reflowable EPUB 3.",
  openGraph: { title: "Arabic Reflow", siteName: "Arabic Reflow", type: "website",
    images: [{ url: "/brand/arabic-reflow-logo.png", width: 1254, height: 1254, alt: "Logo Arabic Reflow" }] },
  twitter: { card: "summary", title: "Arabic Reflow", images: ["/brand/arabic-reflow-logo.png"] },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // Browser integrations may add webcrx attributes before React hydrates.
    // Accept root attributes only; hydration checks still apply to children.
    <html
      lang="id"
      className={`${inter.variable} ${lyon.variable}`}
      suppressHydrationWarning
    >
      <body>
        <a className="skip-link" href="#main-content">
          Langsung ke isi
        </a>
        <header className="border-b border-black/8 bg-pure-white">
          <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-4 px-4 py-4 sm:px-8">
            <Link
              href="/"
              className="shrink-0 rounded-small"
              aria-label="Arabic Reflow — halaman unggah"
            >
              <Brand />
            </Link>
            <a
              href="/#panduan"
              className="inline-flex min-h-12 items-center text-right text-sm text-graphite hover:text-notion-blue"
            >
              Panduan singkat
            </a>
          </div>
        </header>
        {children}
        <footer className="mx-auto max-w-[1500px] px-4 py-8 text-xs leading-relaxed text-stone sm:px-8">
          <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2">
            <Link href="/" aria-label="Arabic Reflow — halaman unggah"><Brand compact /></Link>
            <span>v{APP_VERSION}</span>
          </div>
          <p>Teks sumber tetap menjadi acuan. Periksa hasil ekstraksi, terutama
          teks Arab dan harakat, sebelum digunakan.</p>
        </footer>
      </body>
    </html>
  );
}
