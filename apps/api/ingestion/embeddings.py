import logging
from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from openai import OpenAI, OpenAIError

from ingestion.errors import IngestionError
from ingestion.models import EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)


def model_id() -> str:
    """Identifies the active model; stored on every chunk."""
    return f"{settings.EMBEDDING_PROVIDER}:{settings.EMBEDDING_MODEL}"


@lru_cache(maxsize=1)
def _openai_client() -> OpenAI:
    if not settings.OPENAI_API_KEY:
        raise ImproperlyConfigured("OPENAI_API_KEY is not set.")
    # The SDK retries transient errors (timeouts, 429, 5xx) with backoff.
    return OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30.0, max_retries=3)


@lru_cache(maxsize=1)
def _local_model():
    # Imported here so the model is only loaded (and downloaded) when used.
    from fastembed import TextEmbedding

    return TextEmbedding(
        model_name=settings.EMBEDDING_MODEL, cache_dir=settings.FASTEMBED_CACHE_DIR
    )


def _embed_openai(texts: list[str]) -> list[list[float]]:
    try:
        response = _openai_client().embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=texts,
            # text-embedding-3 models can be shortened, keeping the schema stable.
            dimensions=EMBEDDING_DIMENSIONS,
        )
    except OpenAIError as exc:
        logger.warning("Embedding request failed: %s", exc)
        raise IngestionError(
            "The embedding service is unavailable or over quota. Please retry later."
        ) from exc
    return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]


def _embed_local(texts: list[str]) -> list[list[float]]:
    try:
        return [vector.tolist() for vector in _local_model().embed(texts)]
    except Exception as exc:
        logger.exception("Local embedding failed")
        raise IngestionError("The embedding model could not run. Please retry later.") from exc


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Returns one vector per input, in order."""
    provider = settings.EMBEDDING_PROVIDER
    if provider == "local":
        vectors = _embed_local(texts)
    elif provider == "openai":
        vectors = _embed_openai(texts)
    else:
        raise ImproperlyConfigured(f"Unknown EMBEDDING_PROVIDER: {provider!r}")

    if len(vectors) != len(texts) or any(len(v) != EMBEDDING_DIMENSIONS for v in vectors):
        raise IngestionError("The embedding service returned an unexpected response.")
    return vectors
