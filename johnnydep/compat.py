import oyaml


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

try:
    text_type = unicode
except NameError:
    text_type = str
else:
    oyaml.add_representer(
        unicode, lambda d, s: oyaml.ScalarNode(tag="tag:yaml.org,2002:str", value=s)
    )
