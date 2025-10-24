// API Types

export interface Session {
  session_id: string;
  created_at: string;
  status: 'created' | 'processing' | 'completed' | 'error';
  current_stage: number;
  files: Record<string, string>;
  error?: string;
}

export interface SessionCreate {
  session_id: string;
  created_at: string;
}

export interface FileUploadResponse {
  file_id: string;
  filename: string;
  size: number;
  message: string;
}

export interface TextExtractionStats {
  pages: number;
  total_characters: number;
  total_words: number;
  avg_chars_per_page: number;
  avg_words_per_page: number;
  empty_pages?: number[];
}

export interface CleanedTextStats {
  kept_pages: number;
  kept_original_page_numbers: number[];
  empty_pages_after_cleaning: number[];
  total_characters: number;
  total_words: number;
  avg_chars_per_page: number;
  avg_words_per_page: number;
}

export interface TextExtractionResponse {
  raw_text_url: string;
  cleaned_text_url: string;
  stats: {
    raw: TextExtractionStats;
    cleaned: CleanedTextStats;
  };
}

export interface QuestionPart {
  partLabel: string;
  text: string;
  marks: number | null;
  markingScheme: string | null;
  parts: QuestionPart[];
}

export interface Question {
  questionNumber: number;
  mainText: string;
  totalMarks: number | null;
  parts: QuestionPart[];
}

export interface QuestionExtractionResponse {
  questions_url: string;
  stats: {
    total_questions: number;
    total_parts: number;
    total_marks: number;
    questions: Question[];
  };
}

export interface ValidationError {
  valid: boolean;
  errors: string[];
  warnings: string[];
  stats: {
    total_errors: number;
    total_warnings: number;
  };
}

export interface MarkingSchemes {
  [ref: string]: string;
}

export interface MarkingSchemeExtractionResponse {
  marking_schemes_url: string;
  stats: {
    total_entries: number;
    marking_schemes: MarkingSchemes;
  };
}

export interface MergeStats {
  successful: number;
  failed: number;
  failed_refs: string[];
  total_parts: number;
  parts_with_schemes: number;
  coverage_percentage: number;
}

export interface MergeResponse {
  merged_url: string;
  stats: MergeStats;
  questions: Question[];
}

export interface MergeStatistics {
  total_questions: number;
  total_parts: number;
  parts_with_schemes: number;
  parts_without_schemes: number;
  coverage_percentage: number;
  total_marks: number;
}
