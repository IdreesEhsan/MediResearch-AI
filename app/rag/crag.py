# ============================================================
# app/rag/crag.py
# ============================================================
# Corrective RAG (CRAG) — Quality Control for Retrieval
#
# Every chunk retrieved from Pinecone is scored and classified:
#   Score >= 0.7  → RELEVANT   ✅ passed to the LLM
#   Score 0.4–0.7 → PARTIAL    ⚠️ passed with a warning
#   Score < 0.4   → IRRELEVANT ❌ discarded completely
#
# If NO chunks pass → web search fallback activates automatically
# ============================================================

from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple

from pinecone import Pinecone

from app.utils.config import config
from app.rag.embeddings import embedder

# ── Relevance Labels ──────────────────────────────────────────

class RelevanceLabel(str, Enum):
    RELEVANT = "RELEVANT" # Score >= 0.7 ✅
    PARTIAL    = "PARTIAL"     # Score 0.4 – 0.69 ⚠️
    IRRELEVANT = "IRRELEVANT"  # Score < 0.4 ❌
    
# ── Single Chunk with Score ───────────────────────────────────

@dataclass
class ScoredChunk:
    """
    One retrieved document chunk with its relevance score and label.

    Attributes:
        text:     The actual text content of the chunk
        source:   Where it came from (filename + page number)
        score:    Cosine similarity score from Pinecone (0.0 to 1.0)
        label:    RELEVANT / PARTIAL / IRRELEVANT
        metadata: Full metadata dict stored in Pinecone
    """
    text: str
    source: str
    score: float
    label: RelevanceLabel
    metadata: dict

# ── CRAG Result ───────────────────────────────────────────────

@dataclass
class CRAGResult:
    """
    Output of a full CRAG pipeline run.

    Attributes:
        context:          Formatted text ready to inject into LLM prompt
        passed_chunks:    Chunks that passed validation
        discarded_chunks: Chunks that were filtered out
        sources:          Unique source file references
        used_fallback:    True if no chunks passed (web search needed)
    """
    context:           str
    passed_chunks:     List[ScoredChunk]
    discarded_chunks:  List[ScoredChunk]
    sources:           List[str]
    used_fallback:     bool

# ── CRAG Retriever ────────────────────────────────────────────

class CRAGRetriever:
    """
    Handles retrieval from Pinecone and CRAG validation.

    Main method to call from the RAG Agent:
        retriever = CRAGRetriever()
        result = retriever.retrieve_and_validate("diabetes treatment")
        # result.context      → inject into LLM prompt
        # result.used_fallback → True means activate web search
    """
    
    def __init__(self):
        # Connect to Pinecone using API key from config
        self.pc = Pinecone(api_key=config.PINECONE_API_KEY)
        self.index = self.pc.Index(config.PINECONE_INDEX)
    
    def retrieve(self, query: str, top_k: int = None) -> List[ScoredChunk]:
        """
        Query Pinecone and return scored chunks.

        Args:
            query: The research question to search for.
            top_k: Number of chunks to retrieve (default from config).

        Returns:
            List of ScoredChunk objects sorted by score, highest first.
        """
        top_k = top_k or config.TOP_K_RETRIEVAL
        
        # Convert query text to a 384-dim vector
        query_vector = embedder.embed_text(query)

        # Search the medical-docs namespace in Pinecone
        results = self.index.query(
            vector=query_vector,
            top_k=top_k,
            namespace=config.PINECONE_DOCS_NAMESPACE,
            include_metadata=True
        )
        
        chunks = []
        for match in results.get("matches", []):
            score = match["score"]
            metadata = match.get("metadata", {})
            
            # Classify the chunk based on its score
            if score >= config.CRAG_RELEVANT_THRESHOLD:
                label = RelevanceLabel.RELEVANT
            elif score >= config.CRAG_PARTIAL_THRESHOLD:
                label = RelevanceLabel.PARTIAL
            else:
                label = RelevanceLabel.IRRELEVANT
            
            # Build a readable source reference
            source_file = metadata.get("source", "unknown")
            page_num    = metadata.get("page", "?")
            source_ref  = f"{source_file} (page {page_num})"
            
            chunks.append(ScoredChunk(
                text=metadata.get("text", ""),
                source=source_ref,
                score=score,
                label=label,
                metadata=metadata
            ))
            
        return chunks
    
    def validate(self, chunks: List[ScoredChunk]) -> Tuple[List[ScoredChunk], List[ScoredChunk]]:
        """
        Split chunks into passed and discarded based on CRAG labels.

        Args:
            chunks: List of ScoredChunk objects from retrieve().

        Returns:
            Tuple of (passed_chunks, discarded_chunks)
        """
        passed = []
        discarded = []
        
        for chunk in chunks:
            if chunk.label == RelevanceLabel.IRRELEVANT:
                # Too low quality — discard to protect LLM from bad context
                discarded.append(chunk)
            else:
                # RELEVANT and PARTIAL both pass through
                passed.append(chunk)
        
        return passed, discarded
    
    def build_context(self, passed_chunks: List[ScoredChunk]) -> str:
        """
        Format passed chunks into a single context string for the LLM.

        Each chunk is labelled with its source and score so the
        LLM can reference them correctly in its response.

        Args:
            passed_chunks: Chunks that passed CRAG validation.

        Returns:
            Formatted context string ready for prompt injection.
        """
        if not passed_chunks:
            return "No relevant context found in knowledge base."

        parts = []
        for i, chunk in enumerate(passed_chunks, 1):
            # Show relevance label visually so LLM understands confidence
            emoji = "✅" if chunk.label == RelevanceLabel.RELEVANT else "⚠️"
            parts.append(
                f"[{i}] {emoji} Source: {chunk.source} "
                f"(score: {chunk.score:.2f})\n"
                f"{chunk.text}"
            )
        
        # Separate chunks with a divider for readability
        return "\n\n---\n\n".join(parts)
    
    def retrieve_and_validate(self, query: str) -> CRAGResult:
        """
        Full CRAG pipeline in one call.
        This is the main method called by the RAG Agent.

        Steps:
            1. Retrieve top-K chunks from Pinecone
            2. Score and classify each chunk
            3. Filter out irrelevant chunks
            4. Build context string
            5. Flag if web fallback is needed

        Args:
            query: The research question.

        Returns:
            CRAGResult with context, sources, and fallback flag.
        """
        # Step 1: Retrieve
        chunks = self.retrieve(query)
        
        # Step 2–3: Validate and split
        passed, discarded = self.validate(chunks)
        
        # Step 4: Build context string for LLM
        context = self.build_context(passed)
        
        # Step 5: Check if fallback is needed
        # Fallback activates only when ZERO chunks passed
        used_fallback = len(passed) == 0

        # Collect unique source file references for the report bibliography
        sources = list({chunk.source for chunk in passed})
        
        # Log stats so they appear in LangSmith traces
        print(
            f"📊 CRAG Stats → "
            f"Retrieved: {len(chunks)} | "
            f"Passed: {len(passed)} | "
            f"Discarded: {len(discarded)} | "
            f"Fallback: {'YES' if used_fallback else 'NO'}"
        )
        
        return CRAGResult(
            context=context,
            passed_chunks=passed,
            discarded_chunks=discarded,
            sources=sources,
            used_fallback=used_fallback
        )