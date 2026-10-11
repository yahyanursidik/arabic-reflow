import { test, expect, Page, APIRequestContext } from "@playwright/test";
import path from "node:path";

const fixtures = path.resolve(__dirname, "../../../tests/fixtures");
const api = process.env.REFLOW_E2E_API_URL ?? "http://127.0.0.1:8100/api/v1";

async function upload(page: Page, name = "mixed-id-ar.pdf") {
  await page.goto("/");
  await page
    .getByLabel("Pilih dokumen PDF")
    .setInputFiles(path.join(fixtures, name));
  await page.getByRole("button", { name: "Unggah & lanjutkan" }).click();
  await expect(page).toHaveURL(/\/documents\/[a-f0-9]{32}$/);
  await expect(page.getByRole("heading", { name })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Mulai konversi" }),
  ).toBeEnabled();
  return page.url().split("/").at(-1)!;
}

async function convert(page: Page) {
  await page.getByRole("button", { name: "Mulai konversi" }).click();
  await expect(
    page.getByRole("heading", { name: "Tinjau hasil konversi" }),
  ).toBeVisible();
}

async function paragraph(request: APIRequestContext, id: string) {
  const response = await request.get(`${api}/documents/${id}/reflow`);
  const reflow = await response.json();
  return reflow.chapters
    .flatMap(
      (chapter: {
        blocks: { id: string; type: string; content?: { text: string }[] }[];
      }) => chapter.blocks,
    )
    .find((block: { type: string }) => block.type === "paragraph");
}

