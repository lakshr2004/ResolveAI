from pathlib import Path

from sqlalchemy import (
    MetaData,
    create_engine,
    event,
    inspect,
    select,
    text,
)

from app.config import settings
from app.database import Base, engine

# Register all SQLAlchemy models.
import app.models  # noqa: F401


SOURCE_DB = Path(__file__).resolve().parents[1] / "resolveai.db"

TABLE_ORDER = [
    "users",
    "tickets",
    "knowledge_documents",
    "ticket_ai_results",
    "ticket_history",
    "agent_notes",
    "ticket_action_history",
]

FOREIGN_KEY_CHECKS = [
    "ticket_ai_results",
    "ticket_history",
    "agent_notes",
    "ticket_action_history",
]


def create_source_engine():
    if not SOURCE_DB.is_file():
        raise FileNotFoundError(
            f"Source SQLite database not found: {SOURCE_DB}"
        )

    source_url = f"sqlite:///{SOURCE_DB.as_posix()}"

    source_engine = create_engine(
        source_url,
        connect_args={"check_same_thread": False},
    )

    # Enforce read-only mode for every source connection.
    @event.listens_for(source_engine, "connect")
    def make_source_read_only(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA query_only=ON")
        cursor.close()

    return source_engine


def migrate():
    if engine.dialect.name != "postgresql":
        raise RuntimeError(
            "Destination DATABASE_URL must point to PostgreSQL."
        )

    if not SOURCE_DB.is_file():
        raise FileNotFoundError(
            f"SQLite source not found: {SOURCE_DB}"
        )

    source_engine = create_source_engine()

    try:
        # Inspect source database without modifying it.
        source_metadata = MetaData()

        with source_engine.connect() as source_connection:
            integrity = source_connection.execute(
                text("PRAGMA integrity_check")
            ).scalar_one()

            if integrity != "ok":
                raise RuntimeError(
                    f"SQLite integrity check failed: {integrity}"
                )

            foreign_key_errors = source_connection.execute(
                text("PRAGMA foreign_key_check")
            ).all()

            if foreign_key_errors:
                raise RuntimeError(
                    f"SQLite foreign-key errors: {foreign_key_errors}"
                )

            source_metadata.reflect(
                bind=source_connection,
                only=TABLE_ORDER,
            )

            missing = set(TABLE_ORDER) - set(source_metadata.tables)

            if missing:
                raise RuntimeError(
                    f"Missing source tables: {sorted(missing)}"
                )

            source_rows = {}

            for table_name in TABLE_ORDER:
                table = source_metadata.tables[table_name]

                source_rows[table_name] = [
                    dict(row)
                    for row in source_connection.execute(
                        select(table)
                    ).mappings().all()
                ]

        source_counts = {
            name: len(rows)
            for name, rows in source_rows.items()
        }

        print("Source SQLite integrity: OK")
        print("Source record counts:", source_counts)

        # Do not overwrite an existing destination database.
        existing_tables = inspect(engine).get_table_names()

        if existing_tables:
            raise RuntimeError(
                "Destination PostgreSQL is not empty. "
                f"Existing tables: {existing_tables}. "
                "Migration cancelled without modifying them."
            )

        # Create schema and import data in one transaction.
        with engine.begin() as destination_connection:

            destination_connection.execute(
                text("SET LOCAL TIME ZONE 'UTC'")
            )

            Base.metadata.create_all(
                bind=destination_connection
            )

            for table_name in TABLE_ORDER:
                rows = source_rows[table_name]

                if not rows:
                    continue

                destination_table = Base.metadata.tables[table_name]

                destination_connection.execute(
                    destination_table.insert(),
                    rows,
                )

                print(
                    f"Imported {len(rows)} rows into {table_name}"
                )

            # Verify every table before committing.
            for table_name in TABLE_ORDER:
                destination_table = Base.metadata.tables[table_name]

                destination_count = destination_connection.execute(
                    select(
                        text("COUNT(*)")
                    ).select_from(destination_table)
                ).scalar_one()

                expected_count = source_counts[table_name]

                if destination_count != expected_count:
                    raise RuntimeError(
                        f"Count mismatch in {table_name}: "
                        f"expected {expected_count}, "
                        f"got {destination_count}"
                    )

            # Verify ticket foreign-key relationships.
            for table_name in FOREIGN_KEY_CHECKS:
                invalid_count = destination_connection.execute(
                    text(
                        f"""
                        SELECT COUNT(*)
                        FROM {table_name} child
                        LEFT JOIN tickets parent
                        ON child.ticket_id = parent.ticket_id
                        WHERE parent.ticket_id IS NULL
                        """
                    )
                ).scalar_one()

                if invalid_count:
                    raise RuntimeError(
                        f"Foreign-key verification failed "
                        f"for {table_name}: {invalid_count} invalid rows"
                    )

            # Reset PostgreSQL ID sequences after explicit ID imports.
            for table_name in TABLE_ORDER:
                destination_table = Base.metadata.tables[table_name]

                if "id" not in destination_table.c:
                    continue

                max_id = destination_connection.execute(
                    select(
                        text("MAX(id)")
                    ).select_from(destination_table)
                ).scalar_one()

                destination_connection.execute(
                    text(
                        """
                        SELECT setval(
                            pg_get_serial_sequence(:table_name, 'id'),
                            :last_value,
                            :is_called
                        )
                        """
                    ),
                    {
                        "table_name": f"public.{table_name}",
                        "last_value": max_id if max_id is not None else 1,
                        "is_called": max_id is not None,
                    },
                )

        print("\nMigration completed successfully.")
        print("Verified record counts:")

        for table_name, count in source_counts.items():
            print(f"  {table_name}: {count}")

        print(f"\nTotal records migrated: {sum(source_counts.values())}")

    finally:
        source_engine.dispose()


if __name__ == "__main__":
    migrate()
