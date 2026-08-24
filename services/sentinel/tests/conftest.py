import os
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture(scope="session", autouse=True)
def isolated_trace_db(tmp_path_factory):
    """Give each test session its own span database.

    The default path is committed to the working tree, so successive runs
    accumulated spans and collided on the span_id unique constraint.
    """
    db = tmp_path_factory.mktemp("sentinel") / "test.db"
    os.environ["TRACER_DB_PATH"] = str(db)
    yield
    os.environ.pop("TRACER_DB_PATH", None)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
