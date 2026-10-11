const { test } = require("node:test");
const assert = require("node:assert/strict");
const {
  parseReflow,
  parseJob,
  parseTextRepairResult,
  ContractError,
} = require("../.test-build/contract.js");
const { validatePdf, MAX_UPLOAD_BYTES } = require("../.test-build/files.js");
const {
  searchKey,
  needsReview,
  isolatedText,
  repairCandidates,
} = require("../.test-build/review.js");
const { apiErrorMessage } = require("../.test-build/api.js");

test("source word images retain their node type and resource rather than becoming editable text", () => {
  const block = parseReflow({ chapters: [{ blocks: [{ id: "p", type: "paragraph", content: [
    { type: "text", text: "Latin " },
    { type: "inline_image", resource_id: "source-word", alt: "al-amr" },
    { type: "text", text: " lanjut." },
  ] }] }] }).blocks[0];
  assert.deepEqual(block.nodes[1], { kind: "image", text: "al-amr", resourceId: "source-word" });
  assert.throws(() => parseReflow({ chapters: [{ blocks: [{ id: "p", type: "paragraph", content: [
    { type: "inline_image", alt: "al-amr" },
  ] }] }] }), ContractError);
});

test("repair candidates skip saved edits and include known text artifacts", () => {
  const blocks = parseReflow({ schema_version: "0.1", document_id: "d", chapters: [{ id: "c", blocks: [
    { id: "bad", type: "quote", text: "ﻻ", warnings: [] },
    { id: "review", type: "quote", text: "عربي", warnings: ["OCR_LOW_CONFIDENCE"] },
    { id: "edited", type: "quote", text: "ﻻ", modified_by_user: true },
    { id: "healthy", type: "quote", text: "سليم", warnings: ["AUTO_TEXT_REPAIRED"] },
    { id: "image", type: "image", resource_id: "r", warnings: ["OCR_LOW_CONFIDENCE"] },
  ] }] }).blocks;
  assert.deepEqual(repairCandidates(blocks).map((block) => block.id), ["bad", "review"]);
});

test("repair responses validate changed, unchanged, skipped and review IDs", () => {
  const result = parseTextRepairResult({ changed_block_ids: ["p"], unchanged_block_ids: [], skipped_block_ids: ["q"], review_block_ids: ["p"] });
  assert.deepEqual(result.changedBlockIds, ["p"]);
  assert.deepEqual(result.reviewBlockIds, ["p"]);
  assert.throws(() => parseTextRepairResult({ changed_block_ids: [42] }), ContractError);
  assert.throws(() => parseTextRepairResult(null), ContractError);
});
const {
  recentDocuments,
  rememberDocument,
} = require("../.test-build/history.js");

test("PDF validation handles empty, non-PDF, oversized, and uppercase names", () => {
  assert.equal(validatePdf({ name: "book.PDF", size: MAX_UPLOAD_BYTES }), null);
  assert.ok(validatePdf({ name: "book.pdf", size: 0 }));
  assert.ok(validatePdf({ name: "book.pdf", size: MAX_UPLOAD_BYTES + 1 }));
  assert.ok(validatePdf({ name: "book.txt", size: 42 }));
});

test("capabilities distinguish installed languages and optional W3C validation", () => {
  const { parseCapabilities } = require("../.test-build/contract.js");
  const capabilities = parseCapabilities({
    validation: { epubcheck: true },
    ocr: {
      engines: [
        {
          name: "tesseract",
          available: false,
          languages: ["en"],
          message: "Missing ara/ind",
        },
      ],
    },
  });
  assert.equal(capabilities.epubcheckAvailable, true);
  assert.deepEqual(capabilities.ocr.engines[0].languages, ["en"]);
  assert.throws(
    () => parseCapabilities({ ocr: { engines: [{ name: "unknown" }] } }),
    ContractError,
  );
});

test("nested blocks inherit source pages and retain safe sibling movement boundaries", () => {
  const { flattenBlocks } = require("../.test-build/review.js");
  const model = parseReflow({
    chapters: [
      {
        blocks: [
          {
            id: "note",
            type: "footnote",
            source: { page: 3 },
            blocks: [
              {
                id: "inner",
                type: "paragraph",
                content: [{ type: "text", text: "Catatan" }],
              },
            ],
          },
        ],
      },
    ],
  });
  const flat = flattenBlocks(model.blocks);
  assert.equal(flat[1].page, 3);
  assert.equal(flat[1].parentId, "note");
  assert.equal(flat[1].canMoveUp, false);
  assert.equal(flat[1].canMoveDown, false);
});

