import sys

import pytest
from pip.exceptions import DistributionNotFound
from testfixtures import ShouldRaise

from johnnydep.lib import JohnnyDist


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


@pytest.mark.skipif(condition=sys.version_info < (3, 3), reason='conditional deps')
def test_conditional_deps_python3():
    dist = JohnnyDist('copyingmock')
    assert dist.deps == []


@pytest.mark.skipif(condition=sys.version_info >= (3, 3), reason='This test is for Python')
def test_conditional_deps_python2():
    dist = JohnnyDist('copyingmock')
    assert dist.deps == ['mock']


def test_serialiser():
    dist = JohnnyDist('wheel')
    assert dist.serialise() == {'name': 'wheel', 'requires': []}
    assert dist.serialise(format='toml') == 'name = "wheel"\nrequires = []\n'
    with ShouldRaise(Exception('Unsupported format')):
        dist.serialise(format='bogus')
