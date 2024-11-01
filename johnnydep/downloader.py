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


def download_dist(url, f, index_urls=()):
    auth = None
    for index_url in index_urls:
        p = urlparse(index_url)
        if p.username and p.password and p.hostname == urlparse(url).hostname:
            # handling private PyPI credentials directly in index_url
            auth = p.username, p.password
    _urlretrieve(url, f, auth=auth)
