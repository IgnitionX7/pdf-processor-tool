import axios from 'axios';
import type {
  Session,
  SessionCreate,
  FileUploadResponse,
  TextExtractionResponse,
  Question,
  QuestionExtractionResponse,
  ValidationError,
  MarkingSchemes,
  MarkingSchemeExtractionResponse,
  MergeResponse,
  MergeStatistics,
} from '../types';

// Use environment variable or fallback to relative URL for production
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ||
                     (import.meta.env.DEV ? 'http://localhost:8000' : '');

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Session Management
export const createSession = async (): Promise<SessionCreate> => {
  const response = await api.post('/api/sessions');
  return response.data;
};

export const getSession = async (sessionId: string): Promise<Session> => {
  const response = await api.get(`/api/sessions/${sessionId}`);
  return response.data;
};

export const deleteSession = async (sessionId: string): Promise<void> => {
  await api.delete(`/api/sessions/${sessionId}`);
};

// Stage 1: Text Extraction
export const uploadQuestionPaper = async (
  sessionId: string,
  file: File
): Promise<FileUploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post(
    `/api/sessions/${sessionId}/stage1/upload-question-paper`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  return response.data;
};

export const extractText = async (sessionId: string): Promise<TextExtractionResponse> => {
  const response = await api.post(`/api/sessions/${sessionId}/stage1/extract-text`);
  return response.data;
};

export const getText = async (sessionId: string, type: 'raw' | 'cleaned'): Promise<string> => {
  const response = await api.get(`/api/sessions/${sessionId}/stage1/text/${type}`);
  return response.data;
};

export const getTextStats = async (sessionId: string, type: 'raw' | 'cleaned'): Promise<any> => {
  const response = await api.get(`/api/sessions/${sessionId}/stage1/stats/${type}`);
  return response.data;
};

export const updateCleanedText = async (
  sessionId: string,
  text: string
): Promise<{ message: string; characters: number; words: number }> => {
  const response = await api.put(`/api/sessions/${sessionId}/stage1/text/cleaned`, { text });
  return response.data;
};

export const downloadText = (sessionId: string, type: 'raw' | 'cleaned'): string => {
  return `${API_BASE_URL || ''}/api/sessions/${sessionId}/stage1/download/${type}`;
};

// Stage 2: Question Extraction
export const extractQuestions = async (sessionId: string): Promise<QuestionExtractionResponse> => {
  const response = await api.post(`/api/sessions/${sessionId}/stage2/extract-questions`);
  return response.data;
};

export const getQuestions = async (sessionId: string): Promise<Question[]> => {
  const response = await api.get(`/api/sessions/${sessionId}/stage2/questions`);
  return response.data;
};

export const updateQuestions = async (
  sessionId: string,
  questions: Question[]
): Promise<{ message: string; stats: any }> => {
  const response = await api.put(`/api/sessions/${sessionId}/stage2/questions`, questions);
  return response.data;
};

export const validateQuestions = async (sessionId: string): Promise<ValidationError> => {
  const response = await api.post(`/api/sessions/${sessionId}/stage2/validate`);
  return response.data;
};

export const downloadQuestions = (sessionId: string): string => {
  return `${API_BASE_URL || ''}/api/sessions/${sessionId}/stage2/download`;
};

// Stage 3: Marking Scheme Extraction
export const uploadMarkingScheme = async (
  sessionId: string,
  file: File
): Promise<FileUploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post(
    `/api/sessions/${sessionId}/stage3/upload-marking-scheme`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  return response.data;
};

export const extractMarkingSchemes = async (
  sessionId: string,
  startPage: number = 8
): Promise<MarkingSchemeExtractionResponse> => {
  const response = await api.post(
    `/api/sessions/${sessionId}/stage3/extract-marking-schemes`,
    null,
    {
      params: { start_page: startPage },
    }
  );
  return response.data;
};

export const getMarkingSchemes = async (sessionId: string): Promise<MarkingSchemes> => {
  const response = await api.get(`/api/sessions/${sessionId}/stage3/marking-schemes`);
  return response.data;
};

export const updateMarkingSchemes = async (
  sessionId: string,
  markingSchemes: MarkingSchemes
): Promise<{ message: string; stats: any }> => {
  const response = await api.put(
    `/api/sessions/${sessionId}/stage3/marking-schemes`,
    markingSchemes
  );
  return response.data;
};

export const downloadMarkingSchemes = (sessionId: string): string => {
  return `${API_BASE_URL || ''}/api/sessions/${sessionId}/stage3/download`;
};

// Stage 4: Merge
export const mergeMarkingSchemes = async (sessionId: string): Promise<MergeResponse> => {
  const response = await api.post(`/api/sessions/${sessionId}/stage4/merge`);
  return response.data;
};

