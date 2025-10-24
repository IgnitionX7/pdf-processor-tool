import { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Alert,
  CircularProgress,
  Grid,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CodeIcon from '@mui/icons-material/Code';
import VisibilityIcon from '@mui/icons-material/Visibility';
import SaveIcon from '@mui/icons-material/Save';
import JsonEditor from '../common/JsonEditor';
import {
  extractQuestions,
  updateQuestions,
  validateQuestions,
  downloadQuestions,
} from '../../services/api';
import type { Question } from '../../types';

interface Stage2Props {
  sessionId: string;
  onNext: () => void;
  onBack: () => void;
}

export default function Stage2({ sessionId, onNext, onBack }: Stage2Props) {
  const [extracting, setExtracting] = useState(false);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'visual' | 'json'>('visual');
  const [jsonText, setJsonText] = useState('');

  const handleExtractQuestions = async () => {
    try {
      setExtracting(true);
      setError(null);

      const response = await extractQuestions(sessionId);
      setQuestions(response.stats.questions);
      setJsonText(JSON.stringify(response.stats.questions, null, 2));
      setSuccess(
        `Extracted ${response.stats.total_questions} questions with ${response.stats.total_parts} parts`
      );

      // Auto-validate
      await validateQuestions(sessionId);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Extraction failed');
    } finally {
      setExtracting(false);
    }
  };

  const handleDownload = () => {
    window.open(downloadQuestions(sessionId), '_blank');
  };

  const handleSaveJson = async () => {
    try {
      const parsedQuestions = JSON.parse(jsonText);
      await updateQuestions(sessionId, parsedQuestions);
      setQuestions(parsedQuestions);
      setSuccess('Questions saved successfully!');
    } catch (err: any) {
      if (err instanceof SyntaxError) {
        setError('Invalid JSON format. Please check your syntax.');
      } else {
        setError(err.response?.data?.detail || 'Save failed');
      }
    }
  };

  const toggleViewMode = () => {
    if (viewMode === 'visual') {
      setJsonText(JSON.stringify(questions, null, 2));
      setViewMode('json');
    } else {
      setViewMode('visual');
    }
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Stage 2: Extract Questions
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

      <Grid container spacing={3}>
        {questions.length === 0 && (
          <Grid item xs={12}>
            <Paper sx={{ p: 3, textAlign: 'center' }}>
              <Typography variant="h6" gutterBottom>
                Extract Questions from Cleaned Text
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                This will parse the cleaned text and identify all questions with their parts
              </Typography>
              <Button
                variant="contained"
                size="large"
                onClick={handleExtractQuestions}
                disabled={extracting}
                startIcon={extracting ? <CircularProgress size={20} /> : <PlayArrowIcon />}
              >
                {extracting ? 'Extracting...' : 'Extract Questions'}
              </Button>
            </Paper>
          </Grid>
        )}

        {/* Validation Results */}
        {/* {validation && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Validation Results
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  {validation.valid ? (
                    <CheckCircleIcon color="success" />
                  ) : (
                    <WarningIcon color="warning" />
                  )}
                  <Typography>
                    {validation.errors.length} errors, {validation.warnings.length} warnings
                  </Typography>
                </Box>
                {validation.warnings.slice(0, 5).map((warning, i) => (
                  <Typography key={i} variant="body2" color="warning.main">
                    • {warning}
                  </Typography>
                ))}
              </CardContent>
            </Card>
          </Grid>
        )} */}

        {/* View Mode Toggle */}
        {questions.length > 0 && (
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <Button
                variant={viewMode === 'visual' ? 'contained' : 'outlined'}
                onClick={() => setViewMode('visual')}
                startIcon={<VisibilityIcon />}
              >
                Visual View
              </Button>
              <Button
                variant={viewMode === 'json' ? 'contained' : 'outlined'}
                onClick={toggleViewMode}
                startIcon={<CodeIcon />}
              >
                JSON View
              </Button>
            </Box>
          </Grid>
        )}

        {/* JSON Editor */}
        {questions.length > 0 && viewMode === 'json' && (
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Edit Questions JSON
              </Typography>
              <JsonEditor
                value={jsonText}
                onChange={setJsonText}
                height="600px"
                language="json"
              />
              <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
                <Button
                  variant="contained"
                  startIcon={<SaveIcon />}
                  onClick={handleSaveJson}
                >
                  Save JSON
                </Button>
                <Button variant="outlined" onClick={handleDownload}>
                  Download JSON
                </Button>
              </Box>
            </Paper>
          </Grid>
        )}

        {/* Questions List */}
        {questions.length > 0 && viewMode === 'visual' && questions.map((question) => (
          <Grid item xs={12} key={question.questionNumber}>
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="h6">
                  Question {question.questionNumber} ({question.totalMarks || '?'} marks,{' '}
                  {question.parts.length} parts)
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                {question.mainText && (
                  <Typography variant="body2" paragraph>
                    <strong>Main Text:</strong> {question.mainText}
                  </Typography>
                )}
                {question.parts.map((part) => (
                  <Box key={part.partLabel} sx={{ ml: 2, mb: 1 }}>
                    <Typography variant="body2">
                      <strong>({part.partLabel})</strong> {part.text.substring(0, 100)}...
                      {part.marks && ` [${part.marks}]`}
                    </Typography>
                    {part.parts && part.parts.length > 0 && (
                      <Box sx={{ ml: 3 }}>
                        {part.parts.map((subpart) => (
                          <Typography key={subpart.partLabel} variant="body2" color="text.secondary">
                            ({subpart.partLabel}) {subpart.text.substring(0, 80)}...
                          </Typography>
                        ))}
                      </Box>
                    )}
                  </Box>
                ))}
              </AccordionDetails>
            </Accordion>
          </Grid>
        ))}


        {/* Navigation */}
        <Grid item xs={12}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Button variant="outlined" onClick={onBack} startIcon={<NavigateBeforeIcon />}>
              Back
            </Button>
            {questions.length > 0 && (
              <Button variant="contained" onClick={onNext} endIcon={<NavigateNextIcon />}>
                Next: Extract Marking Schemes
              </Button>
            )}
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
}
