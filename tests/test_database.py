import builtins
import types
import pytest

from src.db import analysis_repo
from src.db import database


class DummyResponse:
    def __init__(self, data=None):
        self.data = data or []

    def execute(self):
        return self


class DummyTable:
    def __init__(self):
        self.last_upsert_args = None
        self.last_returning = None
        self.last_on_conflict = None

    def upsert(self, result, on_conflict=None, returning=None):
        self.last_upsert_args = result
        self.last_on_conflict = on_conflict
        self.last_returning = returning
        return DummyResponse([{"id": "abc123"}])


class DummyTableNoData(DummyTable):
    def upsert(self, result, on_conflict=None, returning=None):
        super().upsert(result, on_conflict=on_conflict, returning=returning)
        return DummyResponse([])


class DummyDB:
    def __init__(self, table_obj):
        self.table_obj = table_obj
        self.last_table_name = None

    def table(self, name):
        self.last_table_name = name
        return self.table_obj


@pytest.fixture(autouse=True)
def clear_db_cache():
    database.get_db.cache_clear()
    yield
    database.get_db.cache_clear()


def test_get_db_uses_env_and_caches(monkeypatch):
    created = []

    def fake_create_client(url, key):
        created.append((url, key))
        return "DB_CLIENT"

    monkeypatch.setenv("SUPABASE_URL", "http://example.com")
    monkeypatch.setenv("SUPABASE_KEY", "secret")
    monkeypatch.setattr(database, "create_client", fake_create_client)

    first = database.get_db()
    second = database.get_db()

    assert first == "DB_CLIENT"
    assert second == "DB_CLIENT"
    # ensure client created only once thanks to lru_cache
    assert created == [("http://example.com", "secret")]


def test_insert_analysis_upsert_called_with_conflict(monkeypatch):
    table = DummyTable()
    db = DummyDB(table)

    result_id = analysis_repo.insert_analysis(db, result={"ticker": "AAPL", "period": "1y"})

    assert result_id == "abc123"
    assert db.last_table_name == database.TABLE_NAME
    assert table.last_on_conflict == "ticker,period"
    assert table.last_returning == "representation"
    assert table.last_upsert_args == {"ticker": "AAPL", "period": "1y"}


def test_insert_analysis_returns_empty_when_no_rows(monkeypatch):
    table = DummyTableNoData()
    db = DummyDB(table)

    result_id = analysis_repo.insert_analysis(db, result={"ticker": "MSFT", "period": "6mo"})

    assert result_id == ""
    assert table.last_upsert_args == {"ticker": "MSFT", "period": "6mo"}
