from setuptools import setup

setup(
    name='johnnydep',
    version='0.1',
    description='Display dependency tree of Python distribution',
    long_description='',
    packages=['johnnydep'],
    author='Wim Glenn',
    author_email='hey@wimglenn.com',
    license='MIT',
    url='https://github.com/wimglenn/johnnydep',
    install_requires=[
        'anytree', 'structlog', 'tabulate', 'wimpy', 'colorama', 'cachetools',
        'pip', 'wheel', 'testfixtures', 'oyaml', 'pytoml', 'setuptools>=38.3',
    ],
    entry_points={'console_scripts': ['johnnydep=johnnydep.cli:main']},
)
