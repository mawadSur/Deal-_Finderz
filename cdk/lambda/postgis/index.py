import json
import os
import logging
import pg8000

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def run_sql(conn, sql: str):
    with conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()


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
        conn.close()
        return {
            "PhysicalResourceId": f"postgis-{host}",
            "Status": "SUCCESS",
            "Data": {"Extension": "postgis", "Enabled": True},
        }
    except Exception as e:
        logger.exception("Failed to enable PostGIS")
        raise

