# coding: utf-8
from __future__ import unicode_literals

import json
import os
from pathlib import Path
from textwrap import dedent

from johnnydep.cli import main
from johnnydep.pipper import main as pipper_main


def test_printed_table_on_stdout(mocker, capsys):
    mocker.patch('sys.argv', 'johnnydep fakedist==1.2.3'.split())
    main()
    out, err = capsys.readouterr()
    assert err == ''
    assert out == dedent('''\
        name             summary
        ---------------  ------------------------------------------------------
        fakedist==1.2.3  This is a fake distribution for johnnydep's test suite
    ''')


def test_printed_table_on_stdout_with_specifier(mocker, capsys):
    mocker.patch('sys.argv', 'johnnydep fakedist==1.2.3 --fields specifier'.split())
    main()
    out, err = capsys.readouterr()
    assert err == ''
    assert out == dedent('''\
        name      specifier
        --------  -----------
        fakedist  ==1.2.3
    ''')


def test_printed_tree_on_stdout(mocker, capsys):
    mocker.patch('sys.argv', 'johnnydep fakedist[dev] --fields extras_available extras_requested'.split())
    main()
    out, err = capsys.readouterr()
    assert err == ''
    assert out == dedent('''\
        name               extras_available                           extras_requested
        -----------------  -----------------------------------------  ------------------
        fakedist[dev]      dev                                        dev
        └── wheel>=0.30.0  faster-signatures, signatures, test, tool
    ''')


def test_pretty_json_out(mocker, capsys):
    mocker.patch('sys.argv', 'johnnydep fakedist>1.2 --fields=ALL --output-format=json'.split())
    main()
    out, err = capsys.readouterr()
    assert err == ''
    assert out == dedent('''\
        {
          "name": "fakedist>1.2",
          "requires": [],
          "summary": "This is a fake distribution for johnnydep's test suite",
          "specifier": ">1.2",
          "import_names": [
            "fakedistmod"
          ],
          "homepage": "https://notexist",
          "extras_available": [
            "dev"
          ],
          "extras_requested": [],
          "project_name": "fakedist",
          "versions_available": [
            "1.2.3"
          ],
          "version_installed": null,
          "version_latest": "1.2.3",
          "version_latest_in_spec": "1.2.3",
          "download_link": "https://pypi.python.org/simple/fakedist/fakedist-1.2.3-py2.py3-none-any.whl",
          "checksum": "sha256=61698aa9386aac2567238386dd438c21f40d3be0bfcc6359e8aa5d0abe978c1f"
        }
    ''')


def test_yaml_out(mocker, capsys):
    mocker.patch('sys.argv', 'johnnydep fakedist --fields=ALL --output-format=yaml'.split())
    main()
    out, err = capsys.readouterr()
    assert err == ''
    assert out == dedent('''\
        name: fakedist
        requires: []
        summary: This is a fake distribution for johnnydep's test suite
        specifier: ''
        import_names: [fakedistmod]
        homepage: https://notexist
        extras_available: [dev]
        extras_requested: []
        project_name: fakedist
        versions_available: [1.2.3]
        version_installed: null
        version_latest: 1.2.3
        version_latest_in_spec: 1.2.3
        download_link: https://pypi.python.org/simple/fakedist/fakedist-1.2.3-py2.py3-none-any.whl
        checksum: sha256=61698aa9386aac2567238386dd438c21f40d3be0bfcc6359e8aa5d0abe978c1f

    ''')


def test_pipper(mocker, capsys):
    mocker.patch('sys.argv', 'pipper.py fakedist'.split())
    pipper_main()
    out, err = capsys.readouterr()
    output = json.loads(out)
    path = Path(output.pop('path'))
    assert path.is_file()
    assert err == ''
    assert output == {
        'hashtype': 'sha256',
        'srchash': '61698aa9386aac2567238386dd438c21f40d3be0bfcc6359e8aa5d0abe978c1f',
        'url': 'https://pypi.python.org/simple/fakedist/fakedist-1.2.3-py2.py3-none-any.whl',
    }
    assert path.name == 'fakedist-1.2.3-py2.py3-none-any.whl'
