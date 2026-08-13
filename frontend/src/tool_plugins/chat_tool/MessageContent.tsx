import { Fragment, useState, type ReactNode } from "react";

/**
 * Renders assistant/user message text as lightweight markdown.
 *
 * Why hand-rolled instead of a markdown dependency: the model only emits a
 * small subset (fenced code blocks, inline code, bold/italic, links, simple
 * lists), and a full parser pulls in a dependency for syntax we never use.
 * Everything renders as React nodes — never ``dangerouslySetInnerHTML`` — so
 * model text (which is echoed from user input and is therefore untrusted) is
 * always escaped. Links are protocol-whitelisted before becoming anchors.
 *
 * The streamed form of a reply (unclosed fences mid-stream) degrades to plain
 * text and "upgrades" when the final ``result`` frame lands — a cheap, safe
 * trade compared to reformatting every chunk.
 */

interface Props {
  content: string;
  /** Streaming replies render as plain text until the final result frame. */
  plain?: boolean;
}

type Block =
  | { type: "code"; lang: string; code: string }
  | { type: "text"; text: string };

const FENCE_RE = /```(\w*)[ \t]*\n?([\s\S]*?)```/g;

function splitBlocks(content: string): Block[] {
  const blocks: Block[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  FENCE_RE.lastIndex = 0;
  while ((m = FENCE_RE.exec(content)) !== null) {
    if (m.index > last) {
      blocks.push({ type: "text", text: content.slice(last, m.index) });
    }
    blocks.push({ type: "code", lang: m[1] || "", code: m[2] });
    last = m.index + m[0].length;
  }
  if (last < content.length) {
    blocks.push({ type: "text", text: content.slice(last) });
  }
  if (blocks.length === 0) {
    blocks.push({ type: "text", text: content });
  }
  return blocks;
}

/* ── Inline formatting ── */

const INLINE_RE = /(`[^`\n]+`)|(\*\*[^*\n]+\*\*)|(\*[^*\n]+\*)|(\[[^\]\n]+\]\([^)\s]+\))/g;

function safeLink(label: string, url: string, key: number): ReactNode {
  try {
    const u = new URL(url, window.location.href);
    if (u.protocol === "http:" || u.protocol === "https:" || u.protocol === "mailto:") {
      return (
        <a key={key} href={u.href} target="_blank" rel="noreferrer">
          {label}
        </a>
      );
    }
  } catch {
    /* malformed URL — fall through to plain text */
  }
  return <Fragment key={key}>{label}</Fragment>;
}

function renderInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  INLINE_RE.lastIndex = 0;
  while ((m = INLINE_RE.exec(text)) !== null) {
    if (m.index > last) {
      nodes.push(text.slice(last, m.index));
    }
    if (m[1]) {
      nodes.push(<code key={key++}>{m[1].slice(1, -1)}</code>);
    } else if (m[2]) {
      nodes.push(<strong key={key++}>{m[2].slice(2, -2)}</strong>);
    } else if (m[3]) {
      nodes.push(<em key={key++}>{m[3].slice(1, -1)}</em>);
    } else if (m[4]) {
      const inner = m[4].match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (inner) nodes.push(safeLink(inner[1], inner[2].trim(), key++));
      else nodes.push(m[4]);
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) {
    nodes.push(text.slice(last));
  }
  return nodes;
}

/* ── Block layout: paragraphs + simple lists ── */

const BULLET_RE = /^[-*+]\s+(.*)$/;
const ORDERED_RE = /^\d+[.)]\s+(.*)$/;

function TextBlock({ text }: { text: string }) {
  const lines = text.split(/\r?\n/);
  const out: ReactNode[] = [];
  let para: string[] = [];
  let list: { ordered: boolean; items: ReactNode[] } | null = null;
  let key = 0;

  const flushPara = () => {
    if (para.length > 0) {
      out.push(
        <p className="msg-text" key={`p${key++}`}>
          {renderInline(para.join("\n"))}
        </p>
      );
      para = [];
    }
  };
  const flushList = () => {
    if (list) {
      const items = list.items.map((it, i) => <li key={i}>{it}</li>);
      out.push(
        list.ordered ? (
          <ol key={`l${key++}`}>{items}</ol>
        ) : (
          <ul key={`l${key++}`}>{items}</ul>
        )
      );
      list = null;
    }
  };

  for (const line of lines) {
    const bullet = line.match(BULLET_RE);
    const ordered = line.match(ORDERED_RE);
    if (bullet || ordered) {
      flushPara();
      if (!list || list.ordered !== Boolean(ordered)) {
        flushList();
        list = { ordered: Boolean(ordered), items: [] };
      }
      list.items.push(renderInline((bullet ? bullet[1] : ordered![1])));
    } else if (line.trim() === "") {
      flushPara();
      flushList();
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();
  return <>{out}</>;
}

/* ── Fenced code block with a copy button ── */

function CodeBlock({ lang, code }: { lang: string; code: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = code;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="msg-code">
      <div className="msg-code-head">
        <span className="msg-code-lang">{lang || "code"}</span>
        <button type="button" className="msg-code-copy" onClick={copy}>
          {copied ? "✓ 已复制" : "复制"}
        </button>
      </div>
      <pre>
        <code>{code}</code>
      </pre>
    </div>
  );
}

export default function MessageContent({ content, plain = false }: Props) {
  if (plain) {
    return (
      <div className="msg-content">
        <p className="msg-text">{content}</p>
      </div>
    );
  }
  const blocks = splitBlocks(content);
  return (
    <div className="msg-content">
      {blocks.map((b, i) =>
        b.type === "code" ? (
          <CodeBlock key={i} lang={b.lang} code={b.code} />
        ) : (
          <TextBlock key={i} text={b.text} />
        )
      )}
    </div>
  );
}
