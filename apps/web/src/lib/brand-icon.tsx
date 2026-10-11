import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ImageResponse } from "next/og";

// Frame the supplied book symbol for small app icons; do not redraw its lettering.
export async function brandIcon(size: number) {
  const logo = await readFile(join(process.cwd(), "public/brand/arabic-reflow-logo.png"));
  return new ImageResponse(
    <div style={{ display: "flex", position: "relative", width: size, height: size,
      overflow: "hidden", background: "white" }}>
      <div style={{ display: "flex", position: "absolute", width: size, height: size * 0.81,
        top: size * 0.095, overflow: "hidden" }}><img src={`data:image/png;base64,${logo.toString("base64")}`} alt=""
        width={size * 1.25} height={size * 1.25}
        style={{ position: "absolute", left: -size * 0.14, top: -size * 0.13 }} /></div>
    </div>,
    { width: size, height: size },
  );
}
