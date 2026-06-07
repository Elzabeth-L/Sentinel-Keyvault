import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_postgresql_supports_tenant_session_context() -> None:
    database_url = os.getenv("SENTINEL_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("SENTINEL_TEST_DATABASE_URL is not configured")
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": "00000000-0000-0000-0000-000000000001"},
            )
            value = await connection.scalar(text("SELECT current_setting('app.tenant_id')"))
            assert value == "00000000-0000-0000-0000-000000000001"
    finally:
        await engine.dispose()
