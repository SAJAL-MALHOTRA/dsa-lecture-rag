import React from "react";
import { ExternalLink, Code } from "lucide-react";
import { DSASnippet } from "../types/api";

interface AlgorithmBannerProps {
  snippet: DSASnippet | null;
  onOpenDrawer: () => void;
}

export const AlgorithmBanner: React.FC<AlgorithmBannerProps> = ({
  snippet,
  onOpenDrawer,
}) => {
  if (!snippet) return null;

  const diff = snippet.leetcode_difficulty || "Medium";
  const diffClass =
    diff.toLowerCase() === "easy"
      ? "bg-[#E6F4EA] text-[#16845B] border-[#A7F3D0]"
      : diff.toLowerCase() === "hard"
      ? "bg-[#FDE8E8] text-[#C43D48] border-[#FECACA]"
      : "bg-[#FEF3C7] text-[#B7791F] border-[#FDE68A]";

  const lcUrl =
    snippet.leetcode_url ||
    `https://leetcode.com/problems/${snippet.leetcode_slug || "two-sum"}/`;

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 rounded-lg border border-[#E5E7EB] border-l-4 border-l-[#356AE6] bg-white p-3.5 shadow-xs transition-colors">
      <div className="flex flex-col gap-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold text-sm text-[#20242B] tracking-tight">
            {snippet.title}
          </span>
          <span
            className={`rounded px-1.5 py-0.5 text-[10px] font-mono font-semibold uppercase border ${diffClass}`}
          >
            {diff}
          </span>
          <span className="rounded border border-[#E5E7EB] bg-[#F6F7F9] px-1.5 py-0.5 text-[10px] font-mono text-[#68717D]">
            {snippet.topic.replace(/^\d+\./, "")}
          </span>
          {snippet.time_complexity && (
            <span className="rounded border border-[#FDE68A] bg-[#FEF3C7] px-1.5 py-0.5 text-[10px] font-mono font-semibold text-[#B7791F]">
              Time: {snippet.time_complexity}
            </span>
          )}
          {snippet.space_complexity && (
            <span className="rounded border border-[#E5E7EB] bg-[#F6F7F9] px-1.5 py-0.5 text-[10px] font-mono text-[#68717D]">
              Space: {snippet.space_complexity}
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
        <a
          href={lcUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 rounded-md border border-[#FDBA74] bg-[#FFF7ED] px-2.5 py-1.5 text-xs font-mono font-semibold text-[#C2410C] hover:bg-[#FFEDD5] hover:border-[#EA580C] transition-all shadow-xs"
          title="Directly solve on LeetCode"
        >
          <span>🟠</span> Solve on LeetCode
          <ExternalLink className="h-3 w-3" />
        </a>

        <button
          onClick={onOpenDrawer}
          className="inline-flex items-center gap-1.5 rounded-md border border-[#E5E7EB] bg-[#F6F7F9] px-2.5 py-1.5 text-xs font-mono font-medium text-[#20242B] hover:border-[#356AE6] hover:bg-[#EDF3FF] hover:text-[#356AE6] transition-all"
        >
          <Code className="h-3.5 w-3.5" />
          Code &amp; Approach
        </button>
      </div>
    </div>
  );
};
