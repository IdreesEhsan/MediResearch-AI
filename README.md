# 🏥 MediResearch AI

> **Multi-Agent Medical Research Assistant** — an intelligent, LLM-powered research platform that orchestrates specialized AI agents to search, retrieve, fact-check, summarize, and export medical research — all from a clean web interface.

---

## Overview

MediResearch AI is a **multi-agent medical research assistant** built on top of LangChain, LangGraph, and Groq. It leverages a graph-based agent workflow to intelligently route research queries through a pipeline of specialized agents — performing web search, RAG-based document retrieval, news aggregation, fact-checking, summarization, and report generation — all persisted in a local SQLite database and exportable as PDF or DOCX.

The system is designed for **medical researchers, clinicians, and students** who need quick, structured, and verifiable insights from both local document corpora and the live web.

---

## Features

- 🤖 **Multi-Agent Orchestration** — LangGraph-powered workflow routes queries to the right agent(s) automatically
- 🔍 **Web Search** — Tavily & SerpAPI integration for real-time web results
- 📄 **RAG (Retrieval-Augmented Generation)** — Query your own medical PDF documents via Pinecone vector store
- 🔄 **CRAG (Corrective RAG)** — Self-correcting retrieval to improve answer quality
- 📰 **Medical News Agent** — Fetches the latest relevant medical news
- ✅ **Fact-Checking Agent** — Validates claims against retrieved sources
- 🧠 **Memory Agent** — Maintains session-level context across queries
- 📝 **Report Generation** — Auto-generates structured research reports
- 📤 **Export** — Download reports as **PDF** or **DOCX**
- 💾 **Session Persistence** — SQLite-backed research session history
- 🖥️ **Clean Web UI** — Vanilla JS + HTML frontend served over FastAPI

---

## Architecture

        User Query
            │
            ▼

┌─────────────────────────────────────────┐
│ LangGraph Workflow │
│ │
│ ┌──────────┐ ┌──────────────────┐ │
│ │ Router │─────▶│ Agent Selector │ │
│ └──────────┘ └────────┬─────────┘ │
│ │ │
│ ┌───────────────────┼───────────┤
│ ▼ ▼ ▼ │
│ Search Agent RAG Agent News Agent │
│ │ │ │ │
│ └─────┬─────┘ │ │
│ ▼ ▼ │
│ Fact-Check Agent Memory Agent │
│ │ │
│ ▼ │
│ Summarizer Agent │
│ │ │
│ ▼ │
│ Report Agent ──▶ Export Agent │
└─────────────────────────────────────────┘
│
▼
FastAPI Backend ──▶ Frontend (HTML/JS/CSS)
│
▼
SQLite (mediresearch.db)

---

## Tech Stack

| Layer               | Technology                          |
| ------------------- | ----------------------------------- |
| **LLM Provider**    | Groq (LLaMA 3 / Mixtral)            |
| **Agent Framework** | LangChain + LangGraph               |
| **Embeddings**      | Sentence Transformers               |
| **Vector Store**    | Pinecone                            |
| **Web Search**      | Tavily, SerpAPI                     |
| **Backend API**     | FastAPI + Uvicorn                   |
| **Frontend**        | HTML, CSS, Vanilla JS               |
| **Database**        | SQLite (aiosqlite)                  |
| **Document Export** | ReportLab (PDF), python-docx (DOCX) |
| **Observability**   | LangSmith                           |
| **Testing**         | Pytest + pytest-asyncio             |

---

## Project Structure