test("real upload → conversion → preview selection → save → metadata → EPUB download", async ({
  page,
  request,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const id = await upload(page);
  await convert(page);
  const block = await paragraph(request, id);
  await page.locator(`[data-block-id="${block.id}"]`).click();
  await expect(page.getByLabel("Teks hasil ekstraksi")).toHaveValue(
    block.content.map((node: { text: string }) => node.text).join(""),
  );
  const revised =
    "Hadits dari أَبِي هُرَيْرَةَ, dalam kitab. Suntingan pengguna.";
  await page.getByLabel("Teks hasil ekstraksi").fill(revised);
  await expect(
    page.getByRole("button", { name: "Unduh EPUB 3" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Simpan suntingan" }).click();
  await expect(page.getByLabel("Teks hasil ekstraksi")).toHaveValue(revised);
  await expect(
    page.getByRole("button", { name: "Unduh EPUB 3" }),
  ).toBeEnabled();
  await expect(
    page.locator(`[data-block-id="${block.id}"] bdi[dir="rtl"]`),
  ).toContainText("أَبِي هُرَيْرَةَ");
  const isolated = page.locator(`[data-block-id="${block.id}"] bdi[dir="rtl"]`);
  expect(await isolated.textContent()).toBe("أَبِي هُرَيْرَةَ");
  expect(
    await isolated.evaluate((node) => node.previousSibling?.textContent),
  ).toBe(" ");
  await page.screenshot({
    path: testInfo.outputPath("workspace-desktop.png"),
    fullPage: true,
  });
  await page
    .getByLabel("Judul buku", { exact: true })
    .fill(" Buku hasil review ");
  await page
    .getByLabel("Penulis (pisahkan dengan koma)")
    .fill("Pengguna, Penulis Kedua");
  await page.getByRole("button", { name: "Simpan identitas" }).click();
  await expect(page.getByLabel("Judul buku", { exact: true })).toHaveValue(
    "Buku hasil review",
  );
  await expect(
    page.getByRole("button", { name: "Unduh EPUB 3" }),
  ).toBeEnabled();
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Unduh EPUB 3" }).click();
  const download = await downloaded;
  expect(download.suggestedFilename()).toBe("mixed-id-ar.epub");
  expect(await download.failure()).toBeNull();
  await expect(
    page.getByRole("status").filter({ hasText: "Unduhan telah dimulai" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("unsaved edits are guarded and cancel returns original text", async ({
  page,
  request,
}) => {
  const id = await upload(page);
  await convert(page);
  const block = await paragraph(request, id);
  await page.locator(`[data-block-id="${block.id}"]`).click();
  const original = await page.getByLabel("Teks hasil ekstraksi").inputValue();
  await page.getByLabel("Teks hasil ekstraksi").fill("Belum disimpan.");
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("link", { name: "Unggah PDF lain" }).click();
  await expect(page).toHaveURL(new RegExp(id));
  await expect(page.getByLabel("Teks hasil ekstraksi")).toHaveValue(
    "Belum disimpan.",
  );
  await page.getByRole("button", { name: "Batalkan perubahan" }).click();
  await expect(page.getByLabel("Teks hasil ekstraksi")).toHaveValue(original);
});

test("reconversion loads the latest job and displays results automatically", async ({
  page,
}) => {
  await upload(page);
  await convert(page);
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Konversi ulang" }).click();
  await expect(
    page.getByRole("heading", { name: "Tinjau hasil konversi" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Unduh EPUB 3" }),
  ).toBeEnabled();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Tinjau hasil konversi" }),
  ).toBeVisible();
});

test("failed conversion exposes retry; empty scans cannot download blank EPUB", async ({
  page,
}) => {
  const id = await upload(page, "scanned.pdf");
  const failed = {
    id: "failed-job",
    document_id: id,
    status: "failed",
    stage: "failed",
    progress: 35,
    warnings: [],
    error: "OCR engine unavailable",
  };
  await page.route(`**/api/v1/documents/${id}/convert`, (route) =>
    route.fulfill({ status: 202, json: { job_id: failed.id } }),
  );
  await page.route(`**/api/v1/jobs/${failed.id}`, (route) =>
    route.fulfill({ json: failed }),
  );
  await page.getByRole("button", { name: "Mulai konversi" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "OCR engine unavailable" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Coba konversi lagi" }),
  ).toBeEnabled();
  await page.unroute(`**/api/v1/documents/${id}/convert`);
  await page.getByRole("button", { name: "Coba konversi lagi" }).click();
  await expect(
    page.getByRole("heading", { name: "Tinjau hasil konversi" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Unduh EPUB 3" }),
  ).toBeDisabled();
  await expect(
    page.getByText("Belum ada isi buku.", { exact: false }),
  ).toBeVisible();
});

test("export network failures are visible and retry remains available", async ({
  page,
}) => {
  const id = await upload(page);
  await convert(page);
  await page.route(`**/api/v1/documents/${id}/export/epub`, (route) =>
    route.abort("failed"),
  );
  await page.getByRole("button", { name: "Unduh EPUB 3" }).click();
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "Tidak dapat menghubungi server" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Unduh EPUB 3" }),
  ).toBeEnabled();
});

test("mobile panes, selected source page, and search work without horizontal overflow", async ({
  page,
  request,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const id = await upload(page, "two-column.pdf");
  await convert(page);
  const block = await paragraph(request, id);
  await page.locator(`[data-block-id="${block.id}"]`).press("Enter");
  await expect(page.getByLabel("Teks hasil ekstraksi")).toBeVisible();
  await page
    .getByLabel("Cari teks, jenis blok, atau halaman")
    .fill("TidakAdaKataIni");
  await expect(
    page.getByText("Tidak ada blok yang cocok.", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "PDF sumber", exact: true }).click();
  await expect(page.getByAltText(/Halaman 1 PDF sumber/)).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("workspace-mobile.png"),
    fullPage: true,
  });
});

test("source navigation clamps page input and selection restores its source page", async ({
  page,
  request,
}) => {
  const id = await upload(page, "hybrid.pdf");
  await convert(page);
  const block = await paragraph(request, id);
  await page.getByRole("button", { name: "Halaman sumber berikutnya" }).click();
  await expect(page.getByLabel("Halaman", { exact: true })).toHaveValue("2");
  await expect(page.getByAltText(/Halaman 2 PDF sumber/)).toBeVisible();
  await page.getByLabel("Tampilkan pratinjau").selectOption("page");
  await expect(
    page.getByText("Tidak ada blok hasil ekstraksi untuk halaman ini.", {
      exact: false,
    }),
  ).toBeVisible();
  await page.getByLabel("Tampilkan pratinjau").selectOption("all");
  await page.locator(`[data-block-id="${block.id}"]`).click();
  await expect(page.getByLabel("Halaman", { exact: true })).toHaveValue("1");
  await page.getByLabel("Halaman", { exact: true }).fill("99");
  await page.getByLabel("Halaman", { exact: true }).press("Enter");
  await expect(page.getByLabel("Halaman", { exact: true })).toHaveValue("2");
});

test("saved edits can be restored once and the restore action then disables", async ({
  page,
  request,
}) => {
  const id = await upload(page);
  await convert(page);
  const block = await paragraph(request, id);
  const original = block.content
    .map((node: { text: string }) => node.text)
    .join("");
  await page.locator(`[data-block-id="${block.id}"]`).click();
  await page
    .getByLabel("Teks hasil ekstraksi")
    .fill("Suntingan yang akan dipulihkan.");
  await page.getByRole("button", { name: "Simpan suntingan" }).click();
  await expect(
    page.getByRole("button", { name: "Unduh EPUB 3" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Pulihkan teks awal" }).click();
  await expect(page.getByLabel("Teks hasil ekstraksi")).toHaveValue(original);
  await expect(
    page.getByRole("button", { name: "Pulihkan teks awal" }),
  ).toBeDisabled();
});

test("file validation and missing documents show useful recovery", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Pilih dokumen PDF").setInputFiles({
    name: "notes.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("not a pdf"),
  });
  await expect(
    page.getByRole("alert").filter({ hasText: "Pilih berkas PDF" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Unggah & lanjutkan" }),
  ).toBeDisabled();
  await page.goto("/documents/doesnotexist");
  await expect(
    page.getByRole("heading", { name: "Dokumen belum bisa dibuka" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Kembali ke unggahan" }),
  ).toBeVisible();
});

test("structure editor updates heading levels, outline, and reading order", async ({
  page,
  request,
}) => {
  const id = await upload(page);
  await convert(page);
  const block = await paragraph(request, id);
  await page.locator(`[data-block-id="${block.id}"]`).click();
  await page.getByLabel("Jenis blok", { exact: true }).selectOption("heading");
  await page.getByLabel("Level judul", { exact: true }).selectOption("2");
  await page.getByRole("button", { name: "Simpan suntingan" }).click();
  await expect(page.locator(`[data-block-id="${block.id}"] h2`)).toBeVisible();
  await expect(page.getByLabel("Jenis blok", { exact: true })).toHaveValue(
    "heading",
  );
  await expect(page.getByLabel("Level judul", { exact: true })).toHaveValue(
    "2",
  );
  const before = await (
    await request.get(`${api}/documents/${id}/reflow`)
  ).json();
  const index = before.chapters[0].blocks.findIndex(
    (item: { id: string }) => item.id === block.id,
  );
  await page.getByRole("button", { name: "Pindahkan ke atas" }).click();
  await expect
    .poll(async () => {
      const after = await (
        await request.get(`${api}/documents/${id}/reflow`)
      ).json();
      return after.chapters[0].blocks.findIndex(
        (item: { id: string }) => item.id === block.id,
      );
    })
    .toBe(index - 1);
});

test("footnote inner text is selectable and editable without changing the outer marker", async ({
  page,
  request,
}) => {
  const id = await upload(page, "footnote-heavy.pdf");
  await convert(page);
  const model = await (
    await request.get(`${api}/documents/${id}/reflow`)
  ).json();
  const note = model.chapters[0].blocks.find(
    (block: { type: string }) => block.type === "footnote",
  );
  await page.locator(`[data-block-id="${note.blocks[0].id}"]`).click();
  await page
    .getByLabel("Teks hasil ekstraksi")
    .fill("Catatan kaki disunting pengguna.");
  await page.getByRole("button", { name: "Simpan suntingan" }).click();
  await expect(
    page.locator(`[data-block-id="${note.blocks[0].id}"]`),
  ).toContainText("Catatan kaki disunting pengguna.");
  const after = await (
    await request.get(`${api}/documents/${id}/reflow`)
  ).json();
  expect(
    after.chapters[0].blocks.find(
      (block: { id: string }) => block.id === note.id,
    ).marker,
  ).toBe(note.marker);
});

test("image alternative descriptions can be saved for accessible EPUB export", async ({
  page,
  request,
}) => {
  const id = await upload(page, "image-caption.pdf");
  await convert(page);
  const model = await (
    await request.get(`${api}/documents/${id}/reflow`)
  ).json();
  const image = model.chapters[0].blocks.find(
    (block: { type: string }) => block.type === "image",
  );
  await page.locator(`[data-block-id="${image.id}"]`).click();
  await page
    .getByLabel("Deskripsi alternatif gambar")
    .fill('Diagram "sumber" untuk pembaca layar.');
  await page.getByRole("button", { name: "Simpan deskripsi" }).click();
  await expect(
    page.getByAltText('Diagram "sumber" untuk pembaca layar.'),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Unduh EPUB 3" }),
  ).toBeEnabled();
});

test("OCR readiness explains missing engines rather than launching a known broken job", async ({
  page,
}) => {
  await page.route("**/api/v1/capabilities", (route) =>
    route.fulfill({
      json: {
        ocr: {
          engines: [
            {
              name: "tesseract",
              available: false,
              languages: [],
              message: "Missing binary",
            },
            {
              name: "paddle",
              available: false,
              languages: [],
              message: "Missing runtime",
            },
          ],
        },
        validation: { epubcheck: false },
      },
    }),
  );
  await upload(page, "scanned.pdf");
  await page
    .getByLabel("OCR untuk halaman pindai / teks rusak", { exact: true })
    .check();
  await expect(
    page.getByText("OCR belum siap untuk bahasa yang dipilih.", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Mulai konversi" }),
  ).toBeDisabled();
  await page
    .getByLabel("OCR untuk halaman pindai / teks rusak", { exact: true })
    .uncheck();
  await expect(
    page.getByRole("button", { name: "Mulai konversi" }),
  ).toBeEnabled();
});
