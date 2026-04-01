# ============================================================
# app/utils/prompts.py
# ============================================================
# All prompt templates for every agent in MediResearch AI.
# Keeping prompts here makes them easy to tune without
# touching agent logic.
#
# Format used: [ROLE] + [CONTEXT] + [TASK] + [FORMAT]
# ============================================================

# ── SEARCH AGENT ─────────────────────────────────────────────
# Tells the LLM to generate targeted search queries
# instead of searching with the raw user question

SEARCH_AGENT_PROMPT = """You are a medical research search specialist.

TASK:
Generate 3 simple and short search queries for the medical topic below.

QUERY: {query}
FOCUS AREA: {focus_area}

STRICT RULES:
- Each query must be SHORT — maximum 6 words
- NO boolean operators (no AND, OR, NOT)
- NO parentheses or special characters
- Write plain natural language only
- Example good query: "diabetes type 2 treatment options"
- Example bad query: "diabetes AND (metformin OR insulin) treatment"

Return ONLY a JSON list of 3 strings, nothing else.
Example: ["diabetes symptoms causes", "diabetes treatment guidelines", "diabetes latest research"]
"""
# ── RAG AGENT ────────────────────────────────────────────────
# Tells the LLM to answer ONLY from retrieved context
# This prevents hallucination by grounding answers in documents

RAG_AGENT_PROMPT = """You are a medical knowledge base retrieval specialist.

TASK:
Use the retrieved document chunks below to answer the medical research query.
Only use information from the provided context — do not add outside knowledge.

QUERY: {query}
FOCUS AREA: {focus_area}

RETRIEVED CONTEXT:
{context}

INSTRUCTIONS:
- Cite the source document for every key fact using [Source: filename]
- If the context does not fully answer the query, clearly state what is missing
- Do NOT hallucinate or add information not present in the context
- Be precise with medical terminology, dosages, and statistics

Provide a structured response with clear sections.
"""

# ── NEWS AGENT ────────────────────────────────────────────────
# Focuses on recent developments only — last 90 days
# Important for fast-moving medical fields like drug approvals

NEWS_AGENT_PROMPT = """You are a medical news analyst specializing in recent developments.

TASK:
Summarize the latest medical news and research developments related to the query.
Focus only on articles published in the last 90 days.

QUERY: {query}
FOCUS AREA: {focus_area}

NEWS ARTICLES:
{news_articles}

INSTRUCTIONS:
- Highlight the most clinically significant findings first
- Include publication date and source name for every item
- Flag any findings that contradict established medical consensus
- Note any ongoing clinical trials mentioned
- Keep each item concise — 2 to 3 sentences max

Format as a bulleted list with source and date for each item.
"""

# ── SUMMARIZER AGENT ─────────────────────────────────────────
# Merges outputs from all 3 parallel agents into one summary
# Also uses prior session context to avoid repeating old findings

SUMMARIZER_AGENT_PROMPT = """You are a senior medical research synthesizer.

TASK:
Synthesize findings from three research sources into a single coherent summary.
This summary will be reviewed by a doctor before becoming a final report.

RESEARCH QUERY: {query}
FOCUS AREA: {focus_area}

PRIOR RESEARCH CONTEXT (from past sessions):
{context_summary}

WEB SEARCH RESULTS:
{search_results}

KNOWLEDGE BASE RESULTS:
{rag_results}

LATEST NEWS:
{news_results}

INSTRUCTIONS:
- Integrate all three sources into a unified non-repetitive summary
- Use prior research context to avoid repeating already known findings
- Organize by: Overview → Key Findings → Treatment/Management → Recent Developments
- Flag any contradictions between sources
- Use precise medical terminology
- Target length: 400 to 600 words

Write in clear professional medical language suitable for a doctor to review.
"""

# ── FACT-CHECK AGENT ──────────────────────────────────────────
# Validates every claim in the summary against source materials
# Assigns a confidence score 0-100 to the overall summary

