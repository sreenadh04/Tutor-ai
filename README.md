# MediTutor AI

MediTutor AI started from a very practical observation from MBBS students.

Unlike many other learners, medical students often cannot rely on short notes alone. They need to study directly from dense textbooks, understand concepts deeply, retain them for long periods, and revise them repeatedly in a structured way. The same pattern also appears in other serious exam ecosystems such as NEET PG, NEET UG, JEE, and GATE, where students are highly dependent on textbooks, conceptual clarity, and disciplined revision.

During discussions with students, one recurring point came up again and again: revision is where many learners struggle the most. They may read a chapter once, even understand it reasonably well, but they do not always have an effective system to revisit and retain what they studied. Some students use tools like Anki to manually create flashcards and revise using spaced repetition, but building that material by hand from large textbooks is slow, repetitive, and mentally expensive.

That is where the core project idea came from:

> Can generative AI and RAG be used to turn heavy textbook study into an interactive, revision-friendly learning system without losing grounding in the actual source material?

MediTutor AI is the answer to that question. It is a full-stack, AI-powered study assistant for textbook-based learning. A user uploads a PDF, the system extracts and chunks the text, builds a searchable knowledge base, and then enables grounded question answering, flashcard generation, MCQ generation, prerequisite guidance, and progress tracking.

This project is built with a FastAPI backend and a Streamlit frontend. The backend uses local embeddings, FAISS vector search, SQLite persistence, and free-tier LLM providers. The frontend provides a lightweight multi-page study experience.

## Origin of the Project

The real motivation behind this project is not “build another chatbot.”

The motivation is to support learners who:

- study from large, concept-heavy textbooks
- need understanding, not just summaries
- revise repeatedly over weeks and months
- prepare for competitive or professional exams where retention matters as much as first-time learning

This makes GenAI and RAG a very strong fit:

- RAG helps keep answers grounded in the actual textbook instead of generic AI guesses
- generative AI can turn textbook content into flashcards, quizzes, and study explanations
- progress tracking can help identify weak areas over time
- prerequisite analysis can help students know what to study first before tackling difficult concepts

In simple terms, the project aims to bridge this gap:

```text
Heavy textbook learning
        +
Poor revision workflow
        +
Manual flashcard effort
        =
High cognitive load for students
```

MediTutor AI tries to reduce that cognitive load by transforming textbooks into an interactive study system.

## Problem Statement

Students who depend heavily on textbooks, especially MBBS students and serious exam aspirants, often face a very specific learning problem:

- they must study large volumes of dense material
- they need conceptual understanding, not shallow memorization
- they need strong revision strategies over time
- they often lack a fast way to convert textbook content into reusable revision material

Traditional reading alone is not enough because it creates several practical bottlenecks:

- searching for a specific concept in a large document is slow
- asking targeted questions about a document requires manual reading and cross-referencing
- generating revision material such as flashcards and quizzes takes extra effort
- learners struggle to identify weak topics and prerequisite gaps
- most AI tools are generic and not grounded in the user’s own material
- many AI solutions are not designed safely for multi-user environments

MediTutor AI addresses these problems by creating a document-grounded AI study workflow that is specific to each user and each uploaded document.

## What This Project Does With GenAI and RAG

This project applies generative AI and retrieval-augmented generation in a focused and practical way rather than using AI for vague open-ended chat.

### 1. Textbook Grounding Through RAG

Instead of answering from generic model memory, the system:

- retrieves relevant chunks from the uploaded textbook
- uses those chunks as context
- generates answers grounded in the actual source material

This is important for medical and exam-focused learning because students need textbook-faithful responses.

### 2. AI-Powered Revision Material

Once the document is indexed, generative AI can turn raw textbook content into:

- flashcards for revision
- MCQs for active recall
- structured study explanations
- prerequisite suggestions for difficult concepts

This is where your GenAI knowledge becomes genuinely useful. You are not replacing studying; you are reducing the friction involved in revising effectively.

### 3. Personalized Learning Feedback

By combining generated quizzes with progress tracking, the system can:

- identify weak topics
- show strong topics
- help the user focus revision where it matters most

### 4. A Bridge Between Textbooks and Spaced Revision

Students already use tools like Anki because spaced revision works. The opportunity here is:

- use AI to generate revision material from textbooks faster
- let students review that material inside your app
- optionally export flashcards for external spaced-repetition workflows

