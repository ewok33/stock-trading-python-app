from curses import def_shell_mode
import os
import requests
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
import snowflake.connector


MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY")
LIMIT = 1000
DS = '2026-05-12'

# Schema aligned with sample reference row (+ partition date from job)
EXAMPLE_TICKER = {
    "ticker": "HELE",
    "name": "Helen Of Troy Ltd",
    "market": "stocks",
    "locale": "us",
    "primary_exchange": "XNAS",
    "type": "CS",
    "active": True,
    "currency_name": "usd",
    "cik": "0000916789",
    "last_updated_utc": "2026-01-28T07:06:04.298459012Z",
}
ROW_KEYS = list(EXAMPLE_TICKER.keys()) + ["ds"]


def _snowflake_connect():
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    user = os.getenv("SNOWFLAKE_USER")
    password = os.getenv("SNOWFLAKE_PASSWORD")
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
    database = os.getenv("SNOWFLAKE_DATABASE")
    schema = os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC")
    role = os.getenv("SNOWFLAKE_ROLE")
    missing = [
        name
        for name, val in [
            ("SNOWFLAKE_ACCOUNT", account),
            ("SNOWFLAKE_USER", user),
            ("SNOWFLAKE_PASSWORD", password),
            ("SNOWFLAKE_WAREHOUSE", warehouse),
            ("SNOWFLAKE_DATABASE", database),
        ]
        if not val
    ]
    if missing:
        raise ValueError(f"Set environment variables: {', '.join(missing)}")

    kwargs = {
        "user": user,
        "password": password,
        "account": account,
        "warehouse": warehouse,
        "database": database,
        "schema": schema,
    }
    if role:
        kwargs["role"] = role
    return snowflake.connector.connect(**kwargs)


def _ensure_table(cursor, fq_table: str) -> None:
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {fq_table} (
            ticker VARCHAR(32),
            name VARCHAR(1024),
            market VARCHAR(64),
            locale VARCHAR(16),
            primary_exchange VARCHAR(32),
            type VARCHAR(32),
            active BOOLEAN,
            currency_name VARCHAR(32),
            cik VARCHAR(32),
            last_updated_utc TIMESTAMP_TZ(9),
            ds DATE
        )
        """
    )


def _row_tuple(row: dict, ds: str):
    def g(key):
        v = row.get(key)
        if v == "":
            return None
        return v

    return (
        g("ticker"),
        g("name"),
        g("market"),
        g("locale"),
        g("primary_exchange"),
        g("type"),
        g("active"),
        g("currency_name"),
        g("cik"),
        g("last_updated_utc"),
        ds,
    )


def run_stock_job():
    ds = datetime.now().strftime("%Y-%m-%d")
    tickers = []

    url = (
        f"https://api.massive.com/v3/reference/tickers?market=stocks&active=true"
        f"&order=asc&limit={LIMIT}&sort=ticker&apiKey={MASSIVE_API_KEY}"
    )
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    for ticker in data["results"]:
        ticker["ds"] = ds
        tickers.append(ticker)

    while "next_url" in data:
        print("requesting next page", data["next_url"])
        response = requests.get(data["next_url"] + f"&apiKey={MASSIVE_API_KEY}")
        response.raise_for_status()
        data = response.json()
        for ticker in data["results"]:
            ticker["ds"] = ds
            tickers.append(ticker)

    table = (os.getenv("SNOWFLAKE_TABLE", "TICKERS") or "TICKERS").upper()
    schema = (os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC") or "PUBLIC").upper()
    database = os.getenv("SNOWFLAKE_DATABASE")
    fq_table = f"{database}.{schema}.{table}"

    cols_sql = ", ".join(
        [
            "ticker",
            "name",
            "market",
            "locale",
            "primary_exchange",
            "type",
            "active",
            "currency_name",
            "cik",
            "last_updated_utc",
            "ds",
        ]
    )
    placeholders = ", ".join(["%s"] * len(ROW_KEYS))
    insert_sql = f"INSERT INTO {fq_table} ({cols_sql}) VALUES ({placeholders})"

    conn = _snowflake_connect()
    try:
        cursor = conn.cursor()
        _ensure_table(cursor, fq_table)
        cursor.execute(f'DELETE FROM {fq_table} WHERE ds = %s', (ds,))
        rows = [_row_tuple(t, ds) for t in tickers]
        cursor.executemany(insert_sql, rows)
        conn.commit()
        print(f"Loaded {len(rows)} rows into {fq_table} for ds={ds}")
    finally:
        conn.close()
