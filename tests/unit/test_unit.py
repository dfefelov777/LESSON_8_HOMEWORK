import pytest
from unittest.mock import MagicMock
from datetime import datetime
from homework.app.scoring import get_score, get_interests
from homework.app.store import RedisStore


@pytest.fixture
def mock_store():
    store = MagicMock(spec=RedisStore)
    return store


@pytest.mark.parametrize(
    "phone,email,expected_score",
    [
        ("71234567890", None, 1.5),
        (None, "vasya@example.com", 1.5),
        ("71234567890", "vasya@example.com", 3.0),
        (None, None, 0.0),
    ],
)
def test_get_score_phone_email(mock_store, phone, email, expected_score):
    mock_store.cache_get.return_value = None
    score = get_score(mock_store, phone=phone, email=email)
    assert score == expected_score


def test_get_score_full(mock_store):
    mock_store.cache_get.return_value = None
    score = get_score(
        mock_store,
        phone="71234567890",
        email="vasya@example.com",
        birthday=datetime(1990, 1, 1),
        gender=1,
        first_name="Вася",
        last_name="Пупкин",
    )
    assert score == 5.0


def test_get_score_cache_hit(mock_store):
    mock_store.cache_get.return_value = "2.5"
    score = get_score(mock_store, phone="71234567890")
    assert score == 2.5


def test_get_score_cache_miss(mock_store):
    mock_store.cache_get.return_value = None
    score = get_score(mock_store, phone="71234567890")
    mock_store.cache_set.assert_called()


def test_get_score_store_unavailable(mock_store):
    mock_store.cache_get.side_effect = Exception("Store unavailable")
    score = get_score(mock_store, phone="71234567890")
    assert score == 1.5


def test_get_interests_success(mock_store):
    mock_store.get.return_value = '["books", "music"]'
    interests = get_interests(mock_store, "1")
    assert interests == ["books", "music"]


def test_get_interests_store_unavailable(mock_store):
    mock_store.get.side_effect = Exception("Store unavailable")
    interests = get_interests(mock_store, "1")
    assert interests == []
