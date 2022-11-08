from setuptools import setup

setup(
    name="johnnydep",
    version="1.15",
    description="Display dependency tree of Python distribution",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
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
        "oyaml",
        "toml",
        "pip",
        "packaging >= 17",
        "wheel >= 0.32.0",
        "setuptools >= 38.3",  # for pkg_resources
        "pkginfo >= 1.4.2",
    ],
    entry_points={
        "console_scripts": [
            "johnnydep = johnnydep.cli:main",
            "pipper = johnnydep.pipper:main",
        ]
    },
    options={"bdist_wheel": {"universal": True}},
)
