try:
    from urllib.request import urlretrieve
except ImportError:
    # Python 2
    from urllib import urlretrieve

try:
    from json import JSONDecodeError
except ImportError:
    # Python 2
    JSONDecodeError = ValueError
