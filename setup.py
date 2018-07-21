from setuptools import setup

setup(
    name="johnnydep",
    version="0.1a1",
    description="Display dependency tree of Python distribution",
    long_description="",
    packages=["johnnydep"],
    author="Wim Glenn",
    author_email="hey@wimglenn.com",
    license="MIT",
    url="https://github.com/wimglenn/johnnydep",
    install_requires=[
        "anytree",
        "structlog",
        "tabulate",
        "wimpy",
        "colorama",  # colored output for structlog
        "cachetools",
        "testfixtures",
        "oyaml",
        "pytoml",
        "packaging>=17.0",
        "pip>=10.0.0",
        "wheel>=0.31.0",
        "setuptools>=38.3",  # for pkg_reources
        "pkginfo>=1.4.2",
    ],
    entry_points={"console_scripts": ["johnnydep=johnnydep.cli:main"]},
)
