import React from "react";
import { Play, Sparkles, Wrench, ExternalLink, ArrowRight, ArrowLeft } from "lucide-react";
import { AnswerResponse, EnrichmentMetadata } from "../types/api";

interface GroundedAnswerCardProps {
  answer: AnswerResponse | null;
  enrichment?: EnrichmentMetadata | null;
  onSeek: (videoId: string, seekSec: number, title?: string) => void;
}

export const GroundedAnswerCard: React.FC<GroundedAnswerCardProps> = ({
  answer,
  enrichment,
  onSeek,
}) => {
  if (!answer) return null;

  const hasBullets = answer.bullets && answer.bullets.length > 0;
  const mergedEnrichment = answer.enrichment || enrichment;

  return (
    <div className="rounded-xl border border-[#E5E7EB] bg-white p-5 shadow-xs space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-5 w-5 items-center justify-center rounded bg-[#EDF3FF] text-[#356AE6]">
            <Sparkles className="h-3 w-3" />
          </div>
          <span className="font-semibold text-xs tracking-tight uppercase text-[#68717D] font-mono">
            Grounded Lecture Answer
          </span>
        </div>
        <span className="rounded-full bg-[#F5F6F7] border border-[#E5E7EB] px-2 py-0.5 text-[10px] font-mono font-medium text-[#68717D]">
          {answer.provider ? answer.provider.toUpperCase() : "EXTRACTIVE"} CITATION
        </span>
      </div>

      {/* Striver's Intuition Callout */}
      {answer.approach_summary && (
        <div className="rounded-lg border border-[#EDF3FF] bg-[#F5F8FF] p-3 text-xs text-[#20242B] leading-relaxed">
          <div className="flex items-center gap-1.5 font-semibold text-[#356AE6] mb-1">
            <span>💡</span> Striver's Approach Intuition (Brute → Optimal)
          </div>
          <p>{answer.approach_summary}</p>
        </div>
      )}

      {/* Bullets with inline interactive citations */}
      {hasBullets ? (
        <div className="space-y-2.5">
          {answer.bullets.map((bullet, idx) => (
            <div key={idx} className="flex items-start gap-2 text-xs text-[#20242B] leading-relaxed">
              <span className="text-[#356AE6] mt-0.5 font-bold">•</span>
              <div className="flex-1">
                <span>{bullet.text} </span>
                {bullet.citations && bullet.citations.length > 0 && (
                  <span className="inline-flex flex-wrap gap-1.5 ml-1">
                    {bullet.citations.map((c, cIdx) => (
                      <button
                        key={cIdx}
                        type="button"
                        onClick={() => onSeek(c.video_id, c.seek_sec, c.video_title)}
                        className="inline-flex items-center gap-1 rounded bg-[#EDF3FF] border border-[#BFDBFE] px-1.5 py-0.5 text-[10px] font-mono font-semibold text-[#356AE6] hover:bg-[#356AE6] hover:text-white transition-colors"
                        title={`Seek to ${c.timestamp_display} in ${c.video_title}`}
                      >
                        <Play className="h-2.5 w-2.5 fill-current" />
                        {c.timestamp_display}
                      </button>
                    ))}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-[#68717D]">
          {answer.message || "Select any lecture moment below to inspect grounded timestamp evidence."}
        </p>
      )}

      {/* Enrichment Card: Visualizers, Curriculum & Practice Problems */}
      {mergedEnrichment && (
        <div className="rounded-lg border border-[#E5E7EB] bg-[#F9FAFB] p-3.5 space-y-3 mt-4 text-xs">
          <div className="flex items-center gap-1.5 font-semibold text-[#20242B] text-xs">
            <Wrench className="h-3.5 w-3.5 text-[#356AE6]" />
            Visualizers, Curriculum &amp; Practice
          </div>

          {/* Interactive Visualizers */}
          {mergedEnrichment.visualizers && mergedEnrichment.visualizers.length > 0 && (
            <div className="space-y-1">
              <div className="text-[11px] font-mono text-[#68717D] uppercase font-medium">
                🎨 Interactive Visualizers
              </div>
              <div className="flex flex-wrap gap-1.5">
                {mergedEnrichment.visualizers.map((v, vIdx) => (
                  <a
                    key={vIdx}
                    href={v.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 rounded border border-[#E5E7EB] bg-white px-2 py-1 text-xs text-[#20242B] hover:border-[#356AE6] hover:text-[#356AE6] transition-colors"
                  >
                    <span>{v.title}</span>
                    <ExternalLink className="h-3 w-3 text-[#9299A3]" />
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Prerequisites and Next Topics */}
          {(mergedEnrichment.prerequisites?.length || mergedEnrichment.next_topics?.length) ? (
            <div className="flex flex-wrap items-center gap-4 text-[11px] text-[#68717D] border-t border-[#E5E7EB] pt-2">
              {mergedEnrichment.prerequisites && mergedEnrichment.prerequisites.length > 0 && (
                <div className="flex items-center gap-1">
                  <ArrowLeft className="h-3 w-3 text-[#9299A3]" />
                  <span className="font-semibold text-[#20242B]">Prereqs:</span>
                  <span>{mergedEnrichment.prerequisites.join(", ")}</span>
                </div>
              )}
              {mergedEnrichment.next_topics && mergedEnrichment.next_topics.length > 0 && (
                <div className="flex items-center gap-1">
                  <ArrowRight className="h-3 w-3 text-[#9299A3]" />
                  <span className="font-semibold text-[#20242B]">Next:</span>
                  <span>{mergedEnrichment.next_topics.join(", ")}</span>
                </div>
              )}
            </div>
          ) : null}

          {/* Curated Practice Problems */}
          {mergedEnrichment.practice_problems && mergedEnrichment.practice_problems.length > 0 && (
            <div className="space-y-1 border-t border-[#E5E7EB] pt-2">
              <div className="text-[11px] font-mono text-[#68717D] uppercase font-medium">
                💻 Curated Practice Problems
              </div>
              <div className="flex flex-wrap gap-1.5">
                {mergedEnrichment.practice_problems.slice(0, 3).map((p, pIdx) => {
                  const isLC = p.url.includes("leetcode.com");
                  const diffColor =
                    p.difficulty.toLowerCase() === "easy"
                      ? "text-[#16845B] bg-[#E6F4EA]"
                      : p.difficulty.toLowerCase() === "hard"
                      ? "text-[#C43D48] bg-[#FDE8E8]"
                      : "text-[#B7791F] bg-[#FEF3C7]";
                  return (
                    <a
                      key={pIdx}
                      href={p.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 rounded border border-[#E5E7EB] bg-white px-2 py-1 text-xs hover:border-[#356AE6] transition-colors"
                    >
                      <span>{isLC ? "🟠" : "🔗"}</span>
                      <span className="font-medium text-[#20242B]">{p.title}</span>
                      <span className={`rounded px-1 text-[10px] font-mono font-semibold ${diffColor}`}>
                        {p.difficulty}
                      </span>
                      <ExternalLink className="h-2.5 w-2.5 text-[#9299A3]" />
                    </a>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
