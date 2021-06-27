[![Build Status](https://github.com/wimglenn/djangorestframework-queryfields/actions/workflows/main.yml/badge.svg)](https://github.com/wimglenn/djangorestframework-queryfields/actions/workflows/main.yml/) [![Coverage Status](https://codecov.io/gh/wimglenn/johnnydep/branch/master/graph/badge.svg)](https://codecov.io/gh/wimglenn/johnnydep) [![PyPI](https://img.shields.io/pypi/v/johnnydep.svg)](https://pypi.org/project/johnnydep/)

Johnnydep
=========

Pretty-print a dependency tree for a Python distribution. A simple example:

    $ johnnydep requests
    name                       summary
    -------------------------  ----------------------------------------------------------------------
    requests                   Python HTTP for Humans.
    ├── certifi>=2017.4.17     Python package for providing Mozilla's CA Bundle.
    ├── chardet<3.1.0,>=3.0.2  Universal encoding detector for Python 2 and 3
    ├── idna<2.8,>=2.5         Internationalized Domain Names in Applications (IDNA)
    └── urllib3<1.24,>=1.21.1  HTTP library with thread-safe connection pooling, file post, and more.

A more complex tree:

    $ johnnydep boto3
    name                                     summary
    ---------------------------------------  -------------------------------------------------
    boto3                                    The AWS SDK for Python
    ├── botocore<1.11.0,>=1.10.77            Low-level, data-driven core of boto 3.
    │   ├── docutils>=0.10                   Docutils -- Python Documentation Utilities
    │   ├── jmespath<1.0.0,>=0.7.1           JSON Matching Expressions
    │   └── python-dateutil<3.0.0,>=2.1      Extensions to the standard Python datetime module
    │       └── six>=1.5                     Python 2 and 3 compatibility utilities
    ├── jmespath<1.0.0,>=0.7.1               JSON Matching Expressions
    └── s3transfer<0.2.0,>=0.1.10            An Amazon S3 Transfer Manager
        └── botocore<2.0.0,>=1.3.0           Low-level, data-driven core of boto 3.
            ├── docutils>=0.10               Docutils -- Python Documentation Utilities
            ├── jmespath<1.0.0,>=0.7.1       JSON Matching Expressions
            └── python-dateutil<3.0.0,>=2.1  Extensions to the standard Python datetime module
                └── six>=1.5                 Python 2 and 3 compatibility utilities

Johnnydep can also attempt to resolve the dependency tree:

    $ johnnydep ipython --output-format pinned
    ipython==6.5.0
    appnope==0.1.0
    backcall==0.1.0
    decorator==4.3.0
    jedi==0.12.1
    pexpect==4.6.0
    pickleshare==0.7.4
    prompt-toolkit==1.0.15
    pygments==2.2.0
    setuptools==40.0.0
    simplegeneric==0.8.1
    traitlets==4.3.2
    parso==0.3.1
    ptyprocess==0.6.0
    six==1.11.0
    wcwidth==0.1.7
    ipython-genutils==0.2.0

Note that [`pip install` lacked a working solver](https://github.com/pypa/pip/issues/988) for many years, but [pip v20.3 has a new solver](https://blog.python.org/2020/11/pip-20-3-release-new-resolver.html) (December 2020) which has really improved matters!

Check `johnnydep --help` for other features and options.


Helpful links
-------------

* [Core metadata specifications](https://packaging.python.org/specifications/core-metadata/)
* [PEP 427 -- The Wheel Binary Package Format 1.0](https://www.python.org/dev/peps/pep-0427/)
* [PEP 426 -- Metadata for Python Software Packages 2.0](https://www.python.org/dev/peps/pep-0426/) (now [revoked](https://www.python.org/dev/peps/pep-0426/#pep-withdrawal) but still commonly seen in the wild)
* [PEP 566 -- Metadata for Python Software Packages 2.1](https://www.python.org/dev/peps/pep-0566/)
* [PEP 503 -- Simple Repository API](https://www.python.org/dev/peps/pep-0503/)
