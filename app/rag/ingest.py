# ============================================================
# app/rag/ingest.py
# ============================================================
# Sprint 1 — RAG Knowledge Base Ingestion Pipeline
#
# Pipeline steps:
#   1. Connect to Pinecone (create index if needed)
#   2. Load all PDFs from data/medical_docs/
#   3. Split pages into smaller chunks
#   4. Clean extracted text
#   5. Generate embeddings and upload to Pinecone
#   6. Verify the index with a test query
#
# Run once to build knowledge base:
#   python -m app.rag.ingest
# ============================================================

import os
import re
import uuid
from pathlib import Path
from typing import List

from tqdm import tqdm
from pinecone import Pinecone, ServerlessSpec
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.utils.config import config
from app.rag.embeddings import embedder

# ── Step 1: Connect to Pinecone ───────────────────────────────

def get_pinecone_index():
    """
    Connect to Pinecone and return the index.
    Creates the index automatically if it does not exist yet.
    """
    
    # Initialize Pinecone client with API key from config
    pc = Pinecone(api_key=config.PINECONE_API_KEY)
    
    # Get list of existing index names
    existing = [i.name for i in pc.list_indexes()]
    
    if config.PINECONE_INDEX not in existing:
        print(f"📦 Creating new index: '{config.PINECONE_INDEX}'")
        pc.create_index(
            name=config.PINECONE_INDEX,
            dimension=config.PINECONE_DIMENSION,  # 384 for MiniLM
            metric=config.PINECONE_METRIC,         # cosine similarity
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        print("✅ Index created")
    else:
        print(f"✅ Index '{config.PINECONE_INDEX}' already exists")

    return pc.Index(config.PINECONE_INDEX)

# ── Step 2: Load PDFs ─────────────────────────────────────────

def load_documents(docs_dir: str = "data/medical_docs") -> List:
    """
    Load all PDF files from the medical_docs directory.
    Each page becomes a separate Document object with metadata.
    """
    docs_path = Path(docs_dir)
    
    if not docs_path.exists():
        raise FileNotFoundError(f"Folder not found: {docs_dir}")
    
    # Count available PDFs
    pdf_files = list(docs_path.glob("*.pdf"))
    if not pdf_files:
        raise ValueError(
            f"No PDFs found in {docs_dir}.\n"
            f"Add medical PDFs to this folder and try again."
        )
    
    print(f"📂 Found {len(pdf_files)} PDF files")
    
    # DirectoryLoader loads all PDFs at once
    loader = DirectoryLoader(
        str(docs_path),
        glob="*.pdf",
        loader_cls=PyPDFLoader,
        show_progress=True
    )
    
    documents = loader.load()
    print(f"📄 Loaded {len(documents)} pages total")
    return documents

# ── Step 3: Split into Chunks ─────────────────────────────────

def split_documents(documents: List) -> List:
    """
    Split pages into smaller overlapping chunks.

    Why we split:
    - LLMs have token limits — we can't pass entire books
    - Smaller chunks allow more precise retrieval
    - Overlap preserves context at chunk boundaries
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        # Try splitting at paragraphs first, then sentences, then words
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    chunks = splitter.split_documents(documents)
    print(f"✂️  Created {len(chunks)} chunks")
    return chunks

# ── Step 4: Clean Text ────────────────────────────────────────

def clean_text(text: str) -> str:
    """
    Clean raw PDF text before embedding.

    PDFs often contain:
    - Repeated page headers and footers
    - Page numbers mid-sentence
    - Multiple consecutive spaces and newlines
    """
    # Remove page number patterns like "Page 1 of 50"
    text = re.sub(r'\bPage\s+\d+\s*(of\s*\d+)?\b', '', text, flags=re.IGNORECASE)
    
    # Collapse multiple spaces into one
    text = re.sub(r' {2,}', ' ', text)

    # Collapse more than 2 newlines into 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove copyright lines
    text = re.sub(r'(?i)(copyright|all rights reserved).*?\n', '', text)

    return text.strip()

def upload_to_pinecone(chunks: List, index, namespace: str, batch_size: int = 100) -> int:
    """
    Embed each chunk and upload to Pinecone in batches.

    Args:
        chunks:     Document chunks to upload.
        index:      Pinecone index object.
        namespace:  Which namespace to upload to.
        batch_size: Vectors per API call (100 is Pinecone's recommended max).

    Returns:
        Total number of vectors uploaded.
    """
    total = 0
    
    for i in tqdm(range(0, len(chunks), batch_size), desc="☁️  Uploading"):
        batch = chunks[i: i + batch_size]
        
        # Clean text for each chunk in the batch
        texts = [clean_text(chunk.page_content) for chunk in batch]
        
        # Skip chunks that are too short to be useful
        valid = [(t, c) for t, c in zip(texts, batch) if len(t) > 50]
        if not valid:
            continue
        
        texts, batch = zip(*valid)
        
        # Generate embeddings for the whole batch at once
        vectors = embedder.embed_batch(list(texts))
        
        # Build Pinecone records — each needs an id, vector, and metadata
        records = []
        for j, (text, vector, chunk) in enumerate(zip(texts,vectors, batch)):
            records.append({
                "id": str(uuid.uuid4()), # Unique ID for each chunk
                "values": vector,        # 384-dim embedding vector
                "metadata": {
                    "text": text,
                    "source": chunk.metadata.get("source", ""),
                    "page": chunk.metadata.get("page", 0),
                    "chunk_index": i+j,
                }
            })
            
        # Upsert means insert or update if ID already exists
        index.upsert(vectors=records, namespace=namespace)
        total += len(records)

    return total

# ── Step 6: Verify ────────────────────────────────────────────

def verify_index(index, namespace: str) -> None:
    """
    Run a test query to confirm retrieval is working.
    """
    print("\n🔍 Running verification query...")
    
    test_vector = embedder.embed_text("symptoms and treatment of diabetes")
    
    results = index.query(
        vector=test_vector,
        top_k=3,
        namespace=namespace,
        include_metadata=True
    )
    
    if results["matches"]:
        top = results["matches"][0]
        print(f"✅ Verification passed!")
        print(f"   Top result score : {top['score']:.3f}")
        print(f"   Source           : {top['metadata'].get('source', 'unknown')}")
    else:
        print("⚠️  No results returned — check your PDFs were uploaded.")

# ── Main Pipeline ─────────────────────────────────────────────

def run_ingestion_pipeline(docs_dir: str = "data/medical_docs") -> None:
    """
    Run the complete ingestion pipeline end to end.
    """
    print("=" * 55)
    print("MediResearch AI — RAG Ingestion Pipeline")
    print("=" * 55)

    # Step 1: Connect
    index = get_pinecone_index()
    
    # Show current vector count before ingestion
    stats = index.describe_index_stats()
    print(f"\n Vectors before ingestion: {stats.get('total_vector_count', 0)}")
    # Steps 2–3: Load and split
    documents = load_documents(docs_dir)
    chunks    = split_documents(documents)

    # Steps 4–5: Clean, embed, upload
    print(f"\n  Uploading to namespace '{config.PINECONE_DOCS_NAMESPACE}'...")
    total = upload_to_pinecone(
        chunks,
        index,
        namespace=config.PINECONE_DOCS_NAMESPACE
    )
    print(f"\n Upload complete — {total} vectors uploaded")

    # Step 6: Verify
    verify_index(index, namespace=config.PINECONE_DOCS_NAMESPACE)

    # Final count
    stats = index.describe_index_stats()
    print(f"\n Vectors after ingestion : {stats.get('total_vector_count', 0)}")
    print("\n Knowledge base is ready!")


# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    run_ingestion_pipeline()