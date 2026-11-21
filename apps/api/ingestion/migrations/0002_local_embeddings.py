import pgvector.django
from django.db import migrations, models


def reset_chunks(apps, schema_editor):
    """Vectors of another model or size are meaningless: drop them and queue the
    affected documents again so the worker re-embeds them."""
    Chunk = apps.get_model("ingestion", "Chunk")
    Document = apps.get_model("documents", "Document")
    Chunk.objects.all().delete()
    Document.objects.filter(status__in=["ready", "processing"]).update(status="pending")


class Migration(migrations.Migration):
    # Not atomic: avoids Postgres "pending trigger events" errors when deleting
    # rows and altering the same table in one transaction.
    atomic = False

    dependencies = [
        ("documents", "0001_initial"),
        ("ingestion", "0001_initial"),
    ]

    operations = [
        migrations.RemoveIndex(model_name="chunk", name="chunk_embedding_hnsw"),
        migrations.RunPython(reset_chunks, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="chunk",
            name="embedding",
            field=pgvector.django.VectorField(dimensions=384),
        ),
        migrations.AddField(
            model_name="chunk",
            name="embedding_model",
            field=models.CharField(default="", max_length=100),
            preserve_default=False,
        ),
        migrations.AddIndex(
            model_name="chunk",
            index=pgvector.django.HnswIndex(
                fields=["embedding"],
                m=16,
                ef_construction=64,
                name="chunk_embedding_hnsw",
                opclasses=["vector_cosine_ops"],
            ),
        ),
    ]
