"""HTTP session configuration with retries and connection pooling."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def get_http_session() -> requests.Session:
    """
    Create and configure a shared HTTP session with retries and connection pooling.
    
    Returns:
        Configured requests.Session object
    """
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=10,
        pool_maxsize=10
    )
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


# Global shared session instance
_session = get_http_session()
