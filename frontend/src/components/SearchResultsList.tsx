import React from "react";
import { Play, Code, ExternalLink, Clock } from "lucide-react";
import { SearchResultItem } from "../types/api";

interface SearchResultsListProps {
  results: SearchResultItem[];
  activeVideoId: string;
  activeSeekSec: number;
  isLoading?: boolean;
  onSelectMoment: (item: SearchResultItem) => void;
  onOpenCodeDrawer: (item: SearchResultItem) => void;
}

export const SearchResultsList: React.FC<SearchResultsListProps> = ({
  results,
  activeVideoId,
  activeSeekSec,
  isLoading = false,
  onSelectMoment,
  onOpenCodeDrawer,
}) => {
  if (isLoading) {
    return (
      <div className="space-y-3">
        <div className="h-4 w-44 rounded bg-gray-200 animate-pulse" />
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="flex flex-col sm:flex-row gap-3 rounded-lg border border-[#E5E7EB] bg-white p-3 animate-pulse"
          >
            <div className="aspect-video w-full sm:w-36 rounded bg-gray-200 shrink-0" />
            <div className="flex flex-1 flex-col justify-between space-y-2 py-1">
              <div className="h-4 w-3/4 rounded bg-gray-200" />
              <div className="h-3 w-full rounded bg-gray-100" />
              <div className="h-3 w-1/2 rounded bg-gray-100" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!results || results.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-[#E5E7EB] bg-white p-8 text-center text-xs text-[#9299A3]">
        No lecture moments found. Try searching for a specific algorithm like "Two Sum", "Kadane", or "Binary Search".
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-1">
        <span className="text-xs font-mono font-medium uppercase text-[#68717D]">
          Retrieved Lecture Moments ({results.length})
        </span>
        <span className="text-[11px] text-[#9299A3]">Click card to jump video</span>
      </div>

      <div className="space-y-2.5">
        {results.map((item, index) => {
          const isActive =
            item.video_id === activeVideoId &&
            Math.abs(item.seek_sec - activeSeekSec) < 30;

          const lcUrl =
            item.dsa_snippet?.leetcode_url ||
            (item.dsa_snippet?.leetcode_slug
              ? `https://leetcode.com/problems/${item.dsa_snippet.leetcode_slug}/`
              : null);

          return (
            <div
              key={`${item.video_id}-${item.seek_sec}-${index}`}
              onClick={() => onSelectMoment(item)}
              className={`group flex flex-col sm:flex-row gap-3 rounded-lg border p-3 transition-all cursor-pointer ${
                isActive
                  ? "border-[#356AE6] bg-[#F5F8FF] shadow-xs"
                  : "border-[#E5E7EB] bg-white hover:border-[#D1D5DB] hover:bg-[#FAFAF9]"
              }`}
            >
              {/* Thumbnail */}
              <div className="relative aspect-video w-full sm:w-36 shrink-0 overflow-hidden rounded-md bg-gray-100 border border-[#E5E7EB]">
                <img
                  src={`https://img.youtube.com/vi/${item.video_id}/mqdefault.jpg`}
                  alt={item.video_title}
                  className="h-full w-full object-cover transition-transform group-hover:scale-105"
                  loading="lazy"
                />
                <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-white/90 text-[#356AE6] shadow-sm">
                    <Play className="h-3.5 w-3.5 fill-current ml-0.5" />
                  </div>
                </div>
                <div className="absolute bottom-1 right-1 rounded bg-black/80 px-1 py-0.5 text-[9px] font-mono font-medium text-white flex items-center gap-0.5">
                  <Clock className="h-2 w-2" />
                  {item.timestamp_display}
                </div>
              </div>

              {/* Main Content */}
              <div className="flex flex-1 flex-col justify-between min-w-0">
                <div className="space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="text-xs font-semibold text-[#20242B] line-clamp-1 group-hover:text-[#356AE6] transition-colors">
                      {item.video_title}
                    </h4>
                    <span className="shrink-0 rounded border border-[#E5E7EB] bg-[#F6F7F9] px-1 py-0.2 text-[9px] font-mono text-[#68717D]">
                      Score: {item.score ? item.score.toFixed(3) : "—"}
                    </span>
                  </div>
                  <p className="text-[11px] text-[#68717D] line-clamp-2 leading-relaxed">
                    {item.snippet}
                  </p>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1.5 pt-2 mt-auto">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectMoment(item);
                    }}
                    className="inline-flex items-center gap-1 rounded bg-[#EDF3FF] px-2 py-1 text-[10px] font-mono font-medium text-[#356AE6] hover:bg-[#356AE6] hover:text-white transition-colors"
                  >
                    <Play className="h-2.5 w-2.5 fill-current" />
                    Seek {item.timestamp_display}
                  </button>

                  {lcUrl && (
                    <a
                      href={lcUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="inline-flex items-center gap-1 rounded border border-[#FDBA74] bg-[#FFF7ED] px-2 py-1 text-[10px] font-mono font-medium text-[#C2410C] hover:bg-[#FFEDD5] transition-colors"
                      title="Directly solve on LeetCode"
                    >
                      <span>🟠</span> LC
                      <ExternalLink className="h-2.5 w-2.5" />
                    </a>
                  )}

                  {item.dsa_snippet && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenCodeDrawer(item);
                      }}
                      className="inline-flex items-center gap-1 rounded border border-[#E5E7EB] bg-white px-2 py-1 text-[10px] font-mono font-medium text-[#68717D] hover:border-[#356AE6] hover:text-[#356AE6] transition-colors"
                    >
                      <Code className="h-2.5 w-2.5" />
                      Code
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
