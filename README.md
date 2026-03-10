<p align="center">
  <img src="https://img.shields.io/badge/Version-3.0-blue?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.11-green?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/React-18-blue?style=flat-square&logo=react" alt="React">
  <img src="https://img.shields.io/badge/FastAPI-0.115-teal?style=flat-square&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/XGBoost-AUC%200.91-orange?style=flat-square" alt="XGBoost">
</p>

# Intelli-Credit

**AI-Powered Corporate Credit Decisioning Engine for Indian Banks**

An end-to-end credit appraisal platform that automates the traditionally manual 4–6 week process of corporate loan assessment. The system ingests multi-source financial data, runs ML-based risk scoring, executes agentic workflows for research and analysis, and auto-generates explainable Credit Appraisal Memos (CAMs) — reducing turnaround from weeks to minutes.

> Built for the IIT Hyderabad Hackathon — March 2026

---

## Table of Contents

- [Key Features](#key-features)
- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Application Flow](#application-flow)
- [ML Models](#ml-models)
- [Agentic Workflows](#agentic-workflows)
- [5-Portal Architecture](#5-portal-architecture)
- [Database Schema](#database-schema)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Deployment](#deployment)
- [Environment Variables](#environment-variables)
- [API Documentation](#api-documentation)
- [Team](#team)

---

## Key Features

- **Multi-Source Document Parsing** — Docling + PyMuPDF + EasyOCR extract structured data from messy Indian financial PDFs (balance sheets, ITRs, GST returns, bank statements)
- **4 Specialized ML Models** — Pre-qualification eligibility, XGBoost credit risk scoring (AUC 0.91), circular trading detection via Isolation Forest, and banking behavior analysis
- **8 LangGraph Agentic Workflows** — Document intelligence, financial extraction, GST analysis, research aggregation, qualitative scoring, risk timeline building, CAM writing, and policy checking
- **SHAP Explainability** — Every credit decision comes with a SHAP waterfall showing exactly which factors increased or decreased the risk score
- **Risk Timeline** — Chronological aggregation of all red flags across financial anomalies, GST issues, bank bounces, legal proceedings, and news — a unique differentiator
- **Circular Trading Detection** — ML + rule-based GST fraud detection catching fake invoices, ITC manipulation, and revenue inflation
- **Auto-Generated CAM** — AI-generated Credit Appraisal Memo with citations to source documents, editable by analysts
- **5 Role-Based Portals** — Mirrors real Indian banking hierarchy: Borrower → RM → Analyst → Credit Manager → Sanctioning Authority
- **Field Visit Before CAM** — Correct banking sequence where field verification informs the credit memo, not the other way around

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Vite + React)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐ ┌───────────┐│
│  │ Borrower │ │    RM    │ │ Analyst  │ │  CM  │ │Sanctioning││
│  │  Portal  │ │  Portal  │ │  Portal  │ │Portal│ │  Portal   ││
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──┬───┘ └─────┬─────┘│
└───────┼────────────┼────────────┼───────────┼───────────┼──────┘
        │            │            │           │           │
        └────────────┴─────┬──────┴───────────┴───────────┘
                           │ REST API
┌──────────────────────────┴──────────────────────────────────────┐
│                     BACKEND (FastAPI)                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │  API Layer │  │  ML Layer  │  │  Services  │                │
│  │ 8 endpoints│  │  4 models  │  │ Groq/Tavily│                │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘                │
│        │               │               │                        │
│  ┌─────┴───────────────┴───────────────┴──────┐                │
│  │         LangGraph Agent Orchestration       │                │
│  │   12 nodes • research subgraph • stateful   │                │
│  └─────────────────────┬───────────────────────┘                │
└────────────────────────┼────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
  ┌─────┴─────┐   ┌──────┴─────┐   ┌─────┴─────┐
  │ Supabase  │   │  Firebase  │   │  External │
  │ PostgreSQL│   │    Auth    │   │   APIs    │
  │ + pgvector│   │   + JWT    │   │Tavily/MCA │
  │ + Storage │   │            │   │eCourts/RBI│
  │ + Realtime│   │            │   │           │
  └───────────┘   └────────────┘   └───────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | React 18 + TypeScript + Vite | SPA with role-based portals |
| **UI Components** | shadcn/ui + Tailwind CSS + Recharts | Design system + data visualization |
| **Backend** | FastAPI (Python 3.11) | Async API with ML inference |
| **Authentication** | Firebase Auth + JWT | Role-based access (5 roles) |
| **Database** | Supabase (PostgreSQL + pgvector) | Data storage + vector search + RLS |
| **Real-time** | Supabase Realtime | Live agent progress updates |
| **Agent Orchestration** | LangGraph | Stateful multi-agent workflows |
| **LLM** | Groq API (LLaMA 3.3 70B) | Document understanding + CAM writing |
| **Web Research** | Tavily Search API | Multi-source intelligence |
| **PDF Parsing** | Docling + PyMuPDF + EasyOCR | Table extraction + OCR for scanned docs |
| **ML Models** | XGBoost + scikit-learn + SHAP | Credit risk scoring + explainability |
| **Document Generation** | python-docx + ReportLab | CAM and sanction letter generation |
| **Deployment** | Railway (API) + Vercel (Frontend) | Production hosting |

---

## Application Flow

The system follows a **7-stage banking-aligned workflow**:

```
Stage 0: Pre-Qualification ──────→ ML eligibility model (instant)
    │
Stage 1: Document Upload ────────→ Background AI parsing
    │
Stage 2: RM Review ──────────────→ Document cross-validation
    │
Stage 3: Field Visit ────────────→ Qualitative scoring agent
    │
Stage 4: Credit Analysis ────────→ Financial/GST/Research/Timeline/CAM
    │
Stage 5: Credit Manager Review ──→ XGBoost risk scoring + SHAP
    │
Stage 6: Sanctioning Decision ───→ Auto-generated sanction letter
    │
Stage 7: Post-Sanction ──────────→ Archived with full audit trail
```

**Key design decisions:**
- Field visit happens at **Stage 3** (before CAM generation), matching real banking practice
- Pre-qualification at **Stage 0** filters weak applications early
- 5 distinct portals mirror actual Indian bank organizational hierarchy

---

## ML Models

### Model 1: Pre-Qualification (Logistic Regression)
- **Purpose:** Instant eligibility screening at Stage 0
- **Input:** 8 features (sector risk, turnover ratio, years in business, NPA flag, etc.)
- **Output:** Score 0–100 → Eligible / Borderline / Not Eligible
- **Performance:** Accuracy 78.2% · AUC-ROC 0.84 · Latency <50ms

### Model 2: Credit Risk Scoring (XGBoost)
- **Purpose:** Final risk grade assignment at Stage 5
- **Input:** 28 features across 5 categories (Financial, GST, Banking, Collateral, External)
- **Output:** Risk Grade (A–E) + Probability of Default (PD%) + SHAP waterfall
- **Performance:** Accuracy 84.7% · AUC-ROC 0.91 · Latency <200ms

### Model 3: Circular Trading Detection (Isolation Forest + Rules)
- **Purpose:** GST fraud detection at Stage 4
- **Method:** Anomaly detection + 5 rule-based checks (turnover mismatch, ITC reversal, round-tripping, etc.)
- **Output:** Risk Score 0–100 with specific flags

### Model 4: Banking Behavior Scorer (Logistic Regression)
- **Purpose:** Account health assessment at Stage 4
- **Input:** 12 time-series features (bounce rate, cash withdrawal patterns, EMI burden, etc.)
- **Output:** Banking Conduct Score 0–100

---

## Agentic Workflows

The system uses **LangGraph** to orchestrate 8 specialized agent workflows:

```
CreditAppraisalGraph (master state machine)
├── Document Intelligence Agent ──── Docling + PyMuPDF + EasyOCR parsing
├── Financial Extraction Agent ───── P&L, Balance Sheet, Cash Flow, ratios
├── GST Analysis Agent ──────────── 24-month GST processing + anomalies
├── Banking Analysis Agent ──────── 12-month bank statement analysis
├── Qualitative Scoring Agent ───── Field visit → risk adjustments
├── Research Agent (parallel) ───── Multi-source intelligence
│   ├── Company News (Tavily)
│   ├── MCA21 Check
│   ├── e-Courts Check
│   ├── RBI List Check
│   ├── Sector Research
│   └── Research Aggregator
├── Anomaly Detection Agent ─────── Cross-source red flag detection
├── Risk Timeline Builder ──────── Chronological risk event mapping
├── ML Scoring Agent ────────────── XGBoost + SHAP inference
├── Policy Check Agent ─────────── Credit policy rules engine
├── CAM Writer Agent ────────────── LLM-generated CAM with citations
└── Sanction Letter Agent ──────── Auto-generated approval/rejection letters
```

All agent state is checkpointed in Supabase for crash recovery and resumability.

---

## 5-Portal Architecture

### Portal 1: Borrower Portal
- Pre-qualification form (10 fields) with instant ML eligibility check
- Smart document upload with loan-type-specific checklist
- Real-time application tracking with stage progress bar

### Portal 2: Relationship Manager (RM) Portal
- Application pipeline dashboard with filtering
- Document verification checklist with AI cross-validation
- Traffic light risk signals
- Actions: Send back / Reject / Schedule field visit / Forward to analysis

### Portal 3: Credit Analyst Portal
- **Field Visit Form** — Capacity utilization, factory condition, management assessment
- **6-Tab Analysis Workspace:**
  - Tab 1: Financial Analysis (3-year tables + ratio dashboard + charts)
  - Tab 2: GST & Banking (GST chart + ITC analysis + Banking behavior)
  - Tab 3: External Research (severity-coded findings with source attribution)
  - Tab 4: Risk Timeline (chronological red flag visualization)
  - Tab 5: CAM Generator (AI-written CAM with edit capability)
  - Tab 6: What-If Simulator (adjust inputs → see score change in real-time)

### Portal 4: Credit Manager Portal
- XGBoost Risk Score panel with grade visualization
- SHAP explainability bars (positive/negative factor contributions)
- Automated policy checklist (pass/fail/exception flags)
- Actions: Approve / Modify / Return / Reject

### Portal 5: Sanctioning Authority Portal
- One-screen decision pack (borrower info, risk grade, key metrics, SHAP summary)
- Full CAM document access
- Actions: Approve / Approve with modifications / Reject / Return for DD

---

## Database Schema

**17 tables** across two categories:

### Config Tables (6)
| Table | Purpose |
|---|---|
| `sector_benchmarks` | Industry-specific ratio benchmarks |
| `policy_rules` | Credit policy rules (editable by Risk team) |
| `model_config` | ML model versioning and metadata |
| `rate_config` | Interest rate bands by risk grade |
| `loan_type_config` | Document checklists by loan type |
| `sector_policy` | Sector blacklist/whitelist/restricted |

### Application Tables (11)
| Table | Purpose |
|---|---|
| `loan_applications` | Core application records |
| `documents` | Uploaded documents + extraction status |
| `extracted_financials` | 3-year P&L, BS, CF, computed ratios |
| `gst_monthly_data` | 24-month GST filing data |
| `bank_statement_data` | 12-month banking data |
| `field_visit_notes` | Field observations + risk adjustments |
| `research_findings` | Multi-source research results |
| `risk_scores` | All ML scores + SHAP values |
| `loan_decisions` | Approval/rejection records |
| `cam_documents` | Generated CAM documents |
| `audit_logs` | Complete audit trail |

All tables have Row Level Security (RLS) enabled with Supabase Realtime on `agent_progress`.

---

## Project Structure

```
intelli-credit/
├── frontend/                          # React + Vite + TypeScript
│   ├── src/
│   │   ├── pages/
│   │   │   ├── BorrowerDashboard.tsx  # Borrower portal
│   │   │   ├── PreQualForm.tsx        # Pre-qualification form
│   │   │   ├── DocumentUpload.tsx     # Document upload interface
│   │   │   ├── RMDashboard.tsx        # RM pipeline dashboard
│   │   │   ├── RMApplicationReview.tsx# RM review workspace
│   │   │   ├── FieldVisitForm.tsx     # Field visit form
│   │   │   ├── AnalysisWorkspace.tsx  # 6-tab analysis workspace
│   │   │   ├── CreditManagerDecision.tsx # CM portal
│   │   │   └── SanctioningDecision.tsx   # Sanctioning portal
│   │   ├── components/                # Reusable UI components
│   │   ├── hooks/                     # React Query API hooks
│   │   └── lib/                       # Auth, API client, utilities
│   ├── vercel.json                    # Vercel deployment config
│   └── package.json
│
├── backend/                           # FastAPI (Python 3.11)
│   ├── api/                           # REST API endpoints
│   │   ├── pre_qual.py                # Pre-qualification
│   │   ├── documents.py               # Document upload + parsing
│   │   ├── field_visit.py             # Field visit submission
│   │   ├── analysis.py                # Financial/GST/Research data
│   │   ├── cam.py                     # CAM generation + export
│   │   ├── risk_score.py              # XGBoost scoring endpoint
│   │   ├── decisions.py               # Approval/rejection workflow
│   │   └── applications.py            # Application CRUD
│   │
│   ├── agents/                        # LangGraph Agents
│   │   ├── graph.py                   # Master CreditAppraisalGraph
│   │   ├── state.py                   # Agent state definition
│   │   └── nodes/                     # 12 agent nodes
│   │       ├── document_ingestion.py
│   │       ├── financial_extraction.py
│   │       ├── gst_analysis.py
│   │       ├── banking_analysis.py
│   │       ├── qualitative_scoring.py
│   │       ├── anomaly_detection.py
│   │       ├── risk_timeline.py
│   │       ├── ml_scoring.py
│   │       ├── policy_check.py
│   │       ├── cam_writer.py
│   │       ├── sanction_letter.py
│   │       └── research/              # Parallel research subgraph
│   │           ├── company_news.py
│   │           ├── mca_check.py
│   │           ├── ecourts_check.py
│   │           ├── rbi_list_check.py
│   │           ├── sector_research.py
│   │           └── aggregator.py
│   │
│   ├── ml/                            # Machine Learning
│   │   ├── model_loader.py            # Model registry + loading
│   │   ├── feature_engineering.py     # 28-feature pipeline
│   │   ├── credit_risk_model.py       # XGBoost inference
│   │   ├── circular_trading.py        # Isolation Forest
│   │   ├── banking_scorer.py          # Banking behavior model
│   │   ├── pre_qual_model.py          # Pre-qualification model
│   │   └── models/                    # Pre-trained .pkl files
│   │       ├── credit_risk_v1.pkl
│   │       ├── pre_qual_v1.pkl
│   │       ├── isolation_forest_v1.pkl
│   │       ├── banking_scorer_v1.pkl
│   │       └── shap_explainer_v1.pkl
│   │
│   ├── parsers/                       # Document Parsers
│   │   ├── docling_parser.py
│   │   ├── pymupdf_parser.py
│   │   ├── easyocr_parser.py
│   │   ├── financial_parser.py
│   │   ├── gst_parser.py
│   │   └── banking_parser.py
│   │
│   ├── services/                      # External Services
│   │   ├── groq_service.py            # LLM integration
│   │   ├── tavily_service.py          # Web research
│   │   ├── cam_generator.py           # Document generation
│   │   └── supabase_client.py         # Database client
│   │
│   ├── migrations/                    # SQL schema migrations
│   │   ├── 001_config_tables.sql
│   │   ├── 002_application_tables.sql
│   │   └── 003_seed_data.sql
│   │
│   ├── Dockerfile                     # Production container
│   ├── railway.toml                   # Railway deployment
│   └── requirements.txt               # Python dependencies
│
└── .env.example                       # Environment variable template
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Supabase account (free tier)
- Firebase project (free tier)
- Groq API key (free tier)
- Tavily API key (free tier)

### 1. Clone the Repository

```bash
git clone https://github.com/aatmman/INTELLI-CREDIT.git
cd INTELLI-CREDIT
```

### 2. Set Up Environment Variables

```bash
cp .env.example backend/.env
```

Edit `backend/.env` with your API keys and credentials.

### 3. Initialize the Database

Run the SQL migration files in your Supabase SQL Editor in order:
1. `backend/migrations/001_config_tables.sql`
2. `backend/migrations/002_application_tables.sql`
3. `backend/migrations/003_seed_data.sql`

### 4. Start the Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`.

### 5. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

The application will be available at `http://localhost:5173`.

---

## Deployment

### Backend → Railway

1. Connect your GitHub repo at [railway.app](https://railway.app)
2. Set root directory to `backend`
3. Railway auto-detects the `Dockerfile`
4. Add environment variables in the Railway dashboard
5. Deploy

### Frontend → Vercel

1. Import your repo at [vercel.com](https://vercel.com)
2. Set root directory to `frontend`
3. Set framework preset to `Vite`
4. Add `VITE_API_URL` environment variable pointing to your Railway backend URL
5. Update the API proxy URL in `frontend/vercel.json`
6. Deploy

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key |
| `GROQ_API_KEY` | Yes | Groq API key for LLM inference |
| `TAVILY_API_KEY` | Yes | Tavily API key for web research |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Yes | Path to Firebase service account |
| `OPENAI_API_KEY` | No | OpenAI fallback key |
| `DATABRICKS_HOST` | No | Databricks Community Edition URL |
| `DATABRICKS_TOKEN` | No | Databricks access token |
| `APP_ENV` | No | `development` or `production` |
| `FRONTEND_URL` | No | Frontend URL for CORS |
| `ALLOWED_ORIGINS` | No | Comma-separated allowed origins |

---

## API Documentation

Once the backend is running, visit:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

### Key Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/pre-qual/check` | Run pre-qualification ML model |
| `POST` | `/api/documents/upload` | Upload and parse documents |
| `POST` | `/api/field-visit/submit` | Submit field visit observations |
| `GET` | `/api/analysis/{app_id}/financial` | Get financial analysis data |
| `GET` | `/api/analysis/{app_id}/gst` | Get GST analysis data |
| `GET` | `/api/analysis/{app_id}/research` | Get research findings |
| `POST` | `/api/cam/generate` | Generate Credit Appraisal Memo |
| `POST` | `/api/risk-score/compute` | Run XGBoost + SHAP scoring |
| `POST` | `/api/decisions/submit` | Submit approval/rejection |
| `GET` | `/api/applications` | List all applications |
| `GET` | `/health` | Health check |

---

## Success Metrics

| Metric | Target | Achieved |
|---|---|---|
| PDF Extraction Accuracy | >90% | 94% (Docling) |
| Credit Risk AUC-ROC | >0.85 | **0.91** |
| Pre-Qual Latency | <100ms | <50ms |
| Risk Scoring Latency | <500ms | <200ms |
| Research Sources | ≥4 | **5** (News, MCA, eCourts, RBI, Sector) |
| Portal Coverage | ≥3 | **5** |

---

## License

This project is developed for the IIT Hyderabad Hackathon (March 2026).

---

<p align="center">
  <strong>Intelli-Credit v3.0</strong> · IIT Hyderabad Hackathon 2026
</p>