MediResearch-AI/
├── app/
│ ├── api/
│ │ ├── main.py # FastAPI app entry point
│ │ ├── routes.py # API route definitions
│ │ └── schemas.py # Pydantic request/response schemas
│ ├── agents/
│ │ ├── search_agent.py # Web search via Tavily/SerpAPI
│ │ ├── rag_agent.py # RAG over local medical documents
│ │ ├── news_agent.py # Medical news retrieval
│ │ ├── factcheck_agent.py # Claim verification agent
│ │ ├── memory_agent.py # Session memory management
│ │ ├── summarizer_agent.py # Research summarization
│ │ ├── report_agent.py # Structured report builder
│ │ └── export_agent.py # PDF/DOCX export
│ ├── graph/
│ │ ├── workflow.py # LangGraph workflow definition
│ │ ├── router.py # Query routing logic
│ │ └── state.py # Shared agent state schema
│ ├── rag/
│ │ ├── ingest.py # PDF ingestion & chunking
│ │ ├── embeddings.py # Embedding model setup
│ │ └── crag.py # Corrective RAG implementation
│ └── utils/
│ ├── config.py # App configuration
│ ├── prompts.py # LLM prompt templates
│ └── langsmith_config.py
├── frontend/
│ ├── index.html # Main research interface
│ ├── report.html # Report viewer
│ ├── sessions.html # Session history
│ ├── css/style.css
│ └── js/
│ ├── api.js
│ ├── research.js
│ ├── report.js
│ └── sessions.js
├── data/
│ └── medical_docs/ # Place your PDF documents here
├── exports/ # Generated PDF/DOCX files
├── tests/
│ ├── test_agents.py
│ ├── test_export.py
│ └── test_workflow.py
├── mediresearch.db # SQLite session store
├── requirements.txt
└── .env.example

---

## Getting Started

### Prerequisites

- Python **3.11+**
- A [Groq](https://console.groq.com/) API key
- A [Pinecone](https://www.pinecone.io/) API key and index
- A [Tavily](https://tavily.com/) API key
- _(Optional)_ A [LangSmith](https://smith.langchain.com/) API key for tracing

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/IdreesEhsan/MediResearch-AI.git
cd MediResearch-AI

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

### Environment Variables

Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

Then edit `.env`:

```env
# LLM
GROQ_API_KEY=your_groq_api_key

# Vector Store
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=your_index_name

# Web Search
TAVILY_API_KEY=your_tavily_api_key
SERPAPI_API_KEY=your_serpapi_key        # optional

# Observability (optional)
LANGSMITH_API_KEY=your_langsmith_key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=MediResearch-AI
```

### Ingest Your Documents

Place your medical PDF files inside `data/medical_docs/`, then run:

```bash
python -m app.rag.ingest
```

This will chunk, embed, and upsert your documents into Pinecone.

### Running the App

```bash
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

Then open your browser at `http://localhost:8000`.

---

## Agents

| Agent              | Responsibility                                                 |
| ------------------ | -------------------------------------------------------------- |
| `search_agent`     | Real-time web search using Tavily / SerpAPI                    |
| `rag_agent`        | Retrieves relevant chunks from local medical PDFs via Pinecone |
| `news_agent`       | Fetches the latest medical news articles                       |
| `factcheck_agent`  | Cross-validates claims against retrieved sources               |
| `memory_agent`     | Maintains and injects session-level conversation context       |
| `summarizer_agent` | Condenses multi-source results into a coherent summary         |
| `report_agent`     | Assembles a structured, citation-backed research report        |
| `export_agent`     | Serializes the final report to PDF or DOCX                     |

All agents are orchestrated by **LangGraph**, with a central router determining which agents to invoke based on query type and context availability.

---

## RAG Pipeline

1. **Ingestion** — PDFs are loaded via `pypdf`, split into chunks using `langchain-text-splitters`, and embedded with `sentence-transformers`
2. **Indexing** — Embeddings are upserted into a **Pinecone** vector index
3. **Retrieval** — On query, the top-k most relevant chunks are fetched
4. **CRAG** — A corrective step evaluates retrieval quality; if the retrieved context is insufficient, it falls back to web search to augment before passing to the LLM

---

## API Reference

| Method | Endpoint                      | Description                  |
| ------ | ----------------------------- | ---------------------------- |
| `POST` | `/api/research`               | Submit a research query      |
| `GET`  | `/api/sessions`               | List all research sessions   |
| `GET`  | `/api/sessions/{id}`          | Get a specific session       |
| `GET`  | `/api/report/{id}`            | Retrieve a generated report  |
| `GET`  | `/api/export/{id}?format=pdf` | Export report as PDF or DOCX |

Interactive docs available at `http://localhost:8000/docs`.

---

## Testing

```bash
pytest tests/ -v
```

Test modules cover:

- `test_agents.py` — Unit tests for individual agents
- `test_workflow.py` — End-to-end LangGraph workflow tests
- `test_export.py` — PDF/DOCX export validation

---