That makes the project especially valuable for users who are revision-heavy and textbook-heavy at the same time.

## Solution Overview

The system provides a document-centered study pipeline:

1. A user uploads a PDF.
2. The backend extracts text page by page.
3. The text is split into overlapping chunks.
4. Chunks are embedded using a local sentence-transformers model.
5. Embeddings are stored in a user-isolated FAISS index.
6. The user can:
   - ask grounded questions
   - generate flashcards
   - generate MCQ quizzes
   - track progress over time
   - identify weak and prerequisite topics

The project is designed around these principles:

- grounded AI responses
- full user isolation
- production-safe request handling
- compatibility with free services where possible
- local persistence for uploads, vectors, cache, and progress

## Core Goals

- prevent cross-user data leakage
- ensure every document, cache entry, vector index, and progress record is user-scoped
- keep the backend usable on low-cost or free infrastructure where possible
- maintain a clean separation between UI, API, business logic, and storage

## Key Features

### 1. PDF Upload and Processing

Users upload text-based PDFs. The backend:

- validates file type and size
- stores the file on disk
- extracts text using PyMuPDF
- chunks content using a recursive text splitter
- records document metadata in SQLite
- creates a user-scoped vector index

### 2. RAG-Based Q&A

The Q&A flow:

- receives a question for a specific document
- verifies document ownership
- retrieves top matching chunks from the user’s vector index
- builds a context-aware prompt
- calls an LLM provider
- returns an answer with source citations

This keeps answers grounded in the uploaded material instead of generic unsupported responses.

### 3. Flashcard Generation

The flashcard module:

- retrieves relevant document chunks
- prompts the LLM to generate structured flashcards
- parses and validates model output
- stores generated flashcards in the database
- supports CSV export for Anki-style usage

### 4. MCQ Quiz Generation and Grading

The MCQ module:

- retrieves relevant chunks
- generates four-option multiple-choice questions
- validates options and explanations
- stores generated MCQs
- accepts answer submission
- grades the quiz
- updates progress and topic-level performance

### 5. Progress Tracking

The progress subsystem tracks:

- study sessions
- question attempts
- topic-level attempts and accuracy
- weak topics
- strong topics
- recent learning sessions

This lets the user measure improvement over time rather than only consuming generated content.

### 6. Prerequisite Guidance

The prerequisite checker combines:

- relevant document chunks from vector retrieval
- the user’s own weak topics from progress tracking
- an LLM prompt that identifies missing concepts and recommended study order

This helps students answer the question: “What should I know first before understanding this topic?”

## Architecture

## High-Level Architecture

```text
Frontend (Streamlit)
    |
    | HTTP / JSON + X-User-ID
    v
Backend (FastAPI)
    |
    +-- Routers
    |     +-- PDF Router
    |     +-- QA Router
    |     +-- Flashcard Router
    |     +-- MCQ Router
    |     +-- Progress Router
    |     +-- Prerequisite Router
    |
    +-- Services
    |     +-- PDF Service
    |     +-- Vector Service
    |     +-- LLM Service
    |     +-- Flashcard Service
    |     +-- MCQ Service
    |     +-- Progress Service
    |
    +-- Storage
          +-- SQLite database
          +-- Uploaded PDF files
          +-- FAISS vector indexes
          +-- Disk cache
```

## Backend Stack

- FastAPI
- SQLAlchemy
- SQLite
- FAISS
- sentence-transformers
- PyMuPDF
- httpx

## Frontend Stack

- Streamlit
- requests

## Data Flow by Feature

### PDF Pipeline

```text
PDF Upload
  -> Save file to local disk
  -> Extract page text
  -> Chunk text
  -> Generate embeddings
  -> Build FAISS index
  -> Save document metadata in SQLite
```

### Q&A Pipeline

```text
User question
  -> Verify user owns document
  -> Retrieve top-k chunks from FAISS
  -> Build prompt
  -> Call LLM
  -> Return answer + sources
```

### Flashcard Pipeline

```text
Generate flashcards request
  -> Verify ownership
  -> Retrieve relevant chunks
  -> Prompt LLM
  -> Parse JSON response
  -> Store flashcards
  -> Return cards
```

### MCQ Pipeline

```text
Generate quiz
  -> Verify ownership
  -> Retrieve relevant chunks
  -> Prompt LLM
  -> Parse questions
  -> Store MCQs

Submit quiz
  -> Verify ownership and session
  -> Grade answers
  -> Record attempts
  -> Update topic progress
```