test("quality report preserves export gate and page review targets", () => {
  const { parseReport } = require("../.test-build/contract.js");
  const report = parseReport({
    quality: {
      block_count: 2,
      edited_block_count: 1,
      can_export: false,
      review_block_ids: ["p"],
      pages: [{ page: 3, block_count: 2, review_block_ids: ["p"] }],
      issues: [
        { code: "MISSING_RESOURCE", severity: "error", message: "Missing" },
      ],
    },
  });
  assert.equal(report.quality.canExport, false);
  assert.equal(report.quality.pages[0].page, 3);
});

test("mixed text and harakat remain untouched in the UI contract", () => {
  const arabic = "إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ";
  const model = parseReflow({
    document_id: "demo",
    chapters: [
      {
        blocks: [
          {
            id: "p",
            type: "paragraph",
            content: [
              { type: "text", text: "Hadits: " },
              { type: "span", text: arabic, lang: "ar", dir: "rtl" },
            ],
          },
        ],
      },
    ],
  });
  assert.equal(model.blocks[0].text, `Hadits: ${arabic}`);
  assert.equal(model.blocks[0].nodes[1].dir, "rtl");
  assert.equal(searchKey(arabic), "إنما الأعمال بالنيات");
  assert.equal(model.blocks[0].nodes[1].text, arabic);
});

test("list/table/footnote content is available for real previews and search", () => {
  const p = {
    id: "inner",
    type: "paragraph",
    content: [{ type: "text", text: "Isi daftar" }],
  };
  const model = parseReflow({
    chapters: [
      {
        blocks: [
          { id: "list", type: "list", ordered: true, items: [{ blocks: [p] }] },
          {
            id: "table",
            type: "table",
            rows: [[{ text: "خانة", dir: "rtl", lang: "ar" }]],
          },
          { id: "note", type: "footnote", marker: "1", blocks: [p] },
        ],
      },
    ],
  });
  assert.equal(model.blocks[0].text, "Isi daftar");
  assert.equal(model.blocks[0].items[0][0].text, "Isi daftar");
  assert.equal(model.blocks[1].rows[0][0].dir, "rtl");
  assert.equal(model.blocks[2].text, "Isi daftar");
});

test("unknown API types fail explicitly instead of rendering empty content", () => {
  assert.throws(
    () => parseJob({ id: "j", document_id: "d", status: "unknown" }),
    ContractError,
  );
  assert.throws(
    () =>
      parseReflow({ chapters: [{ blocks: [{ id: "p", type: "unknown" }] }] }),
    ContractError,
  );
});

test("uncertain tables retain their source image fallback", () => {
  const model = parseReflow({
    chapters: [
      {
        blocks: [
          {
            id: "table",
            type: "table",
            rows: [],
            fallback_resource_id: "table-source",
          },
        ],
      },
    ],
    resources: [
      { id: "table-source", media_type: "image/png", content: "aGVsbG8=" },
    ],
  });
  assert.equal(model.blocks[0].fallbackResourceId, "table-source");
  assert.ok(
    model.resources[model.blocks[0].fallbackResourceId].dataUrl.startsWith(
      "data:image/png;base64,",
    ),
  );
});

test("review indicators account for Arabic integrity and report IDs", () => {
  const block = parseReflow({
    chapters: [
      { blocks: [{ id: "p", type: "paragraph", content: [], warnings: [] }] },
    ],
  }).blocks[0];
  assert.equal(needsReview(block), false);
  assert.equal(needsReview(block, new Set(["p"])), true);
  assert.equal(needsReview({ ...block, integrityScore: 0.4 }), true);
});

test("whitespace stays outside RTL isolation without changing text", () => {
  for (const text of [" أَبِي هُرَيْرَةَ ", "\tLatin\n", " ", "عربي", ""]) {
    const parts = isolatedText(text);
    assert.equal(parts.before + parts.content + parts.after, text);
    assert.equal(parts.content, parts.content.trim());
  }
});

test("API failures have actionable Indonesian messages", () => {
  assert.match(apiErrorMessage(422, [{ msg: "invalid input" }]), /belum valid/);
  assert.match(apiErrorMessage(400, "PDF is encrypted"), /kata sandi/);
  assert.match(apiErrorMessage(409), /Konversi masih berjalan/);
});

test("recent documents deduplicate and survive unavailable browser storage", () => {
  const data = new Map();
  global.localStorage = {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => data.set(key, value),
  };
  const document = {
    id: "one",
    filename: "book.pdf",
    size: 42,
    createdAt: "today",
  };
  rememberDocument(document);
  rememberDocument(document);
  assert.equal(recentDocuments().length, 1);
  assert.equal(recentDocuments()[0].createdAt, "today");
  global.localStorage = {
    getItem: () => {
      throw new Error("unavailable");
    },
    setItem: () => {
      throw new Error("unavailable");
    },
  };
  assert.deepEqual(recentDocuments(), []);
  assert.doesNotThrow(() => rememberDocument(document));
});
