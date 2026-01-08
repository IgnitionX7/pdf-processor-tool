import { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Alert,
  CircularProgress,
  TextField,
  Chip,
  Stack,
} from '@mui/material';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import SaveIcon from '@mui/icons-material/Save';
import DownloadIcon from '@mui/icons-material/Download';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import {
  getEnhancedExtractedText,
  updateEnhancedExtractedText,
  downloadEnhancedExtractedText,
  extractEnhancedQuestions,
  getEnhancedProcessingStatus,
} from '../../services/api';

interface EnhancedStage2TextProps {
  sessionId: string;
  onNext: () => void;
  onBack: () => void;
}

function EnhancedStage2Text({ sessionId, onNext, onBack }: EnhancedStage2TextProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [extractedText, setExtractedText] = useState('');
  const [originalText, setOriginalText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [charCount, setCharCount] = useState(0);
  const [lineCount, setLineCount] = useState(0);

  useEffect(() => {
    loadExtractedText();
  }, [sessionId]);

  useEffect(() => {
    // Update statistics when text changes
    setCharCount(extractedText.length);
    setLineCount(extractedText.split('\n').length);
  }, [extractedText]);

  const loadExtractedText = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await getEnhancedExtractedText(sessionId);
      setExtractedText(response.text);
      setOriginalText(response.text);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load extracted text');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);
      setSuccess(null);

      await updateEnhancedExtractedText(sessionId, extractedText);
      setOriginalText(extractedText);
      setSuccess('Text saved successfully!');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleDownload = () => {
    const url = downloadEnhancedExtractedText(sessionId);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'extracted_text.txt');
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const handleReset = () => {
    setExtractedText(originalText);
    setSuccess(null);
    setError(null);
  };

  const handleExtractQuestions = async () => {
    // Save changes first if there are any
    if (hasChanges) {
      try {
        await updateEnhancedExtractedText(sessionId, extractedText);
        setOriginalText(extractedText);
      } catch (err: any) {
        setError('Please save your changes first before extracting questions');
        return;
      }
    }

    try {
      setExtracting(true);
      setError(null);
      setSuccess(null);

      // Start question extraction
      await extractEnhancedQuestions(sessionId);

      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const status = await getEnhancedProcessingStatus(sessionId);

          if (status.status === 'completed') {
            clearInterval(pollInterval);
            setExtracting(false);
            setSuccess(`Extraction complete! Found ${status.question_count_latex || 0} questions.`);
            setTimeout(() => {
              onNext(); // Navigate to Stage 3
            }, 1500);
          } else if (status.status === 'error') {
            clearInterval(pollInterval);
            setExtracting(false);
            setError(status.error || 'Question extraction failed');
          }
        } catch (err: any) {
          clearInterval(pollInterval);
          setExtracting(false);
          setError('Failed to check extraction status');
        }
      }, 2000); // Poll every 2 seconds

    } catch (err: any) {
      setExtracting(false);
      setError(err.response?.data?.detail || 'Failed to start question extraction');
    }
  };

  const hasChanges = extractedText !== originalText;

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
          Enhanced Combined Extractor - Review Extracted Text
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Review and edit the extracted text. Text was extracted from the PDF{' '}
          {/* TODO: Show if exclusion zones were applied */}
          with exclusion zones applied to filter out figure/table regions.
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

        {/* Statistics */}
        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          <Chip label={`${charCount.toLocaleString()} characters`} size="small" />
          <Chip label={`${lineCount.toLocaleString()} lines`} size="small" />
          {hasChanges && <Chip label="Unsaved changes" color="warning" size="small" />}
        </Stack>

        {/* Text Editor */}
        <TextField
          fullWidth
          multiline
          minRows={20}
          maxRows={30}
          value={extractedText}
          onChange={(e) => setExtractedText(e.target.value)}
          placeholder="Extracted text will appear here..."
          sx={{
            mb: 2,
            '& .MuiInputBase-root': {
              fontFamily: 'monospace',
              fontSize: '0.9rem',
            },
          }}
        />

        {/* Action Buttons */}
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={saving || !hasChanges}
            startIcon={saving ? <CircularProgress size={20} /> : <SaveIcon />}
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>

          <Button
            variant="outlined"
            onClick={handleReset}
            disabled={!hasChanges}
          >
            Reset
          </Button>

          <Button
            variant="outlined"
            onClick={handleDownload}
            startIcon={<DownloadIcon />}
          >
            Download Text
          </Button>
        </Box>
      </Paper>

      {/* Navigation */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Button
          variant="outlined"
          onClick={onBack}
          startIcon={<NavigateBeforeIcon />}
        >
          Back to Figures/Tables
        </Button>

        <Button
          variant="contained"
          onClick={handleExtractQuestions}
          disabled={extracting}
          endIcon={extracting ? <CircularProgress size={20} /> : <AutorenewIcon />}
        >
          {extracting ? 'Extracting Questions...' : 'Extract Questions'}
        </Button>
      </Box>
    </Box>
  );
}

export default EnhancedStage2Text;
