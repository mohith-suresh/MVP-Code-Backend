# your_app/migrations/0001_enable_pgvector_extension.py

from django.db import migrations
from pgvector.django import VectorExtension

class Migration(migrations.Migration):

    # initial = True

    # dependencies = [
    # ]

    operations = [
        VectorExtension(),
    ]
