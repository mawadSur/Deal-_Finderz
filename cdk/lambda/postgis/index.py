import json
import os
import logging
import pg8000
import pathlib

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def run_sql(conn, sql: str):
    with conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()


def split_statements(sql_text: str):
    # naive split on semicolons; ignores empty fragments
    parts = []
    buff = []
    for line in sql_text.splitlines():
        buff.append(line)
        if line.strip().endswith(";"):
            stmt = "\n".join(buff).strip()
            buff = []
            if stmt:
                parts.append(stmt)
    # any trailing content
    tail = "\n".join(buff).strip()
    if tail:
        parts.append(tail)
    return parts


def ensure_migrations_table(conn):
    run_sql(
        conn,
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id TEXT PRIMARY KEY,
            executed_at TIMESTAMPTZ DEFAULT now()
        );
        """,
    )


def has_run(conn, migration_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM schema_migrations WHERE id = %s", (migration_id,))
        row = cur.fetchone()
        return bool(row)


def run_migrations_if_any(conn):
    sql_dir = pathlib.Path(__file__).parent / "sql"
    if not sql_dir.exists():
        return
    ensure_migrations_table(conn)
    # run files in sorted order
    for p in sorted(sql_dir.glob("*.sql")):
        mid = p.name
        if has_run(conn, mid):
            logger.info(f"Skipping already applied migration {mid}")
            continue
        sql_text = p.read_text(encoding="utf-8")
        for stmt in split_statements(sql_text):
            with conn.cursor() as cur:
                cur.execute(stmt)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO schema_migrations(id) VALUES (%s)", (mid,))
        conn.commit()
        logger.info(f"Applied migration {mid}")


def handler(event, context):
    logger.info(f"Event: {json.dumps(event)}")
    request_type = event.get("RequestType") or event.get("RequestType".lower()) or event.get("requestType")
    # Environment config
    host = os.environ["DB_HOST"]
    port = int(os.environ.get("DB_PORT", "5432"))
    dbname = os.environ["DB_NAME"]
    user = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]

    # Only run on Create/Update; ignore Delete
    if request_type in ("Delete", "delete"):
        return {"PhysicalResourceId": f"postgis-{host}", "Status": "SUCCESS"}

    try:
        conn = pg8000.connect(host=host, port=port, database=dbname, user=user, password=password, ssl_context=True)
        # Ensure extension exists
        run_sql(conn, "CREATE EXTENSION IF NOT EXISTS postgis;")
        # Run optional migrations if property provided
        props = event.get("ResourceProperties") or {}
        if str(props.get("RunMigrations", "false")).lower() in ("true", "1", "yes"):
            run_migrations_if_any(conn)
        conn.close()
        return {
            "PhysicalResourceId": f"postgis-{host}",
            "Status": "SUCCESS",
            "Data": {"Extension": "postgis", "Enabled": True},
        }
    except Exception as e:
        logger.exception("Failed to enable PostGIS")
        raise
