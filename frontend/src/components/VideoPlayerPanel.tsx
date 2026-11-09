import React, { useRef, useEffect } from "react";
import { Play, Code, ExternalLink, Image as ImageIcon } from "lucide-react";
import { DSASnippet } from "../types/api";

interface VideoPlayerPanelProps {
  videoId: string;
  seekSec: number;
  lectureTitle: string;
  activeDsa: DSASnippet | null;
  onOpenDrawer: () => void;
  onSeek: (videoId: string, sec: number) => void;
}

export const VideoPlayerPanel: React.FC<VideoPlayerPanelProps> = ({
  videoId,
  seekSec,
  lectureTitle,
  activeDsa,
  onOpenDrawer,
  onSeek,
}) => {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Sync iframe src on videoId or seekSec change
  const embedUrl = `https://www.youtube-nocookie.com/embed/${videoId}?start=${seekSec}&autoplay=1&enablejsapi=1&rel=0`;

  // Format seconds to mm:ss
  const formatTime = (totalSec: number) => {
    const m = Math.floor(totalSec / 60);
    const s = Math.floor(totalSec % 60);
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  };

  const lcUrl =
    activeDsa?.leetcode_url ||
    (activeDsa?.leetcode_slug
      ? `https://leetcode.com/problems/${activeDsa.leetcode_slug}/`
      : null);

  // Keyframes for quick scrubbing
  const keyframes = [
    { sec: 300, label: "Hash Map Intuition", time: "05:00" },
    { sec: 900, label: "Two Pointer Approach", time: "15:00" },
    { sec: 1500, label: "Code Walkthrough", time: "25:00" },
  ];

  return (
    <div className="space-y-4 rounded-xl border border-[#E5E7EB] bg-white p-4 shadow-xs">
      {/* Video Container */}
      <div className="relative aspect-video w-full overflow-hidden rounded-lg bg-black shadow-inner border border-[#E5E7EB]">
        <iframe
          ref={iframeRef}
          key={`${videoId}-${seekSec}`}
          src={embedUrl}
          title={lectureTitle || "Striver DSA Lecture"}
          className="h-full w-full"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
        />
      </div>

      {/* Video Meta & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 border-b border-[#E5E7EB] pb-3">
        <div className="space-y-1 min-w-0">
          <h3 className="font-semibold text-sm text-[#20242B] truncate" title={lectureTitle}>
            {lectureTitle || "Lecture Playback"}
          </h3>
          <div className="flex items-center gap-2 text-xs text-[#68717D]">
            <span className="font-mono text-[11px] text-[#356AE6] font-medium bg-[#EDF3FF] px-1.5 py-0.5 rounded">
              ⏱ Synced at {formatTime(seekSec)}
            </span>
            <span>•</span>
            <span className="text-[11px]">Click timestamps to seek</span>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {lcUrl && (
            <a
              href={lcUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-md border border-[#FDBA74] bg-[#FFF7ED] px-2.5 py-1.5 text-xs font-mono font-medium text-[#C2410C] hover:bg-[#FFEDD5] transition-colors"
            >
              <span>🟠</span> LeetCode
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
          <button
            onClick={onOpenDrawer}
            className="inline-flex items-center gap-1.5 rounded-md border border-[#E5E7EB] bg-[#F6F7F9] px-2.5 py-1.5 text-xs font-mono font-medium text-[#20242B] hover:border-[#356AE6] hover:bg-[#EDF3FF] hover:text-[#356AE6] transition-colors"
          >
            <Code className="h-3.5 w-3.5" />
            Code
          </button>
        </div>
      </div>

      {/* Keyframe Gallery Strip */}
      <div className="space-y-2">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-[#68717D] font-mono uppercase">
          <ImageIcon className="h-3 w-3 text-[#356AE6]" />
          Whiteboard Keyframes
        </div>

        <div className="grid grid-cols-3 gap-2">
          {keyframes.map((kf) => (
            <button
              key={kf.sec}
              onClick={() => onSeek(videoId, kf.sec)}
              className="group relative flex flex-col overflow-hidden rounded-md border border-[#E5E7EB] bg-[#F9FAFB] text-left transition-all hover:border-[#356AE6] hover:shadow-xs p-1"
            >
              <div className="relative aspect-video w-full overflow-hidden rounded bg-gray-200">
                <img
                  src={`https://img.youtube.com/vi/${videoId}/mqdefault.jpg`}
                  alt={kf.label}
                  className="h-full w-full object-cover group-hover:scale-105 transition-transform"
                />
                <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity">
                  <Play className="h-4 w-4 fill-white text-white" />
                </div>
                <span className="absolute bottom-1 right-1 rounded bg-black/80 px-1 py-0.5 text-[8px] font-mono font-medium text-white">
                  {kf.time}
                </span>
              </div>
              <span className="text-[10px] font-medium text-[#20242B] line-clamp-1 mt-1 px-0.5 group-hover:text-[#356AE6]">
                {kf.label}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
