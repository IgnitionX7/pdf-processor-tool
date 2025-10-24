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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
} from '@mui/material';
import { useDropzone } from 'react-dropzone';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import CodeIcon from '@mui/icons-material/Code';
import VisibilityIcon from '@mui/icons-material/Visibility';
import SaveIcon from '@mui/icons-material/Save';
import JsonEditor from '../common/JsonEditor';
import {
  uploadMarkingScheme,
  extractMarkingSchemes,
  updateMarkingSchemes,
  downloadMarkingSchemes,
} from '../../services/api';
import type { MarkingSchemes } from '../../types';

interface Stage3Props {
  sessionId: string;
  onNext: () => void;
  onBack: () => void;
}

export default function Stage3({ sessionId, onNext, onBack }: Stage3Props) {
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [startPage, setStartPage] = useState(8);
  const [markingSchemes, setMarkingSchemes] = useState<MarkingSchemes>({});
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'visual' | 'json'>('visual');
  const [jsonText, setJsonText] = useState('');

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    onDrop: async (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        const file = acceptedFiles[0];
        setUploadedFile(file);
        setError(null);

        try {
          setUploading(true);
          await uploadMarkingScheme(sessionId, file);
          setSuccess(`Uploaded: ${file.name}`);
        } catch (err: any) {
          setError(err.response?.data?.detail || 'Upload failed');
        } finally {
          setUploading(false);
        }
      }
    },
  });

  const handleExtract = async () => {
    try {
      setExtracting(true);
      setError(null);

      const response = await extractMarkingSchemes(sessionId, startPage);
      setMarkingSchemes(response.stats.marking_schemes);
      setJsonText(JSON.stringify(response.stats.marking_schemes, null, 2));
      setSuccess(`Extracted ${response.stats.total_entries} marking scheme entries`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Extraction failed');
    } finally {
      setExtracting(false);
    }
  };

  const handleDownload = () => {
    window.open(downloadMarkingSchemes(sessionId), '_blank');
  };

  const handleSaveJson = async () => {
    try {
      const parsedSchemes = JSON.parse(jsonText);
      await updateMarkingSchemes(sessionId, parsedSchemes);
      setMarkingSchemes(parsedSchemes);
      setSuccess('Marking schemes saved successfully!');
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
      setJsonText(JSON.stringify(markingSchemes, null, 2));
      setViewMode('json');
    } else {
      setViewMode('visual');
    }
  };

  const entries = Object.entries(markingSchemes);

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Stage 3: Extract Marking Schemes
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
        {/* Upload Section */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              1. Upload Marking Scheme PDF
            </Typography>

            <Box
              {...getRootProps()}
              sx={{
                border: '2px dashed',
                borderColor: isDragActive ? 'primary.main' : 'grey.400',
                borderRadius: 2,
                p: 4,
                textAlign: 'center',
                cursor: 'pointer',
                bgcolor: isDragActive ? 'action.hover' : 'background.paper',
              }}
            >
              <input {...getInputProps()} />
              <UploadFileIcon sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
              <Typography variant="h6">
                {uploadedFile ? uploadedFile.name : 'Upload Marking Scheme PDF'}
              </Typography>
            </Box>

            {uploading && (
              <Box sx={{ mt: 2, textAlign: 'center' }}>
                <CircularProgress />
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Extract Section */}
        {uploadedFile && entries.length === 0 && (
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                2. Extract Marking Schemes
              </Typography>
              <TextField
                label="Start Page"
                type="number"
                value={startPage}
                onChange={(e) => setStartPage(parseInt(e.target.value))}
                sx={{ mb: 2, mr: 2 }}
              />
              <Button
                variant="contained"
                onClick={handleExtract}
                disabled={extracting}
                startIcon={extracting ? <CircularProgress size={20} /> : <PlayArrowIcon />}
              >
                {extracting ? 'Extracting...' : 'Extract'}
              </Button>
            </Paper>
          </Grid>
        )}

        {/* View Mode Toggle */}
        {entries.length > 0 && (
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <Button
                variant={viewMode === 'visual' ? 'contained' : 'outlined'}
                onClick={() => setViewMode('visual')}
                startIcon={<VisibilityIcon />}
              >
                Table View
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
        {entries.length > 0 && viewMode === 'json' && (
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Edit Marking Schemes JSON
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

        {/* Results Table */}
        {entries.length > 0 && viewMode === 'visual' && (
          <>
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Extracted {entries.length} Marking Scheme Entries
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12}>
              <TableContainer component={Paper}>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Reference</TableCell>
                      <TableCell>Marking Scheme</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {entries.slice(0, 20).map(([ref, scheme]) => (
                      <TableRow key={ref}>
                        <TableCell>{ref}</TableCell>
                        <TableCell>
                          {scheme.length > 100 ? scheme.substring(0, 100) + '...' : scheme}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
              {entries.length > 20 && (
                <Typography variant="body2" sx={{ mt: 1 }} color="text.secondary">
                  Showing first 20 of {entries.length} entries
                </Typography>
              )}
            </Grid>
          </>
        )}

        {/* Navigation */}
        <Grid item xs={12}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Button variant="outlined" onClick={onBack} startIcon={<NavigateBeforeIcon />}>
              Back
            </Button>
            {entries.length > 0 && (
              <Button variant="contained" onClick={onNext} endIcon={<NavigateNextIcon />}>
                Next: Merge & Review
              </Button>
            )}
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
}
