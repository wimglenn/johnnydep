[![Build Status](https://github.com/wimglenn/johnnydep/actions/workflows/ci.yml/badge.svg)](https://github.com/wimglenn/johnnydep/actions/workflows/ci.yml/)
[![Coverage Status](https://codecov.io/gh/wimglenn/johnnydep/branch/master/graph/badge.svg)](https://codecov.io/gh/wimglenn/johnnydep)
[![PyPI](https://img.shields.io/pypi/v/johnnydep.svg)](https://pypi.org/project/johnnydep/)

Johnnydep
=========

Pretty-print a dependency tree for a Python distribution. A simple example:

    $ johnnydep requests
     name                           summary
    ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
     requests                       Python HTTP for Humans.
     ├── certifi>=2023.5.7          Python package for providing Mozilla's CA Bundle.
     ├── charset_normalizer<4,>=2   The Real First Universal Charset Detector. Open, modern and actively maintained alternative to Chardet.
     ├── idna<4,>=2.5               Internationalized Domain Names in Applications (IDNA)
     └── urllib3<3,>=1.26           HTTP library with thread-safe connection pooling, file post, and more.

A more complex tree:

    $ johnnydep boto3
     name                                      summary
    ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────
     boto3                                     The AWS SDK for Python
     ├── botocore<1.44.0,>=1.43.12             Low-level, data-driven core of boto 3.
     │   ├── jmespath<2.0.0,>=0.7.1            JSON Matching Expressions
     │   ├── python-dateutil<3.0.0,>=2.1       Extensions to the standard Python datetime module
     │   │   └── six>=1.5                      Python 2 and 3 compatibility utilities
     │   └── urllib3!=2.2.0,<3,>=1.25.4        HTTP library with thread-safe connection pooling, file post, and more.
     ├── jmespath<2.0.0,>=0.7.1                JSON Matching Expressions
     └── s3transfer<0.18.0,>=0.17.0            An Amazon S3 Transfer Manager
         └── botocore<2.0a.0,>=1.37.4          Low-level, data-driven core of boto 3.
             ├── jmespath<2.0.0,>=0.7.1        JSON Matching Expressions
             ├── python-dateutil<3.0.0,>=2.1   Extensions to the standard Python datetime module
             │   └── six>=1.5                  Python 2 and 3 compatibility utilities
             └── urllib3!=2.2.0,<3,>=1.25.4    HTTP library with thread-safe connection pooling, file post, and more.

You can also view the download size and installed size of dependencies:

    $ johnnydep boto3 --fields name formatted_size formatted_installed_size

    name                                     formatted_size   formatted_installed_size
    ---------------------------------------------------------------------------------------
    boto3                                    136.8 KB         969.2 KB
    ├── botocore<1.41.0,>=1.40.18            13.4 MB          17.5 MB
    │   ├── jmespath<2.0.0,>=0.7.1           19.8 KB          68.0 KB
    │   ├── python-dateutil<3.0.0,>=2.1      224.5 KB         431.2 KB
    │   │   └── six>=1.5                     10.8 KB          37.1 KB
    │   └── urllib3!=2.2.0,<3,>=1.25.4       126.8 KB         414.9 KB
    ├── jmespath<2.0.0,>=0.7.1               19.8 KB          68.0 KB
    └── s3transfer<0.14.0,>=0.13.0           83.3 KB          309.4 KB
        └── botocore<2.0a.0,>=1.37.4         13.4 MB          17.5 MB
            ├── jmespath<2.0.0,>=0.7.1       19.8 KB          68.0 KB
            ├── python-dateutil<3.0.0,>=2.1  224.5 KB         431.2 KB
            │   └── six>=1.5                 10.8 KB          37.1 KB
            └── urllib3!=2.2.0,<3,>=1.25.4   126.8 KB         414.9 KB

Johnnydep can also attempt to resolve the dependency tree:

    $ johnnydep ipython --output-format pinned
    ipython==9.13.0
    decorator==5.3.1
    ipython_pygments_lexers==1.1.1
    jedi==0.20.0
    matplotlib-inline==0.2.2
    pexpect==4.9.0
    prompt_toolkit==3.0.52
    psutil==7.2.2
    Pygments==2.20.0
    stack-data==0.6.3
    traitlets==5.15.0
    parso==0.8.7
    ptyprocess==0.7.0
    wcwidth==0.7.0
    asttokens==3.0.1
    executing==2.2.1
    pure_eval==0.2.3

Note that [`pip install` lacked a working solver](https://github.com/pypa/pip/issues/988) for many years, but [pip v20.3 has a new solver](https://blog.python.org/2020/11/pip-20-3-release-new-resolver.html) (December 2020) which has really improved matters!

Check `johnnydep --help` for other features and options.


Helpful links
-------------

* [Core metadata specifications](https://packaging.python.org/specifications/core-metadata/)
* [PEP 427 -- The Wheel Binary Package Format 1.0](https://www.python.org/dev/peps/pep-0427/)
* [PEP 426 -- Metadata for Python Software Packages 2.0](https://www.python.org/dev/peps/pep-0426/) (now [revoked](https://www.python.org/dev/peps/pep-0426/#pep-withdrawal) but still commonly seen in the wild)
* [PEP 566 -- Metadata for Python Software Packages 2.1](https://www.python.org/dev/peps/pep-0566/)
* [PEP 503 -- Simple Repository API](https://www.python.org/dev/peps/pep-0503/)
