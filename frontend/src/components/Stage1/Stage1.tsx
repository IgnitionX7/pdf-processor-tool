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
} from '@mui/material';
import { useDropzone } from 'react-dropzone';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import JsonEditor from '../common/JsonEditor';
import {
  uploadQuestionPaper,
  extractText,
  getText,
  updateCleanedText,
  downloadText,
} from '../../services/api';

interface Stage1Props {
  sessionId: string;
  onNext: () => void;
  onBack: () => void;
}

export default function Stage1({ sessionId, onNext }: Stage1Props) {
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [cleanedText, setCleanedText] = useState('');
  const [stats, setStats] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'application/pdf': ['.pdf'],
    },
    maxFiles: 1,
    onDrop: async (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        const file = acceptedFiles[0];
        setUploadedFile(file);
        setError(null);
        setSuccess(null);

        try {
          setUploading(true);
          await uploadQuestionPaper(sessionId, file);
          setSuccess(`Uploaded: ${file.name}`);
        } catch (err: any) {
          setError(err.response?.data?.detail || 'Upload failed');
        } finally {
          setUploading(false);
        }
      }
    },
  });

  const handleExtractText = async () => {
    try {
      setExtracting(true);
      setError(null);

      const response = await extractText(sessionId);
      setStats(response.stats);

      const text = await getText(sessionId, 'cleaned');
      setCleanedText(text);

      setSuccess('Text extracted successfully!');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Extraction failed');
    } finally {
      setExtracting(false);
    }
  };

  const handleSaveText = async () => {
    try {
      await updateCleanedText(sessionId, cleanedText);
      setSuccess('Text saved successfully!');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Save failed');
    }
  };

  const handleDownload = () => {
    window.open(downloadText(sessionId, 'cleaned'), '_blank');
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Stage 1: Upload & Extract Text
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
              1. Upload Question Paper PDF
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
                '&:hover': {
                  bgcolor: 'action.hover',
                },
              }}
            >
              <input {...getInputProps()} />
              <UploadFileIcon sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
              <Typography variant="h6" gutterBottom>
                {isDragActive
                  ? 'Drop the PDF here'
                  : uploadedFile
                  ? uploadedFile.name
                  : 'Drag & drop PDF here, or click to select'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Accepts .pdf files only
              </Typography>
            </Box>

            {uploading && (
              <Box sx={{ mt: 2, textAlign: 'center' }}>
                <CircularProgress />
                <Typography variant="body2" sx={{ mt: 1 }}>
                  Uploading...
                </Typography>
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Extract Button */}
        {uploadedFile && !cleanedText && (
          <Grid item xs={12}>
            <Button
              variant="contained"
              size="large"
              fullWidth
              onClick={handleExtractText}
              disabled={extracting}
              startIcon={extracting ? <CircularProgress size={20} /> : <PlayArrowIcon />}
            >
              {extracting ? 'Extracting...' : 'Extract Text'}
            </Button>
          </Grid>
        )}

        {/* Statistics */}
        {stats && (
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Raw Text Statistics
                </Typography>
                <Typography>Pages: {stats.raw.pages}</Typography>
                <Typography>Words: {stats.raw.total_words.toLocaleString()}</Typography>
                <Typography>
                  Characters: {stats.raw.total_characters.toLocaleString()}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        )}

        {stats && (
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Cleaned Text Statistics
                </Typography>
                <Typography>Kept Pages: {stats.cleaned.kept_pages}</Typography>
                <Typography>Words: {stats.cleaned.total_words.toLocaleString()}</Typography>
                <Typography>
                  Characters: {stats.cleaned.total_characters.toLocaleString()}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Text Editor */}
        {cleanedText && (
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                2. Review & Edit Cleaned Text
              </Typography>

              <JsonEditor
                value={cleanedText}
                onChange={setCleanedText}
                height="500px"
                language="plaintext"
              />

              <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
                <Button variant="outlined" onClick={handleSaveText}>
                  Save Changes
                </Button>
                <Button variant="outlined" startIcon={<CloudDownloadIcon />} onClick={handleDownload}>
                  Download
                </Button>
              </Box>
            </Paper>
          </Grid>
        )}

        {/* Navigation */}
        {cleanedText && (
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button
                variant="contained"
                size="large"
                onClick={onNext}
                endIcon={<NavigateNextIcon />}
              >
                Next: Extract Questions
              </Button>
            </Box>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}
