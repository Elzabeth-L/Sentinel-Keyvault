from sentinel_common.config import Settings


def test_empty_optional_blob_url_is_disabled() -> None:
    settings = Settings(login_blob_account_url="")

    assert settings.login_blob_account_url is None
