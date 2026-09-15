from __future__ import annotations

import time

from google import genai
from google.genai import types

from app.config import settings


def create_embeddings(texts: list[str], batch_size: int = 8) -> list[list[float]]:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required for embedding generation")
    if not texts:
        return []

    client = genai.Client(api_key=settings.gemini_api_key)
    all_vectors: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        if i > 0:
            time.sleep(4.5)  # Enforce < 13.3 RPM to stay strictly under the 15 RPM free-tier limit
        batch = texts[i : i + batch_size]

        # Retry up to 3 times on rate limits
        for attempt in range(4):
            try:
                response = client.models.embed_content(
                    model=settings.gemini_embedding_model,
                    contents=[
                        types.Content(parts=[types.Part.from_text(text=text)])
                        for text in batch
                    ],
                    config=types.EmbedContentConfig(
                        output_dimensionality=settings.gemini_embedding_dimensions,
                    ),
                )
                break
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    wait_time = 15.0 * (attempt + 1)
                    print(f"  [Rate limit hit, waiting {wait_time:.0f}s before retry {attempt + 1}/3...]")
                    time.sleep(wait_time)
                else:
                    raise

        vectors = [embedding.values for embedding in response.embeddings or []]
        invalid = [
            len(vector)
            for vector in vectors
            if len(vector) != settings.gemini_embedding_dimensions
        ]
        if invalid:
            raise ValueError(
                f"Embedding dimension mismatch: expected {settings.gemini_embedding_dimensions}, got {invalid}"
            )
        if len(vectors) != len(batch):
            raise ValueError(
                f"Embedding count mismatch: expected {len(batch)}, got {len(vectors)}"
            )
        all_vectors.extend(vectors)

    return all_vectors