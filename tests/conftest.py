import glob
import os
import sys
from collections import defaultdict

import pytest
import requests_mock as _requests_mock

from johnnydep.pipper import compute_checksum


@pytest.fixture(autouse=True)
def requests_mock(mocker):
    adapter = _requests_mock.Adapter()
    mocker.patch('pip._vendor.requests.sessions.Session.get_adapter', return_value=adapter)
    if sys.version_info.major == 2:
        target = 'socket.gethostbyname'
    else:
        target = 'urllib.request.socket.gethostbyname'
    mocker.patch(target, {'pypi.python.org': '151.101.44.223'}.__getitem__)
    return adapter


@pytest.fixture(autouse=True)
def fakeindex(requests_mock):
    """sets up a response for fakedist v1.2.3 with some metadata to parse, and some other distributions"""
    index_path = os.path.join(os.path.dirname(__file__), 'fakeindex')
    index_data = defaultdict(list)
    for path in glob.glob(os.path.join(index_path, '*', '*')):
        hash_ = compute_checksum(path, algorithm='md5')
        name, fname = path.split(os.sep)[-2:]
        index_data[name].append((fname, hash_))
    for name, files in index_data.items():
        links = ['<a href="./{0}#md5={1}">{0}</a><br/>'.format(*file) for file in files]
        requests_mock.register_uri(
            method='GET',
            url='https://pypi.python.org/simple/{}/'.format(name),
            headers={'Content-Type': 'text/html'},
            text='''
            <!DOCTYPE html><html><head><title>Links for {name}</title></head>
            <body><h1>Links for fakedist</h1>
            {links}
            </body></html>'''.format(name=name, links='\n'.join(links)),
        )
        for fname, hash in files:
            path = os.path.join(index_path, name, fname)
            with open(str(path), mode='rb') as f:
                content = f.read()
            requests_mock.register_uri(
                method='GET',
                url='https://pypi.python.org/simple/{}/{}'.format(name, fname),
                headers={'Content-Type': 'binary/octet-stream'},
                content=content,
            )
    yield
    try:
        os.remove('fakedist-1.2.3-py2.py3-none-any.whl')
    except OSError:
        pass
