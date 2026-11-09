/**
 * Shared TypeScript definitions matching FastAPI backend contracts.
 */

export interface Citation {
  video_id: string;
  video_title: string;
  seek_sec: number;
  timestamp_display: string;
  url?: string;
}

export interface AnswerBullet {
  text: string;
  citations: Citation[];
}

export interface LeetCodeExample {
  input: string;
  output: string;
  explanation?: string;
}

export interface DSASnippet {
  id: string;
  title: string;
  topic: string;
  subtopic: string;
  question: string;
  approach: string;
  code_cpp: string;
  code_python: string;
  code_java: string;
  time_complexity: string;
  space_complexity: string;
  file_path?: string;
  source_repo?: string;
  leetcode_url?: string;
  leetcode_slug?: string;
  leetcode_submit_url?: string;
  leetcode_difficulty?: "Easy" | "Medium" | "Hard" | string;
  leetcode_title?: string;
  leetcode_tags?: string[];
  leetcode_id?: number | string;
  leetcode_examples?: LeetCodeExample[];
  leetcode_default_input?: string;
  leetcode_default_output?: string;
}

export interface SearchResultItem {
  video_id: string;
  video_title: string;
  seek_sec: number;
  start_sec: number;
  end_sec: number;
  timestamp_display: string;
  snippet: string;
  url: string;
  score: number;
  dsa_snippet?: DSASnippet | null;
}

export interface PatternChunk {
  chunk_id?: string;
  source?: string;
  content_type?: string;
  pattern_name: string;
  language?: string;
  canonical_topic?: string;
  title?: string;
  text?: string;
  url?: string;
}

export interface VisualizerItem {
  title: string;
  url: string;
  description?: string;
  category?: string;
}

export interface PracticeProblemItem {
  title: string;
  platform: string;
  url: string;
  difficulty: string;
  tag?: string;
}

export interface EnrichmentMetadata {
  visualizers?: VisualizerItem[];
  practice_problems?: PracticeProblemItem[];
  prerequisites?: string[];
  next_topics?: string[];
}

export interface SearchResponse {
  query: string;
  total_found: number;
  summary: string;
  results: SearchResultItem[];
  dsa_snippet: DSASnippet | null;
  canonical_topics: string[];
  pattern_chunks: PatternChunk[];
  enrichment?: EnrichmentMetadata | null;
}

export interface AnswerResponse {
  query: string;
  provider: string;
  approach_summary?: string;
  bullets: AnswerBullet[];
  dsa_snippet?: DSASnippet | null;
  enrichment?: EnrichmentMetadata | null;
  pattern_chunks?: PatternChunk[];
  message?: string;
}

export interface RoadmapProblem {
  id: string;
  title: string;
  topic: string;
  subtopic: string;
  difficulty: "Easy" | "Medium" | "Hard" | string;
  time_complexity?: string;
  space_complexity?: string;
}

export interface RoadmapSubtopic {
  name: string;
  count: number;
  problems: RoadmapProblem[];
}

export interface RoadmapTopic {
  raw_name: string;
  name: string;
  icon: string;
  total_count: number;
  subtopics: RoadmapSubtopic[];
}

export interface RoadmapResponse {
  total_problems: number;
  topics: RoadmapTopic[];
}
