from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class UploadUserRateThrottle(UserRateThrottle):
    scope = "import_uploads"


class UploadAnonRateThrottle(AnonRateThrottle):
    scope = "import_uploads_anon"
