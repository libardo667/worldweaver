# Add storylet embedding column and embedding service

## Problem

The vision's core mechanic — semantic proximity-based storylet selection —
requires every storylet to have a vector embedding. Currently the `Storylet`
model has no embedding column, and there is no service to compute embeddings.
Without this, the entire semantic storylet engine described in VISION.md
cannot be built.

## Proposed Solution

1. **Add `embedding` column to `Storylet`** — a JSON column storing a list
   of floats (the embedding vector). Nullable initially so existing storylets
   don't break.

2. **Create `src/services/embedding_service.py`** with:
   - `embed_text(text: str) -> list[float]` — calls an embedding API
     (OpenAI `text-embedding-3-small` or configurable) and returns the vector.
   - `embed_storylet(storylet: Storylet) -> list[float]` — builds a composite
     text from the storylet's title, text_template, choice labels, and
     requires keys, then embeds it.
   - `embed_all_storylets(db: Session)` — batch-embeds all storylets that
     have a null embedding column.
   - `cosine_similarity(a: list[float], b: list[float]) -> float` — pure
     Python cosine similarity for selection scoring.

3. **Hook into storylet creation** — after `save_storylets_with_postprocessing`
   in `author.py`, call `embed_storylet` for each new storylet.

4. **Add config** — `EMBEDDING_MODEL` and `EMBEDDING_DIMENSIONS` in the
   config system (or env vars until config is formalised).

## Files Affected

- `src/models/__init__.py` — add `embedding` column to `Storylet`
- `src/services/embedding_service.py` — new file
- `src/api/author.py` — hook embedding into storylet creation
- `tests/service/test_embedding_service.py` — new test file

## Acceptance Criteria

- [ ] `Storylet.embedding` column exists and stores a float vector
- [ ] `embed_text` returns a vector of the configured dimensionality
- [ ] `embed_storylet` builds a meaningful composite text before embedding
- [ ] `embed_all_storylets` fills in null embeddings without re-embedding
      existing ones
- [ ] New storylets created via the author API get embeddings automatically
- [ ] `cosine_similarity` returns 1.0 for identical vectors and ~0 for
      orthogonal ones
- [ ] Tests cover embedding, similarity, and batch fill

## Risks & Rollback

Requires an embedding API key (can share the OpenAI key). If the embedding
service is unavailable, storylet creation should still succeed — the
embedding column just stays null and the system falls back to the existing
`requires`-based selection. Rollback: drop the column and delete the service.
