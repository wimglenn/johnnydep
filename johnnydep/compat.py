from urllib.parse import urlparse
from urllib.request import HTTPPasswordMgrWithDefaultRealm
from urllib.request import HTTPBasicAuthHandler
from urllib.request import build_opener


def urlretrieve(url, filename, data=None, auth=None):
    if auth is not None:
        # https://docs.python.org/3/howto/urllib2.html#id5
        password_mgr = HTTPPasswordMgrWithDefaultRealm()
        username, password = auth
        top_level_url = urlparse(url).netloc
        password_mgr.add_password(None, top_level_url, username, password)
        handler = HTTPBasicAuthHandler(password_mgr)
        opener = build_opener(handler)
    else:
        opener = build_opener()
    res = opener.open(url, data=data)
    headers = res.info()
    with open(filename, "wb") as fp:
        fp.write(res.read())
    return filename, headers
