import type { ReactNode } from "react";

/** Renders inline **bold** and `code` within a single line of text. */
function inline(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const token = match[0];
    if (token.startsWith("**")) {
      parts.push(<strong key={key++}>{token.slice(2, -2)}</strong>);
    } else {
      parts.push(
        <code key={key++} className="bg-slate-100 text-slate-700 rounded px-1 py-0.5 text-sm">
          {token.slice(1, -1)}
        </code>
      );
    }
    last = match.index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

/** Minimal markdown: paragraphs, and "- " bullet groups. */
function Markdown({ content }: { content: string }) {
  const lines = content.split("\n");
  const blocks: ReactNode[] = [];
  let bullets: string[] = [];

  const flushBullets = (key: number) => {
    if (!bullets.length) return;
    blocks.push(
      <ul key={`ul-${key}`} className="list-disc pl-5 space-y-0.5 my-1">
        {bullets.map((b, i) => (
          <li key={i}>{inline(b)}</li>
        ))}
      </ul>
    );
    bullets = [];
  };

  lines.forEach((line, i) => {
    if (line.startsWith("- ")) {
      bullets.push(line.slice(2));
    } else {
      flushBullets(i);
      if (line.trim() !== "") blocks.push(<p key={i}>{inline(line)}</p>);
    }
  });
  flushBullets(lines.length);
  return <div className="space-y-2 leading-relaxed">{blocks}</div>;
}

export default function Message({ role, content }: { role: "assistant" | "user"; content: string }) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
          isUser ? "bg-blue-600 text-white" : "bg-white border border-slate-200 text-slate-800"
        }`}
      >
        <Markdown content={content} />
      </div>
    </div>
  );
}
