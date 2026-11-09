import React, { useState } from "react";
import { X, Copy, Check, ExternalLink, Rocket } from "lucide-react";
import { DSASnippet } from "../types/api";

interface CodeDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  snippet: DSASnippet | null;
}

export const CodeDrawer: React.FC<CodeDrawerProps> = ({
  isOpen,
  onClose,
  snippet,
}) => {
  const [activeLang, setActiveLang] = useState<"cpp" | "python" | "java">("cpp");
  const [copied, setCopied] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  if (!isOpen || !snippet) return null;

  const getCode = () => {
    switch (activeLang) {
      case "python":
        return snippet.code_python || "# Python solution not available";
      case "java":
        return snippet.code_java || "// Java solution not available";
      default:
        return snippet.code_cpp || "// C++ solution not available";
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(getCode());
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  const handleSubmitLeetcode = () => {
    navigator.clipboard.writeText(getCode());
    setToastMessage("📋 Code copied! Opening LeetCode to submit...");
    setTimeout(() => setToastMessage(null), 2500);

    const lcUrl =
      snippet.leetcode_url ||
      `https://leetcode.com/problems/${snippet.leetcode_slug || "two-sum"}/`;
    window.open(lcUrl, "_blank", "noopener,noreferrer");
  };

  const lcUrl =
    snippet.leetcode_url ||
    `https://leetcode.com/problems/${snippet.leetcode_slug || "two-sum"}/`;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs transition-opacity animate-in fade-in duration-200">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-60 flex items-center gap-2 rounded-lg bg-[#20242B] px-4 py-2.5 text-xs font-medium text-white shadow-xl animate-in slide-in-from-bottom-2">
          {toastMessage}
        </div>
      )}

      {/* Drawer Container */}
      <div className="flex h-full w-full max-w-2xl flex-col bg-white shadow-2xl border-l border-[#E5E7EB] animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#E5E7EB] px-5 py-4">
          <div className="space-y-1 min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="font-semibold text-base text-[#20242B] truncate">
                {snippet.title}
              </h2>
              {snippet.leetcode_difficulty && (
                <span className="rounded bg-[#E6F4EA] border border-[#A7F3D0] px-1.5 py-0.5 text-[10px] font-mono font-semibold text-[#16845B]">
                  {snippet.leetcode_difficulty}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-[#68717D]">
              <span>{snippet.topic.replace(/^\d+\./, "")}</span>
              <span>•</span>
              <span>Time: {snippet.time_complexity}</span>
              <span>•</span>
              <span>Space: {snippet.space_complexity}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <a
              href={lcUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded border border-[#FDBA74] bg-[#FFF7ED] px-2.5 py-1 text-xs font-mono font-medium text-[#C2410C] hover:bg-[#FFEDD5]"
            >
              <span>🟠</span> LC
              <ExternalLink className="h-3 w-3" />
            </a>
            <button
              onClick={handleSubmitLeetcode}
              className="inline-flex items-center gap-1 rounded bg-[#16845B] px-2.5 py-1 text-xs font-mono font-medium text-white hover:bg-[#0E5C3E] transition-colors"
              title="Copy code and open LeetCode to submit"
            >
              <Rocket className="h-3 w-3" />
              Submit
            </button>
            <button
              onClick={onClose}
              className="rounded-md p-1.5 text-[#68717D] hover:bg-[#F5F6F7] hover:text-[#20242B]"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Code Section */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              {/* Language Selector */}
              <div className="flex items-center gap-1 rounded-md border border-[#E5E7EB] bg-[#F5F6F7] p-0.5 text-xs font-mono">
                <button
                  type="button"
                  onClick={() => setActiveLang("cpp")}
                  className={`rounded px-2.5 py-1 text-xs transition-colors ${
                    activeLang === "cpp"
                      ? "bg-white text-[#20242B] font-semibold shadow-xs"
                      : "text-[#68717D] hover:text-[#20242B]"
                  }`}
                >
                  C++ (Original)
                </button>
                <button
                  type="button"
                  onClick={() => setActiveLang("python")}
                  className={`rounded px-2.5 py-1 text-xs transition-colors ${
                    activeLang === "python"
                      ? "bg-white text-[#20242B] font-semibold shadow-xs"
                      : "text-[#68717D] hover:text-[#20242B]"
                  }`}
                >
                  Python 3 (Idiomatic)
                </button>
                <button
                  type="button"
                  onClick={() => setActiveLang("java")}
                  className={`rounded px-2.5 py-1 text-xs transition-colors ${
                    activeLang === "java"
                      ? "bg-white text-[#20242B] font-semibold shadow-xs"
                      : "text-[#68717D] hover:text-[#20242B]"
                  }`}
                >
                  Java (Solution)
                </button>
              </div>

              {/* Copy Code */}
              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex items-center gap-1 rounded border border-[#E5E7EB] bg-white px-2 py-1 text-xs font-mono text-[#68717D] hover:border-[#356AE6] hover:text-[#356AE6] transition-colors"
              >
                {copied ? (
                  <>
                    <Check className="h-3 w-3 text-[#16845B]" />
                    <span className="text-[#16845B]">Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>

            {/* Code Box */}
            <pre className="overflow-x-auto rounded-lg border border-[#E5E7EB] bg-[#F6F7F9] p-4 font-mono text-xs text-[#20242B] leading-relaxed select-text">
              <code>{getCode()}</code>
            </pre>
          </div>

          {/* Striver's Intuition & Approach */}
          {snippet.approach && (
            <div className="space-y-2">
              <h4 className="text-xs font-mono font-semibold uppercase text-[#68717D]">
                💡 Striver's Step-by-Step Approach
              </h4>
              <div className="rounded-lg border border-[#E5E7EB] bg-[#FAFAF9] p-3.5 text-xs text-[#20242B] leading-relaxed whitespace-pre-wrap">
                {snippet.approach}
              </div>
            </div>
          )}

          {/* Problem Statement & Examples */}
          {snippet.question && (
            <div className="space-y-2">
              <h4 className="text-xs font-mono font-semibold uppercase text-[#68717D]">
                📄 Problem Statement &amp; Examples
              </h4>
              <div className="rounded-lg border border-[#E5E7EB] bg-[#FAFAF9] p-3.5 text-xs text-[#20242B] leading-relaxed whitespace-pre-wrap">
                {snippet.question}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
