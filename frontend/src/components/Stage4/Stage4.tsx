import { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Alert,
  CircularProgress,
  Grid,
  Card,
  CardContent,
  LinearProgress,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import DownloadIcon from '@mui/icons-material/Download';
import CodeIcon from '@mui/icons-material/Code';
import SaveIcon from '@mui/icons-material/Save';
import JsonEditor from '../common/JsonEditor';
import {
  mergeMarkingSchemes,
  getMergeStatistics,
  updateMergedData,
  downloadMergedData,
} from '../../services/api';
import type { Question, MergeStatistics } from '../../types';

interface Stage4Props {
  sessionId: string;
  onNext: () => void;
  onBack: () => void;
}

export default function Stage4({ sessionId, onBack }: Stage4Props) {
  const [merging, setMerging] = useState(false);
  const [mergedQuestions, setMergedQuestions] = useState<Question[]>([]);
  const [statistics, setStatistics] = useState<MergeStatistics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'visual' | 'json'>('visual');
  const [jsonText, setJsonText] = useState('');

  const handleMerge = async () => {
    try {
      setMerging(true);
      setError(null);

      const response = await mergeMarkingSchemes(sessionId);
      setMergedQuestions(response.questions);
      setJsonText(JSON.stringify(response.questions, null, 2));

      const stats = await getMergeStatistics(sessionId);
      setStatistics(stats);

      setSuccess(
        `Merge complete! ${stats.parts_with_schemes}/${stats.total_parts} parts have marking schemes (${stats.coverage_percentage.toFixed(1)}% coverage)`
      );
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Merge failed');
    } finally {
      setMerging(false);
    }
  };

  const handleDownload = () => {
    window.open(downloadMergedData(sessionId), '_blank');
  };

  const handleSaveJson = async () => {
    try {
      setError(null);
      setSuccess(null);

      console.log('Starting save process...');

      // Parse and validate JSON
      let parsedQuestions;
      try {
        parsedQuestions = JSON.parse(jsonText);
        console.log('JSON parsed successfully:', parsedQuestions);
      } catch (parseErr) {
        console.error('JSON parse error:', parseErr);
        setError('Invalid JSON format. Please check your syntax.');
        return;
      }

      // Validate it's an array
      if (!Array.isArray(parsedQuestions)) {
        console.error('Not an array:', parsedQuestions);
        setError('Invalid data: Expected an array of questions');
        return;
      }

      // Validate basic structure
      for (let i = 0; i < parsedQuestions.length; i++) {
        const q = parsedQuestions[i];
        if (typeof q.questionNumber === 'undefined' || q.questionNumber === null) {
          console.error('Invalid question at index', i, ':', q);
          setError(`Invalid question at index ${i}: Missing questionNumber`);
          return;
        }
        if (!q.parts || !Array.isArray(q.parts)) {
          console.error('Invalid parts at index', i, ':', q);
          setError(`Invalid question at index ${i}: Missing or invalid parts array`);
          return;
        }
      }

      console.log('Validation passed, saving to backend...');

      // Save to backend
      try {
        await updateMergedData(sessionId, parsedQuestions);
        console.log('Saved to backend successfully');
      } catch (saveErr: any) {
        console.error('Backend save error:', saveErr);
        console.error('Error response:', saveErr.response);
        console.error('Error data:', saveErr.response?.data);

        // Handle FastAPI validation errors (422)
        if (saveErr.response?.status === 422 && saveErr.response?.data?.detail) {
          const detail = saveErr.response.data.detail;
          console.error('Validation detail:', detail);

          if (Array.isArray(detail)) {
            // Format validation errors
            const errorMessages = detail.map((err: any) => {
              const location = err.loc ? err.loc.join(' -> ') : 'unknown';
              return `${location}: ${err.msg}`;
            }).join('\n');
            setError(`Validation error:\n${errorMessages}`);
            console.error('Formatted error messages:', errorMessages);
          } else if (typeof detail === 'string') {
            setError(detail);
          } else {
            setError('Validation error occurred');
          }
        } else {
          setError(saveErr.response?.data?.detail || saveErr.message || 'Failed to save to backend');
        }
        return;
      }

      // Update state with validated data
      console.log('Updating local state...');
      setMergedQuestions(parsedQuestions);

      // Keep jsonText in sync with saved data
      const formattedJson = JSON.stringify(parsedQuestions, null, 2);
      setJsonText(formattedJson);

      // Refresh statistics with complete data
      console.log('Fetching updated statistics...');
      try {
        const stats = await getMergeStatistics(sessionId);
        console.log('Statistics updated:', stats);
        setStatistics(stats);
      } catch (statsErr: any) {
        console.error('Statistics fetch error:', statsErr);
        // Don't fail the save if statistics fetch fails
      }

      console.log('Save complete!');
      setSuccess('Merged data saved successfully!');
    } catch (err: any) {
      console.error('Unexpected error in handleSaveJson:', err);
      setError(err.message || 'An unexpected error occurred');
    }
  };

  const toggleViewMode = () => {
    if (viewMode === 'visual') {
      setJsonText(JSON.stringify(mergedQuestions, null, 2));
      setViewMode('json');
    } else {
      setViewMode('visual');
    }
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Stage 4: Merge & Review
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2, whiteSpace: 'pre-wrap' }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      <Grid container spacing={3}>
        {mergedQuestions.length === 0 && (
          <Grid item xs={12}>
            <Paper sx={{ p: 3, textAlign: 'center' }}>
              <Typography variant="h6" gutterBottom>
                Merge Marking Schemes into Questions
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                This will match marking schemes with their corresponding question parts
              </Typography>
              <Button
                variant="contained"
                size="large"
                onClick={handleMerge}
                disabled={merging}
                startIcon={merging ? <CircularProgress size={20} /> : <PlayArrowIcon />}
              >
                {merging ? 'Merging...' : 'Start Merge'}
              </Button>
            </Paper>
          </Grid>
        )}

        {/* Statistics */}
        {statistics && (
          <>
            <Grid item xs={12} md={3}>
              <Card>
                <CardContent>
                  <Typography variant="h4" color="primary">
                    {statistics.total_questions}
                  </Typography>
                  <Typography color="text.secondary">Total Questions</Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={3}>
              <Card>
                <CardContent>
                  <Typography variant="h4" color="primary">
                    {statistics.total_parts}
                  </Typography>
                  <Typography color="text.secondary">Total Parts</Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={3}>
              <Card>
                <CardContent>
                  <Typography variant="h4" color="success.main">
                    {statistics.parts_with_schemes}
                  </Typography>
                  <Typography color="text.secondary">With Marking Schemes</Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12} md={3}>
              <Card>
                <CardContent>
                  <Typography variant="h4" color="primary">
                    {statistics.coverage_percentage.toFixed(1)}%
                  </Typography>
                  <Typography color="text.secondary">Coverage</Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Coverage Progress
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={statistics.coverage_percentage}
                    sx={{ height: 10, borderRadius: 5 }}
                  />
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    {statistics.parts_with_schemes} of {statistics.total_parts} parts have marking
                    schemes
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </>
        )}

        {/* View Mode Toggle */}
        {mergedQuestions.length > 0 && (
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              {/* <Button
                variant={viewMode === 'visual' ? 'contained' : 'outlined'}
                onClick={() => setViewMode('visual')}
                startIcon={<VisibilityIcon />}
              >
                Visual View
              </Button> */}
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
        {mergedQuestions.length > 0 && viewMode === 'json' && (
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Edit Merged Data JSON
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
                <Button
                  variant="contained"
                  startIcon={<DownloadIcon />}
                  onClick={handleDownload}
                  color="success"
                >
                  Download JSON
                </Button>
              </Box>
            </Paper>
          </Grid>
        )}

        {/* Merged Questions */}
        {/* {mergedQuestions.length > 0 && viewMode === 'visual' && mergedQuestions.slice(0, 5).map((question) => (
          <Grid item xs={12} key={question.questionNumber}>
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="h6">
                  Question {question.questionNumber} - {question.parts.length} parts
                  {question.parts.filter((p) => p.markingScheme).length > 0 && (
                    <CheckCircleIcon
                      sx={{ ml: 1, verticalAlign: 'middle' }}
                      color="success"
                      fontSize="small"
                    />
                  )}
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                {question.parts.map((part) => (
                  <Box key={part.partLabel} sx={{ mb: 2, p: 2, bgcolor: 'grey.50' }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Part ({part.partLabel}) - {part.marks} marks
                    </Typography>
                    <Typography variant="body2" paragraph>
                      <strong>Question:</strong> {part.text.substring(0, 150)}...
                    </Typography>
                    {part.markingScheme ? (
                      <Paper sx={{ p: 2, bgcolor: 'success.50' }}>
                        <Typography variant="body2" color="success.main">
                          <strong>Marking Scheme:</strong>
                        </Typography>
                        <Typography variant="body2">
                          {part.markingScheme.substring(0, 200)}...
                        </Typography>
                      </Paper>
                    ) : (
                      <Alert severity="warning" sx={{ mt: 1 }}>
                        No marking scheme found
                      </Alert>
                    )}
                  </Box>
                ))}
              </AccordionDetails>
            </Accordion>
          </Grid>
        ))} */}

        {/* {mergedQuestions.length > 5 && viewMode === 'visual' && (
          <Grid item xs={12}>
            <Typography variant="body2" color="text.secondary">
              Showing first 5 of {mergedQuestions.length} questions. Switch to JSON view or download to view all.
            </Typography>
          </Grid>
        )} */}

        {/* Navigation */}
        <Grid item xs={12}>
          <Box sx={{ display: 'flex', justifyContent: 'flex-start' }}>
            <Button variant="outlined" onClick={onBack} startIcon={<NavigateBeforeIcon />}>
              Back
            </Button>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
}
