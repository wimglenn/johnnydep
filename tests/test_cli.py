# coding: utf-8
from __future__ import unicode_literals

import json
import os
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
      [
        {
          "name": "fakedist",
          "summary": "This is a fake distribution for johnnydep's test suite",
          "specifier": ">1.2",
          "requires": [],
          "required_by": [],
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
          "checksum": "md5=63d82676c56d127bd9d1d41af5e8a064"
        }
      ]
    ''')


def test_yaml_out(mocker, capsys):
    mocker.patch('sys.argv', 'johnnydep fakedist --fields=ALL --output-format=yaml'.split())
    main()
    out, err = capsys.readouterr()
    assert err == ''
    assert out == dedent('''\
      - name: fakedist
        summary: This is a fake distribution for johnnydep's test suite
        specifier: ''
        requires: []
        required_by: []
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
        checksum: md5=63d82676c56d127bd9d1d41af5e8a064

    ''')


def test_pipper(mocker, capsys):
    mocker.patch('sys.argv', 'pipper.py fakedist'.split())
    pipper_main()
    out, err = capsys.readouterr()
    output = json.loads(out)
    path = output.pop('path')
    assert os.path.isfile(path)
    assert err == ''
    assert output == {
        'checksum': 'md5=63d82676c56d127bd9d1d41af5e8a064',
        'url': 'https://pypi.python.org/simple/fakedist/fakedist-1.2.3-py2.py3-none-any.whl',
    }
    parent, fname = os.path.split(path)
    assert fname == 'fakedist-1.2.3-py2.py3-none-any.whl'


def test_diamond_deptree(mocker, capsys):
    fields = [
        'name',
        'specifier',
        'requires',
        'required_by',
        'versions_available',
        'version_latest_in_spec',
    ]
    mocker.patch('sys.argv', 'johnnydep distA --fields'.split() + fields)
    main()
    out, err = capsys.readouterr()
    assert err == ''
    assert out == dedent('''\
    name                specifier    requires           required_by    versions_available      version_latest_in_spec
    ------------------  -----------  -----------------  -------------  --------------------  ------------------------
    distA                            distB1, distB2                    0.1                                        0.1
    ├── distB1                       distC[x,z] (<0.3)  distA          0.1                                        0.1
    │   └── distC[x,z]  <0.3                            distB1         0.1, 0.2, 0.3                              0.2
    └── distB2                       distC[y] (!=0.2)   distA          0.1                                        0.1
        └── distC[y]    !=0.2                           distB2         0.1, 0.2, 0.3                              0.3
    ''')


def test_unresolvable_deptree(mocker, capsys):
    # It is still possible to print the dep tree even though there is no acceptable version available for distC
    fields = 'name requires required_by versions_available version_latest_in_spec'.split()
    mocker.patch('sys.argv', 'johnnydep distX --fields'.split() + fields)
    main()
    out, err = capsys.readouterr()
    assert err == ''
    assert out == dedent('''\
        name            requires                     required_by    versions_available      version_latest_in_spec
        --------------  ---------------------------  -------------  --------------------  ------------------------
        distX           distC (<=0.1), distC (>0.2)                 0.1                                        0.1
        ├── distC<=0.1                               distX          0.1, 0.2, 0.3                              0.1
        └── distC>0.2                                distX          0.1, 0.2, 0.3                              0.3
    ''')


def test_requirements_txt_output(mocker, capsys):
    mocker.patch('sys.argv', 'johnnydep distA -o pinned'.split())
    main()
    out, err = capsys.readouterr()
    assert err == ''
    assert out == dedent('''\
        dista==0.1
        distb1==0.1
        distb2==0.1
        distc[x,y,z]==0.1
    ''')
