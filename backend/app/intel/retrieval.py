"""Knowledge Base Loader and Retrieval Engine.
Maintains institutional knowledge, performs hybrid retrieval, and enforces strict zero-hallucination guards.
"""
from pathlib import Path
import re
from typing import List, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from app.contracts.models import Chunk, KnowledgeResult

DATA_DIR = Path(__file__).resolve().parent / "data"

OUT_OF_SCOPE_KEYWORDS = [
    "mbbs", "medical", "nursing", "pharmacy", "b.pharm", "bds", "dentistry", "aviation",
    "pilot", "nasa", "free laptop", "free ipad", "free flight", "free accommodation",
    "stipend", "salary for students", "cricket coach", "celebrity visit"
]


class KnowledgeStore:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.raw_chunks: List[Tuple[str, str]] = []  # (text, source)
        self.vectorizer: TfidfVectorizer | None = None
        self.tfidf_matrix = None
        self.reload()

    def reload(self):
        """Parse all markdown files in data directory into chunked entries with source anchors."""
        chunks = []
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)

        md_files = list(self.data_dir.glob("*.md"))
        for file_path in md_files:
            file_name = file_path.name
            content = file_path.read_text(encoding="utf-8")
            file_chunks = self._chunk_markdown(content, file_name)
            chunks.extend(file_chunks)

        self.raw_chunks = chunks
        if chunks:
            corpus = [f"{src} {txt}" for txt, src in chunks]
            self.vectorizer = TfidfVectorizer(
                ngram_range=(1, 2),
                stop_words="english",
                sublinear_tf=True
            )
            self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        else:
            self.vectorizer = None
            self.tfidf_matrix = None

    def _chunk_markdown(self, content: str, file_name: str) -> List[Tuple[str, str]]:
        """Split markdown by H2 (##) or H3 (###) headers, keeping section source anchors."""
        sections = []
        lines = content.splitlines()
        current_header = file_name.replace(".md", "")
        current_lines: List[str] = []

        for line in lines:
            if line.startswith("## ") or line.startswith("### "):
                if current_lines:
                    text_block = "\n".join(current_lines).strip()
                    if len(text_block) > 40:
                        slug = re.sub(r"[^a-zA-Z0-9]+", "-", current_header.lower()).strip("-")
                        source = f"{file_name}#{slug}"
                        sections.append((text_block, source))
                current_header = line.lstrip("#").strip()
                current_lines = [f"**{current_header}**"]
            else:
                current_lines.append(line)

        if current_lines:
            text_block = "\n".join(current_lines).strip()
            if len(text_block) > 40:
                slug = re.sub(r"[^a-zA-Z0-9]+", "-", current_header.lower()).strip("-")
                source = f"{file_name}#{slug}"
                sections.append((text_block, source))

        return sections

    def search(self, query: str, top_k: int = 3, threshold: float = 0.18) -> KnowledgeResult:
        """Search institutional knowledge with zero-hallucination guard."""
        q_clean = query.strip()
        q_lower = q_clean.lower()

        # 1. Out-of-scope / Hallucination trap guard
        for bad_kw in OUT_OF_SCOPE_KEYWORDS:
            if bad_kw in q_lower:
                return KnowledgeResult(answer_found=False, chunks=[])

        if not self.raw_chunks or self.vectorizer is None or self.tfidf_matrix is None:
            return KnowledgeResult(answer_found=False, chunks=[])

        # 2. Vector search via TF-IDF cosine similarity
        q_vec = self.vectorizer.transform([q_clean])
        scores = (self.tfidf_matrix * q_vec.T).toarray().flatten()

        # 3. Entity & Keyword booster
        boosted_scores = scores.copy()
        for idx, (text, source) in enumerate(self.raw_chunks):
            txt_lower = text.lower()
            # Scholarship specific boosts
            if "scholarship" in q_lower and "scholarship" in txt_lower:
                boosted_scores[idx] += 0.15
            if "b.tech" in q_lower or "btech" in q_lower or "engineering" in q_lower:
                if "b.tech" in txt_lower or "bachelor of technology" in txt_lower:
                    boosted_scores[idx] += 0.15
            if "bba" in q_lower or "business" in q_lower or "management" in q_lower:
                if "bba" in txt_lower or "business administration" in txt_lower:
                    boosted_scores[idx] += 0.15
            if "b.des" in q_lower or "bdes" in q_lower or "design" in q_lower:
                if "b.des" in txt_lower or "design" in txt_lower:
                    boosted_scores[idx] += 0.15
            if "continuation" in q_lower or "cgpa" in q_lower or "subsequent year" in q_lower or "second year" in q_lower:
                if "continuation" in txt_lower or "cgpa" in txt_lower:
                    boosted_scores[idx] += 0.20
            if "sibling" in q_lower or "alumni" in q_lower:
                if "sibling" in txt_lower or "alumni" in txt_lower:
                    boosted_scores[idx] += 0.25
            if "math" in q_lower or "mathematics" in q_lower:
                if "mathematics" in txt_lower or "math" in txt_lower:
                    boosted_scores[idx] += 0.20
            if "hostel" in q_lower or "room" in q_lower or "mess" in q_lower:
                if "hostel" in txt_lower:
                    boosted_scores[idx] += 0.20
            if "fee" in q_lower or "fees" in q_lower or "cost" in q_lower:
                if "fee" in txt_lower:
                    boosted_scores[idx] += 0.10

        # Rank candidates
        ranked_indices = np.argsort(boosted_scores)[::-1]
        results: List[Chunk] = []

        for idx in ranked_indices[:top_k]:
            sc = float(boosted_scores[idx])
            if sc >= threshold:
                text, source = self.raw_chunks[idx]
                results.append(Chunk(text=text, source=source, score=round(sc, 3)))

        if not results:
            return KnowledgeResult(answer_found=False, chunks=[])

        # If best match is too weak, refuse to guess
        if results[0].score < threshold:
            return KnowledgeResult(answer_found=False, chunks=[])

        return KnowledgeResult(answer_found=True, chunks=results)


# Singleton instance
store = KnowledgeStore()


def search_knowledge(query: str) -> KnowledgeResult:
    """Entry point satisfying contracts/models.py and contracts/tools.py signature."""
    return store.search(query)
