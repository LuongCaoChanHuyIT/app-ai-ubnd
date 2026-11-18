export interface InlineSpan {
  text: string;
  bold?: boolean;
  italic?: boolean;
}

export interface MarkdownBlock {
  type: "heading" | "bullet" | "ordered" | "paragraph";
  orderLabel?: string;
  spans: InlineSpan[];
}

export function formatAssistantModeBadge(mode: string): string {
  switch (mode) {
    case "soan_thao":
      return "SOẠN THẢO";
    case "nghiep_vu":
      return "NGHIỆP VỤ";
    case "tham_dinh":
      return "THẨM ĐỊNH";
    default:
      return mode.toUpperCase();
  }
}

export function parseInlineSpans(line: string): InlineSpan[] {
  const spans: InlineSpan[] = [];
  const tokenRegex = /(\*\*[^*]+\*\*|\*[^*\n]+\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = tokenRegex.exec(line)) !== null) {
    if (match.index > lastIndex) {
      spans.push({ text: line.slice(lastIndex, match.index) });
    }
    const token = match[0];
    if (token.startsWith("**") && token.endsWith("**")) {
      spans.push({ text: token.slice(2, -2), bold: true });
    } else if (token.startsWith("*") && token.endsWith("*")) {
      spans.push({ text: token.slice(1, -1), italic: true });
    }
    lastIndex = match.index + token.length;
  }

  if (lastIndex < line.length) {
    spans.push({ text: line.slice(lastIndex) });
  }

  return spans.length > 0 ? spans : [{ text: line }];
}

export function parseMarkdownBlocks(markdown: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = [];
  const rawLines = (markdown ?? "").split(/\r?\n/);

  for (const raw of rawLines) {
    const trimmed = raw.trim();
    if (!trimmed) continue;

    if (/^#{1,4}\s+/.test(trimmed)) {
      const content = trimmed.replace(/^#{1,4}\s+/, "");
      blocks.push({ type: "heading", spans: parseInlineSpans(content) });
      continue;
    }

    if (/^[-•]\s+/.test(trimmed)) {
      const content = trimmed.replace(/^[-•]\s+/, "");
      blocks.push({ type: "bullet", spans: parseInlineSpans(content) });
      continue;
    }

    const orderedMatch = /^(\d+\.)\s+(.*)$/.exec(trimmed);
    if (orderedMatch) {
      blocks.push({
        type: "ordered",
        orderLabel: orderedMatch[1],
        spans: parseInlineSpans(orderedMatch[2]),
      });
      continue;
    }

    blocks.push({ type: "paragraph", spans: parseInlineSpans(trimmed) });
  }

  return blocks;
}