export const getMergedData = async (sessionId: string): Promise<Question[]> => {
  const response = await api.get(`/api/sessions/${sessionId}/stage4/merged`);
  return response.data;
};

export const getMergeStatistics = async (sessionId: string): Promise<MergeStatistics> => {
  const response = await api.get(`/api/sessions/${sessionId}/stage4/statistics`);
  return response.data;
};

export const updateMergedData = async (
  sessionId: string,
  questions: Question[]
): Promise<{ message: string; stats: any }> => {
  const response = await api.put(`/api/sessions/${sessionId}/stage4/merged`, questions);
  return response.data;
};

export const downloadMergedData = (sessionId: string): string => {
  return `${API_BASE_URL || ''}/api/sessions/${sessionId}/stage4/download`;
};

// Enhanced Combined Extractor
export const uploadPdfForEnhanced = async (
  sessionId: string,
  file: File
): Promise<FileUploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post(
    `/api/sessions/${sessionId}/enhanced/upload-pdf`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  return response.data;
};

export const processEnhancedPdf = async (
  sessionId: string
): Promise<{
  message: string;
  status: string;
  status_url: string;
}> => {
  const response = await api.post(`/api/sessions/${sessionId}/enhanced/process`);
  return response.data;
};

export const extractTextWithExclusions = async (
  sessionId: string,
  excludeFigures: boolean = true,
  excludeTables: boolean = true
): Promise<{
  message: string;
  status: string;
  status_url: string;
  exclusion_settings: {
    exclude_figures: boolean;
    exclude_tables: boolean;
  };
}> => {
  const response = await api.post(
    `/api/sessions/${sessionId}/enhanced/extract-text`,
    null,
    {
      params: {
        exclude_figures: excludeFigures,
        exclude_tables: excludeTables,
      },
    }
  );
  return response.data;
};

export const getEnhancedProcessingStatus = async (
  sessionId: string
): Promise<{
  status: string;
  current_stage: number;
  message?: string;
  statistics?: any;
  question_count_latex?: number;
  question_count_plain?: number;
  figures_tables_url?: string;
  questions_url?: string;
  error?: string;
}> => {
  const response = await api.get(`/api/sessions/${sessionId}/enhanced/status`);
  return response.data;
};

export const getEnhancedFiguresTables = async (
  sessionId: string
): Promise<{
  elements: any[];
  total_count: number;
  figures_count: number;
  tables_count: number;
}> => {
  const response = await api.get(`/api/sessions/${sessionId}/enhanced/figures-tables`);
  return response.data;
};

// Enhanced: Get extracted text
export const getEnhancedExtractedText = async (
  sessionId: string
): Promise<{ text: string; char_count: number; line_count: number }> => {
  const response = await api.get(`/api/sessions/${sessionId}/enhanced/extracted-text`);
  return response.data;
};

// Enhanced: Update extracted text
export const updateEnhancedExtractedText = async (
  sessionId: string,
  text: string
): Promise<{ message: string }> => {
  const response = await api.put(
    `/api/sessions/${sessionId}/enhanced/extracted-text`,
    { text }
  );
  return response.data;
};

// Enhanced: Download extracted text
export const downloadEnhancedExtractedText = (sessionId: string): string => {
  return `${API_BASE_URL || ''}/api/sessions/${sessionId}/enhanced/download/extracted-text`;
};

// Enhanced: Extract questions from current text
export const extractEnhancedQuestions = async (
  sessionId: string
): Promise<{
  message: string;
  status: string;
  status_url: string;
}> => {
  const response = await api.post(`/api/sessions/${sessionId}/enhanced/extract-questions`);
  return response.data;
};

export const getEnhancedQuestionsLatex = async (
  sessionId: string
): Promise<{ questions: Question[]; total_count: number }> => {
  const response = await api.get(`/api/sessions/${sessionId}/enhanced/questions-latex`);
  return response.data;
};

export const updateEnhancedQuestionsLatex = async (
  sessionId: string,
  questions: Question[]
): Promise<{ message: string; total_count: number }> => {
  const response = await api.put(
    `/api/sessions/${sessionId}/enhanced/questions-latex`,
    questions
  );
  return response.data;
};

export const downloadEnhancedQuestions = (sessionId: string): string => {
  return `${API_BASE_URL || ''}/api/sessions/${sessionId}/enhanced/download/questions`;
};

export const downloadEnhancedFiguresZip = (sessionId: string): string => {
  return `${API_BASE_URL || ''}/api/sessions/${sessionId}/enhanced/download/figures-zip`;
};
