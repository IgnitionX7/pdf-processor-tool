import { useState, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  CircularProgress,
  Alert,
  Grid,
  Card,
  CardMedia,
  CardContent,
  Chip,
  LinearProgress,
  FormControlLabel,
  Switch,
} from '@mui/material';
import { useDropzone } from 'react-dropzone';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import DownloadIcon from '@mui/icons-material/Download';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import ImageIcon from '@mui/icons-material/Image';
import TableChartIcon from '@mui/icons-material/TableChart';
import {
  uploadPdfForEnhanced,
  processEnhancedPdf,
  extractTextWithExclusions,
  getEnhancedProcessingStatus,
  getEnhancedFiguresTables,
  downloadEnhancedFiguresZip,
} from '../../services/api';
import type {
  ExtractedElement,
  EnhancedProcessingStatistics,
} from '../../types';

interface EnhancedStage1Props {
  sessionId: string;
  onNext: () => void;
}

function EnhancedStage1({ sessionId, onNext }: EnhancedStage1Props) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [uploaded, setUploaded] = useState(false);
  const [processed, setProcessed] = useState(false);
  const [elements, setElements] = useState<ExtractedElement[]>([]);
  const [statistics, setStatistics] = useState<EnhancedProcessingStatistics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [figuresCount, setFiguresCount] = useState(0);
  const [tablesCount, setTablesCount] = useState(0);
  const [excludeFigures, setExcludeFigures] = useState(true);  // Default to enabled
  const [excludeTables, setExcludeTables] = useState(true);    // Default to enabled
  const [extractingText, setExtractingText] = useState(false);  // Phase 2 state
  const [textExtracted, setTextExtracted] = useState(false);    // Phase 2 completion

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0]);
      setError(null);
      setUploaded(false);
      setProcessed(false);
      setElements([]);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
    },
    multiple: false,
  });

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      await uploadPdfForEnhanced(sessionId, file);
      setUploaded(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };
 console.log("statistics", statistics);
  const handleProcess = async () => {
    setProcessing(true);
    setError(null);
    setSuccess(null);

    try {
      // Start Phase 1 background processing (figures/tables only, no exclusion parameters)
      await processEnhancedPdf(sessionId);

      // Poll for status every 2 seconds
      const pollStatus = async () => {
        try {
          const statusResult = await getEnhancedProcessingStatus(sessionId);

          if (statusResult.status === 'completed') {
            // Phase 1 complete - fetch figures/tables
            setStatistics(statusResult.statistics || {});

            const figuresTablesResult = await getEnhancedFiguresTables(sessionId);
            setElements(figuresTablesResult.elements);
            setFiguresCount(figuresTablesResult.figures_count);
            setTablesCount(figuresTablesResult.tables_count);

            setProcessed(true);
            setProcessing(false);
            setSuccess('Figures and tables extracted! Review them and then extract text.');
          } else if (statusResult.status === 'error') {
            setError(statusResult.error || 'Phase 1 processing failed');
            setProcessing(false);
          } else if (statusResult.status === 'processing') {
            // Still processing - poll again after 2 seconds
            setTimeout(pollStatus, 2000);
          }
        } catch (err: any) {
          setError(err.response?.data?.detail || 'Failed to check status');
          setProcessing(false);
        }
      };

      // Start polling after 2 seconds
      setTimeout(pollStatus, 2000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Phase 1 processing failed');
      setProcessing(false);
    }
  };

  const handleExtractText = async () => {
    setExtractingText(true);
    setError(null);
    setSuccess(null);

    try {
      // Start Phase 2 background processing (text extraction with exclusion zones)
      await extractTextWithExclusions(sessionId, excludeFigures, excludeTables);

      // Poll for status every 2 seconds
      const pollStatus = async () => {
        try {
          const statusResult = await getEnhancedProcessingStatus(sessionId);

          if (statusResult.status === 'completed') {
            // Phase 2 complete - update statistics with Phase 2 data
            if (statusResult.statistics) {
              setStatistics(statusResult.statistics);
            }

            setTextExtracted(true);
            setExtractingText(false);
            setSuccess(
              `Text extraction complete! Exclusions: Figures ${excludeFigures ? 'ON' : 'OFF'}, Tables ${excludeTables ? 'ON' : 'OFF'}`
            );
          } else if (statusResult.status === 'error') {
            setError(statusResult.error || 'Phase 2 text extraction failed');
            setExtractingText(false);
          } else if (statusResult.status === 'processing') {
            // Still processing - poll again after 2 seconds
            setTimeout(pollStatus, 2000);
          }
        } catch (err: any) {
          setError(err.response?.data?.detail || 'Failed to check status');
          setExtractingText(false);
        }
      };

      // Start polling after 2 seconds
      setTimeout(pollStatus, 2000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Text extraction failed');
      setExtractingText(false);
    }
  };

  const handleDownload = () => {
    const url = downloadEnhancedFiguresZip(sessionId);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'figures_tables.zip');
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h5" gutterBottom>
          Enhanced Combined Extractor - Upload & Process
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Upload your question paper PDF. The enhanced extractor will extract figures, tables, and questions with LaTeX notation support.
        </Typography>

        {/* File Upload */}
        {!uploaded && (
          <Box
            {...getRootProps()}
            sx={{
              border: '2px dashed',
              borderColor: isDragActive ? 'primary.main' : 'grey.300',
              borderRadius: 2,
              p: 4,
              textAlign: 'center',
              bgcolor: isDragActive ? 'action.hover' : 'background.default',
              cursor: 'pointer',
              mb: 2,
            }}
          >
            <input {...getInputProps()} />
            <CloudUploadIcon sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
            <Typography variant="h6" gutterBottom>
              {isDragActive ? 'Drop the PDF here' : 'Drag & drop a PDF here, or click to select'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {file ? `Selected: ${file.name}` : 'No file selected'}
            </Typography>
          </Box>
        )}

        {file && !uploaded && (
          <Button
            variant="contained"
            onClick={handleUpload}
            disabled={uploading}
            startIcon={uploading ? <CircularProgress size={20} /> : <CloudUploadIcon />}
            fullWidth
            sx={{ mb: 2 }}
          >
            {uploading ? 'Uploading...' : 'Upload PDF'}
          </Button>
        )}

        {/* Process Button */}
        {uploaded && !processed && (
          <Box sx={{ mb: 2 }}>
            <Alert severity="success" sx={{ mb: 2 }}>
              PDF uploaded successfully! Click process to extract figures and tables.
            </Alert>

            <Button
              variant="contained"
              onClick={handleProcess}
              disabled={processing}
              startIcon={processing ? <CircularProgress size={20} /> : <PlayArrowIcon />}
              fullWidth
            >
              {processing ? 'Extracting Figures & Tables...' : 'Extract Figures & Tables'}
            </Button>
            {processing && (
              <Box sx={{ mt: 2 }}>
                <LinearProgress />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                  Extracting figures and tables... This may take a moment.
                </Typography>
              </Box>
            )}
          </Box>
        )}

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
      </Paper>

      {/* Results Section */}
      {processed && (
        <>
          {/* Statistics */}
          {/* {statistics && (
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                Extraction Statistics
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom>
                        Total Figures
                      </Typography>
                      <Typography variant="h4">{statistics.total_figures || 0}</Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom>
                        Total Tables
                      </Typography>
                      <Typography variant="h4">{statistics.total_tables || 0}</Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom>
                        Total Pages
                      </Typography>
                      <Typography variant="h4">{statistics.total_pages || 0}</Typography>
                    </CardContent>
                  </Card>
                </Grid>
                {textExtracted && statistics.pages_with_text !== undefined && (
                  <>
                    <Grid item xs={12} sm={6} md={3}>
                      <Card variant="outlined">
                        <CardContent>
                          <Typography color="text.secondary" gutterBottom>
                            Pages with Text
                          </Typography>
                          <Typography variant="h4">{statistics.pages_with_text}</Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                      <Card variant="outlined">
                        <CardContent>
                          <Typography color="text.secondary" gutterBottom>
                            Characters Extracted
                          </Typography>
                          <Typography variant="h4">{statistics.total_chars?.toLocaleString() || 0}</Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                      <Card variant="outlined">
                        <CardContent>
                          <Typography color="text.secondary" gutterBottom>
                            Filter Efficiency
                          </Typography>
                          <Typography variant="h4">{statistics.filter_percentage?.toFixed(1) || 0}%</Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                  </>
                )}
              </Grid>
            </Paper>
          )} */}

          

          {/* Figures and Tables */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                Extracted Figures & Tables
              </Typography>
              <Box>
                <Chip
                  icon={<ImageIcon />}
                  label={`${figuresCount} Figures`}
                  color="primary"
                  sx={{ mr: 1 }}
                />
                <Chip
                  icon={<TableChartIcon />}
                  label={`${tablesCount} Tables`}
                  color="secondary"
                />
              </Box>
            </Box>

            {elements.length === 0 ? (
              <Alert severity="info">No figures or tables found in the PDF.</Alert>
            ) : (
              <Grid container spacing={2}>
                {elements.map((element, index) => (
                  <Grid item xs={12} sm={6} md={4} key={index}>
                    <Card>
                      {element.imageData && (
                        <CardMedia
                          component="img"
                          image={element.imageData}
                          alt={element.caption || element.filename}
                          sx={{ height: 200, objectFit: 'contain', bgcolor: 'grey.100' }}
                        />
                      )}
                      <CardContent>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Chip
                            size="small"
                            label={element.type}
                            color={element.type === 'figure' ? 'primary' : 'secondary'}
                          />
                          <Chip size="small" label={`Page ${element.page}`} variant="outlined" />
                        </Box>
                        <Typography variant="body2" color="text.secondary">
                          {element.caption || element.filename}
                        </Typography>
                        {element.source && (
                          <Typography variant="caption" color="text.secondary">
                            Source: {element.source}
                          </Typography>
                        )}
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            )}

            {/* Phase 2: Text Extraction Controls */}
          {!textExtracted && (
            <Paper variant="outlined" sx={{ p: 3, mb: 3, bgcolor: 'info.50' }}>
              <Typography variant="h6" gutterBottom>
                Step 2: Extract Text
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Review the extracted figures and tables below. Choose whether to exclude these regions during text extraction.
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 2 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={excludeFigures}
                      onChange={(e) => setExcludeFigures(e.target.checked)}
                      disabled={extractingText}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body1">Exclude Figure Regions</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Remove text from figure bounding boxes
                      </Typography>
                    </Box>
                  }
                />

                <FormControlLabel
                  control={
                    <Switch
                      checked={excludeTables}
                      onChange={(e) => setExcludeTables(e.target.checked)}
                      disabled={extractingText}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body1">Exclude Table Regions</Typography>
                      <Typography variant="caption" color="text.secondary">
                        Remove text from table bounding boxes
                      </Typography>
                    </Box>
                  }
                />
              </Box>

              <Button
                variant="contained"
                size="large"
                onClick={handleExtractText}
                disabled={extractingText}
                startIcon={extractingText ? <CircularProgress size={20} /> : <PlayArrowIcon />}
                fullWidth
              >
                {extractingText ? 'Extracting Text...' : 'Extract Text'}
              </Button>

              {extractingText && (
                <Box sx={{ mt: 2 }}>
                  <LinearProgress />
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                    Extracting text with your chosen exclusion settings...
                  </Typography>
                </Box>
              )}
            </Paper>
          )}

          {textExtracted && (
            <Alert severity="success" sx={{ mb: 2 }}>
              Text extraction complete! Proceed to Stage 2 to review the extracted text.
            </Alert>
          )}

            <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
              <Button
                variant="outlined"
                onClick={handleDownload}
                startIcon={<DownloadIcon />}
              >
                Download All as ZIP
              </Button>
              <Button
                variant="contained"
                onClick={onNext}
                disabled={!textExtracted}
                endIcon={<ArrowForwardIcon />}
              >
                Review Extracted Text
              </Button>
            </Box>
          </Paper>
        </>
      )}
    </Box>
  );
}

export default EnhancedStage1;
