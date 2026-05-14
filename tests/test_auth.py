from backend.app.enterprise.security import sha256_token


def test_token_hash_is_deterministic_and_not_plain():
    token = "abc"
    assert sha256_token(token) == sha256_token(token)
    assert sha256_token(token) != token
