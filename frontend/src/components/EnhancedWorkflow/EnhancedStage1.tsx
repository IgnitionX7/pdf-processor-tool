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
  const [figuresCount, setFiguresCount] = useState(0);
  const [tablesCount, setTablesCount] = useState(0);

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

  const handleProcess = async () => {
    setProcessing(true);
    setError(null);

    try {
      const processResult = await processEnhancedPdf(sessionId);
      setStatistics(processResult.statistics);

      const figuresTablesResult = await getEnhancedFiguresTables(sessionId);
      setElements(figuresTablesResult.elements);
      setFiguresCount(figuresTablesResult.figures_count);
      setTablesCount(figuresTablesResult.tables_count);

      setProcessed(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Processing failed');
    } finally {
      setProcessing(false);
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
              PDF uploaded successfully! Click below to process.
            </Alert>
            <Button
              variant="contained"
              onClick={handleProcess}
              disabled={processing}
              startIcon={processing ? <CircularProgress size={20} /> : <PlayArrowIcon />}
              fullWidth
            >
              {processing ? 'Processing PDF...' : 'Process PDF'}
            </Button>
            {processing && (
              <Box sx={{ mt: 2 }}>
                <LinearProgress />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                  Extracting figures, tables, and text... This may take a moment.
                </Typography>
              </Box>
            )}
          </Box>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
      </Paper>

      {/* Results Section */}
      {processed && (
        <>
          {/* Statistics */}
          {statistics && (
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                Extraction Statistics
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom>
                        Figures & Tables
                      </Typography>
                      <Typography variant="h4">{statistics.total_figures}</Typography>
                    </CardContent>
                  </Card>
                </Grid>
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
                      <Typography variant="h4">{statistics.total_chars_after.toLocaleString()}</Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography color="text.secondary" gutterBottom>
                        Filter Efficiency
                      </Typography>
                      <Typography variant="h4">{statistics.filter_percentage.toFixed(1)}%</Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            </Paper>
          )}

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
                endIcon={<ArrowForwardIcon />}
              >
                See Extracted Questions
              </Button>
            </Box>
          </Paper>
        </>
      )}
    </Box>
  );
}

export default EnhancedStage1;
