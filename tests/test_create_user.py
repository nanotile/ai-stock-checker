"""Tests for user provisioning CLI."""
import tempfile
from stock_checker.create_user import main, hash_password
from stock_checker.persistence import DataPersistence


def test_hash_password():
    import bcrypt
    hashed = hash_password("test123")
    assert bcrypt.checkpw(b"test123", hashed.encode("utf-8"))


def test_create_user_cli():
    d = tempfile.mkdtemp()
    # Need to init persistence to create schema
    DataPersistence(data_dir=d)

    result = main([
        "--username", "testuser",
        "--email", "test@test.com",
        "--password", "test123",
        "--data-dir", d,
    ])
    assert result == 0

    p = DataPersistence(data_dir=d)
    user = p.get_user_by_username("testuser")
    assert user is not None
    assert user["email"] == "test@test.com"


def test_create_user_with_portfolio():
    d = tempfile.mkdtemp()
    DataPersistence(data_dir=d)

    result = main([
        "--username", "kent",
        "--email", "kent@test.com",
        "--password", "pass",
        "--data-dir", d,
        "--portfolio-name", "USD Book",
        "--currency", "USD",
        "--initial-cash", "50000",
    ])
    assert result == 0

    p = DataPersistence(data_dir=d)
    user = p.get_user_by_username("kent")
    portfolios = p.list_portfolios(user["id"])
    assert len(portfolios) == 1
    assert portfolios[0]["currency"] == "USD"
    assert portfolios[0]["name"] == "USD Book"


def test_create_duplicate_user_fails():
    d = tempfile.mkdtemp()
    DataPersistence(data_dir=d)

    assert main(["--username", "dup", "--email", "a@b.com", "--password", "x", "--data-dir", d]) == 0
    assert main(["--username", "dup", "--email", "c@d.com", "--password", "y", "--data-dir", d]) == 1
