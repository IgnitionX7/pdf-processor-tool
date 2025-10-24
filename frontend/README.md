# PDF Processor Frontend

React + TypeScript frontend for the PDF Processor application.

## Features

✅ **4-Stage Workflow**
- Stage 1: Upload question paper PDF & extract/edit text
- Stage 2: Extract and review questions with parts
- Stage 3: Upload marking scheme PDF & extract schemes
- Stage 4: Merge and review final results

✅ **Modern UI**
- Material-UI components
- Responsive design
- Drag & drop file upload
- Real-time validation
- Statistics dashboards

✅ **Full Integration**
- Connects to FastAPI backend
- React Query for data fetching
- TypeScript for type safety
- Error handling throughout

## Quick Start

### 1. Install Dependencies

```bash
npm install
```

### 2. Start Development Server

```bash
npm run dev
```

The app will be available at http://localhost:5173

### 3. Make Sure Backend is Running

The frontend expects the backend at http://localhost:8000

```bash
cd ../backend
venv\Scripts\activate
python run.py
```

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── Stage1/       # Text extraction
│   │   ├── Stage2/       # Question extraction
│   │   ├── Stage3/       # Marking scheme
│   │   └── Stage4/       # Merge & review
│   ├── services/
│   │   └── api.ts        # API client
│   ├── types/
│   │   └── index.ts      # TypeScript types
│   ├── App.tsx           # Main app with routing
│   └── main.tsx          # Entry point
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Lint code

## Technology Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Material-UI** - Component library
- **React Router** - Routing
- **React Query** - Data fetching
- **Axios** - HTTP client
- **React Dropzone** - File uploads

## Usage

### Complete Workflow

1. **Stage 1: Text Extraction**
   - Upload question paper PDF
   - Click "Extract Text"
   - Review and edit cleaned text
   - Click "Next"

2. **Stage 2: Question Extraction**
   - Click "Extract Questions"
   - Review parsed questions and parts
   - Check validation results
   - Click "Next"

3. **Stage 3: Marking Scheme Extraction**
   - Upload marking scheme PDF
   - Set start page (default: 8)
   - Click "Extract"
   - Review extracted marking schemes
   - Click "Next"

4. **Stage 4: Merge & Review**
   - Click "Start Merge"
   - Review statistics and coverage
   - Check sample merged questions
   - Download final JSON

## Configuration

The frontend is configured to proxy API requests to the backend:

```typescript
// vite.config.ts
server: {
  port: 5173,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

## Features by Stage

### Stage 1
- ✅ Drag & drop PDF upload
- ✅ Progress indicators
- ✅ Text statistics display
- ✅ Editable text area
- ✅ Download cleaned text

### Stage 2
- ✅ Auto-extraction from cleaned text
- ✅ Expandable question accordion
- ✅ Validation with error reporting
- ✅ Question statistics
- ✅ Download questions JSON

### Stage 3
- ✅ Drag & drop PDF upload
- ✅ Configurable start page
- ✅ Table display of schemes
- ✅ Preview with pagination
- ✅ Download schemes JSON

### Stage 4
- ✅ One-click merge
- ✅ Coverage statistics
- ✅ Visual progress bar
- ✅ Question preview with schemes
- ✅ Download merged JSON

## API Integration

All API calls are handled through the `services/api.ts` module:

```typescript
// Example: Extract text
import { extractText } from './services/api';

const response = await extractText(sessionId);
console.log(response.stats);
```

## Error Handling

All components include:
- Try/catch blocks for API calls
- User-friendly error messages
- Loading states
- Success notifications

## Development

### Adding a New Component

1. Create component in appropriate directory
2. Import and use in parent component
3. Connect to API if needed
4. Add TypeScript types

### Modifying Styles

Components use Material-UI's `sx` prop:

```typescript
<Box sx={{ p: 3, mb: 2 }}>
  Content
</Box>
```

## Building for Production

```bash
npm run build
```

Output will be in `dist/` directory.

## Troubleshooting

**Port already in use:**
```bash
# Change port in vite.config.ts
server: { port: 3000 }
```

**API connection errors:**
- Make sure backend is running on port 8000
- Check CORS settings in backend

**TypeScript errors:**
```bash
npm run build  # Will show all type errors
```

## Next Steps

### Enhancements
- [ ] Add Monaco Editor for better text editing
- [ ] Implement question part editing
- [ ] Add batch file processing
- [ ] Export to multiple formats
- [ ] Add user authentication
- [ ] Improve mobile responsiveness

### Production Deployment
- [ ] Add environment variables
- [ ] Configure production API URL
- [ ] Add error tracking (Sentry)
- [ ] Optimize bundle size
- [ ] Add PWA support

## Support

- **Frontend**: http://localhost:5173
- **Backend**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
