import json

from johnnydep.env_check import main


def test_env_check(capsys):
    main()
    out, err = capsys.readouterr()
    assert err == ""
    data = json.loads(out)
    assert "py_ver" in data