## Repository Structure

```text
backend/
  config.py
  database.py
  main.py
  models.py
  routers/
  services/
  utils/
  data/

frontend/
  app.py
  common.py
  pages/

render.yaml
Procfile
README.md
```

## Backend Design

### main.py

The backend entrypoint configures:

- FastAPI app creation
- request ID middleware
- auth middleware
- lightweight per-user request rate limiting
- CORS
- gzip compression
- health checks
- user data management endpoints

### database.py

The database layer defines:

- `Document`
- `StudySession`
- `QuestionAttempt`
- `Flashcard`
- `MCQuestion`
- `TopicProgress`

It also includes compatibility migrations for older rows and user-related columns.

### models.py

Pydantic models define typed request and response schemas for:

- PDF metadata
- Q&A
- flashcards
- MCQs
- progress
- prerequisite checks

### routers/

Routers handle API boundaries:

- input validation
- extracting authenticated `user_id`
- ownership verification
- translation between HTTP requests and service-layer logic

### services/

Services contain business logic:

- PDF extraction and chunking
- vector indexing and search
- LLM provider fallback
- flashcard generation
- MCQ generation and grading
- session and progress updates

### utils/cache.py

The cache manager stores cached JSON responses on disk, scoped per user.

## Frontend Design

The frontend is a multi-page Streamlit application.

### app.py

The home page:

- initializes shared session state
- displays document selection
- starts study sessions
- shows backend health information

### common.py

This module centralizes:

- backend base URL resolution
- `user_id` creation in session state
- API header generation
- study session initialization

### Pages

- `1_Upload.py`: upload and document listing
- `2_QA_Chat.py`: grounded document chat
- `3_Flashcards.py`: flashcard generation and review
- `4_MCQ_Quiz.py`: quiz generation and submission
- `5_Progress.py`: topic and session analytics
- `6_Prereq.py`: prerequisite analysis

## Multi-User Isolation and Security

This project underwent a security-focused refactor to eliminate cross-user leakage.

### User Isolation Strategy

The backend now treats `X-User-ID` as the primary authenticated user context for every feature.

User isolation is enforced across:

- database records
- uploaded files
- vector indexes
- cached responses
- sessions
- progress tracking

### What Was Fixed

The following major issues were addressed:

- vector indexes are now stored per user and per document
- routers verify document ownership before read, delete, export, and generation operations
- `default_student` usage was removed from active request flows
- frontend now sends `X-User-ID` consistently
- cache entries are user-scoped
- session handling is bound to the current user
- prerequisite and progress flows use the actual authenticated user

### Current Auth Model

The project currently uses client-generated UUIDs sent in `X-User-ID`.

This provides isolation but is not full identity authentication. For stronger production security, the next step would be integrating a real auth layer such as:

- JWT-based auth
- Clerk
- Supabase Auth
- Auth0

For the current stage, the important improvement is that the backend now consistently enforces ownership based on request user context instead of ignoring it.

## LLM and Retrieval Strategy

### Embeddings

Embeddings are generated locally with:

- `sentence-transformers/all-MiniLM-L6-v2`

Advantages:

- no paid embedding API required
- consistent local vectorization
- better retrieval quality than simple keyword search

Tradeoff:

- memory usage is significantly higher than a lightweight lexical search system

### Vector Search

FAISS is used for semantic retrieval.

The vector service:

- loads or builds a document-specific index
- supports exact and large-index strategies
- stores metadata alongside vectors
- ensures each user’s data is isolated

### LLM Providers

The LLM service uses a fallback strategy:

1. Groq
2. Hugging Face Inference API

This keeps the project compatible with free-tier AI usage while still allowing generation features.

## Database Schema Summary

### Document

Stores:

- document ID
- filename
- total pages
- total chunks
- vector storage path
- user ID
- created timestamp

### StudySession

Stores:

- session ID
- document ID
- user ID
- start/end timestamps

### QuestionAttempt

Stores:

- session ID
- user ID
- question text and type
- topic
- user answer
- correct answer
- correctness
- score

### Flashcard

Stores:

- flashcard content
- linked document
- user ID
- difficulty
- review metadata

### MCQuestion

Stores:

- question text
- answer options
- explanation
- topic
- user ID

### TopicProgress

Stores:

- user ID
- document ID
- topic
- attempts
- correct answers
- accuracy
- weak-topic flag

