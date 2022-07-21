from collections import OrderedDict

import oyaml

try:
    from urllib.parse import urlparse
    from urllib import request as urllib2
except ImportError:
    # Python 2
    import urllib2
    from urlparse import urlparse


if oyaml._std_dict_is_order_preserving:
    dict = dict
else:
    dict = OrderedDict


def urlretrieve(url, filename, data=None, auth=None):
    if auth is not None:
        # https://docs.python.org/2.7/howto/urllib2.html#id6
        password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()

        # Add the username and password.
        # If we knew the realm, we could use it instead of None.
        username, password = auth
        top_level_url = urlparse(url).netloc
        password_mgr.add_password(None, top_level_url, username, password)

        handler = urllib2.HTTPBasicAuthHandler(password_mgr)

        # create "opener" (OpenerDirector instance)
        opener = urllib2.build_opener(handler)
    else:
        opener = urllib2.build_opener()

    res = opener.open(url, data=data)

    headers = res.info()

    with open(filename, "wb") as fp:
        fp.write(res.read())

    return filename, headers


try:
    from json import JSONDecodeError
except ImportError:
    # Python 2
    JSONDecodeError = ValueError

try:
    text_type = unicode
except NameError:
    text_type = str
else:
    oyaml.add_representer(
        unicode, lambda d, s: oyaml.ScalarNode(tag="tag:yaml.org,2002:str", value=s)
    )
