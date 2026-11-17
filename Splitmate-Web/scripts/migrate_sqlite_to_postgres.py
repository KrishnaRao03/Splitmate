import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import Boolean, Date, DateTime, MetaData, create_engine, func, select, text

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import db
from app import create_app


TABLE_ORDER = [
    'user',
    'group',
    'group_members',
    'expense',
    'expense_split',
    'expense_history',
    'payment',
    'note',
    'task',
]


def sqlite_url(path):
    return f"sqlite:///{Path(path).resolve().as_posix()}"


def parse_datetime(value):
    if value is None or isinstance(value, (date, datetime)):
        return value

    value = str(value)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return value


def clean_row(row, source_table, target_table):
    source_columns = set(source_table.columns.keys())
    cleaned = {}

    for column in target_table.columns:
        if column.name not in source_columns:
            continue

        value = row[column.name]
        if value is not None and isinstance(column.type, Boolean):
            value = bool(value)
        elif value is not None and isinstance(column.type, (DateTime, Date)):
            value = parse_datetime(value)

        cleaned[column.name] = value

    return cleaned


def table_has_rows(connection, table):
    return connection.execute(select(func.count()).select_from(table)).scalar_one() > 0


def reset_sequence(connection, table):
    if 'id' not in table.columns:
        return

    if connection.engine.dialect.name != 'postgresql':
        return

    quoted_table = connection.engine.dialect.identifier_preparer.quote(table.name)
    connection.execute(text(f"""
        SELECT setval(
            pg_get_serial_sequence('{quoted_table}', 'id'),
            COALESCE((SELECT MAX(id) FROM {quoted_table}), 1),
            (SELECT MAX(id) IS NOT NULL FROM {quoted_table})
        )
    """))


def main():
    parser = argparse.ArgumentParser(description='Copy Splitmate data from SQLite to PostgreSQL.')
    parser.add_argument(
        '--sqlite-path',
        default=Path('instance') / 'splitmate.db',
        help='Path to the existing SQLite database.',
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Delete rows in the target database before copying.',
    )
    args = parser.parse_args()

    if not os.environ.get('DATABASE_URL'):
        raise SystemExit('DATABASE_URL must point to the target PostgreSQL database before running this script.')

    sqlite_path = Path(args.sqlite_path)
    if not sqlite_path.exists():
        raise SystemExit(f'SQLite database not found: {sqlite_path}')

    app = create_app()
    with app.app_context():
        if db.engine.dialect.name != 'postgresql':
            raise SystemExit(f'DATABASE_URL must use PostgreSQL, not {db.engine.dialect.name}.')

        db.create_all()

        source_engine = create_engine(sqlite_url(sqlite_path))
        source_meta = MetaData()
        target_meta = MetaData()
        source_meta.reflect(source_engine)
        target_meta.reflect(db.engine)

        with db.engine.begin() as target_connection:
            target_has_data = any(
                table_name in target_meta.tables and table_has_rows(target_connection, target_meta.tables[table_name])
                for table_name in TABLE_ORDER
            )

            if target_has_data and not args.force:
                raise SystemExit('Target database already has rows. Re-run with --force to replace them.')

            if args.force:
                for table_name in reversed(TABLE_ORDER):
                    if table_name in target_meta.tables:
                        target_connection.execute(target_meta.tables[table_name].delete())

            with source_engine.connect() as source_connection:
                for table_name in TABLE_ORDER:
                    if table_name not in source_meta.tables or table_name not in target_meta.tables:
                        continue

                    source_table = source_meta.tables[table_name]
                    target_table = target_meta.tables[table_name]
                    rows = [
                        clean_row(row._mapping, source_table, target_table)
                        for row in source_connection.execute(select(source_table))
                    ]

                    if rows:
                        target_connection.execute(target_table.insert(), rows)

                    reset_sequence(target_connection, target_table)
                    print(f'{table_name}: copied {len(rows)} rows')


if __name__ == '__main__':
    main()
