import { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  CircularProgress,
  Alert,
  Chip,
  Divider,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import MergeTypeIcon from '@mui/icons-material/MergeType';
import DownloadIcon from '@mui/icons-material/Download';
import DescriptionIcon from '@mui/icons-material/Description';
import axios from 'axios';
import JsonEditor from '../common/JsonEditor';

// Configure axios with base URL for production
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
});

interface MergeResult {
  work_id: string;
  output_filename: string;
  merged_data: any;
  download_url: string;
  message: string;
}

function URLMerger() {
  const [questionsFile, setQuestionsFile] = useState<File | null>(null);
  const [urlsFile, setUrlsFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MergeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editedJson, setEditedJson] = useState<string>('');

  const handleQuestionsFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      const file = event.target.files[0];
      if (!file.name.endsWith('.json')) {
        setError('Please select a JSON file for questions');
        return;
      }
      setQuestionsFile(file);
      setError(null);
      setResult(null);
    }
  };

  const handleUrlsFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      const file = event.target.files[0];
      if (!file.name.endsWith('.txt')) {
        setError('Please select a TXT file for URLs');
        return;
      }
      setUrlsFile(file);
      setError(null);
      setResult(null);
    }
  };

  const handleMerge = async () => {
    if (!questionsFile) {
      setError('Please select a questions JSON file');
      return;
    }

    if (!urlsFile) {
      setError('Please select a URLs TXT file');
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('questions_file', questionsFile);
    formData.append('urls_file', urlsFile);

    try {
      const response = await api.post('/api/url-merger/merge', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setResult(response.data);
      setEditedJson(JSON.stringify(response.data.merged_data, null, 2));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Merge failed');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!result) return;

    try {
      // Create a Blob from the edited JSON
      const blob = new Blob([editedJson], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', result.output_filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError('Download failed');
    }
  };

  const handleJsonChange = (value: string) => {
    setEditedJson(value);
  };

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h5" gutterBottom>
          Merge Image URLs to Questions JSON
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Merge image URLs from a text file into the corresponding questions in your JSON file
        </Typography>

        <Box sx={{ mb: 3 }}>
          <Box sx={{ mb: 2 }}>
            <input
              accept=".json"
              style={{ display: 'none' }}
              id="questions-upload"
              type="file"
              onChange={handleQuestionsFileChange}
            />
            <label htmlFor="questions-upload">
              <Button
                variant="outlined"
                component="span"
                startIcon={<UploadFileIcon />}
                fullWidth
              >
                Select Questions JSON File
              </Button>
            </label>
            {questionsFile && (
              <Chip
                icon={<DescriptionIcon />}
                label={questionsFile.name}
                color="primary"
                sx={{ mt: 1 }}
              />
            )}
          </Box>

          <Box sx={{ mb: 2 }}>
            <input
              accept=".txt"
              style={{ display: 'none' }}
              id="urls-upload"
              type="file"
              onChange={handleUrlsFileChange}
            />
            <label htmlFor="urls-upload">
              <Button
                variant="outlined"
                component="span"
                startIcon={<UploadFileIcon />}
                fullWidth
              >
                Select URLs TXT File
              </Button>
            </label>
            {urlsFile && (
              <Chip
                icon={<DescriptionIcon />}
                label={urlsFile.name}
                color="secondary"
                sx={{ mt: 1 }}
              />
            )}
          </Box>
        </Box>

        <Button
          variant="contained"
          onClick={handleMerge}
          disabled={!questionsFile || !urlsFile || loading}
          startIcon={loading ? <CircularProgress size={20} /> : <MergeTypeIcon />}
          fullWidth
        >
          {loading ? 'Merging...' : 'Merge URLs into Questions'}
        </Button>

        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </Paper>

      {result && (
        <Paper sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">
              Merged Result
            </Typography>
            <Button
              variant="contained"
              color="success"
              startIcon={<DownloadIcon />}
              onClick={handleDownload}
            >
              Download JSON
            </Button>
          </Box>

          <Alert severity="success" sx={{ mb: 2 }}>
            {result.message}
          </Alert>

          <Divider sx={{ my: 2 }} />

          <Typography variant="subtitle1" gutterBottom>
            Preview & Edit:
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            You can edit the JSON below before downloading
          </Typography>

          <JsonEditor
            value={editedJson}
            onChange={handleJsonChange}
            height="500px"
          />
        </Paper>
      )}
    </Box>
  );
}

export default URLMerger;
