import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Arabic Reflow", short_name: "Arabic Reflow",
    description: "PDF Arab–Latin menjadi EPUB yang nyaman dibaca.",
    start_url: "/", display: "standalone", lang: "id",
    background_color: "#ffffff", theme_color: "#062449",
    icons: [{ src: "/icon", sizes: "512x512", type: "image/png", purpose: "any" }],
  };
}
