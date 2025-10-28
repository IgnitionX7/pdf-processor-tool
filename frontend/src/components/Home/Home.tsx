import { Box, Card, CardContent, CardActionArea, Typography, Grid, Container } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import QuestionAnswerIcon from '@mui/icons-material/QuestionAnswer';
import ImageIcon from '@mui/icons-material/Image';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import MergeTypeIcon from '@mui/icons-material/MergeType';

const options = [
  {
    id: 'questions-extractor',
    title: 'Questions Extractor',
    description: '4-stage pipeline to extract questions and marking schemes from PDF papers',
    icon: QuestionAnswerIcon,
    route: '/stage1',
    color: '#1976d2',
  },
  {
    id: 'figure-extractor',
    title: 'Figure & Table Extractor',
    description: 'Extract figures and tables from PDFs as high-resolution images',
    icon: ImageIcon,
    route: '/figure-extractor',
    color: '#2e7d32',
  },
  {
    id: 'gcs-uploader',
    title: 'Upload Images to GCS',
    description: 'Upload extracted images to Google Cloud Storage and get URLs',
    icon: CloudUploadIcon,
    route: '/gcs-uploader',
    color: '#ed6c02',
  },
  {
    id: 'url-merger',
    title: 'Merge URLs to Questions',
    description: 'Merge image URLs from GCS into questions JSON file',
    icon: MergeTypeIcon,
    route: '/url-merger',
    color: '#9c27b0',
  },
];

function Home() {
  const navigate = useNavigate();

  return (
    <Container maxWidth="xl">
      <Box sx={{ mt: 4, mb: 4 }}>
        <Typography variant="h3" component="h1" gutterBottom align="center">
          PDF Processor Tool
        </Typography>
        <Typography variant="h6" color="text.secondary" align="center" sx={{ mb: 6 }}>
          Choose a processing option below
        </Typography>

        <Grid container spacing={3}>
          {options.map((option) => {
            const IconComponent = option.icon;
            return (
              <Grid item xs={12} sm={6} md={3} key={option.id}>
                <Card
                  sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    transition: 'transform 0.2s, box-shadow 0.2s',
                    '&:hover': {
                      transform: 'translateY(-4px)',
                      boxShadow: 6,
                    },
                  }}
                >
                  <CardActionArea
                    onClick={() => navigate(option.route)}
                    sx={{
                      height: '100%',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'stretch',
                      justifyContent: 'flex-start',
                    }}
                  >
                    <Box
                      sx={{
                        width: '100%',
                        bgcolor: option.color,
                        py: 3,
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                      }}
                    >
                      <IconComponent sx={{ fontSize: 64, color: 'white' }} />
                    </Box>
                    <CardContent sx={{ flexGrow: 1 }}>
                      <Typography gutterBottom variant="h5" component="h2">
                        {option.title}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {option.description}
                      </Typography>
                    </CardContent>
                  </CardActionArea>
                </Card>
              </Grid>
            );
          })}
        </Grid>
      </Box>
    </Container>
  );
}

export default Home;