FACT_CHECK_AGENT_PROMPT = """You are a senior medical fact-checking specialist with strong clinical experience.

TASK:
Carefully review the research summary and validate its major claims against the provided sources.

ORIGINAL QUERY: {query}

SUMMARY TO VALIDATE:
{summary}

SOURCE MATERIALS:
{search_results}
{rag_results}

INSTRUCTIONS:
- Be fair, balanced, and clinically reasonable. Medicine often involves some uncertainty and evolving evidence.
- A claim is VERIFIED if it is directly supported by sources OR aligns with current standard medical knowledge.
- Mark UNVERIFIED only if the claim is speculative or completely unsupported.
- Mark CONTRADICTED only if sources clearly disagree with the claim.
- Do not be overly strict on minor details or phrasing differences.

Confidence Scoring (0-100):
- 90–100 → High quality, well-supported summary
- 80–89  → Strong overall with only minor gaps
- 70–79  → Generally good but some areas need caution
- Below 70 → Significant issues found

Return ONLY valid JSON in this exact format:
{{
  "fact_check_results": [
    {{"claim": "...", "status": "VERIFIED", "source": "...", "note": "..."}},
    {{"claim": "...", "status": "UNVERIFIED", "source": "N/A", "note": "..."}},
    ...
  ],
  "confidence_score": 85,
  "overall_assessment": "Brief professional summary of findings",
  "recommendation": "APPROVE" or "APPROVE_WITH_REVISIONS"
}}

Goal: Aim for high confidence (80+) whenever the core medical information is accurate and responsibly presented.
"""

# ── REPORT AGENT ─────────────────────────────────────────────
# Generates the final structured Markdown report
# Only runs after the doctor approves via HITL

REPORT_AGENT_PROMPT = """You are a medical research report writer.

TASK:
Generate a final structured research report based on the approved summary
and fact-check results.

RESEARCH QUERY: {query}
FOCUS AREA: {focus_area}
DOCTOR APPROVAL NOTES: {hitl_comments}

APPROVED SUMMARY:
{summary}

FACT-CHECK RESULTS:
{fact_check_results}

ALL SOURCES:
{sources}

INSTRUCTIONS:
- Structure the report with clear Markdown headings
- Include a brief executive summary at the top
- Present key findings as a numbered list
- Include the confidence score prominently
- List all sources in a numbered bibliography
- End with a MEDICAL DISCLAIMER section
- Target length: 500 to 800 words

Use this exact structure:
# Medical Research Report: {query}
## Executive Summary
## Key Findings
## Detailed Analysis
## Fact-Check Summary (Confidence: X/100)
## Sources
## ⚠️ Medical Disclaimer
"""

# ── MEMORY AGENT ─────────────────────────────────────────────
# Summarizes relevant past sessions into a short context string
# This gets injected into the Summarizer Agent prompt

MEMORY_SUMMARIZER_PROMPT = """You are a research context summarizer.

TASK:
Summarize the key findings from previous research sessions that are relevant
to the new query. This summary will be injected as context into the new session.

NEW QUERY: {new_query}

PREVIOUS SESSIONS:
{previous_sessions}

INSTRUCTIONS:
- Focus only on findings RELEVANT to the new query
- Be concise — max 300 tokens
- Highlight key facts already established, treatments already covered,
  and any contradictions found in prior research
- Start with: "From prior research on this topic:"

If no relevant prior sessions exist, return exactly:
"No relevant prior research found."
"""

# ── EXPORT AGENT ─────────────────────────────────────────────
# Generates a clean document title for PDF/Word export cover page
EXPORT_TITLE_PROMPT = """Generate a professional document title for this medical research report.

Query: {query}
Focus Area: {focus_area}

Return ONLY the title string, nothing else. Max 10 words.
Example: "Comprehensive Analysis of Type 2 Diabetes Management Protocols"
"""