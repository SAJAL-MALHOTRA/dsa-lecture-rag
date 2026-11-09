import React from "react";
import { Terminal, Database, BookOpen, Sparkles, ExternalLink } from "lucide-react";

interface NavbarProps {
  activeTab: "search" | "roadmap";
  onSelectTab: (tab: "search" | "roadmap") => void;
  onOpenAiChat: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onSelectTab,
  onOpenAiChat,
}) => {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-[#E5E7EB] bg-[#FFFFFF]/90 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        {/* Brand */}
        <div
          onClick={() => onSelectTab("search")}
          className="flex items-center gap-3 cursor-pointer"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-[#356AE6] text-white shadow-sm font-mono font-bold text-sm">
            LR
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm tracking-tight text-[#20242B]">
                Lecture Retriever
              </span>
              <span className="hidden sm:inline-block rounded border border-[#E5E7EB] bg-[#F5F6F7] px-1.5 py-0.5 text-[10px] font-mono font-medium text-[#68717D]">
                Striver DSA
              </span>
            </div>
          </div>
        </div>

        {/* Center / Navigation Links */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onSelectTab("search")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              activeTab === "search"
                ? "bg-[#F5F6F7] text-[#20242B] border border-[#E5E7EB] shadow-xs"
                : "text-[#68717D] hover:bg-[#F5F6F7] hover:text-[#20242B]"
            }`}
          >
            <Terminal className="h-3.5 w-3.5 text-[#356AE6]" />
            Search &amp; Moments
          </button>
          <button
            type="button"
            onClick={() => onSelectTab("roadmap")}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              activeTab === "roadmap"
                ? "bg-[#F5F6F7] text-[#20242B] border border-[#E5E7EB] shadow-xs"
                : "text-[#68717D] hover:bg-[#F5F6F7] hover:text-[#20242B]"
            }`}
          >
            <BookOpen className="h-3.5 w-3.5" />
            A2Z Roadmap
          </button>
          <button
            type="button"
            onClick={onOpenAiChat}
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium text-[#68717D] hover:bg-[#F5F6F7] hover:text-[#20242B] transition-colors"
          >
            <Sparkles className="h-3.5 w-3.5 text-amber-500" />
            Ask Striver AI
          </button>
        </div>

        {/* Right Status */}
        <div className="flex items-center gap-3">
          <div className="hidden lg:flex items-center gap-1.5 text-xs text-[#68717D]">
            <Database className="h-3.5 w-3.5 text-[#16845B]" />
            <span className="font-mono text-[11px]">6,881 moments</span>
          </div>
          <a
            href="https://github.com/SAJAL-MALHOTRA/dsa-lecture-rag"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:inline-flex items-center gap-1 rounded-md border border-[#E5E7EB] bg-white px-2.5 py-1 text-xs font-medium text-[#20242B] hover:bg-[#F5F6F7] shadow-xs"
          >
            <span>GitHub</span>
            <ExternalLink className="h-3 w-3 text-[#9299A3]" />
          </a>
        </div>
      </div>
    </header>
  );
};
