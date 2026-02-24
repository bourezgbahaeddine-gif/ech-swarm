# Session Handoff — 2026-02-24

## 1) Verified Result (Server)

Test executed on server:

```bash
PDF="/home/bourezgbahaeddine/A2026013.pdf"
curl -sS -X POST http://127.0.0.1:8000/api/v1/document-intel/extract ...
```

Observed output:

- `parser = pypdf`
- `news = 3`
- `data = 38`
- `warnings = ['Docling timed out after 90s; using fallback parser.']`

Status:

- Endpoint is stable (no `504`).
- Extraction returns useful output on official gazette PDF.
- Docling is still timing out for this file, fallback works as designed.

## 2) Current Diagnosis

- For this gazette-like PDF, `pypdf` currently gives practical results faster than Docling.
- Some official gazette files are likely scanned/image-heavy; OCR path is required to improve coverage.
- Keep `PDF` variable in one line only:
  - Correct: `PDF="/home/bourezgbahaeddine/A2026013.pdf"`
  - Do not include line break inside quotes.

## 3) Code Status (Local Repo)

Latest document-intel related commits:

1. `a21a876` Add OCR fallback pipeline for scanned official gazettes
2. `051696a` Improve gazette extraction resilience and make upload size configurable
3. `6da54a9` Make docling timeout and size thresholds configurable
4. `e9f677f` Fix doc intel timeout fallback and resolve auth hydration mismatch
5. `bdf66c9` Enable Docling build toggle, improve multilingual extraction, and add draft action

## 4) Tomorrow Start Plan

### A) Push + deploy OCR commit

PowerShell:

```powershell
cd "D:\AI Agent GOOGLE\echorouk-swarm"
git push origin main
```

SSH:

```bash
cd ~/ech-swarm
git pull origin main
docker compose build backend worker
docker compose up -d --force-recreate backend worker
```

### B) Verify OCR toolchain in backend container

```bash
docker compose exec -T backend sh -lc "which pdftoppm && which tesseract && tesseract --version | head -n 1"
```

### C) Configure OCR for official gazettes

```bash
grep -q '^ECHOROUK_OS_DOCUMENT_INTEL_OCR_ENABLED=' .env || echo 'ECHOROUK_OS_DOCUMENT_INTEL_OCR_ENABLED=true' >> .env
grep -q '^ECHOROUK_OS_DOCUMENT_INTEL_OCR_TIMEOUT_SECONDS=' .env || echo 'ECHOROUK_OS_DOCUMENT_INTEL_OCR_TIMEOUT_SECONDS=240' >> .env
grep -q '^ECHOROUK_OS_DOCUMENT_INTEL_OCR_MAX_PAGES=' .env || echo 'ECHOROUK_OS_DOCUMENT_INTEL_OCR_MAX_PAGES=30' >> .env
grep -q '^ECHOROUK_OS_DOCUMENT_INTEL_OCR_DPI=' .env || echo 'ECHOROUK_OS_DOCUMENT_INTEL_OCR_DPI=250' >> .env
grep -q '^ECHOROUK_OS_DOCUMENT_INTEL_OCR_TRIGGER_MIN_CHARS=' .env || echo 'ECHOROUK_OS_DOCUMENT_INTEL_OCR_TRIGGER_MIN_CHARS=2500' >> .env
docker compose up -d --force-recreate backend worker
```

### D) Re-test on same file and compare

```bash
PDF="/home/bourezgbahaeddine/A2026013.pdf"
TOKEN=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"bourezgb","password":"password123"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

curl -sS -X POST "http://127.0.0.1:8000/api/v1/document-intel/extract" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@${PDF}" \
  -F "language_hint=ar" \
  -F "max_news_items=10" \
  -F "max_data_points=40" \
| python3 -c 'import sys,json; d=json.load(sys.stdin); print("parser=",d["parser_used"],"news=",len(d["news_candidates"]),"data=",len(d["data_points"]),"warnings=",d.get("warnings"))'
```

Target tomorrow:

- If OCR is triggered, expect parser `ocr_tesseract` on weak scanned PDFs.
- If file is text-based, parser may still be `pypdf` (acceptable).
