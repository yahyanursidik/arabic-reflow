import { UiBlock } from "./contract";
import { warningInfo } from "./warnings";

export function needsReview(
  block: UiBlock,
  lowConfidence = new Set<string>(),
): boolean {
  return (
    lowConfidence.has(block.id) ||
    (block.integrityScore !== undefined && block.integrityScore < 0.85) ||
    block.warnings.some((code) => warningInfo(code).needsReview)
  );
}

export function searchKey(text: string): string {
  // Search-only normalization: never replace source/preview content.
  return text
    .normalize("NFKC")
    .toLocaleLowerCase("id")
    .replace(/[\u0640\u064b-\u065f\u0670\u06d6-\u06ed]/g, "");
}

export function repairCandidates(blocks: UiBlock[], reviewIds = new Set<string>()): UiBlock[] {
  return blocks.filter((block) =>
    ["paragraph", "heading", "quote"].includes(block.type) &&
    !block.modifiedByUser &&
    (needsReview(block, reviewIds) || /[\uFB00-\uFB06\uFB50-\uFDFF\uFE70-\uFEFF\u0000-\u0008\u000B\u000C\u000E-\u001F]/u.test(block.text)),
  );
}

export function isolatedText(text: string) {
  const start = text.length - text.trimStart().length;
  const end = Math.max(start, text.trimEnd().length);
  return {
    before: text.slice(0, start),
    content: text.slice(start, end),
    after: text.slice(end),
  };
}

export function flattenBlocks(
  blocks: UiBlock[],
  parentId?: string,
  inheritedPage?: number,
): UiBlock[] {
  return blocks.flatMap((block, index) => {
    const normalized = {
      ...block,
      page: block.page ?? inheritedPage,
      parentId,
      canMoveUp: index > 0,
      canMoveDown: index < blocks.length - 1,
    };
    return [
      normalized,
      ...flattenBlocks(block.blocks ?? [], block.id, normalized.page),
      ...(block.items ?? []).flatMap((item) =>
        flattenBlocks(item, block.id, normalized.page),
      ),
    ];
  });
}
