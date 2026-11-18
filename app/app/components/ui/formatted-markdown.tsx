import { parseMarkdownBlocks, type InlineSpan } from "~/lib/markdown-helpers";

function renderSpans(spans: InlineSpan[]) {
  return spans.map((sp, i) => {
    if (sp.bold) {
      return (
        <strong key={i} className="font-semibold text-slate-900">
          {sp.text}
        </strong>
      );
    }
    if (sp.italic) {
      return (
        <em key={i} className="italic text-slate-600">
          {sp.text}
        </em>
      );
    }
    return <span key={i}>{sp.text}</span>;
  });
}

export function FormattedMarkdown({ content }: { content: string }) {
  const blocks = parseMarkdownBlocks(content);
  return (
    <div className="space-y-2 text-[13.5px] leading-relaxed">
      {blocks.map((block, idx) => {
        if (block.type === "heading") {
          return (
            <h4
              key={idx}
              className="pt-1 text-sm font-bold text-slate-900"
            >
              {renderSpans(block.spans)}
            </h4>
          );
        }
        if (block.type === "bullet") {
          return (
            <div key={idx} className="flex items-start gap-2 pl-1">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-600" />
              <div className="flex-1">{renderSpans(block.spans)}</div>
            </div>
          );
        }
        if (block.type === "ordered") {
          return (
            <div key={idx} className="flex items-start gap-2 pl-1">
              <span className="font-semibold text-blue-700 shrink-0">
                {block.orderLabel}
              </span>
              <div className="flex-1">{renderSpans(block.spans)}</div>
            </div>
          );
        }
        return <p key={idx}>{renderSpans(block.spans)}</p>;
      })}
    </div>
  );
}
