import { useState, useEffect } from 'react';
import { Routes, Route, useNavigate } from 'react-router-dom';
import {
  Container,
  Box,
  Stepper,
  Step,
  StepLabel,
  Paper,
  AppBar,
  Toolbar,
  Typography,
  Button,
} from '@mui/material';
import { createSession } from './services/api';
import Stage1 from './components/Stage1/Stage1';
import Stage2 from './components/Stage2/Stage2';
import Stage3 from './components/Stage3/Stage3';
import Stage4 from './components/Stage4/Stage4';
import ErrorBoundary from './components/common/ErrorBoundary';
import HomeIcon from '@mui/icons-material/Home';

const steps = [
  'Upload & Extract Text',
  'Extract Questions',
  'Extract Marking Schemes',
  'Merge & Review',
];

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeStep, setActiveStep] = useState(0);
  const navigate = useNavigate();

  useEffect(() => {
    // Create session on mount
    createSession().then((session) => {
      setSessionId(session.session_id);
      console.log('Session created:', session.session_id);
    });
  }, []);

  const handleNext = () => {
    const nextStep = activeStep + 1;
    setActiveStep(nextStep);
    navigate(`/stage${nextStep + 1}`);
  };

  const handleBack = () => {
    const prevStep = activeStep - 1;
    setActiveStep(prevStep);
    navigate(`/stage${prevStep + 1}`);
  };

  const handleStepClick = (step: number) => {
    setActiveStep(step);
    navigate(`/stage${step + 1}`);
  };

  const handleHome = () => {
    setActiveStep(0);
    navigate('/');
  };

  if (!sessionId) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
        }}
      >
        <Typography variant="h6">Initializing session...</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <AppBar position="static">
        <Toolbar>
          <Button color="inherit" startIcon={<HomeIcon />} onClick={handleHome}>
            PDF Processor
          </Button>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1, ml: 2 }}>
            Session: {sessionId.substring(0, 8)}...
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ mt: 4, mb: 4, flexGrow: 1 }}>
        <Paper sx={{ p: 3, mb: 3 }}>
          <Stepper activeStep={activeStep}>
            {steps.map((label, index) => (
              <Step key={label}>
                <StepLabel
                  onClick={() => handleStepClick(index)}
                  sx={{ cursor: 'pointer' }}
                >
                  {label}
                </StepLabel>
              </Step>
            ))}
          </Stepper>
        </Paper>

        <Routes>
          <Route
            path="/"
            element={
              <Stage1
                sessionId={sessionId}
                onNext={handleNext}
                onBack={handleBack}
              />
            }
          />
          <Route
            path="/stage1"
            element={
              <Stage1
                sessionId={sessionId}
                onNext={handleNext}
                onBack={handleBack}
              />
            }
          />
          <Route
            path="/stage2"
            element={
              <Stage2
                sessionId={sessionId}
                onNext={handleNext}
                onBack={handleBack}
              />
            }
          />
          <Route
            path="/stage3"
            element={
              <Stage3
                sessionId={sessionId}
                onNext={handleNext}
                onBack={handleBack}
              />
            }
          />
          <Route
            path="/stage4"
            element={
              <ErrorBoundary>
                <Stage4
                  sessionId={sessionId}
                  onNext={handleNext}
                  onBack={handleBack}
                />
              </ErrorBoundary>
            }
          />
        </Routes>
      </Container>

      <Box
        component="footer"
        sx={{
          py: 2,
          px: 2,
          mt: 'auto',
          backgroundColor: (theme) => theme.palette.grey[200],
        }}
      >
        <Container maxWidth="xl">
          <Typography variant="body2" color="text.secondary" align="center">
            PDF Processor - Process exam papers and marking schemes
          </Typography>
        </Container>
      </Box>
    </Box>
  );
}

export default App;
