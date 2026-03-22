from rest_framework import serializers
from import_engine.domain.models import ImportJob, ImportChunk, ImportLog


class ImportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportJob
        fields = "__all__"


class ImportChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportChunk
        fields = "__all__"


class ImportLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportLog
        fields = "__all__"
