import { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Alert,
  CircularProgress,
} from '@mui/material';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import SaveIcon from '@mui/icons-material/Save';
import DownloadIcon from '@mui/icons-material/Download';
import JsonEditor from '../common/JsonEditor';
import {
  getEnhancedQuestionsLatex,
  updateEnhancedQuestionsLatex,
  downloadEnhancedQuestions,
} from '../../services/api';
import type { Question } from '../../types';

interface EnhancedStage2Props {
  sessionId: string;
  onNext: () => void;
  onBack: () => void;
}

function EnhancedStage2({ sessionId, onNext, onBack }: EnhancedStage2Props) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [jsonText, setJsonText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadQuestions();
  }, [sessionId]);

  const loadQuestions = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await getEnhancedQuestionsLatex(sessionId);
      setQuestions(response.questions);
      setJsonText(JSON.stringify(response.questions, null, 2));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load questions');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);

      const parsedQuestions = JSON.parse(jsonText);
      await updateEnhancedQuestionsLatex(sessionId, parsedQuestions);
      setQuestions(parsedQuestions);
      setSuccess('Questions saved successfully!');
    } catch (err: any) {
      if (err instanceof SyntaxError) {
        setError('Invalid JSON format. Please check your syntax.');
      } else {
        setError(err.response?.data?.detail || 'Save failed');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDownload = () => {
    const url = downloadEnhancedQuestions(sessionId);
    window.open(url, '_blank');
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h5" gutterBottom>
          Enhanced Combined Extractor - Review Questions (LaTeX)
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Review and edit the extracted questions with LaTeX notation. Questions were automatically extracted from the PDF.
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {success && (
          <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
            {success}
          </Alert>
        )}

        {questions.length === 0 ? (
          <Alert severity="warning">
            No questions found. Please go back and process the PDF first.
          </Alert>
        ) : (
          <>
            <Alert severity="info" sx={{ mb: 2 }}>
              Found {questions.length} questions with LaTeX formatting. You can edit the JSON below.
            </Alert>

            <Box sx={{ mb: 2, display: 'flex', gap: 2 }}>
              <Button
                variant="outlined"
                onClick={handleSave}
                disabled={saving}
                startIcon={saving ? <CircularProgress size={20} /> : <SaveIcon />}
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </Button>
              <Button
                variant="outlined"
                onClick={handleDownload}
                startIcon={<DownloadIcon />}
              >
                Download JSON
              </Button>
            </Box>

            <Paper variant="outlined" sx={{ mb: 3 }}>
              <JsonEditor
                value={jsonText}
                onChange={setJsonText}
                height="600px"
                language="json"
              />
            </Paper>
          </>
        )}
      </Paper>

      {/* Navigation Buttons */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 3 }}>
        <Button
          variant="outlined"
          onClick={onBack}
          startIcon={<NavigateBeforeIcon />}
        >
          Back
        </Button>
        <Button
          variant="contained"
          onClick={onNext}
          endIcon={<NavigateNextIcon />}
          disabled={questions.length === 0}
        >
          Go to Next Stage (Upload Marking Scheme)
        </Button>
      </Box>
    </Box>
  );
}

export default EnhancedStage2;
