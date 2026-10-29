import pytest

from app.routers.utils.auth import login_identifier, validate_register_payload


@pytest.fixture
def valid_payload():
    return {
        "email": "user@example.com",
        "username": "exampleuser",
        "first_name": "Example",
        "last_name": "User",
        "password": "password123456",
    }


@pytest.mark.parametrize(
    ("field", "valid", "invalid"),
    [
        ("email", "a" * 243 + "@example.com", "a" * 244 + "@example.com"),
        ("username", "a" * 100, "a" * 101),
        ("username", "abc", "ab"),
        ("first_name", "a" * 30, "a" * 31),
        ("last_name", "a" * 30, "a" * 31),
        ("password", "a" * 12, "a" * 11),
        ("password", "a" * 128, "a" * 129),
    ],
)
def test_registration_field_boundaries(valid_payload, field, valid, invalid):
    assert validate_register_payload({**valid_payload, field: valid}) == {}
    assert set(validate_register_payload({**valid_payload, field: invalid})) == {field}


@pytest.mark.parametrize(
    "field", ["email", "username", "first_name", "last_name", "password"]
)
@pytest.mark.parametrize("invalid", [None, [], 123, ""])
def test_registration_requires_text(valid_payload, field, invalid):
    assert field in validate_register_payload({**valid_payload, field: invalid})


@pytest.mark.parametrize("email", ["a@b", "a b@example.com", "a@@example.com"])
def test_registration_rejects_invalid_email(valid_payload, email):
    assert "email" in validate_register_payload({**valid_payload, "email": email})


def test_registration_normalizes_identifiers_and_names(valid_payload):
    payload = {
        **valid_payload,
        "email": " USER@EXAMPLE.COM ",
        "username": " EXAMPLEUSER ",
        "first_name": " Example ",
        "last_name": " User ",
    }
    assert validate_register_payload(payload) == {}


def test_identifier_precedence_and_fallback():
    assert login_identifier({"identifier": " FIRST ", "email": "second"}) == "first"
    assert login_identifier({"identifier": [], "email": " SECOND "}) == "second"
    assert (
        login_identifier({"identifier": " ", "email": "\x00", "username": " THIRD "})
        == "third"
    )
