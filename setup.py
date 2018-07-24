from setuptools import setup

setup(
    name="johnnydep",
    version="0.3",
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
        "colorama",  # pretty output for structlog
        "cachetools",
        "testfixtures",
        "oyaml",
        "pytoml",
        "packaging>=17",
        "pip",
        "wheel>=0.31.0",
        "setuptools>=38.3",  # for pkg_resources
        "pkginfo>=1.4.2",
    ],
    entry_points={"console_scripts": ["johnnydep=johnnydep.cli:main", "pipper=johnnydep.pipper:main"]},
)
