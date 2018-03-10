import sys

import pytest
from pip.exceptions import DistributionNotFound
from testfixtures import ShouldRaise

from johnnydep.lib import JohnnyDist
from johnnydep.lib import flatten_deps


def test_version_nonexisting():
    # v0.404 does not exist in index
    with ShouldRaise(DistributionNotFound('No matching distribution found for wheel==0.404')):
        JohnnyDist('wheel==0.404')


def test_version_conflict():
    # wheel v0.30.0 is already installed, but v0.29.0 does exist in index
    dist = JohnnyDist('wheel<0.30.0')
    assert dist.version_installed == '0.30.0'
    assert dist.version_latest == '0.30.0'
    assert dist.versions_available == ['0.29.0', '0.30.0']
    assert dist.version_latest_in_spec == '0.29.0'


def test_build_from_sdist():
    dist = JohnnyDist('copyingmock')
    assert dist.name == 'copyingmock'
    assert dist.summary == 'A subclass of MagicMock that copies the arguments'
    assert dist.required_by == []
    assert dist.import_names == ['copyingmock']
    assert dist.homepage == 'https://github.com/wimglenn/copyingmock'
    assert dist.extras_available == []
    assert dist.extras_requested == []
    assert dist.project_name == 'copyingmock'
    assert dist.download_link == 'https://pypi.python.org/simple/copyingmock/copyingmock-0.2.tar.gz'
    assert dist.checksum == 'md5=9aa6ba13542d25e527fe358d53cdaf3b'


@pytest.mark.skipif(condition=sys.version_info < (3, 3), reason='This test is for Python >= 3.3 only')
def test_conditional_deps_python3():
    dist = JohnnyDist('copyingmock')
    assert dist.requires == []


@pytest.mark.skipif(condition=sys.version_info >= (3, 3), reason='This test is for Python < 3.3 only')
def test_conditional_deps_python2():
    dist = JohnnyDist('copyingmock')
    assert dist.requires == ['mock']


def test_serialiser():
    dist = JohnnyDist('wheel')
    assert dist.serialise(format=None) == [{'name': 'wheel', 'summary': 'A built-package format for Python.'}]
    assert dist.serialise(format='toml') == 'name = "wheel"\nsummary = "A built-package format for Python."\n'
    assert dist.serialise(format='yaml') == '- {name: wheel, summary: A built-package format for Python.}\n'
    with ShouldRaise(Exception('Unsupported format')):
        dist.serialise(format='bogus')


def test_flatten_dist_with_nodeps():
    dist = JohnnyDist('fakedist')
    reqs = list(flatten_deps(dist))
    assert reqs == [dist]


def test_flatten_dist_with_deps():
    dist = JohnnyDist('fakedist[dev]')
    reqs = list(flatten_deps(dist))
    [dist0, dist1] = reqs
    assert dist0.name == 'fakedist'
    assert dist0 is dist
    assert str(dist1.req) == 'wheel>=0.30.0'


def test_serialiser_with_deps():
    dist = JohnnyDist('fakedist[dev]')
    assert dist.serialise(fields=['name']) == [
        {'name': 'fakedist'},
        {'name': 'wheel'},
    ]


def test_children():
    dist = JohnnyDist('fakedist[dev]')
    assert len(dist.children) == 1
    [child] = dist.children
    assert child.project_name == 'wheel'


def test_non_json_metadata():
    # this dist uses old-skool metadata format (plaintext not json)
    dist = JohnnyDist('testpath==0.3.1')
    assert dist.serialise(fields=['name', 'summary', 'import_names']) == [{
        'name': 'testpath',
        'summary': 'Test utilities for code working with files and commands',
        'import_names': ['testpath'],
    }]


def test_diamond_dependency_tree():
    dist = JohnnyDist('distA')
    fields = [
        'name', 'summary', 'specifier', 'requires', 'required_by', 'import_names', 'homepage',
        'extras_available', 'extras_requested', 'project_name', 'versions_available', 'version_installed',
        'version_latest', 'version_latest_in_spec', 'download_link', 'checksum',
    ]
    data = dist.serialise(fields=fields)
    data = [dict(x) for x in data]
    assert data == [
        {
            'checksum': 'md5=c422ba4693b32da3c0721d425aff4eed',
            'download_link': 'https://pypi.python.org/simple/dista/distA-0.1-py2.py3-none-any.whl',
            'extras_available': [],
            'extras_requested': [],
            'homepage': None,
            'import_names': [],
            'name': 'dista',
            'project_name': 'distA',
            'required_by': [],
            'requires': ['distB1', 'distB2'],
            'specifier': '',
            'summary': 'Top of a diamond dependency tree',
            'version_installed': None,
            'version_latest': '0.1',
            'version_latest_in_spec': '0.1',
            'versions_available': ['0.1'],
        },
        {
            'checksum': 'md5=a96f048902789a3faf8e8e829a27a5ec',
            'download_link': 'https://pypi.python.org/simple/distb1/distB1-0.1-py2.py3-none-any.whl',
            'extras_available': [],
            'extras_requested': [],
            'homepage': None,
            'import_names': [],
            'name': 'distb1',
            'project_name': 'distB1',
            'required_by': ['distA'],
            'requires': ['distC[x,z] (<0.3)'],
            'specifier': '',
            'summary': 'Left edge of a diamond dependency tree',
            'version_installed': None,
            'version_latest': '0.1',
            'version_latest_in_spec': '0.1',
            'versions_available': ['0.1'],
        },
        {
            'checksum': 'md5=bc5761d4232c8e4a95dc0125605f5f65',
            'download_link': 'https://pypi.python.org/simple/distb2/distB2-0.1-py2.py3-none-any.whl',
            'extras_available': [],
            'extras_requested': [],
            'homepage': None,
            'import_names': [],
            'name': 'distb2',
            'project_name': 'distB2',
            'required_by': ['distA'],
            'requires': ['distC[y] (!=0.2)'],
            'specifier': '',
            'summary': 'Right edge of a diamond dependency tree',
            'version_installed': None,
            'version_latest': '0.1',
            'version_latest_in_spec': '0.1',
            'versions_available': ['0.1'],
        },
        {
            'checksum': 'md5=e3404449fa48c97b384b6b64c52f5ce2',
            'download_link': 'https://pypi.python.org/simple/distc/distC-0.1-py2.py3-none-any.whl',
            'extras_available': ['X', 'Y', 'Z'],
            'extras_requested': ['x', 'y', 'z'],  # Note: extras got merged
            'homepage': None,
            'import_names': [],
            'name': 'distc',
            'project_name': 'distC',
            'required_by': ['distB1', 'distB2'],
            'requires': [],
            'specifier': '!=0.2,<0.3',  # Note: specifiers got merged
            'summary': 'Bottom of a diamond dependency tree',
            'version_installed': None,
            'version_latest': '0.3',
            'version_latest_in_spec': '0.1',  # Even though this was not "best" for either dep
            'versions_available': ['0.1', '0.2', '0.3'],
        },
    ]


def test_resolve_unresolvable():
    dist = JohnnyDist('distX')
    data = dist.serialise(recurse=False, fields=['project_name', 'summary', 'requires'])
    assert data == [{
        'project_name': 'distX',
        'summary': 'Dist with unresolvable dependencies',
        'requires': ['distC (<=0.1)', 'distC (>0.2)'],  # this installation requirement can not be resolved
    }]
    gen = flatten_deps(dist)
    assert next(gen) is dist
    with ShouldRaise(DistributionNotFound('No matching distribution found for distc<=0.1,>0.2')):
        next(gen)
