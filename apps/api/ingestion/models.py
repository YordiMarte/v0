from django.db import models
from pgvector.django import HnswIndex, VectorField

from documents.models import Document
from organizations.models import Organization

# Must match the output size of the embedding model. OpenAI embeddings can be
# shortened to this size, so switching provider does not change the schema.
EMBEDDING_DIMENSIONS = 384


class Chunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    # Denormalized from the document so retrieval can filter by organization
    # without a join, and as a second line of defense for tenant isolation.
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="chunks")
    position = models.PositiveIntegerField()
    content = models.TextField()
    embedding = VectorField(dimensions=EMBEDDING_DIMENSIONS)
    # Vectors from different models are not comparable: record which one made this.
    embedding_model = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document_id", "position"]
        constraints = [
            models.UniqueConstraint(fields=["document", "position"], name="unique_chunk_position")
        ]
        indexes = [
            HnswIndex(
                name="chunk_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]

    def __str__(self) -> str:
        return f"{self.document_id}#{self.position}"
