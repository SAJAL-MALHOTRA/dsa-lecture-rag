"use client";

import React, { useState, useEffect } from "react";
import { CheckCircle2, Circle, Search, ChevronDown, ChevronRight, Play, ExternalLink, Filter } from "lucide-react";
import { fetchRoadmap } from "../lib/api";
import { RoadmapResponse, RoadmapTopic, RoadmapProblem } from "../types/api";

interface RoadmapViewProps {
  onSelectProblem: (query: string) => void;
}

export const RoadmapView: React.FC<RoadmapViewProps> = ({ onSelectProblem }) => {
  const [data, setData] = useState<RoadmapResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterDifficulty, setFilterDifficulty] = useState<string>("All");
  const [searchFilter, setSearchFilter] = useState<string>("");
  const [expandedTopics, setExpandedTopics] = useState<Record<string, boolean>>({});
  const [completedIds, setCompletedIds] = useState<Set<string>>(new Set());

  // Load completed from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem("striver_dsa_completed");
      if (stored) {
        setCompletedIds(new Set(JSON.parse(stored)));
      }
    } catch {
      // ignore
    }
  }, []);

  // Fetch roadmap
  useEffect(() => {
    let active = true;
    fetchRoadmap()
      .then((res) => {
        if (!active) return;
        setData(res);
        // Expand first 2 topics by default
        const initial: Record<string, boolean> = {};
        res.topics.slice(0, 2).forEach((t) => {
          initial[t.raw_name] = true;
        });
        setExpandedTopics(initial);
      })
      .catch((err) => console.error("Failed to load roadmap:", err))
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const toggleComplete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const next = new Set(completedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setCompletedIds(next);
    try {
      localStorage.setItem("striver_dsa_completed", JSON.stringify(Array.from(next)));
    } catch {
      // ignore
    }
  };

  const toggleTopic = (rawName: string) => {
    setExpandedTopics((prev) => ({
      ...prev,
      [rawName]: !prev[rawName],
    }));
  };

  const totalProblems = data?.total_problems || 369;
  const completedCount = completedIds.size;
  const progressPct = Math.round((completedCount / totalProblems) * 100);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-[#E5E7EB] bg-white p-8">
        <div className="flex items-center gap-3 text-sm font-mono text-[#68717D]">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#356AE6] border-t-transparent" />
          Loading Striver's A2Z DSA Curriculum (369 Problems)...
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-xs text-red-600">
        Failed to load roadmap data. Please try again.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header & Stats Bar */}
      <div className="rounded-xl border border-[#E5E7EB] bg-white p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-lg font-bold tracking-tight text-[#20242B]">
              Striver's A2Z DSA Sheet Curriculum
            </h1>
            <p className="text-xs text-[#68717D] mt-0.5">
              Comprehensive 369-problem interview roadmap with interactive lecture moments &amp; multi-language code.
            </p>
          </div>

          {/* Progress */}
          <div className="flex items-center gap-3 bg-[#F5F6F7] border border-[#E5E7EB] px-3.5 py-2 rounded-lg">
            <div className="text-right">
              <div className="text-xs font-semibold text-[#20242B]">
                {completedCount} / {totalProblems} Solved
              </div>
              <div className="text-[10px] font-mono text-[#68717D]">{progressPct}% Complete</div>
            </div>
            <div className="h-8 w-8 rounded-full border-2 border-[#356AE6] flex items-center justify-center text-[10px] font-mono font-bold text-[#356AE6]">
              {progressPct}%
            </div>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="mt-4 pt-4 border-t border-[#E5E7EB] flex flex-col sm:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-[#9299A3]" />
            <input
              type="text"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Filter by problem name or topic..."
              className="h-8 w-full rounded-md border border-[#E5E7EB] bg-[#FAFAF9] pl-9 pr-3 text-xs text-[#20242B] placeholder-[#9299A3] outline-none focus:border-[#356AE6]"
            />
          </div>

          <div className="flex items-center gap-1.5 self-start sm:self-auto shrink-0">
            <span className="text-xs text-[#68717D] flex items-center gap-1 mr-1">
              <Filter className="h-3 w-3" />
              Diff:
            </span>
            {["All", "Easy", "Medium", "Hard"].map((d) => (
              <button
                key={d}
                onClick={() => setFilterDifficulty(d)}
                className={`rounded px-2.5 py-1 text-xs font-mono transition-colors ${
                  filterDifficulty === d
                    ? "bg-[#356AE6] text-white font-medium"
                    : "bg-[#F5F6F7] text-[#68717D] hover:bg-[#E5E7EB]"
                }`}
              >
                {d}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Topics Accordion */}
      <div className="space-y-3">
        {data.topics.map((topic) => {
          const isExpanded = !!expandedTopics[topic.raw_name];

          // Filter problems inside topic
          const matchingSubtopics = topic.subtopics
            .map((sub) => {
              const filteredProbs = sub.problems.filter((p) => {
                const matchDiff =
                  filterDifficulty === "All" ||
                  p.difficulty.toLowerCase() === filterDifficulty.toLowerCase();
                const matchSearch =
                  !searchFilter ||
                  p.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
                  topic.name.toLowerCase().includes(searchFilter.toLowerCase());
                return matchDiff && matchSearch;
              });
              return { ...sub, problems: filteredProbs };
            })
            .filter((sub) => sub.problems.length > 0);

          if (matchingSubtopics.length === 0 && (searchFilter || filterDifficulty !== "All")) {
            return null;
          }

          const topicProblems = topic.subtopics.flatMap((s) => s.problems);
          const topicCompleted = topicProblems.filter((p) => completedIds.has(p.id)).length;

          return (
            <div
              key={topic.raw_name}
              className="rounded-xl border border-[#E5E7EB] bg-white overflow-hidden shadow-xs transition-colors"
            >
              {/* Topic Header */}
              <button
                type="button"
                onClick={() => toggleTopic(topic.raw_name)}
                className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-[#FAFAF9] text-left transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="text-base">{topic.icon}</span>
                  <div>
                    <span className="text-sm font-semibold text-[#20242B]">
                      {topic.name}
                    </span>
                    <span className="ml-2 text-[11px] font-mono text-[#68717D]">
                      ({topicCompleted}/{topic.total_count} completed)
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono rounded bg-[#F5F6F7] border border-[#E5E7EB] px-2 py-0.5 text-[#68717D]">
                    {topic.subtopics.length} Sections
                  </span>
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4 text-[#68717D]" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-[#68717D]" />
                  )}
                </div>
              </button>

              {/* Subtopics & Problems */}
              {isExpanded && (
                <div className="border-t border-[#E5E7EB] divide-y divide-[#E5E7EB] bg-[#FAFAF9]/50">
                  {matchingSubtopics.map((sub, sIdx) => (
                    <div key={sIdx} className="p-3 sm:p-4 space-y-2">
                      <div className="text-[11px] font-mono font-semibold uppercase text-[#68717D]">
                        {sub.name} ({sub.problems.length})
                      </div>

                      <div className="grid grid-cols-1 gap-1.5">
                        {sub.problems.map((p) => {
                          const isDone = completedIds.has(p.id);
                          const diffClass =
                            p.difficulty.toLowerCase() === "easy"
                              ? "bg-[#E6F4EA] text-[#16845B] border-[#A7F3D0]"
                              : p.difficulty.toLowerCase() === "hard"
                              ? "bg-[#FDE8E8] text-[#C43D48] border-[#FECACA]"
                              : "bg-[#FEF3C7] text-[#B7791F] border-[#FDE68A]";

                          return (
                            <div
                              key={p.id}
                              onClick={() => onSelectProblem(p.title)}
                              className={`group flex items-center justify-between rounded-lg border px-3 py-2 text-xs transition-all cursor-pointer ${
                                isDone
                                  ? "border-[#E5E7EB] bg-white opacity-80"
                                  : "border-[#E5E7EB] bg-white hover:border-[#356AE6] hover:shadow-xs"
                              }`}
                            >
                              <div className="flex items-center gap-2.5 min-w-0">
                                <button
                                  type="button"
                                  onClick={(e) => toggleComplete(p.id, e)}
                                  className="text-[#9299A3] hover:text-[#16845B] transition-colors"
                                  title={isDone ? "Mark as incomplete" : "Mark as done"}
                                >
                                  {isDone ? (
                                    <CheckCircle2 className="h-4 w-4 text-[#16845B]" />
                                  ) : (
                                    <Circle className="h-4 w-4" />
                                  )}
                                </button>
                                <span
                                  className={`font-medium truncate ${
                                    isDone
                                      ? "line-through text-[#9299A3]"
                                      : "text-[#20242B] group-hover:text-[#356AE6]"
                                  }`}
                                >
                                  {p.title}
                                </span>
                              </div>

                              <div className="flex items-center gap-2 shrink-0 ml-2">
                                <span
                                  className={`rounded px-1.5 py-0.5 text-[9px] font-mono font-semibold uppercase border ${diffClass}`}
                                >
                                  {p.difficulty}
                                </span>
                                {p.time_complexity && (
                                  <span className="hidden md:inline-block rounded border border-[#E5E7EB] bg-[#F5F6F7] px-1.5 py-0.5 text-[9px] font-mono text-[#68717D]">
                                    {p.time_complexity}
                                  </span>
                                )}
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onSelectProblem(p.title);
                                  }}
                                  className="inline-flex items-center gap-1 rounded bg-[#EDF3FF] border border-[#BFDBFE] px-2 py-0.5 text-[10px] font-mono font-semibold text-[#356AE6] group-hover:bg-[#356AE6] group-hover:text-white transition-colors"
                                >
                                  <Play className="h-2.5 w-2.5 fill-current" />
                                  Study Moment
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
