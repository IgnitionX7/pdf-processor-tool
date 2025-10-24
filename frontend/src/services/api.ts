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
