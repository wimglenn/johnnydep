from setuptools import setup

with open("johnnydep/__init__.py") as f:
    for line in f:
        if line.startswith("__version__ = "):
            version = str(line.split()[-1].strip('"'))
            break

setup(
    name="johnnydep",
    version=version,
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
        "colorama ; python_version < '3.7' or platform_system == 'Windows'",  # structlog
        "cachetools",
        "oyaml",
        "pyblake2 ; python_version < '3.6'",
        "toml",
        "pip",
        "packaging >= 17, != 22",
        "wheel >= 0.32.0",
        "importlib_metadata ; python_version < '3.10'",
        "zipfile38 ; python_version < '3.8' and python_version != '2.7'",
        "zipfile39 ; python_version == '2.7'",
    ],
    entry_points={
        "console_scripts": [
            "johnnydep = johnnydep.cli:main",
            "pipper = johnnydep.pipper:main",
        ]
    },
    options={"bdist_wheel": {"universal": True}},
)
