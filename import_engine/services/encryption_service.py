import logging
from django.conf import settings
try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None

logger = logging.getLogger(__name__)

class EncryptionService:
    """Symmetric Payload Encryption via Fernet."""
    
    _fernet: Fernet = None

    @classmethod
    def _get_fernet(cls) -> Fernet:
        if not Fernet:
            return None
        if not cls._fernet:
            key = getattr(settings, "DATA_ENCRYPTION_KEY", None)
            if not key:
                # Log a critical warning if PII encryption is requested but no key exists
                logger.critical("EncryptionService: DATA_ENCRYPTION_KEY missing in settings!")
                return None
            try:
                cls._fernet = Fernet(key.encode() if isinstance(key, str) else key)
            except Exception as e:
                logger.error(f"EncryptionService: Invalid key configuration: {e}")
                return None
        return cls._fernet

    @classmethod
    def encrypt(cls, value: str) -> str:
        """Encrypts a plain-text value (e.g., SSN)."""
        if not value:
            return value
        
        fernet = cls._get_fernet()
        if not fernet:
            return f"ENCRYPT_FAILED:{value}"
            
        try:
            return fernet.encrypt(str(value).encode()).decode()
        except Exception as e:
            logger.error(f"EncryptionService: Encryption failure: {e}")
            return "ENCRYPT_ERR_INTERNAL"

    @classmethod
    def decrypt(cls, cipher_text: str) -> str:
        """Decrypts a cipher-text value."""
        if not cipher_text:
            return cipher_text
            
        fernet = cls._get_fernet()
        if not fernet:
            return cipher_text
            
        try:
            return fernet.decrypt(str(cipher_text).encode()).decode()
        except Exception:
            # If decryption fails, return as-is (might not be encrypted)
            return cipher_text
