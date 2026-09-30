# ⚡ Autonomous Recruitment Pipeline (ARP)

[![CI — Lint, Type-check, Test, Build](https://github.com/ravipatil-9225/Autonomous-Recruitment-Pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/ravipatil-9225/Autonomous-Recruitment-Pipeline/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/Orchestrator-LangGraph-FF6F00.svg)](https://github.com/langchain-ai/langgraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An enterprise-grade, privacy-first **Autonomous Multi-Agent Recruitment & Talent Intelligence Platform**. ARP automates the end-to-end talent acquisition lifecycle—from job description parsing, resume ingestion, and vector similarity ranking to automated technical interview generation, algorithmic bias auditing, and human-in-the-loop (HITL) recruiter decision approval.

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph Ingestion ["Ingestion & Security Layer"]
        JD["Job Description (JD)"] --> JD_Analyzer["JD Analyzer Agent<br>(Gemini 2.5 Flash)"]
        Resumes["Resume Documents<br>(PDF / DOCX)"] --> S3["S3 / MinIO Storage"]
        S3 --> AES["AES-256-GCM PII Encryption<br>+ SHA-256 De-identification"]
    end

    subgraph LangGraph ["LangGraph Multi-Agent Orchestration"]
        AES --> ParserNode["1. Resume Parser Node<br>(spaCy NER + Rule Pipeline)"]
        JD_Analyzer --> MatchNode["2. Matching & Vector Scoring<br>(all-MiniLM-L6-v2 Embeddings)"]
        ParserNode --> MatchNode
        MatchNode --> EvalNode["3. Evaluation & Ranking Agent<br>(Composite Scoring)"]
        EvalNode --> BiasNode["4. Bias Audit Agent<br>(Four-Fifths Disparate Impact)"]
        BiasNode --> Checkpoint["⏸ HITL Interrupt Checkpoint"]
        Checkpoint --> Recruiter["5. Recruiter Decision Review<br>(Approve / Reject)"]
        Recruiter --> SchedNode["6. Interview Scheduler & Outreach<br>(Calendar Booking Tool)"]
    end

    subgraph Delivery ["Presentation & API Layer"]
        SchedNode --> API["FastAPI REST & WebSocket API"]
        API --> Dashboard["Enterprise Dark-Mode Web Dashboard<br>(Live DAG Visualizer & Candidate Matrix)"]
    end
```

---

## ✨ Key Features

- 🤖 **LangGraph Multi-Agent Architecture**: Stateful cyclic execution graph with conditional checkpointing, rollbacks, and human-in-the-loop interruptions.
- 🔒 **Enterprise PII Encryption at Rest**: AES-256-GCM cryptographic envelope for candidate contact information (`name`, `email`, `phone`) and salted SHA-256 deduplication.
- ⚖️ **Algorithmic Fairness & Bias Auditing**: EEOC 4/5ths (80%) disparate impact analysis flagging statistical score divergences before recruiter review.
- ⚡ **Asynchronous Worker Queue**: Celery + Redis distributed task queue for heavy resume parsing, NER extractions, and embedding indexing.
- 📊 **Vector Similarity Engine**: ChromaDB and `all-MiniLM-L6-v2` dense embeddings for semantic skill and experience matching.
- 🖥️ **Production-Ready Web Dashboard**: High-density dark-mode UI with live LangGraph execution graphs, candidate radar breakdowns, and instant GDPR right-to-deletion controls.
- 📈 **MLflow Telemetry**: Automatic experiment logging, pipeline execution latency, candidate rankings, and audit trails.

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Agentic AI & Orchestration** | LangGraph, Google Gemini 2.5 Flash, SentenceTransformers (`all-MiniLM-L6-v2`), spaCy |
| **Backend API** | FastAPI, Pydantic v2, Python 3.11+, SQLAlchemy 2.0 (Async), Alembic |
| **Task Queue & Cache** | Celery, Redis |
| **Databases & Vector Storage** | PostgreSQL 16 (Asyncpg), ChromaDB, MinIO / AWS S3 |
| **Frontend Dashboard** | HTML5, Modern Vanilla CSS3 (Custom Design System), ES6 Modules, WebSockets |
| **DevOps & Quality** | Docker Compose, Ruff, Black, Pytest, Pytest-Asyncio, GitHub Actions CI |

---

## 🚀 Quickstart Guide

### 1. Clone & Setup Environment

```bash
git clone https://github.com/ravipatil-9225/Autonomous-Recruitment-Pipeline.git
cd Autonomous-Recruitment-Pipeline

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r backend/requirements-backend.txt
python -m spacy download en_core_web_sm
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```ini
# Security & Auth
SECRET_KEY=your_super_secret_jwt_key_at_least_32_chars
PII_ENCRYPTION_KEY=generate_with_base64_urandom_32_bytes

# AI Models
GOOGLE_API_KEY=your_gemini_api_key

# Database & Infrastructure
DATABASE_URL=postgresql+asyncpg://arp:arp_password@localhost:5432/arp_db
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
```

### 3. Run with Docker Compose (Full Stack)

To launch PostgreSQL, Redis, MinIO, Backend API, and Celery Workers:

```bash
cd backend
docker-compose up -d --build
```

Access services:
- **Web Dashboard**: [http://localhost:8000/dashboard/](http://localhost:8000/dashboard/)
- **FastAPI Interactive Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **MinIO Console**: [http://localhost:9001](http://localhost:9001)

---

## 💻 Running the Interactive CLI Pipeline

You can run the multi-agent recruitment graph directly in your terminal:

```bash
# Full interactive recruitment pipeline with recruiter HITL review:
python main.py

# Offline dry-run mode (no external APIs required):
python main.py --dry-run
```

---

## 📡 REST API Reference

| Method | Endpoint | Description | Role Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/token` | Obtain JWT Bearer access token | Public |
| `GET` | `/api/v1/jobs` | List job requisitions (paginated) | `viewer` |
| `POST` | `/api/v1/jobs` | Create new draft job requisition | `recruiter` |
| `POST` | `/api/v1/jobs/{id}/publish` | Publish job requisition (`draft` → `open`) | `recruiter` |
| `POST` | `/api/v1/resumes/upload` | Upload resume file (PDF/DOCX) for async parsing | `recruiter` |
| `DELETE` | `/api/v1/resumes/candidate/{id}` | GDPR Right-to-Deletion (Wipe PII & Chroma) | `admin` |
| `POST` | `/api/v1/pipeline/run` | Trigger async LangGraph multi-agent execution | `recruiter` |
| `GET` | `/api/v1/pipeline/{run_id}` | Get pipeline status & evaluation summary | `viewer` |
| `POST` | `/api/v1/pipeline/{run_id}/decision` | Submit recruiter HITL decision (`hire`/`no_hire`) | `recruiter` |
| `WS` | `/ws/pipeline/{run_id}` | Real-time WebSocket streaming of agent steps | Public / Client |

---

## 🧪 Testing & Code Quality

ARP enforces strict linting, code formatting, and 100% async test suite coverage:

```bash
# Run full unit & integration test suite (27 tests)
pytest tests/ -v

# Run Ruff linter
ruff check .

# Run Black code formatter check
black --check .
```

---

## 🛡️ License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