## Deployment Status

## What Was Successfully Deployed

The project was deployed on Render in this state:

- backend deployed and reachable
- health endpoint working
- database reachable
- vector service loading
- LLM keys configured
- frontend able to communicate with backend

The backend health response confirmed:

- app startup success
- database success
- vector store success
- LLM provider configuration success

## Render Issue Encountered

The backend repeatedly failed on Render free tier due to memory limits.

Observed Render failure:

- service exceeded 512 MB RAM
- instance was killed
- frontend received HTTP 502 during upload

This is an infrastructure limitation, not a correctness bug in the business logic.

### Why Render Free Tier Fails

The combination of these components is too heavy for 512 MB RAM:

- sentence-transformers
- PyTorch dependency chain
- FAISS
- PDF extraction and chunking
- active request processing

The backend sometimes starts successfully but becomes unstable during uploads or memory-intensive operations.

## Current Recommended Hosting Direction

For this codebase as it exists today:

- frontend can remain on Render or Streamlit
- backend should move to a higher-memory host

Recommended option:

- Oracle Cloud Always Free VM for backend

Reason:

- enough memory for local embeddings + FAISS + FastAPI
- preserves current architecture
- avoids major backend redesign

## Render Configuration Notes

The project includes [render.yaml](./render.yaml) for backend deployment.

The persistent disk mount path was corrected to:

```yaml
/opt/render/project/src/backend/data
```

This aligns Render storage with the backend’s actual runtime path.

## Environment Variables

### Backend

- `GROQ_API_KEY`
- `HUGGINGFACE_API_KEY`
- `ALLOWED_ORIGINS`
- `DEBUG`

### Frontend

- `BACKEND_URL`

## Local Development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## API Summary

### PDF

- `POST /api/v1/pdf/upload`
- `GET /api/v1/pdf/list`
- `GET /api/v1/pdf/{doc_id}`
- `DELETE /api/v1/pdf/{doc_id}`
- `POST /api/v1/pdf/{doc_id}/reprocess`

### QA

- `POST /api/v1/qa/ask`
- `POST /api/v1/qa/ask/batch`
- `GET /api/v1/qa/suggestions/{document_id}`

### Flashcards

- `POST /api/v1/flashcards/generate`
- `GET /api/v1/flashcards/list/{doc_id}`
- `GET /api/v1/flashcards/{flashcard_id}`
- `POST /api/v1/flashcards/{flashcard_id}/review`
- `GET /api/v1/flashcards/export/{doc_id}`
- `DELETE /api/v1/flashcards/{flashcard_id}`

### MCQ

- `POST /api/v1/mcq/generate`
- `POST /api/v1/mcq/submit`

### Progress

- `POST /api/v1/progress/session/start`
- `POST /api/v1/progress/session/{session_id}/end`
- `GET /api/v1/progress/{document_id}`

### Prerequisites

- `POST /api/v1/prereq/check`

### Utility

- `GET /health`
- `DELETE /api/v1/user/data`
- `GET /api/v1/user/stats`

## Project Strengths

- strong modular separation
- full document-grounded AI workflow
- improved multi-user isolation
- free-provider-compatible architecture
- end-to-end educational workflow instead of a single chatbot feature
- clean upgrade path to stronger auth and more scalable storage

## Current Limitations

- current user identity is UUID-based, not full auth
- SQLite is fine for lightweight use but not ideal for high concurrency
- local embeddings are memory-heavy for very small free hosts
- Render free tier is insufficient for this backend architecture
- uploaded PDFs must be text-based, not image-only scans

## Future Improvements

- integrate true auth
- move from SQLite to PostgreSQL if multi-user scale grows
- add OCR for scanned PDFs
- support background indexing jobs
- add vector index compaction and cleanup
- support async task queues for large uploads
- introduce a lighter retrieval mode for ultra-low-memory deployments
- add automated tests for routers and service ownership checks

## Summary

MediTutor AI is a document-grounded AI study platform designed to turn static PDFs into interactive learning experiences. It supports upload, retrieval, Q&A, flashcards, quizzes, progress analytics, and prerequisite guidance. The codebase now enforces much stronger user isolation and is structurally sound for production-minded iteration.

The primary issue discovered during deployment was not application correctness but memory constraints on Render free tier. The next practical step for stable public access is to host the backend on a higher-memory free environment such as Oracle Cloud Always Free while keeping the existing backend architecture intact.
