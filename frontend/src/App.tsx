import { useState, useEffect } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
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
import Home from './components/Home/Home';
import OldExtractorHome from './components/Home/OldExtractorHome';
import Stage1 from './components/Stage1/Stage1';
import Stage2 from './components/Stage2/Stage2';
import Stage3 from './components/Stage3/Stage3';
import Stage4 from './components/Stage4/Stage4';
import FigureExtractor from './components/FigureExtractor/FigureExtractor';
import GCSUploader from './components/GCSUploader/GCSUploader';
import URLMerger from './components/URLMerger/URLMerger';
import EnhancedStage1 from './components/EnhancedWorkflow/EnhancedStage1';
import EnhancedStage2 from './components/EnhancedWorkflow/EnhancedStage2';
import ErrorBoundary from './components/common/ErrorBoundary';
import HomeIcon from '@mui/icons-material/Home';

const steps = [
  'Upload & Extract Text',
  'Extract Questions',
  'Extract Marking Schemes',
  'Merge & Review',
];

const enhancedSteps = [
  'Upload & Process PDF',
  'Review Questions (LaTeX)',
  'Upload Marking Scheme',
  'Merge & Review',
];

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [enhancedSessionId, setEnhancedSessionId] = useState<string | null>(null);
  const [activeStep, setActiveStep] = useState(0);
  const [enhancedActiveStep, setEnhancedActiveStep] = useState(0);
  const [showStepper, setShowStepper] = useState(false);
  const [isEnhancedWorkflow, setIsEnhancedWorkflow] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // Create sessions on mount (one for old workflow, one for enhanced)
    createSession().then((session) => {
      setSessionId(session.session_id);
      console.log('Old workflow session created:', session.session_id);
    });
    createSession().then((session) => {
      setEnhancedSessionId(session.session_id);
      console.log('Enhanced workflow session created:', session.session_id);
    });
  }, []);

  useEffect(() => {
    // Determine if we're in enhanced workflow or old workflow
    const isEnhanced = location.pathname.startsWith('/enhanced-');
    setIsEnhancedWorkflow(isEnhanced);

    // Show stepper on stage routes (old workflow)
    const isStageRoute = location.pathname.startsWith('/stage');
    setShowStepper(isStageRoute || isEnhanced);

    // Update active step based on route
    if (isStageRoute) {
      const stageMatch = location.pathname.match(/\/stage(\d+)/);
      if (stageMatch) {
        setActiveStep(parseInt(stageMatch[1]) - 1);
      }
    } else if (isEnhanced) {
      // Enhanced workflow steps
      if (location.pathname.includes('enhanced-stage1')) {
        setEnhancedActiveStep(0);
      } else if (location.pathname.includes('enhanced-stage2')) {
        setEnhancedActiveStep(1);
      } else if (location.pathname.includes('enhanced-stage3')) {
        setEnhancedActiveStep(2);
      } else if (location.pathname.includes('enhanced-stage4')) {
        setEnhancedActiveStep(3);
      }
    }
  }, [location.pathname]);

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

  // Enhanced workflow handlers
  const handleEnhancedNext = () => {
    const nextStep = enhancedActiveStep + 1;
    setEnhancedActiveStep(nextStep);
    if (nextStep === 1) {
      navigate('/enhanced-stage2');
    } else if (nextStep === 2) {
      navigate('/enhanced-stage3');
    } else if (nextStep === 3) {
      navigate('/enhanced-stage4');
    }
  };

  const handleEnhancedBack = () => {
    const prevStep = enhancedActiveStep - 1;
    setEnhancedActiveStep(prevStep);
    if (prevStep === 0) {
      navigate('/enhanced-stage1');
    } else if (prevStep === 1) {
      navigate('/enhanced-stage2');
    } else if (prevStep === 2) {
      navigate('/enhanced-stage3');
    }
  };

  const handleEnhancedStepClick = (step: number) => {
    setEnhancedActiveStep(step);
    navigate(`/enhanced-stage${step + 1}`);
  };

  const handleHome = () => {
    setActiveStep(0);
    navigate('/');
  };

  if (!sessionId || !enhancedSessionId) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
        }}
      >
        <Typography variant="h6">Initializing sessions...</Typography>
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
            {isEnhancedWorkflow ? `Enhanced Session: ${enhancedSessionId.substring(0, 8)}...` : `Session: ${sessionId.substring(0, 8)}...`}
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ mt: 4, mb: 4, flexGrow: 1 }}>
        {showStepper && (
          <Paper sx={{ p: 3, mb: 3 }}>
            <Stepper activeStep={isEnhancedWorkflow ? enhancedActiveStep : activeStep}>
              {(isEnhancedWorkflow ? enhancedSteps : steps).map((label, index) => (
                <Step key={label}>
                  <StepLabel
                    onClick={() => isEnhancedWorkflow ? handleEnhancedStepClick(index) : handleStepClick(index)}
                    sx={{ cursor: 'pointer' }}
                  >
                    {label}
                  </StepLabel>
                </Step>
              ))}
            </Stepper>
          </Paper>
        )}

        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/old-extractor" element={<OldExtractorHome />} />

          {/* Enhanced Workflow Routes */}
          <Route
            path="/enhanced-workflow"
            element={
              <EnhancedStage1
                sessionId={enhancedSessionId}
                onNext={handleEnhancedNext}
              />
            }
          />
          <Route
            path="/enhanced-stage1"
            element={
              <EnhancedStage1
                sessionId={enhancedSessionId}
                onNext={handleEnhancedNext}
              />
            }
          />
          <Route
            path="/enhanced-stage2"
            element={
              <EnhancedStage2
                sessionId={enhancedSessionId}
                onNext={handleEnhancedNext}
                onBack={handleEnhancedBack}
              />
            }
          />
          <Route
            path="/enhanced-stage3"
            element={
              <Stage3
                sessionId={enhancedSessionId}
                onNext={handleEnhancedNext}
                onBack={handleEnhancedBack}
              />
            }
          />
          <Route
            path="/enhanced-stage4"
            element={
              <ErrorBoundary>
                <Stage4
                  sessionId={enhancedSessionId}
                  onNext={handleEnhancedNext}
                  onBack={handleEnhancedBack}
                />
              </ErrorBoundary>
            }
          />

          {/* Old Workflow Routes */}
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

          {/* Standalone Tools */}
          <Route path="/figure-extractor" element={<FigureExtractor />} />
          <Route path="/gcs-uploader" element={<GCSUploader />} />
          <Route path="/url-merger" element={<URLMerger />} />
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
