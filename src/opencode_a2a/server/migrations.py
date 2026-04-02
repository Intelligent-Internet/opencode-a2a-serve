from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    insert,
    inspect,
    select,
    text,
    update,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

STATE_STORE_SCHEMA_NAME = "state_store"
CURRENT_STATE_STORE_SCHEMA_VERSION = 1

_SCHEMA_VERSION_METADATA = MetaData()

_SCHEMA_VERSIONS = Table(
    "a2a_schema_version",
    _SCHEMA_VERSION_METADATA,
    Column("name", String, primary_key=True),
    Column("version", Integer, nullable=False),
)


def _add_missing_nullable_column(
    connection: Connection,
    *,
    table: Table,
    column_name: str,
) -> None:
    existing_columns = {column["name"] for column in inspect(connection).get_columns(table.name)}
    if column_name in existing_columns:
        return
    column = table.c[column_name]
    if column.primary_key or not column.nullable:
        raise RuntimeError(f"Unsupported state-store migration for {table.name}.{column_name}")
    if connection.dialect.name not in {"sqlite"}:
        raise RuntimeError(
            "Automatic state-store migrations currently support SQLite upgrades only"
        )
    preparer = connection.dialect.identifier_preparer
    table_name_sql = preparer.quote(table.name)
    column_name_sql = preparer.quote(column_name)
    column_type_sql = column.type.compile(dialect=connection.dialect)
    connection.execute(
        text(f"ALTER TABLE {table_name_sql} ADD COLUMN {column_name_sql} {column_type_sql}")
    )


def _migration_1_add_interrupt_details_json(
    connection: Connection,
    *,
    interrupt_requests_table: Table,
) -> None:
    _add_missing_nullable_column(
        connection,
        table=interrupt_requests_table,
        column_name="details_json",
    )


def _read_schema_version(connection: Connection, *, name: str) -> int:
    result = connection.execute(
        select(_SCHEMA_VERSIONS.c.version).where(_SCHEMA_VERSIONS.c.name == name)
    )
    version = result.scalar_one_or_none()
    return int(version) if version is not None else 0


def _write_schema_version(connection: Connection, *, name: str, version: int) -> None:
    exists = connection.execute(
        select(_SCHEMA_VERSIONS.c.name).where(_SCHEMA_VERSIONS.c.name == name)
    ).scalar_one_or_none()
    if exists is None:
        connection.execute(insert(_SCHEMA_VERSIONS).values(name=name, version=version))
        return
    connection.execute(
        update(_SCHEMA_VERSIONS).where(_SCHEMA_VERSIONS.c.name == name).values(version=version)
    )


def migrate_state_store_schema(
    connection: Connection,
    *,
    state_metadata: MetaData,
    interrupt_requests_table: Table,
    current_version: int = CURRENT_STATE_STORE_SCHEMA_VERSION,
) -> int:
    _SCHEMA_VERSION_METADATA.create_all(connection)
    state_metadata.create_all(connection)

    stored_version = _read_schema_version(connection, name=STATE_STORE_SCHEMA_NAME)
    if stored_version > current_version:
        raise RuntimeError(
            "Database state-store schema version is newer than this application supports"
        )

    migrations: dict[int, Callable[[Connection], None]] = {
        1: lambda conn: _migration_1_add_interrupt_details_json(
            conn,
            interrupt_requests_table=interrupt_requests_table,
        ),
    }

    for next_version in range(stored_version + 1, current_version + 1):
        migration = migrations.get(next_version)
        if migration is None:
            raise RuntimeError(f"Missing state-store migration for version {next_version}")
        migration(connection)
        _write_schema_version(connection, name=STATE_STORE_SCHEMA_NAME, version=next_version)

    return current_version
