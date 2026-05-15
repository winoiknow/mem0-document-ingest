# mem0 Document Ingestion Service

A Python service that automatically watches folders for new or modified documents, extracts their text content, and ingests it into a self-hosted [mem0](https://github.com/mem0ai/mem0) instance. Supports PDF, DOCX, XLSX, CSV, Markdown, plain text, and images (via OCR).

## How It Works

```
Folder(s) ──> Scanner ──> Text Extractor ──> Chunker ──> mem0 REST API
                │                                            │
           SQLite manifest                            POST /memories
         (tracks what changed)
```

1. On each run (default: hourly), the scanner walks configured folders and compares files against a local SQLite manifest.
2. Only new or modified files are processed — determined by modified time, file size, and SHA-256 content hash.
3. Text is extracted from each file using format-specific parsers.
4. Long documents are split into overlapping chunks before ingestion.
5. Each chunk is sent to mem0 via `POST /memories` with source metadata attached.

## Prerequisites

- **Python 3.10+**
- **mem0** running locally in Docker, exposed on port 8000 (see [mem0 self-hosting docs](https://docs.mem0.ai/open-source))
- **Tesseract OCR** (optional) — required only if you want to extract text from images. See [Installing Tesseract](#installing-tesseract) below.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/winoiknow/mem0-document-ingest.git
cd mem0-document-ingest

# Install dependencies
pip install -r requirements.txt

# Edit configuration
# Update `folders` to point to your document directories
nano config.yaml

# Run the service (polls every 60 min by default from config.yaml)
python main.py

# Override the poll interval at runtime (e.g. every 5 minutes)
python main.py --interval 5

# Use sub-minute intervals (e.g. every 30 seconds)
python main.py --interval 0.5

# Run a single scan and exit (useful for cron or manual runs)
python main.py --once
```

The service runs an immediate scan on startup, then polls at the configured interval.

### CLI Options

| Flag | Description |
|------|-------------|
| `--interval <minutes>` | Override the poll interval from `config.yaml`. Accepts decimals (e.g. `0.5` = 30 seconds). |
| `--once` | Run a single ingestion pass and exit immediately. Useful for cron jobs or one-off runs. |

## Configuration

All settings live in `config.yaml`:

```yaml
folders:
  - /path/to/your/documents
  - /another/folder

mem0_url: http://localhost:8000
user_id: document_ingest
poll_interval_minutes: 60
chunk_size_tokens: 1000
chunk_overlap_tokens: 100
ocr_enabled: true
supported_extensions:
  - .txt
  - .md
  - .pdf
  - .docx
  - .xlsx
  - .csv
  - .png
  - .jpg
  - .jpeg
  - .tiff
  - .bmp
```

| Setting | Description | Default |
|---------|-------------|---------|
| `folders` | List of directory paths to watch (recursive) | *required* |
| `mem0_url` | URL of the self-hosted mem0 instance | `http://localhost:8000` |
| `user_id` | mem0 user scope for ingested memories | `document_ingest` |
| `poll_interval_minutes` | How often to check for changes | `60` |
| `chunk_size_tokens` | Max words per chunk sent to mem0 | `1000` |
| `chunk_overlap_tokens` | Word overlap between consecutive chunks | `100` |
| `ocr_enabled` | Enable image text extraction via Tesseract | `true` |
| `supported_extensions` | File types to process | See above |

## Supported Formats

| Format | Extension(s) | Extraction Method |
|--------|-------------|-------------------|
| Plain text | `.txt`, `.md` | Direct read (UTF-8) |
| PDF | `.pdf` | PyMuPDF |
| Word | `.docx` | python-docx |
| Excel | `.xlsx` | openpyxl |
| CSV | `.csv` | stdlib csv |
| Images | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp` | Tesseract OCR |

## Project Structure

```
mem0-path-document-ingestion/
├── main.py            # Entry point and scheduler
├── scanner.py         # Folder scanning and change detection
├── extractors.py      # Format-specific text extraction
├── chunker.py         # Text chunking with overlap
├── ingester.py        # mem0 REST API client with retry logic
├── manifest.py        # SQLite manifest for tracking ingested files
├── config.yaml        # Service configuration
├── requirements.txt   # Python dependencies
└── README.md
```

## How Change Detection Works

The service maintains a SQLite database (`ingestion_manifest.db`, created automatically) that tracks every ingested file:

- **File path** — unique identifier
- **Modified time** — from filesystem stat
- **File size** — quick change check
- **SHA-256 hash** — content-level change verification
- **Last ingested timestamp**

On each run, the scanner compares current file metadata against the manifest. A file is re-ingested only when its modification time or size has changed *and* its content hash differs. This prevents redundant processing and makes each run idempotent.

## OCR Support

Image OCR is optional and gracefully degrades:

- If `ocr_enabled: true` and Tesseract is installed, images are processed normally.
- If `ocr_enabled: true` but Tesseract is not installed, images are skipped with a warning log.
- If `ocr_enabled: false`, images are skipped entirely.

No other functionality is affected if Tesseract is absent.

## Installing Tesseract

Tesseract is only needed if you want OCR for image files. If you don't need it, set `ocr_enabled: false` in `config.yaml` and skip this section.

### Windows

1. Download the installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) (recommended) — choose the 64-bit `.exe`.
2. Run the installer. The default install path is `C:\Program Files\Tesseract-OCR`.
3. During installation, optionally select additional language packs under "Additional script data" if you need non-English OCR.
4. Add Tesseract to your system PATH:
   - Open **Settings > System > About > Advanced system settings > Environment Variables**.
   - Under **System variables**, select `Path` and click **Edit**.
   - Add `C:\Program Files\Tesseract-OCR`.
   - Click **OK** to save.
5. Verify the installation in a new terminal:
   ```powershell
   tesseract --version
   ```

If you prefer not to modify PATH, you can set the executable path directly in your environment before running the service:

```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

Or configure pytesseract in Python by setting `pytesseract.pytesseract.tesseract_cmd` (see [pytesseract docs](https://github.com/madmaze/pytesseract#usage)).

### macOS

```bash
brew install tesseract
```

To add language packs:

```bash
brew install tesseract-lang
```

### Linux (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install tesseract-ocr
```

For additional languages (e.g., German, French, Spanish):

```bash
sudo apt install tesseract-ocr-deu tesseract-ocr-fra tesseract-ocr-spa
```

### Linux (Fedora/RHEL)

```bash
sudo dnf install tesseract
```

### Verifying Installation

After installing, confirm Tesseract is available:

```bash
tesseract --version
```

You should see output like `tesseract 5.x.x`. The service will automatically detect and use it on the next run.

## Logging

The service logs to stdout at `INFO` level. Example output:

```
2026-05-15 10:00:00 [INFO] main: Document ingestion service starting (poll every 60 min)
2026-05-15 10:00:00 [INFO] main: Starting ingestion run for 2 folder(s)
2026-05-15 10:00:00 [INFO] scanner: New file: /docs/report.pdf
2026-05-15 10:00:01 [INFO] main: Ingested: /docs/report.pdf (3 chunk(s))
2026-05-15 10:00:01 [INFO] main: Ingestion run complete: 1 processed, 0 failed
```

## Running as a Background Service

### systemd (Linux)

Create `/etc/systemd/system/mem0-ingest.service`:

```ini
[Unit]
Description=mem0 Document Ingestion Service
After=network.target docker.service

[Service]
Type=simple
WorkingDirectory=/path/to/mem0-path-document-ingestion
ExecStart=/usr/bin/python3 main.py
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now mem0-ingest
```

### Windows Task Scheduler

Use Task Scheduler to run `python main.py` at login, or run it in a terminal and leave it running. The APScheduler-based loop handles the hourly timing internally.

## License

MIT
