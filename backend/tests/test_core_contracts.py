from backend.app.auth.security import create_access_token, decode_access_token, get_password_hash, verify_password


def test_password_hash_roundtrip():
    hashed = get_password_hash("SenhaForte123")
    assert hashed != "SenhaForte123"
    assert verify_password("SenhaForte123", hashed)


def test_jwt_roundtrip():
    token = create_access_token("teste@vinance.local")
    assert decode_access_token(token) == "teste@vinance.local"
