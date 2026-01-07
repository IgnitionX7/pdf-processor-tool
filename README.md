# PDF Processor Tool

A comprehensive PDF processing tool for extracting questions, figures, tables, and marking schemes from exam papers with LaTeX notation support.

## Features

- 📄 **Question Extraction** - Extract questions from PDF papers
- 🖼️ **Figure Detection** - Automatically detect and extract figures/diagrams
- 📊 **Table Extraction** - Extract tables with structure preservation
- ✅ **Marking Scheme Processing** - Extract marking schemes with LaTeX formulas
- 🔬 **LaTeX Support** - Preserve mathematical notation (subscripts, superscripts)
- 🚀 **Two Extraction Modes**:
  - Standard Extractor (lightweight)
  - Enhanced Extractor (with visual detection using OpenCV)

## Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd pdf-processor-tool
   ```

2. **Install dependencies**
   ```bash
   # Backend
   pip install -r requirements.txt

   # Frontend
   cd frontend
   npm install
   npm run build
   cd ..
   ```

3. **Run the server**
   ```bash
   python main.py
   ```

4. **Access the app**
   - Frontend: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## Deployment

### Deploy to Render.com (FREE ⭐ Recommended)

**Supports both extractors with OpenCV!**

See [RENDER_DEPLOY.md](./RENDER_DEPLOY.md) for complete instructions.

**Quick steps:**
1. Push code to GitHub
2. Sign up at https://render.com
3. Create new Web Service from your GitHub repo
4. Render auto-detects `render.yaml` and deploys!

**Free tier includes:**
- ✅ Full functionality (both extractors work)
- ✅ Automatic HTTPS
- ✅ 750 hours/month
- ⚠️ Spins down after 15min inactivity (30-60s wake time)

### Deploy to Vercel (Standard Extractor Only)

**Note:** Enhanced extractor not supported on Vercel due to size limits.

1. Deploy to Vercel:
   ```bash
   vercel --prod
   ```

2. Only the standard extractor will work (enhanced extractor is disabled)

## Project Structure

```
pdf-processor-tool/
├── backend/
│   └── app/
│       ├── routes/          # API endpoints
│       ├── processors/      # PDF extraction logic
│       ├── models/          # Data models
│       ├── utils/           # Helper utilities
│       └── combined-extractor/  # Enhanced extractor with OpenCV
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   └── services/        # API client
│   └── dist/                # Built frontend (served by FastAPI)
├── main.py                  # FastAPI app entry point
├── requirements.txt         # Python dependencies
├── requirements-enhanced.txt # Optional OpenCV dependencies for local dev
└── render.yaml             # Render.com deployment config
```

## API Endpoints

### Sessions
- `POST /api/sessions` - Create new session
- `GET /api/sessions/{id}` - Get session status

### Standard Extractor
- **Stage 1**: Upload question paper
- **Stage 2**: Extract questions
- **Stage 3**: Upload marking scheme, extract answers
- **Stage 4**: Merge questions with answers

### Enhanced Extractor
- `POST /api/sessions/{id}/enhanced/upload-pdf` - Upload PDF
- `POST /api/sessions/{id}/enhanced/process` - Process with visual detection
- `GET /api/sessions/{id}/enhanced/figures` - Get extracted figures
- `GET /api/sessions/{id}/enhanced/questions` - Get questions with LaTeX

## Technologies

**Backend:**
- FastAPI - Modern Python web framework
- pdfplumber - PDF text extraction
- PyMuPDF (fitz) - PDF rendering
- OpenCV - Image processing (enhanced extractor)
- pdf2image - PDF to image conversion

**Frontend:**
- React - UI framework
- TypeScript - Type safety
- Vite - Build tool
- TailwindCSS - Styling

## Configuration

Environment variables (optional):

```env
HOST=0.0.0.0
PORT=8000
DEBUG=false
CORS_ORIGINS=*
```

## Development

### Run backend only
```bash
cd backend
python run.py
```

### Run frontend dev server
```bash
cd frontend
npm run dev
```

### Build frontend
```bash
cd frontend
npm run build
```

## Deployment Options Comparison

| Feature | Render.com (Free) | Vercel | Railway |
|---------|------------------|--------|---------|
| **Cost** | 100% Free | Free | $5/month credit |
| **Both Extractors** | ✅ Yes | ❌ No (size limit) | ✅ Yes |
| **Cold Starts** | 30-60s after 15min | None | None |
| **Build Time** | 5-10 min | 2-3 min | 3-5 min |
| **Always On** | ❌ (spins down) | ✅ | ✅ |
| **Setup Difficulty** | ⭐ Easy | ⭐ Easy | ⭐ Easy |

**Recommendation:** Use Render.com for full functionality + free tier.

## Troubleshooting

### OpenCV Issues

If you get `ImportError: libGL.so.1`:
```bash
# Install system dependencies (Linux)
apt-get install -y libgl1-mesa-glx libglib2.0-0
```

### Frontend Not Building

```bash
cd frontend
rm -rf node_modules dist
npm install
npm run build
```

### Session Not Found

Clear session data:
```bash
rm -rf uploads/*
```

## License

[Your License Here]

## Contributing

Contributions welcome! Please open an issue or PR.

## Support

- 📚 [Full Deployment Guide](./RENDER_DEPLOY.md)
- 📖 [Backend README](./backend/README.md)
- 🐛 [Report Issues](https://github.com/your-repo/issues)
