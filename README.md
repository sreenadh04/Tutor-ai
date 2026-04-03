# 🧠 MediTutor AI — Complete Setup Manual

> **Zero-cost AI study assistant.** From ZIP download to live website — every step explained.

---

## 📋 TABLE OF CONTENTS

1. [Architecture Overview](#1-architecture-overview)
2. [Folder Structure](#2-folder-structure)
3. [Prerequisites](#3-prerequisites)
4. [Get Your Free API Keys](#4-get-your-free-api-keys)
5. [Local Setup (Your Computer)](#5-local-setup-your-computer)
6. [Deploy Backend to Render.com (Free)](#6-deploy-backend-to-rendercom-free)
7. [Deploy Frontend to Streamlit Cloud (Free)](#7-deploy-frontend-to-streamlit-cloud-free)
8. [Environment Variables Reference](#8-environment-variables-reference)
9. [How the Multi-Model Fallback Works](#9-how-the-multi-model-fallback-works)
10. [Feature Walkthroughs](#10-feature-walkthroughs)
11. [Troubleshooting](#11-troubleshooting)
12. [Scaling Strategy (Future)](#12-scaling-strategy-future)

---

## 1. ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│                        MediTutor AI                             │
│                                                                 │
│  ┌──────────────────┐          ┌──────────────────────────────┐ │
│  │   FRONTEND       │  HTTP    │   BACKEND (FastAPI)          │ │
│  │  Streamlit UI    │◄────────►│   Port 8000                  │ │
│  │  Port 8501       │  REST    │                              │ │
│  │                  │  API     │  ┌──────────────────────┐    │ │
│  │  6 Pages:        │          │  │  Routers             │    │ │
│  │  • Home          │          │  │  /api/v1/pdf         │    │ │
│  │  • Upload PDF    │          │  │  /api/v1/qa          │    │ │
│  │  • Q&A Chat      │          │  │  /api/v1/flashcards  │    │ │
│  │  • Flashcards    │          │  │  /api/v1/mcq         │    │ │
│  │  • MCQ Quiz      │          │  │  /api/v1/progress    │    │ │
│  │  • Progress      │          │  │  /api/v1/prereq      │    │ │
│  │  • Prerequisites │          │  └──────────┬───────────┘    │ │
│  └──────────────────┘          │             │                 │ │
│                                │  ┌──────────▼───────────┐    │ │
│                                │  │  Services Layer       │    │ │
│                                │  │                       │    │ │
│                                │  │  PDFService           │    │ │
│                                │  │  VectorService (FAISS)│    │ │
│                                │  │  LLMService           │    │ │
│                                │  │  FlashcardService     │    │ │
│                                │  │  MCQService           │    │ │
│                                │  │  ProgressService      │    │ │
│                                │  └──────────┬───────────┘    │ │
│                                │             │                 │ │
│                                │  ┌──────────▼───────────┐    │ │
│                                │  │  Data Layer           │    │ │
│                                │  │                       │    │ │
│                                │  │  SQLite DB            │    │ │
│                                │  │  FAISS Index (disk)   │    │ │
│                                │  │  Disk Cache (JSON)    │    │ │
│                                │  └───────────────────────┘    │ │
│                                └──────────────────────────────┘ │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  EXTERNAL APIs (Free Tier)                               │   │
│  │                                                          │   │
│  │  1st: Groq API ──► llama-3.1-8b-instant (fastest)        │   │
│  │  2nd: HuggingFace ──► Mistral-7B / Zephyr (fallback)    │   │
│  │  Embeddings: sentence-transformers (LOCAL, no API)       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

PDF PROCESSING PIPELINE:
Upload ──► PyMuPDF extract ──► LangChain chunk (1000/200)
──► sentence-transformers embed ──► FAISS index ──► disk

RAG PIPELINE:
Question ──► embed query ──► FAISS search (top-5)
──► build prompt + context ──► Groq/HF LLM ──► answer + citations
```

---

## 2. FOLDER STRUCTURE

```
meditutor-ai/
│
├── backend/                    ← FastAPI backend
│   ├── main.py                 ← App entry point, routes, middleware
│   ├── config.py               ← All settings (env vars, model names)
│   ├── database.py             ← SQLAlchemy ORM models & DB setup
│   ├── models.py               ← Pydantic request/response schemas
│   ├── requirements.txt        ← Python dependencies
│   ├── Dockerfile              ← Docker image for backend
│   │
│   ├── routers/                ← One router per feature
│   │   ├── pdf_router.py       ← Upload, list, delete PDFs
│   │   ├── qa_router.py        ← RAG question answering
│   │   ├── flashcard_router.py ← Generate & export flashcards
│   │   ├── mcq_router.py       ← Generate & grade MCQ quizzes
│   │   ├── progress_router.py  ← Session & progress tracking
│   │   └── prereq_router.py    ← Prerequisite checker
│   │
│   ├── services/               ← Business logic
│   │   ├── llm_service.py      ← Multi-model LLM with fallback
│   │   ├── pdf_service.py      ← PDF extract + chunk
│   │   ├── vector_service.py   ← FAISS embed + search
│   │   ├── flashcard_service.py
│   │   ├── mcq_service.py
│   │   └── progress_service.py
│   │
│   ├── utils/
│   │   └── cache.py            ← Disk-based JSON cache with TTL
│   │
│   └── data/                   ← Created at runtime (gitignored)
│       ├── db/meditutor.db     ← SQLite database
│       ├── vectors/            ← FAISS indexes per document
│       ├── uploads/            ← Uploaded PDF files
│       └── cache/              ← LLM response cache
│
├── frontend/                   ← Streamlit frontend
│   ├── app.py                  ← Home page + sidebar + global CSS
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .streamlit/
│   │   ├── config.toml         ← Theme + server settings
│   │   └── secrets.toml.example
│   │
│   └── pages/                  ← Auto-discovered by Streamlit
│       ├── 1_Upload.py         ← PDF upload page
│       ├── 2_QA_Chat.py        ← Chat Q&A with citations
│       ├── 3_Flashcards.py     ← Flashcard viewer + export
│       ├── 4_MCQ_Quiz.py       ← Interactive quiz + grading
│       ├── 5_Progress.py       ← Dashboard & analytics
│       └── 6_Prereq.py         ← Prerequisite checker
│
├── .env.example                ← Template for environment variables
├── .gitignore
├── docker-compose.yml          ← Local Docker dev environment
├── render.yaml                 ← Render.com deployment spec
├── Procfile                    ← Railway/Heroku deployment
├── setup.sh                    ← Mac/Linux one-command setup
├── setup_windows.bat           ← Windows one-command setup
├── start_backend.bat
├── start_frontend.bat
└── README.md                   ← This file
```

---

## 3. PREREQUISITES

You need these installed on your computer:

| Tool | Version | Download |
|------|---------|----------|
| Python | 3.10 or 3.11 | https://www.python.org/downloads/ |
| Git | Any | https://git-scm.com/downloads |

**To verify Python is installed**, open a terminal/command prompt and type:
```bash
python --version
# Should print: Python 3.10.x or Python 3.11.x
```

> ⚠️ **Windows users**: During Python installation, CHECK the box that says **"Add Python to PATH"**

---

## 4. GET YOUR FREE API KEYS

You need at least ONE of these. Both are completely free.

---

### 4A. Groq API Key (RECOMMENDED — Fastest)

Groq gives you a **free API** to run Llama 3.1, Gemma, and other models at very high speed.

1. Go to **https://console.groq.com**
2. Click **Sign Up** (use Google, GitHub, or email)
3. After logging in, click **API Keys** in the left sidebar
4. Click **Create API Key**
5. Give it a name: `MediTutor AI`
6. Click **Submit**
7. **COPY THE KEY** — it starts with `gsk_...`
   > ⚠️ You can only see it once! Save it immediately.
8. Paste it as `GROQ_API_KEY=gsk_your_key_here` in your `.env` file

**Free tier limits:**
- 30 requests/minute
- 14,400 requests/day
- No credit card required

---

### 4B. HuggingFace API Key (FALLBACK — Always Free)

1. Go to **https://huggingface.co**
2. Click **Sign Up** (it's free)
3. After logging in, click your profile picture → **Settings**
4. In the left menu, click **Access Tokens**
5. Click **New token**
6. Name: `MediTutor AI`, Type: **Read**
7. Click **Generate a token**
8. **COPY THE TOKEN** — it starts with `hf_...`
9. Paste it as `HUGGINGFACE_API_KEY=hf_your_token` in your `.env` file

**Free tier:** Unlimited requests (but slow — models may take 20-30s to warm up)

---

## 5. LOCAL SETUP (YOUR COMPUTER)

### Step 1 — Download the project

**Option A: From the ZIP file**
1. Download `meditutor-ai.zip`
2. Right-click → Extract All (Windows) or double-click (Mac)
3. Open a terminal in the extracted folder

**Option B: From Git**
```bash
git clone https://github.com/YOUR_USERNAME/meditutor-ai.git
cd meditutor-ai
```

---

### Step 2 — Create your `.env` file

```bash
# Mac/Linux:
cp .env.example .env

# Windows (Command Prompt):
copy .env.example .env
```

Open `.env` in any text editor (Notepad, VS Code, etc.) and fill in:
```
GROQ_API_KEY=gsk_your_actual_groq_key_here
HUGGINGFACE_API_KEY=hf_your_actual_hf_token_here
MEDITUTOR_API_URL=http://localhost:8000/api/v1
```
Save the file.

---

### Step 3 — Install dependencies

**Mac/Linux (one command):**
```bash
bash setup.sh
```

**Windows (one command):**
```
setup_windows.bat
```

**Or manually (both platforms):**
```bash
# Backend
cd backend
python -m venv venv

# Activate (Mac/Linux):
source venv/bin/activate
# Activate (Windows):
venv\Scripts\activate

pip install -r requirements.txt
deactivate
cd ..

# Frontend
cd frontend
python -m venv venv
source venv/bin/activate    # Mac/Linux
# OR: venv\Scripts\activate  # Windows
pip install -r requirements.txt
deactivate
cd ..
```

> ⏱️ The first install takes **3-8 minutes** because it downloads PyTorch, FAISS, and the sentence-transformers model (~90 MB).

---

### Step 4 — Start the Backend

Open **Terminal 1** and run:

```bash
# Mac/Linux:
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Windows:
start_backend.bat
```

You should see:
```
INFO:     Started server process [12345]
INFO:     Uvicorn running on http://0.0.0.0:8000
✅ Database tables ready
✅ Groq API configured
```

Test it: open **http://localhost:8000/docs** in your browser → you'll see the interactive API docs.

---

### Step 5 — Start the Frontend

Open **Terminal 2** (keep Terminal 1 running) and run:

```bash
# Mac/Linux:
cd frontend
source venv/bin/activate
streamlit run app.py

# Windows:
start_frontend.bat
```

You should see:
```
  You can now view your Streamlit app in your browser.
  Local URL: http://localhost:8501
```

Your browser should open automatically. If not, go to **http://localhost:8501**

---

### Step 6 — Use the App!

1. Click **📤 Upload PDF** in the sidebar
2. Upload any textbook PDF
3. Wait for processing (1-3 minutes for a 200-page book)
4. Go to **💬 Ask Questions** and ask something!

---

## 6. DEPLOY BACKEND TO RENDER.COM (FREE)

Render.com gives you a **free web service** — perfect for hosting the FastAPI backend.

### Step 1 — Push your code to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/meditutor-ai.git
git push -u origin main
```

### Step 2 — Create a Render account

1. Go to **https://render.com**
2. Sign up with GitHub (recommended)

### Step 3 — Create a new Web Service

1. Click **New** → **Web Service**
2. Connect your GitHub repository
3. Configure:

| Setting | Value |
|---------|-------|
| **Name** | `meditutor-ai-backend` |
| **Root Directory** | `backend` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | `Free` |

### Step 4 — Add Environment Variables

In the Render dashboard, go to **Environment** and add:

```
GROQ_API_KEY         = gsk_your_key_here
HUGGINGFACE_API_KEY  = hf_your_token_here
ALLOWED_ORIGINS      = https://your-app.streamlit.app
DEBUG                = false
```

### Step 5 — Add a Persistent Disk

1. In Render, go to **Disks**
2. Click **Add Disk**
3. Mount Path: `/app/data`
4. Size: `1 GB` (free)

> ⚠️ Without a disk, your uploaded PDFs and database will be deleted every time the server restarts.

### Step 6 — Deploy!

Click **Create Web Service**. Render will:
1. Clone your repo
2. Install dependencies (~5 minutes on first deploy)
3. Start the server

Your backend URL will be: `https://meditutor-ai-backend.onrender.com`

Test it: visit `https://meditutor-ai-backend.onrender.com/health`

> ⚠️ **Free tier cold starts**: Render free services sleep after 15 minutes of inactivity. The first request after sleep takes ~30 seconds. This is normal on the free plan.

---

## 7. DEPLOY FRONTEND TO STREAMLIT CLOUD (FREE)

Streamlit Cloud hosts Streamlit apps for free.

### Step 1 — Push frontend to GitHub

Your frontend code should already be in your GitHub repo from Step 6.

### Step 2 — Create Streamlit Cloud account

1. Go to **https://share.streamlit.io**
2. Sign in with GitHub

### Step 3 — Deploy the app

1. Click **New app**
2. Select your repository
3. Set:
   - **Branch**: `main`
   - **Main file path**: `frontend/app.py`
4. Click **Advanced settings**
5. Add secrets (click **Add secret**):

```toml
MEDITUTOR_API_URL = "https://meditutor-ai-backend.onrender.com/api/v1"
```

6. Click **Deploy!**

### Step 4 — Your app is live! 🎉

Your URL: `https://your-app-name.streamlit.app`

### Step 5 — Update CORS on Render

Go back to your Render backend → Environment:
```
ALLOWED_ORIGINS = https://your-app-name.streamlit.app
```
Redeploy.

---

## 8. ENVIRONMENT VARIABLES REFERENCE

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | ✅ (or HF) | — | Groq API key for LLM calls |
| `HUGGINGFACE_API_KEY` | ✅ (or Groq) | — | HuggingFace token for fallback LLM |
| `MEDITUTOR_API_URL` | Frontend only | `http://localhost:8000/api/v1` | Backend URL used by Streamlit |
| `ALLOWED_ORIGINS` | Production | `http://localhost:8501` | Comma-separated CORS origins |
| `DEBUG` | No | `false` | Enable verbose logging |

---

## 9. HOW THE MULTI-MODEL FALLBACK WORKS

```
User sends question
        │
        ▼
┌───────────────────┐
│  Check Cache      │──► HIT ──► Return cached response instantly
│  (disk JSON)      │
└───────┬───────────┘
        │ MISS
        ▼
┌───────────────────┐
│  Try Groq         │
│  llama-3.1-8b     │──► Success ──► Cache + Return
│  (attempt 1/3)    │
└───────┬───────────┘
        │ Rate limit / error
        ▼
┌───────────────────┐
│  Try Groq         │
│  llama3-8b-8192   │──► Success ──► Cache + Return
│  (fallback model) │
└───────┬───────────┘
        │ Still failing
        ▼
┌───────────────────┐
│  Try Groq         │
│  gemma2-9b-it     │──► Success ──► Cache + Return
└───────┬───────────┘
        │ All Groq failed
        ▼
┌───────────────────┐
│  Try HuggingFace  │
│  Mistral-7B       │──► Success ──► Cache + Return
│  (attempt 1-3)    │
└───────┬───────────┘
        │ Model loading (503)
        │  → wait up to 30s, retry
        ▼
┌───────────────────┐
│  Try HuggingFace  │
│  Zephyr-7B        │──► Success ──► Cache + Return
└───────┬───────────┘
        │ All failed
        ▼
   Error response
   (check API keys)
```

**Caching strategy:**
- Every LLM response is cached to disk for 1 hour
- Same question = instant response (no API call)
- Cache survives server restarts
- Up to 500 items cached (oldest evicted automatically)

---

## 10. FEATURE WALKTHROUGHS

### A. Upload a PDF
1. Click **📤 Upload PDF**
2. Click "Browse files" and select your PDF
3. Click **Process & Index PDF**
4. Wait for the spinner to finish (time depends on PDF size)
5. You'll see: pages extracted, chunks created, ID assigned

### B. Ask a Question (RAG)
1. Select your document in the sidebar
2. Go to **💬 Ask Questions**
3. Type a question in the input box
4. The AI searches your textbook for relevant passages, then generates an answer
5. Expand **Sources** to see exactly which pages the answer came from

### C. Generate Flashcards
1. Go to **🃏 Flashcards**
2. Optionally enter a topic (e.g. "Chapter 3: Pharmacokinetics")
3. Set the number of cards (5-30)
4. Click **Generate Flashcards**
5. Click through cards, click **Reveal Answer** to flip
6. Click **Download Anki CSV** to export for Anki spaced-repetition

### D. Take an MCQ Quiz
1. Go to **📝 MCQ Quiz**
2. Optionally enter a topic
3. Click **Generate Quiz**
4. Answer all questions using radio buttons
5. Click **Submit Quiz**
6. See your score, which questions you got wrong, and detailed explanations

### E. Track Progress
1. Go to **📊 Progress**
2. See overall accuracy, weak topics (< 60%), strong topics (≥ 80%)
3. Topic breakdown shows how you're doing on each subject
4. Recent sessions show your study history

### F. Check Prerequisites
1. Go to **🔍 Prerequisites**
2. Type the topic you're about to study
3. AI identifies what foundational concepts you need
4. Shows your weak related topics from your actual quiz history
5. Gives a step-by-step study order

---

## 11. TROUBLESHOOTING

### ❌ "Backend not reachable"
- Make sure the FastAPI server is running in Terminal 1
- Check that it says `Uvicorn running on http://0.0.0.0:8000`
- Try opening http://localhost:8000/health directly

### ❌ "All LLM providers failed"
- Check your `.env` file has a valid API key
- For Groq: verify at https://console.groq.com/keys
- For HuggingFace: verify at https://huggingface.co/settings/tokens
- Check you have internet access

### ❌ "Could not extract text from this PDF"
- The PDF is likely scanned (images of text, not actual text)
- Try a different PDF — download digital textbooks in PDF format
- Some university PDFs are protected — try another source

### ❌ First install fails / takes too long
- Ensure you have 500 MB free disk space
- Torch and FAISS are large — the install takes 5-10 minutes on slow connections
- If pip fails: try `pip install --upgrade pip` first

### ❌ Streamlit shows blank page
- Hard-refresh the browser: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
- Check the Streamlit terminal for error messages

### ⏱️ Answers are slow (30+ seconds)
- On free tier, this is normal for HuggingFace (model warm-up)
- Groq is much faster — make sure your Groq key is set
- After the first call, responses are cached and return instantly

### ❌ Render backend sleeps (504 timeout)
- Free Render services sleep after 15 min of inactivity
- First request after sleep takes 30-60 seconds
- This is normal on the free plan — upgrade to Starter ($7/mo) to avoid it

---

## 12. SCALING STRATEGY (FUTURE)

When you're ready to scale beyond the free tier:

### Performance
| Upgrade | Impact | Cost |
|---------|--------|------|
| Render Starter plan | No cold starts, faster CPU | $7/mo |
| Replace SQLite → PostgreSQL | Better concurrent queries | Free on Render |
| Replace FAISS → Pinecone | Cloud vector DB, no disk needed | Free tier available |
| Add Redis cache | Faster caching vs disk JSON | ~$5/mo |

### AI Models
| Upgrade | Impact | Cost |
|---------|--------|------|
| Groq paid tier | Higher rate limits | Pay per token |
| OpenAI GPT-4o | Much better quality | ~$5-15/mo typical |
| Local Ollama | Privacy, no API limits | Free (your hardware) |

### Architecture
```
Current (MVP):
  Streamlit ──► FastAPI ──► SQLite + FAISS (disk)

Future (Production):
  Next.js/React ──► FastAPI + Worker Queue
       │                    │
       │            ┌───────┴────────┐
       │            │                │
       │        PostgreSQL      Pinecone DB
       │                             │
       └──────► Redis Cache ◄────────┘
                (faster responses)
```

### Multi-user support
The current MVP uses `"default_student"` as the student ID.
To support multiple users, add:
1. A simple login (FastAPI + JWT tokens)
2. Pass the real `student_id` from the frontend
3. All progress tracking is already designed to be per-student

---

## API DOCUMENTATION

When the backend is running, visit:
- **Interactive docs**: http://localhost:8000/docs
- **Alternative docs**: http://localhost:8000/redoc

### Key Endpoints

```
POST /api/v1/pdf/upload          Upload a PDF
GET  /api/v1/pdf/list            List all documents
POST /api/v1/qa/ask              Ask a question (RAG)
POST /api/v1/flashcards/generate Generate flashcards
GET  /api/v1/flashcards/export/{doc_id}  Export Anki CSV
POST /api/v1/mcq/generate        Generate MCQ quiz
POST /api/v1/mcq/submit          Submit quiz answers
GET  /api/v1/progress/{doc_id}   Get progress data
POST /api/v1/prereq/check        Check prerequisites
GET  /health                     Health check
```

---

*Built with ❤️ using FastAPI, Streamlit, FAISS, Groq, and HuggingFace.*
*100% free to run. No paid APIs required.*
