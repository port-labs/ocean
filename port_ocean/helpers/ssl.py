"""
SSL configuration helpers for the ocean framework.
"""
import os
import ssl
from enum import Enum
from loguru import logger


class SSLClientType(Enum):
    """Type of client to configure SSL for"""
    PORT = "PORT"
    THIRD_PARTY = "THIRD_PARTY"
    

def get_ssl_context(client_type: SSLClientType = SSLClientType.PORT) -> ssl.SSLContext | bool:
    """
    Get SSL context configuration based on environment variables.
    
    Args:
        client_type: Type of client to get SSL context for (PORT or THIRD_PARTY)
    
    Environment Variables for Port client (client_type=PORT):
        OCEAN__VERIFY_SSL: Enable/disable SSL verification (default: True)
        OCEAN__NO_STRICT_VERIFY_SSL: Disable strict x509 verification introduced in Python 3.13 (default: False)
        
    Environment Variables for Third Party clients (client_type=THIRD_PARTY):
        OCEAN__THIRD_PARTY_VERIFY_SSL: Enable/disable SSL verification (default: True)
        OCEAN__THIRD_PARTY_NO_STRICT_VERIFY_SSL: Disable strict x509 verification introduced in Python 3.13 (default: False)
    
    Returns:
        Optional[ssl.SSLContext]: Custom SSL context if verification settings are modified, None for default behavior
    """
    prefix = "OCEAN__THIRD_PARTY_" if client_type == SSLClientType.THIRD_PARTY else "OCEAN__"
    client_name = "third party" if client_type == SSLClientType.THIRD_PARTY else "Port"
    
    verify_ssl = os.getenv(f'{prefix}VERIFY_SSL', 'true').lower() != 'false'
    no_strict_verify = os.getenv(f'{prefix}NO_STRICT_VERIFY_SSL', 'false').lower() == 'true'
    
    if not verify_ssl:
        logger.warning(f"SSL certificate verification is disabled for {client_name} client. "
                      f"This is not recommended for production use.")
        return False
    
    if no_strict_verify:
        logger.warning(f"Strict X.509 certificate verification is disabled for {client_name} client. "
                      f"This may affect security.")
        context = ssl.create_default_context()
        # Remove VERIFY_X509_STRICT flag that is set by default starting Python 3.13
        # See: https://docs.python.org/3/library/ssl.html#ssl.create_default_context
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
        return context
    
    return True