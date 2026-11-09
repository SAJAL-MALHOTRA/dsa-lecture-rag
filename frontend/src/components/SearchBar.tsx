import React, { useState } from "react";
import { Search, X, Loader2 } from "lucide-react";

interface SearchBarProps {
  onSearch: (query: string) => void;
  isLoading: boolean;
  initialQuery?: string;
}

const CURATED_QUERIES = [
  { label: "Two Sum", query: "two sum", topic: "Arrays" },
  { label: "Kadane's Algorithm", query: "kadane algorithm maximum subarray", topic: "Arrays" },
  { label: "Trapping Rain Water", query: "trapping rain water two pointer", topic: "Two Pointers" },
  { label: "Rotting Oranges", query: "rotting oranges bfs", topic: "Graphs" },
  { label: "LRU Cache", query: "lru cache doubly linked list", topic: "Linked List" },
  { label: "Out-of-Domain", query: "react hooks state tutorial", topic: "Gating" },
];

export const SearchBar: React.FC<SearchBarProps> = ({
  onSearch,
  isLoading,
  initialQuery = "",
}) => {
  const [query, setQuery] = useState(initialQuery);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
    }
  };

  const handleChipClick = (q: string) => {
    setQuery(q);
    onSearch(q);
  };

  const handleClear = () => {
    setQuery("");
  };

  return (
    <div className="w-full space-y-2.5">
      <form onSubmit={handleSubmit} className="relative flex items-center">
        <div className="pointer-events-none absolute left-3.5 flex items-center text-[#9299A3]">
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin text-[#356AE6]" />
          ) : (
            <Search className="h-4 w-4" />
          )}
        </div>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask any algorithm doubt, concept, or problem (e.g. Kadane, Two-Pointer, Cycle Detection)..."
          className="h-11 w-full rounded-lg border border-[#E5E7EB] bg-white pl-10 pr-20 text-sm text-[#20242B] placeholder-[#9299A3] shadow-xs outline-none transition-all focus:border-[#356AE6] focus:ring-2 focus:ring-[#EDF3FF]"
        />
        <div className="absolute right-2.5 flex items-center gap-1.5">
          {query && (
            <button
              type="button"
              onClick={handleClear}
              className="rounded p-1 text-[#9299A3] hover:bg-[#F5F6F7] hover:text-[#20242B]"
              title="Clear query"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="flex h-7 items-center rounded bg-[#356AE6] px-2.5 text-xs font-medium text-white transition-opacity hover:opacity-95 disabled:opacity-50"
          >
            Search
          </button>
        </div>
      </form>

      {/* Curated quick-query chips */}
      <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
        <span className="text-[11px] font-mono text-[#9299A3] mr-1">Curated:</span>
        {CURATED_QUERIES.map((c) => (
          <button
            key={c.query}
            type="button"
            onClick={() => handleChipClick(c.query)}
            className="group inline-flex items-center gap-1 rounded border border-[#E5E7EB] bg-[#FFFFFF] px-2 py-1 text-xs text-[#68717D] hover:border-[#356AE6] hover:bg-[#EDF3FF] hover:text-[#356AE6] transition-all"
          >
            <span className="font-medium">{c.label}</span>
            <span className="text-[10px] text-[#9299A3] group-hover:text-[#356AE6]">
              • {c.topic}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
};
