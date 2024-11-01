import pytest

from johnnydep.downloader import download_dist


@pytest.mark.parametrize(
    "url, index_urls, expected_auth, expected_top_level_url",
    [
        (
            "https://pypi.example.com/packages",
            (),
            None,
            None,
        ),
        (
            "https://pypi.example.com/packages",
            ("https://pypi.example.com/simple",),
            None,
            None,
        ),
        (
            "https://pypi.example.com/packages",
            ("https://user:pass@pypi.example.com/simple",),
            ("user", "pass"),
            "pypi.example.com",
        ),
        (
            "https://pypi.extra.com/packages",
            ("https://user:pass@pypi.example.com/simple", "https://pypi.extra.com/simple"),
            None,
            "pypi.example.com",
        ),
        (
            "https://pypi.extra.com/packages",
            ("https://user:pass@pypi.example.com/simple", "https://user:extrapass@pypi.extra.com/simple"),
            ("user", "extrapass"),
            "pypi.extra.com",
        ),
        (
            "https://pypi.extra.com/packages",
            ("https://user:extrapass@pypi.extra.com/simple",),
            ("user", "extrapass"),
            "pypi.extra.com",
        ),
    ],
    ids=(
        "empty urls",
        "index_url without auth",
        "index_url with auth",
        "extra_index_url without auth",
        "extra_index_url with auth",
        "extra_index_url with auth (no index_url)",
    ),
)
def test_download_dist_auth(mocker, url, index_urls, expected_auth, expected_top_level_url, tmp_path):
    mgr = mocker.patch("johnnydep.downloader.HTTPPasswordMgrWithDefaultRealm")
    add_password_mock = mgr.return_value.add_password

    opener = mocker.patch("johnnydep.downloader.build_opener").return_value
    mock_response = opener.open.return_value
    mock_response.read.return_value = b"test body"

    scratch_path = tmp_path / "test-0.1.tar.gz"
    with scratch_path.open("wb") as f:
        download_dist(
            url=url + "/test-0.1.tar.gz",
            f=f,
            index_urls=index_urls,
        )
    if expected_auth is None:
        add_password_mock.assert_not_called()
    else:
        expected_realm = None
        expected_username, expected_password = expected_auth
        add_password_mock.assert_called_once_with(
            expected_realm,
            expected_top_level_url,
            expected_username,
            expected_password,
        )
    assert scratch_path.read_bytes() == b"test body"
