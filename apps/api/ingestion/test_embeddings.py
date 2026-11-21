import pytest
from django.core.exceptions import ImproperlyConfigured

from ingestion import embeddings
from ingestion.errors import IngestionError
from ingestion.models import EMBEDDING_DIMENSIONS


class FakeVector(list):
    def tolist(self):
        return list(self)


class FakeLocalModel:
    def __init__(self, size=EMBEDDING_DIMENSIONS):
        self.size = size

    def embed(self, texts):
        return (FakeVector([1.0] * self.size) for _ in texts)


class BrokenLocalModel:
    def embed(self, _texts):
        raise RuntimeError("model file is corrupt")


def test_local_provider_returns_one_vector_per_text(settings, monkeypatch):
    settings.EMBEDDING_PROVIDER = "local"
    monkeypatch.setattr(embeddings, "_local_model", lambda: FakeLocalModel())

    vectors = embeddings.embed_texts(["a", "b"])

    assert len(vectors) == 2
    assert all(len(vector) == EMBEDDING_DIMENSIONS for vector in vectors)


def test_a_vector_of_the_wrong_size_is_rejected(settings, monkeypatch):
    settings.EMBEDDING_PROVIDER = "local"
    monkeypatch.setattr(embeddings, "_local_model", lambda: FakeLocalModel(size=10))

    with pytest.raises(IngestionError):
        embeddings.embed_texts(["a"])


def test_a_failing_local_model_is_reported_without_internal_details(settings, monkeypatch):
    settings.EMBEDDING_PROVIDER = "local"
    monkeypatch.setattr(embeddings, "_local_model", lambda: BrokenLocalModel())

    with pytest.raises(IngestionError) as excinfo:
        embeddings.embed_texts(["a"])

    assert "corrupt" not in str(excinfo.value)


def test_unknown_provider_is_a_configuration_error(settings):
    settings.EMBEDDING_PROVIDER = "nope"

    with pytest.raises(ImproperlyConfigured):
        embeddings.embed_texts(["a"])


def test_model_id_names_provider_and_model(settings):
    settings.EMBEDDING_PROVIDER = "local"
    settings.EMBEDDING_MODEL = "some-model"

    assert embeddings.model_id() == "local:some-model"
