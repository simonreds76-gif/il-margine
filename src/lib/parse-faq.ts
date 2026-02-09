/**
 * Parses FAQ markdown (docs/faq-content.md) into sections and Q&A items.
 * Format: ## SECTION N: TITLE, ### Q: Question, **A:** Answer
 */

export interface FaqItem {
  q: string;
  a: string;
}

export interface FaqSection {
  id: string;
  title: string;
  items: FaqItem[];
}

/** Section and question IDs: lowercase, hyphenated (dashes). */
function slugify(title: string): string {
  return title
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/** Slug for FAQ question anchors. Use same in homepage links. */
export function questionSlug(q: string): string {
  return slugify(q);
}

export function parseFaqMd(md: string): FaqSection[] {
  const sections: FaqSection[] = [];
  const sectionBlocks = md.split(/\n## SECTION \d+:\s*/).filter(Boolean);

  for (let i = 0; i < sectionBlocks.length; i++) {
    const block = sectionBlocks[i];
    const firstNewline = block.indexOf("\n");
    const titleLine = firstNewline === -1 ? block : block.slice(0, firstNewline);
    const title = titleLine.trim();
    if (!title) continue;

    const body = firstNewline === -1 ? "" : block.slice(firstNewline + 1);
    const qaBlocks = body.split(/\n### Q:\s*/).filter(Boolean);
    const items: FaqItem[] = [];

    for (let j = 0; j < qaBlocks.length; j++) {
      const qa = qaBlocks[j];
      const aMarker = "**A:**";
      const aIndex = qa.indexOf(aMarker);
      if (aIndex === -1) continue;
      const q = qa
        .slice(0, aIndex)
        .replace(/\n/g, " ")
        .replace(/\s+/g, " ")
        .trim();
      const a = qa.slice(aIndex + aMarker.length).trim();
      if (q && a) items.push({ q, a });
    }

    if (items.length > 0) {
      sections.push({
        id: slugify(title),
        title,
        items,
      });
    }
  }

  return sections;
}
