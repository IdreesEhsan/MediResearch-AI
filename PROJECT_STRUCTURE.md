# MediResearch AI Project Structure

The following tree is the full project structure with key files:

```
Final_Project/
├── .env
├── .env.example
├── .git/
├── .gitignore
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── routes.py
│   │   └── schemas.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── export_agent.py
│   │   ├── factcheck_agent.py
│   │   ├── memory_agent.py
│   │   ├── news_agent.py
│   │   ├── rag_agent.py
│   │   ├── report_agent.py
│   │   ├── search_agent.py
│   │   ├── summarizer_agent.py
n│   │   └── workflow_agent.py (placeholder)
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── state.py
│   │   └── workflow.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── crag.py
│   │   ├── embeddings.py
│   │   └── ingest.py
│   └── utils/
│       ├── __init__.py
│       ├── config.py
│       ├── langsmith_config.py
│       └── prompts.py
├── data/
│   ├── README.md
│   └── medical_docs/ (PDF files)
├── exports/ (generated files directory)
├── frontend/
│   ├── index.html
│   ├── report.html
│   ├── sessions.html
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── api.js
│       ├── research.js
│       ├── report.js
│       └── sessions.js
├── mediresearch.db
├── tests/
│   ├── __init__.py
│   ├── test_agents.py
│   ├── test_export.py
│   └── test_workflow.py
└── venv/
```
