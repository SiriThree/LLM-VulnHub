"use client";

import type { MouseEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type SafeMarkdownProps = {
  content: string;
  referenceCount?: number;
  onCitationClick?: (referenceNumber: number) => void;
};

function addCitationLinks(content: string, referenceCount: number): string {
  return content.replace(/\[(\d+)\](?!\()/g, (match, rawNumber: string) => {
    const referenceNumber = Number(rawNumber);
    if (referenceNumber < 1 || referenceNumber > referenceCount) return match;
    return `[${referenceNumber}](#rag-reference-${referenceNumber})`;
  });
}

function safeUrlTransform(url: string): string {
  if (url.startsWith("#rag-reference-")) return url;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.toString() : "";
  } catch {
    return "";
  }
}

export function SafeMarkdown({ content, referenceCount = 0, onCitationClick }: SafeMarkdownProps) {
  const markdown = addCitationLinks(content, referenceCount);

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      skipHtml
      urlTransform={safeUrlTransform}
      components={{
        h1: ({ children }) => <h1 className="mb-3 mt-6 text-xl font-semibold text-slate-900 first:mt-0">{children}</h1>,
        h2: ({ children }) => <h2 className="mb-3 mt-6 text-lg font-semibold text-slate-900 first:mt-0">{children}</h2>,
        h3: ({ children }) => <h3 className="mb-2 mt-5 text-base font-semibold text-slate-900 first:mt-0">{children}</h3>,
        p: ({ children }) => <p className="my-3 leading-7 first:mt-0 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="my-3 list-disc space-y-1.5 pl-6">{children}</ul>,
        ol: ({ children }) => <ol className="my-3 list-decimal space-y-1.5 pl-6">{children}</ol>,
        li: ({ children }) => <li className="pl-1 leading-7">{children}</li>,
        blockquote: ({ children }) => (
          <blockquote className="my-4 border-l-4 border-slate-300 bg-slate-50 px-4 py-2 text-slate-600">
            {children}
          </blockquote>
        ),
        pre: ({ children }) => (
          <pre className="my-4 overflow-x-auto rounded-lg bg-slate-950 p-4 text-sm leading-6 text-slate-100">
            {children}
          </pre>
        ),
        code: ({ className, children }) =>
          className ? (
            <code className={className}>{children}</code>
          ) : (
            <code className="rounded bg-slate-100 px-1.5 py-0.5 text-[0.9em] text-slate-800">{children}</code>
          ),
        table: ({ children }) => (
          <div className="my-4 overflow-x-auto">
            <table className="w-full border-collapse text-sm">{children}</table>
          </div>
        ),
        th: ({ children }) => <th className="border border-slate-200 bg-slate-50 px-3 py-2 text-left font-semibold">{children}</th>,
        td: ({ children }) => <td className="border border-slate-200 px-3 py-2 align-top">{children}</td>,
        hr: () => <hr className="my-6 border-slate-200" />,
        img: ({ alt }) => <span className="text-sm text-slate-500">{alt || "图片已隐藏"}</span>,
        a: ({ href, children }) => {
          const citationMatch = href?.match(/^#rag-reference-(\d+)$/);
          if (citationMatch) {
            const referenceNumber = Number(citationMatch[1]);
            return (
              <button
                type="button"
                className="mx-0.5 inline-flex rounded bg-primary/10 px-1.5 py-0.5 text-xs font-semibold text-primary hover:bg-primary/20"
                onClick={(event: MouseEvent<HTMLButtonElement>) => {
                  event.preventDefault();
                  onCitationClick?.(referenceNumber);
                }}
              >
                [{children}]
              </button>
            );
          }
          return (
            <a
              className="text-primary underline decoration-primary/30 underline-offset-2 hover:decoration-primary"
              href={href}
              rel="noopener noreferrer"
              target="_blank"
            >
              {children}
            </a>
          );
        },
      }}
    >
      {markdown}
    </ReactMarkdown>
  );
}
