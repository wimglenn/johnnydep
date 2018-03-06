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
    assert dist.download_link == 'https://pypi.python.org/simple/copyingmock/copyingmock-0.2.tar.gz'
    assert dist.metadata == {
        'classifiers': [
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 3',
            'License :: OSI Approved :: MIT License',
            'Topic :: Software Development :: Libraries',
            'Intended Audience :: Developers',
        ],
        'description_content_type': 'UNKNOWN',
        'extensions': {
            'python.details':
                {
                    'contacts': [
                        {
                            'email': 'hey@wimglenn.com',
                            'name': 'Wim Glenn',
                            'role': 'author',
                        },
                    ],
                    'document_names': {'description': 'DESCRIPTION.rst'},
                    'project_urls': {'Home': 'https://github.com/wimglenn/copyingmock'},
                },
        },
        'extras': [],
        'generator': 'bdist_wheel (0.30.0)',
        'license': 'MIT',
        'metadata_version': '2.0',
        'name': 'copyingmock',
        'run_requires': [
            {
                'environment': 'python_version < "3.3"',
                'requires': ['mock'],
            },
        ],
        'summary': 'A subclass of MagicMock that copies the arguments',
        'version': '0.2',
    }


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
