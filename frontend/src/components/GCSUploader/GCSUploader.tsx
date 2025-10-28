import { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  TextField,
  CircularProgress,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Chip,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DownloadIcon from '@mui/icons-material/Download';
import ImageIcon from '@mui/icons-material/Image';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import axios from 'axios';

// Configure axios with base URL for production
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
});

interface UploadResult {
  work_id: string;
  uploaded_count: number;
  urls: string[];
  urls_file_url: string;
  message: string;
}

function GCSUploader() {
  const [files, setFiles] = useState<FileList | null>(null);
  const [subject, setSubject] = useState('');
  const [paperFolder, setPaperFolder] = useState('');
  const [subjects, setSubjects] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Fetch valid subjects
    api.get('/api/gcs-uploader/subjects')
      .then(response => setSubjects(response.data.subjects))
      .catch(err => console.error('Failed to fetch subjects', err));
  }, []);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      setFiles(event.target.files);
      setError(null);
      setResult(null);
    }
  };

  const handleUpload = async () => {
    if (!files || files.length === 0) {
      setError('Please select image files');
      return;
    }

    if (!subject) {
      setError('Please select a subject');
      return;
    }

    if (!paperFolder) {
      setError('Please enter paper folder name');
      return;
    }

    // Validate paper folder format
    const folderPattern = new RegExp(`^${subject}-\\d{4}-paper-\\d+$`);
    if (!folderPattern.test(paperFolder)) {
      setError(`Invalid paper folder format. Expected: ${subject}-Year-paper-Number (e.g., ${subject}-2025-paper-1)`);
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('subject', subject);
    formData.append('paper_folder', paperFolder);

    // Append all files
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }

    try {
      const response = await api.post('/api/gcs-uploader/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setResult(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadUrls = async () => {
    if (!result) return;

    try {
      const response = await api.get(result.urls_file_url, {
        responseType: 'blob',
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'uploaded_urls.txt');
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err: any) {
      setError('Download failed');
    }
  };

  const fileList = files ? Array.from(files) : [];

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h5" gutterBottom>
          Upload Images to Google Cloud Storage
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Upload extracted images to GCS and generate a list of public URLs
        </Typography>

        <Box sx={{ mb: 3 }}>
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Subject</InputLabel>
            <Select
              value={subject}
              label="Subject"
              onChange={(e) => setSubject(e.target.value)}
            >
              {subjects.map((subj) => (
                <MenuItem key={subj} value={subj}>
                  {subj}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <TextField
            fullWidth
            label="Paper Folder Name"
            placeholder={subject ? `${subject}-2025-paper-1` : 'Select subject first'}
            value={paperFolder}
            onChange={(e) => setPaperFolder(e.target.value)}
            helperText={`Format: ${subject || 'Subject'}-Year-paper-Number`}
            sx={{ mb: 2 }}
          />

          <input
            accept="image/*"
            style={{ display: 'none' }}
            id="image-upload"
            type="file"
            multiple
            onChange={handleFileChange}
          />
          <label htmlFor="image-upload">
            <Button
              variant="outlined"
              component="span"
              startIcon={<UploadFileIcon />}
              fullWidth
            >
              Select Images
            </Button>
          </label>

          {fileList.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" gutterBottom>
                Selected {fileList.length} file(s):
              </Typography>
              <Box sx={{ maxHeight: 200, overflow: 'auto', border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1 }}>
                {fileList.map((file, index) => (
                  <Chip
                    key={index}
                    icon={<ImageIcon />}
                    label={file.name}
                    size="small"
                    sx={{ m: 0.5 }}
                  />
                ))}
              </Box>
            </Box>
          )}
        </Box>

        <Button
          variant="contained"
          onClick={handleUpload}
          disabled={!files || !subject || !paperFolder || loading}
          startIcon={loading ? <CircularProgress size={20} /> : <CloudUploadIcon />}
          fullWidth
        >
          {loading ? 'Uploading...' : 'Upload to GCS'}
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
                Upload Successful
              </Typography>
              <Chip
                icon={<CheckCircleIcon />}
                label={`${result.uploaded_count} image(s) uploaded`}
                color="success"
              />
            </Box>
            <Button
              variant="contained"
              color="success"
              startIcon={<DownloadIcon />}
              onClick={handleDownloadUrls}
            >
              Download URLs (.txt)
            </Button>
          </Box>

          <Typography variant="subtitle1" gutterBottom sx={{ mt: 3 }}>
            Uploaded URLs:
          </Typography>
          <Paper variant="outlined" sx={{ p: 2, maxHeight: 400, overflow: 'auto', bgcolor: 'grey.50' }}>
            <List dense>
              {result.urls.map((url, index) => (
                <ListItem key={index}>
                  <ListItemIcon>
                    <ImageIcon fontSize="small" />
                  </ListItemIcon>
                  <ListItemText
                    primary={url}
                    primaryTypographyProps={{
                      variant: 'body2',
                      sx: { wordBreak: 'break-all', fontFamily: 'monospace' }
                    }}
                  />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Paper>
      )}
    </Box>
  );
}

export default GCSUploader;
