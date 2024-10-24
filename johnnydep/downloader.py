from urllib.parse import urlparse
from urllib.request import build_opener
from urllib.request import HTTPBasicAuthHandler
from urllib.request import HTTPPasswordMgrWithDefaultRealm

from structlog import get_logger


log = get_logger(__name__)


def _urlretrieve(url, f, data=None, auth=None):
    if auth is None:
        opener = build_opener()
    else:
        # https://docs.python.org/3/howto/urllib2.html#id5
        password_mgr = HTTPPasswordMgrWithDefaultRealm()
        username, password = auth
        top_level_url = urlparse(url).netloc
        password_mgr.add_password(None, top_level_url, username, password)
        handler = HTTPBasicAuthHandler(password_mgr)
        opener = build_opener(handler)
    res = opener.open(url, data=data)
    log.debug("resp info", url=url, headers=res.info())
    f.write(res.read())
    f.flush()


def download_dist(url, f, index_url, extra_index_url):
    auth = None
    if index_url:
        parsed = urlparse(index_url)
        if parsed.username and parsed.password and parsed.hostname == urlparse(url).hostname:
            # handling private PyPI credentials in index_url
            auth = (parsed.username, parsed.password)
    if extra_index_url:
        parsed = urlparse(extra_index_url)
        if parsed.username and parsed.password and parsed.hostname == urlparse(url).hostname:
            # handling private PyPI credentials in extra_index_url
            auth = (parsed.username, parsed.password)
    _urlretrieve(url, f, auth=auth)
