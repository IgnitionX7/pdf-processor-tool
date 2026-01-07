# PDF Processor Backend - Complete Implementation ✅

FastAPI backend for the PDF Processor web application with all 4 processing stages implemented.

## Setup

### 1. Create Virtual Environment

```bash
cd backend
python -m venv venv

# On Windows
venv\Scripts\activate

# On Linux/Mac
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env` and adjust settings if needed:

```bash
cp .env.example .env
```

### 4. Run Development Server

```bash
# Option 1: Using the run script
python run.py

# Option 2: Using uvicorn directly
uvicorn main:app --reload --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app & configuration
│   ├── config.py            # Settings from environment
│   ├── models.py            # Pydantic models
│   ├── routes/              # API endpoints
│   │   ├── sessions.py      # Session management
│   │   └── stage1.py        # Text extraction endpoints
│   ├── processors/          # Core processing logic
│   │   └── text_extractor.py
│   └── utils/               # Utilities
│       ├── session_manager.py
│       └── file_utils.py
├── tests/                   # Unit tests
├── requirements.txt         # Python dependencies
├── .env                     # Environment configuration
└── run.py                   # Development server runner
```

## Features

✅ **Stage 1: Text Extraction** - Extract and clean text from PDF
✅ **Stage 2: Question Extraction** - Parse questions with hierarchical parts
✅ **Stage 3: Marking Scheme Extraction** - Extract marking schemes from PDF
✅ **Stage 4: Merge** - Combine marking schemes with questions
✅ **Session Management** - Isolated processing sessions
✅ **Full CRUD** - Create, read, update, delete for all data
✅ **Validation** - Built-in validation and error reporting
✅ **File Management** - Upload, download, and manage files

## API Endpoints

### Sessions
- `POST /api/sessions` - Create new session
- `GET /api/sessions/{id}` - Get session details
- `DELETE /api/sessions/{id}` - Delete session

### Stage 1: Text Extraction
- `POST /api/sessions/{id}/stage1/upload-question-paper` - Upload PDF
- `POST /api/sessions/{id}/stage1/extract-text` - Extract text
- `GET /api/sessions/{id}/stage1/text/{type}` - Get text (raw/cleaned)
- `PUT /api/sessions/{id}/stage1/text/cleaned` - Update cleaned text
- `GET /api/sessions/{id}/stage1/stats/{type}` - Get statistics
- `GET /api/sessions/{id}/stage1/download/{type}` - Download files

### Stage 2: Question Extraction
- `POST /api/sessions/{id}/stage2/extract-questions` - Extract questions
- `GET /api/sessions/{id}/stage2/questions` - Get questions
- `PUT /api/sessions/{id}/stage2/questions` - Update questions
- `POST /api/sessions/{id}/stage2/validate` - Validate questions
- `GET /api/sessions/{id}/stage2/download` - Download JSON

### Stage 3: Marking Scheme Extraction
- `POST /api/sessions/{id}/stage3/upload-marking-scheme` - Upload PDF
- `POST /api/sessions/{id}/stage3/extract-marking-schemes` - Extract schemes
- `GET /api/sessions/{id}/stage3/marking-schemes` - Get schemes
- `PUT /api/sessions/{id}/stage3/marking-schemes` - Update schemes
- `GET /api/sessions/{id}/stage3/download` - Download JSON

### Stage 4: Merge
- `POST /api/sessions/{id}/stage4/merge` - Merge schemes into questions
- `GET /api/sessions/{id}/stage4/merged` - Get merged data
- `GET /api/sessions/{id}/stage4/statistics` - Get merge statistics
- `PUT /api/sessions/{id}/stage4/merged` - Update merged data
- `GET /api/sessions/{id}/stage4/download` - Download JSON

## Complete Workflow

### Full 4-Stage Pipeline

```bash
# 1. Create Session
curl -X POST http://localhost:8000/api/sessions
# Save the session_id

# 2. Stage 1: Upload & Extract Text
curl -X POST -F "file=@question-paper.pdf" \
  http://localhost:8000/api/sessions/{id}/stage1/upload-question-paper

curl -X POST http://localhost:8000/api/sessions/{id}/stage1/extract-text

# 3. Stage 2: Extract Questions
curl -X POST http://localhost:8000/api/sessions/{id}/stage2/extract-questions

# 4. Stage 3: Upload & Extract Marking Schemes
curl -X POST -F "file=@marking-scheme.pdf" \
  http://localhost:8000/api/sessions/{id}/stage3/upload-marking-scheme

curl -X POST http://localhost:8000/api/sessions/{id}/stage3/extract-marking-schemes?start_page=8

# 5. Stage 4: Merge
curl -X POST http://localhost:8000/api/sessions/{id}/stage4/merge

# 6. Download Final Result
curl -O http://localhost:8000/api/sessions/{id}/stage4/download
```

### Automated Testing

```bash
# Test full pipeline automatically
python test_full_pipeline.py
```

## Configuration

Edit `.env` file to configure:

- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 8000)
- `DEBUG` - Debug mode (default: True)
- `UPLOAD_DIR` - Upload directory path
- `MAX_FILE_SIZE` - Maximum upload size in bytes
- `SESSION_EXPIRY_HOURS` - Auto-cleanup time
- `CORS_ORIGINS` - Allowed CORS origins

## Development

### Run Tests

```bash
pytest tests/
```

### Check Code Quality

```bash
# Format code
black app/

# Lint code
flake8 app/

# Type checking
mypy app/
```

## Troubleshooting

### Port Already in Use

If port 8000 is already in use, change the port in `.env` or run:

```bash
uvicorn main:app --reload --port 8001
```

### File Upload Fails

Check that the upload directory exists and has proper permissions:

```bash
mkdir -p ../uploads
chmod 755 ../uploads
```

### PDF Processing Errors

Make sure pdfplumber dependencies are installed. On some systems you may need:

```bash
# Ubuntu/Debian
sudo apt-get install python3-dev libpoppler-cpp-dev

# macOS
brew install poppler
```
