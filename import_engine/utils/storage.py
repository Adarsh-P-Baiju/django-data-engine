from storages.backends.s3boto3 import S3Boto3Storage


class LocalhostMinioStorage(S3Boto3Storage):
    def url(self, name, parameters=None, expire=None, http_method=None):
        url = super().url(name, parameters, expire, http_method)
        if "minio:9000" in url:
            return url.replace("minio:9000", "localhost:9000")
        return url
