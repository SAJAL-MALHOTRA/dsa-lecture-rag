"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Navbar } from "../components/Navbar";
import { SearchBar } from "../components/SearchBar";
import { AlgorithmBanner } from "../components/AlgorithmBanner";
import { GroundedAnswerCard } from "../components/GroundedAnswerCard";
import { SearchResultsList } from "../components/SearchResultsList";
import { VideoPlayerPanel } from "../components/VideoPlayerPanel";
import { CodeDrawer } from "../components/CodeDrawer";
import { RoadmapView } from "../components/RoadmapView";
import { AiChatDrawer } from "../components/AiChatDrawer";
import { fetchSearch, fetchAnswer } from "../lib/api";
import {
  SearchResultItem,
  DSASnippet,
  AnswerResponse,
  EnrichmentMetadata,
} from "../types/api";
import { AlertCircle, RefreshCw } from "lucide-react";

export default function Home() {
  const [activeTab, setActiveTab] = useState<"search" | "roadmap">("search");
  const [query, setQuery] = useState("two sum");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [activeDsa, setActiveDsa] = useState<DSASnippet | null>(null);
  const [groundedAnswer, setGroundedAnswer] = useState<AnswerResponse | null>(null);
  const [enrichment, setEnrichment] = useState<EnrichmentMetadata | null>(null);

  // Video Player state
  const [activeVideoId, setActiveVideoId] = useState("UXDSeD9mN-k");
  const [activeSeekSec, setActiveSeekSec] = useState(300);
  const [activeLectureTitle, setActiveLectureTitle] = useState(
    "Two Sum | Optimal Hash Map Intuition & Lookup"
  );

  // Drawer state
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerSnippet, setDrawerSnippet] = useState<DSASnippet | null>(null);
  const [isAiChatOpen, setIsAiChatOpen] = useState(false);

  const executeSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) return;
    setIsLoading(true);
    setError(null);
    setQuery(searchQuery);

    try {
      // 1. Fetch fast retrieval results & DSA snippet
      const searchData = await fetchSearch(searchQuery);
      setResults(searchData.results || []);
      setActiveDsa(searchData.dsa_snippet || null);
      setEnrichment(searchData.enrichment || null);

      // Auto-focus the top retrieved moment in the video player
      if (searchData.results && searchData.results.length > 0) {
        const topResult = searchData.results[0];
        setActiveVideoId(topResult.video_id);
        setActiveSeekSec(topResult.seek_sec);
        setActiveLectureTitle(topResult.video_title);
      }
    } catch (err: any) {
      console.error("Search pipeline error:", err);
      setError(
        err?.message ||
          "Failed to retrieve lecture moments. The backend might be waking up—please try again."
      );
    } finally {
      setIsLoading(false);
    }

    // 2. Fetch grounded answer synthesis in background
    try {
      const answerData = await fetchAnswer(searchQuery);
      setGroundedAnswer(answerData);
    } catch (err) {
      console.warn("Answer synthesis error:", err);
    }
  }, []);

  // Initial load with default Striver problem
  useEffect(() => {
    executeSearch("two sum");
  }, [executeSearch]);

  const handleSeek = (videoId: string, sec: number, title?: string) => {
    setActiveVideoId(videoId);
    setActiveSeekSec(sec);
    if (title) setActiveLectureTitle(title);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleOpenDrawerWithSnippet = (snippet: DSASnippet | null) => {
    setDrawerSnippet(snippet || activeDsa);
    setIsDrawerOpen(true);
  };

  const handleSelectFromRoadmap = (problemTitle: string) => {
    setActiveTab("search");
    setQuery(problemTitle);
    executeSearch(problemTitle);
  };

  return (
    <div className="min-h-screen bg-[#FAFAF9] text-[#20242B] flex flex-col">
      <Navbar
        activeTab={activeTab}
        onSelectTab={(tab) => setActiveTab(tab)}
        onOpenAiChat={() => setIsAiChatOpen(true)}
      />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 sm:px-6 py-6">
        {activeTab === "roadmap" ? (
          <RoadmapView onSelectProblem={handleSelectFromRoadmap} />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Left Column: Search, Algorithm Banner, Grounded Answer, Results List (7 cols) */}
            <div className="lg:col-span-7 space-y-5">
              {/* Search Input Bar */}
              <SearchBar
                initialQuery={query}
                onSearch={executeSearch}
                isLoading={isLoading}
              />

              {/* Error Banner if any */}
              {error && (
                <div className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 p-3.5 text-xs text-red-700">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 shrink-0 text-red-600" />
                    <span>{error}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => executeSearch(query)}
                    className="inline-flex items-center gap-1 rounded bg-red-100 hover:bg-red-200 px-2.5 py-1 font-mono font-medium text-red-800 transition-colors"
                  >
                    <RefreshCw className="h-3 w-3" />
                    Retry
                  </button>
                </div>
              )}

              {/* Matched DSA Algorithm Card */}
              {activeDsa && (
                <AlgorithmBanner
                  snippet={activeDsa}
                  onOpenDrawer={() => handleOpenDrawerWithSnippet(activeDsa)}
                />
              )}

              {/* Grounded Lecture Answer */}
              <GroundedAnswerCard
                answer={groundedAnswer}
                enrichment={enrichment}
                onSeek={handleSeek}
              />

              {/* Retrieved Moments Feed */}
              <SearchResultsList
                results={results}
                activeVideoId={activeVideoId}
                activeSeekSec={activeSeekSec}
                isLoading={isLoading}
                onSelectMoment={(m) => handleSeek(m.video_id, m.seek_sec, m.video_title)}
                onOpenCodeDrawer={(m) => handleOpenDrawerWithSnippet(m.dsa_snippet || activeDsa)}
              />
            </div>

            {/* Right Column: Sticky Video Player & Keyframe Gallery (5 cols) */}
            <div className="lg:col-span-5 lg:sticky lg:top-20 space-y-4">
              <VideoPlayerPanel
                videoId={activeVideoId}
                seekSec={activeSeekSec}
                lectureTitle={activeLectureTitle}
                activeDsa={activeDsa}
                onOpenDrawer={() => handleOpenDrawerWithSnippet(activeDsa)}
                onSeek={handleSeek}
              />
            </div>
          </div>
        )}
      </main>

      {/* Code & Multi-language Solution Drawer */}
      <CodeDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        snippet={drawerSnippet || activeDsa}
      />

      {/* Ask Striver AI Chat Drawer */}
      <AiChatDrawer
        isOpen={isAiChatOpen}
        onClose={() => setIsAiChatOpen(false)}
        onSeek={handleSeek}
        currentQuery={query}
      />
    </div>
  );
}
