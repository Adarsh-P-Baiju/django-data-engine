import hashlib
import logging
from django.conf import settings

try:
    import redis
except ImportError:
    redis = None

logger = logging.getLogger(__name__)


class DedupeService:
    """Redis Bloom Filter for row-level deduplication."""


    BLOOM_SIZE = 10**7
    HASH_COUNT = 7

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.redis_client = self._get_client()
        self.key = f"bloom:{model_name.lower()}"

    def _get_client(self):
        if not redis:
            return None
        try:
            url = getattr(settings, "CELERY_BROKER_URL", "redis://redis:6379/0")
            return redis.from_url(url)
        except Exception as e:
            logger.error(f"DedupeService: Redis Connection Failed: {e}")
            return None

    def _get_hashes(self, value: str):
        """Generates multiple hash offsets for the Bloom bitset."""
        hashes = []
        for i in range(self.HASH_COUNT):
            h = hashlib.sha256(f"{i}:{value}".encode()).hexdigest()
            hashes.append(int(h, 16) % self.BLOOM_SIZE)
        return hashes

    def is_duplicate(self, business_key: str) -> bool:
        """
        Checks if the row (via business key) has likely been seen before.
        Returns True if it's a PROBABLE duplicate.
        """
        if not self.redis_client:
            return False

        hashes = self._get_hashes(business_key)


        pipe = self.redis_client.pipeline()
        for h in hashes:
            pipe.getbit(self.key, h)
        results = pipe.execute()


        if any(not b for b in results):

            self._mark_as_seen(hashes)
            return False


        logger.info(f"DedupeService: Probable duplicate detected for {business_key}")
        return True

    def _mark_as_seen(self, hashes: list):
        """Sets the bits for a new entry."""
        pipe = self.redis_client.pipeline()
        for h in hashes:
            pipe.setbit(self.key, h, 1)
        pipe.execute()

    def clear_filter(self):
        """Resets the Bloom filter for this model (e.g., after a full purge)."""
        if self.redis_client:
            self.redis_client.delete(self.key)
