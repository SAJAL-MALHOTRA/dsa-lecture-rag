"use client";

import React, { useState } from "react";
import { X, Sparkles, Send, Loader2, Play, Bot, User } from "lucide-react";
import { fetchAnswer } from "../lib/api";
import { AnswerResponse, Citation } from "../types/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  approach?: string;
}

interface AiChatDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onSeek: (videoId: string, sec: number, title?: string) => void;
  currentQuery?: string;
}

export const AiChatDrawer: React.FC<AiChatDrawerProps> = ({
  isOpen,
  onClose,
  onSeek,
  currentQuery = "",
}) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hello! I am your Striver AI DSA mentor. Ask me any doubt regarding algorithmic intuition, brute-force to optimal transitions, edge cases, or specific YouTube moments from the A2Z sheet.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userText = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userText }]);
    setLoading(true);

    try {
      const res: AnswerResponse = await fetchAnswer(userText);
      const allCitations: Citation[] = [];
      if (res.bullets) {
        res.bullets.forEach((b) => {
          if (b.citations) allCitations.push(...b.citations);
        });
      }

      const bulletText = res.bullets && res.bullets.length > 0
        ? res.bullets.map((b) => `• ${b.text}`).join("\n\n")
        : res.message || "Here is what Striver explains in the lecture:";

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: bulletText,
          citations: allCitations,
          approach: res.approach_summary,
        },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Sorry, couldn't fetch an answer right now (${err?.message || "Server busy"}). Please check your query or try again.`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs transition-opacity animate-in fade-in duration-200">
      <div className="flex h-full w-full max-w-xl flex-col bg-white shadow-2xl border-l border-[#E5E7EB] animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#E5E7EB] px-5 py-3.5 bg-[#FAFAF9]">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[#356AE6] text-white">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <h2 className="font-semibold text-sm text-[#20242B]">Ask Striver AI</h2>
              <p className="text-[10px] font-mono text-[#68717D]">
                Grounded on 6,881 video transcript moments
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-[#9299A3] hover:bg-[#F5F6F7] hover:text-[#20242B]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Messages Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex gap-3 ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {m.role === "assistant" && (
                <div className="h-7 w-7 rounded-full bg-[#EDF3FF] border border-[#BFDBFE] flex items-center justify-center text-[#356AE6] shrink-0 mt-0.5">
                  <Bot className="h-4 w-4" />
                </div>
              )}

              <div
                className={`max-w-[85%] rounded-lg px-3.5 py-2.5 text-xs leading-relaxed ${
                  m.role === "user"
                    ? "bg-[#356AE6] text-white"
                    : "bg-[#F9FAFB] border border-[#E5E7EB] text-[#20242B] space-y-2"
                }`}
              >
                {m.approach && (
                  <div className="rounded bg-[#EDF3FF] border border-[#BFDBFE] p-2 text-[#1E40AF] text-[11px] mb-2 font-medium">
                    💡 <strong>Intuition:</strong> {m.approach}
                  </div>
                )}

                <div className="whitespace-pre-line">{m.content}</div>

                {/* Inline Citations */}
                {m.citations && m.citations.length > 0 && (
                  <div className="pt-2 border-t border-[#E5E7EB] space-y-1">
                    <div className="text-[10px] font-mono text-[#68717D] uppercase font-semibold">
                      Lecture Timestamps:
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {m.citations.map((c, cIdx) => (
                        <button
                          key={cIdx}
                          type="button"
                          onClick={() => {
                            onSeek(c.video_id, c.seek_sec, c.video_title);
                            onClose();
                          }}
                          className="inline-flex items-center gap-1 rounded bg-[#EDF3FF] border border-[#BFDBFE] px-2 py-0.5 text-[10px] font-mono font-medium text-[#356AE6] hover:bg-[#356AE6] hover:text-white transition-colors"
                        >
                          <Play className="h-2.5 w-2.5 fill-current" />
                          {c.timestamp_display} • {c.video_title.substring(0, 24)}...
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {m.role === "user" && (
                <div className="h-7 w-7 rounded-full bg-[#20242B] flex items-center justify-center text-white shrink-0 mt-0.5">
                  <User className="h-4 w-4" />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex items-center gap-2 text-xs font-mono text-[#68717D] pl-10">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-[#356AE6]" />
              Striver AI is retrieving transcripts &amp; synthesizing intuition...
            </div>
          )}
        </div>

        {/* Input Form */}
        <form onSubmit={handleSend} className="p-3 border-t border-[#E5E7EB] bg-[#FAFAF9]">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask any algorithm intuition doubt..."
              className="h-10 flex-1 rounded-lg border border-[#E5E7EB] bg-white px-3 text-xs text-[#20242B] placeholder-[#9299A3] outline-none focus:border-[#356AE6]"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="h-10 px-3.5 rounded-lg bg-[#356AE6] text-white flex items-center justify-center transition-opacity hover:opacity-95 disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
