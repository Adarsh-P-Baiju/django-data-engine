from rest_framework.throttling import UserRateThrottle
from rest_framework.throttling import AnonRateThrottle


class UploadUserRateThrottle(UserRateThrottle):
    scope = "import_uploads"


class UploadAnonRateThrottle(AnonRateThrottle):
    scope = "import_uploads_anon"
