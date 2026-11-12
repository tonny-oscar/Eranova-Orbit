from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.db.models import Base
from tests.conftest import alembic_config


async def test_single_migration_head(connection):
    script = ScriptDirectory.from_config(alembic_config(None))
    assert len(script.get_heads()) == 1


async def test_migrations_match_models(connection):
    """Fails if a model change was made without a migration."""
    from alembic.autogenerate import compare_metadata
    from alembic.runtime.migration import MigrationContext

    def _diff(sync_conn):
        context = MigrationContext.configure(sync_conn, opts={"compare_type": True})
        return compare_metadata(context, Base.metadata)

    assert await connection.run_sync(_diff) == []


async def test_downgrade_to_base_and_upgrade_again(connection):
    def _roundtrip(sync_conn):
        cfg = alembic_config(sync_conn)
        command.downgrade(cfg, "base")
        tables_after_downgrade = set(inspect(sync_conn).get_table_names()) - {"alembic_version"}
        command.upgrade(cfg, "head")
        return tables_after_downgrade

    assert await connection.run_sync(_roundtrip) == set()
