import { useState } from 'react';
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
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import DownloadIcon from '@mui/icons-material/Download';
import ImageIcon from '@mui/icons-material/Image';
import TableChartIcon from '@mui/icons-material/TableChart';
import axios from 'axios';

// Configure axios with base URL for production
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
});

interface ExtractionResult {
  work_id: string;
  total_figures: number;
  total_tables: number;
  figures: Array<{
    fig_num: string;
    filename: string;
    page: number;
    caption: string;
  }>;
  tables: Array<{
    table_num: string;
    filename: string;
    page: number;
    caption: string;
  }>;
  download_url: string;
  zip_base64?: string;  // ZIP file as base64 for immediate download
  zip_filename?: string;  // ZIP filename
  message: string;
}

function FigureExtractor() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      setFile(event.target.files[0]);
      setError(null);
      setResult(null);
    }
  };

  const handleExtract = async () => {
    if (!file) {
      setError('Please select a PDF file');
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await api.post('/api/figure-extractor/extract', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setResult(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Extraction failed');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!result) return;

    try {
      // Prefer using base64 ZIP data if available (from extraction response)
      if (result.zip_base64 && result.zip_filename) {
        // Convert base64 to blob and download
        const binaryString = atob(result.zip_base64);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
          bytes[i] = binaryString.charCodeAt(i);
        }
        const blob = new Blob([bytes], { type: 'application/zip' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', result.zip_filename);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      } else {
        // Fallback to API download endpoint
        const response = await api.get(result.download_url, {
          responseType: 'blob',
        });

        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `extracted_images_${result.work_id}.zip`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      }
    } catch (err: any) {
      setError('Download failed: ' + (err.response?.data?.detail || err.message || 'Unknown error'));
      console.error('Download error:', err);
    }
  };

  const getImageUrl = (workId: string, filename: string) => {
    return `/api/figure-extractor/image/${workId}/${filename}`;
  };

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h5" gutterBottom>
          Figure & Table Extractor
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Upload a PDF to extract figures and tables as high-resolution images
        </Typography>

        <Box sx={{ mb: 3 }}>
          <input
            accept="application/pdf"
            style={{ display: 'none' }}
            id="pdf-upload"
            type="file"
            onChange={handleFileChange}
          />
          <label htmlFor="pdf-upload">
            <Button
              variant="outlined"
              component="span"
              startIcon={<UploadFileIcon />}
              sx={{ mr: 2 }}
            >
              Select PDF
            </Button>
          </label>
          {file && (
            <Typography variant="body2" component="span">
              Selected: {file.name}
            </Typography>
          )}
        </Box>

        <Button
          variant="contained"
          onClick={handleExtract}
          disabled={!file || loading}
          startIcon={loading ? <CircularProgress size={20} /> : <ImageIcon />}
        >
          {loading ? 'Extracting...' : 'Extract Figures & Tables'}
        </Button>

        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </Paper>

      {result && (
        <Paper sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Box>
              <Typography variant="h6" gutterBottom>
                Extraction Results
              </Typography>
              <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                <Chip
                  icon={<ImageIcon />}
                  label={`${result.total_figures} Figure(s)`}
                  color="primary"
                />
                <Chip
                  icon={<TableChartIcon />}
                  label={`${result.total_tables} Table(s)`}
                  color="secondary"
                />
              </Box>
            </Box>
            <Button
              variant="contained"
              color="success"
              startIcon={<DownloadIcon />}
              onClick={handleDownload}
            >
              Download All (ZIP)
            </Button>
          </Box>

          {result.figures.length > 0 && (
            <Box sx={{ mb: 4 }}>
              <Typography variant="h6" gutterBottom>
                Figures
              </Typography>
              <Grid container spacing={2}>
                {result.figures.map((fig) => (
                  <Grid item xs={12} sm={6} md={4} key={fig.filename}>
                    <Card>
                      <CardMedia
                        component="img"
                        image={getImageUrl(result.work_id, fig.filename)}
                        alt={`Fig. ${fig.fig_num}`}
                        sx={{ height: 200, objectFit: 'contain', bgcolor: 'grey.100', p: 1 }}
                        onError={(e: any) => {
                          e.target.style.display = 'none';
                          const parent = e.target.parentElement;
                          if (parent) {
                            const errorDiv = document.createElement('div');
                            errorDiv.style.padding = '20px';
                            errorDiv.style.textAlign = 'center';
                            errorDiv.style.color = '#666';
                            errorDiv.textContent = 'Image not available';
                            parent.appendChild(errorDiv);
                          }
                        }}
                      />
                      <CardContent>
                        <Typography variant="subtitle1" gutterBottom>
                          Fig. {fig.fig_num}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Page {fig.page}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {fig.caption}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </Box>
          )}

          {result.tables.length > 0 && (
            <Box>
              <Typography variant="h6" gutterBottom>
                Tables
              </Typography>
              <Grid container spacing={2}>
                {result.tables.map((table) => (
                  <Grid item xs={12} sm={6} md={4} key={table.filename}>
                    <Card>
                      <CardMedia
                        component="img"
                        image={getImageUrl(result.work_id, table.filename)}
                        alt={`Table ${table.table_num}`}
                        sx={{ height: 200, objectFit: 'contain', bgcolor: 'grey.100', p: 1 }}
                        onError={(e: any) => {
                          e.target.style.display = 'none';
                          const parent = e.target.parentElement;
                          if (parent) {
                            const errorDiv = document.createElement('div');
                            errorDiv.style.padding = '20px';
                            errorDiv.style.textAlign = 'center';
                            errorDiv.style.color = '#666';
                            errorDiv.textContent = 'Image not available';
                            parent.appendChild(errorDiv);
                          }
                        }}
                      />
                      <CardContent>
                        <Typography variant="subtitle1" gutterBottom>
                          Table {table.table_num}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Page {table.page}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {table.caption}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </Box>
          )}
        </Paper>
      )}
    </Box>
  );
}

export default FigureExtractor;
