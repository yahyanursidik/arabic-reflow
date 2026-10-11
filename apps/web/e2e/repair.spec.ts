import { test, expect } from "@playwright/test";
import path from "node:path";
import { readFile, writeFile } from "node:fs/promises";

test("main repair buttons, automatic repairs, dirty guard and restore work together", async ({ page, request }) => {
  const api = process.env.REFLOW_E2E_API_URL ?? "http://127.0.0.1:8100/api/v1";
  const fixture = path.resolve(__dirname, "../../../tests/fixtures/mixed-id-ar.pdf");
  const uploaded = await request.post(`${api}/documents`, { multipart: {
    file: { name: "repair-ui-test.pdf", mimeType: "application/pdf", buffer: await readFile(fixture) },
  } });
  expect(uploaded.status()).toBe(201);
  const { id } = await uploaded.json();
  const conversion = await request.post(`${api}/documents/${id}/convert`, { data: { mode: "native" } });
  const { job_id } = await conversion.json();
  await expect.poll(async () => (await (await request.get(`${api}/jobs/${job_id}`)).json()).status).toBe("completed");

  // Seed extraction defects in this test's own document, never a user document.
  const storage = process.env.REFLOW_E2E_STORAGE ?? path.resolve(__dirname, "../.e2e-storage");
  const file = path.join(storage, "documents", id, "reflow.json");
  const document = JSON.parse(await readFile(file, "utf-8"));
  const original = "ﻻ\u0651\u064e\u001b";
  document.chapters[0].blocks.push({
    id: "repair-candidate", type: "paragraph", lang: "ar", dir: "rtl", source: { page: 1, bbox: [72, 72, 400, 110] },
    content: [{ type: "text", text: original }], warnings: ["OCR_LOW_CONFIDENCE"], confidence: 0.5,
  }, { id: "manual-edit", type: "quote", text: "ﻻ", modified_by_user: true, warnings: ["OCR_LOW_CONFIDENCE"] });
  await writeFile(file, JSON.stringify(document));
  await page.goto(`/documents/${id}`);
  await page.getByLabel("Tampilkan pratinjau").selectOption("all");
  await page.locator('[data-block-id="repair-candidate"]').click();
  const controls = page.getByRole("region", { name: "Perbaikan blok" });
  await expect(controls.getByRole("button", { name: "Perbaiki teks", exact: true })).toBeVisible();
  await expect(controls.getByRole("button", { name: "Jadikan gambar", exact: true })).toBeVisible();
  await expect(controls.getByRole("button", { name: "Pulihkan teks awal" })).toBeDisabled();
  await page.getByLabel("Teks hasil ekstraksi").fill("Belum disimpan.");
  await expect(controls.getByRole("button", { name: "Perbaiki teks", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: /^Perbaiki otomatis/ })).toBeDisabled();
  await page.getByRole("button", { name: "Batalkan perubahan" }).click();
  await page.getByRole("button", { name: /^Perbaiki otomatis/ }).click();
  await expect(page.getByLabel("Teks hasil ekstraksi")).toHaveValue("لا\u0651\u064e");
  await expect(controls.getByRole("button", { name: "Pulihkan teks awal" })).toBeEnabled();
  const after = await (await request.get(`${api}/documents/${id}/reflow`)).json();
  expect(after.chapters[0].blocks.find((block: { id: string }) => block.id === "manual-edit").text).toBe("ﻻ");
  await controls.getByRole("button", { name: "Perbaiki teks", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "0 blok diperbaiki." })).toBeVisible();
  await controls.getByRole("button", { name: "Jadikan gambar", exact: true }).click();
  await expect(page.getByLabel("Deskripsi alternatif gambar")).toBeVisible();
  await expect(controls.getByRole("button", { name: "Perbaiki teks", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Perbesar gambar", exact: true }).click();
  await page.setViewportSize({ width: 375, height: 812 });
  const viewer = page.getByRole("dialog");
  await expect(viewer.getByRole("button", { name: "Zoom 200%. Sesuaikan gambar ke layar" })).toBeVisible();
  const canvas = viewer.getByRole("region", { name: "Gambar ukuran penuh; geser untuk melihat seluruh bagian" });
  await expect(canvas).toHaveAttribute("dir", "rtl");
  expect(await canvas.evaluate((node) => node.scrollWidth > node.clientWidth)).toBe(true);
  await viewer.getByRole("button", { name: "Zoom 200%. Sesuaikan gambar ke layar" }).click();
  await expect(viewer.getByRole("button", { name: "Zoom 100%. Sesuaikan gambar ke layar" })).toBeVisible();
  expect(await canvas.evaluate((node) => {
    const image = node.querySelector("img")!;
    const rectangle = image.getBoundingClientRect();
    return Math.abs(rectangle.width / rectangle.height - image.naturalWidth / image.naturalHeight) < 0.01;
  })).toBe(true);
  await viewer.getByRole("button", { name: "Tutup ×", exact: true }).click();
  await page.setViewportSize({ width: 1280, height: 720 });
  await controls.getByRole("button", { name: "Pulihkan teks awal" }).click();
  await expect(page.getByLabel("Teks hasil ekstraksi")).toHaveValue(original);
  await expect(controls.getByRole("button", { name: "Pulihkan teks awal" })).toBeDisabled();
});
