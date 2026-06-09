import os
import re
import json
from typing import Dict, Any, List, Optional, Tuple

import mysql.connector
from pydantic import BaseModel, Field, field_validator
from mcp.server.fastmcp import FastMCP

# ===== ENV CONFIG =====
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", None)  # default database from env

# ===== MCP SERVER =====
mcp = FastMCP("mysql-readonly")

# ===== MODELS =====
class DBInput(BaseModel):
    database: Optional[str] = Field(None, description="Database/schema name in MySQL")

    @field_validator("database")
    @classmethod
    def no_backticks(cls, v: Optional[str]) -> Optional[str]:
        if v and "`" in v:
            raise ValueError("Invalid database name.")
        return v

class RunSQLInput(DBInput):
    sql: str = Field(..., description="A single SELECT query.")
    limit: int = Field(10, ge=1, le=1000, description="Max rows to return (default 10).")

# ===== HELPERS =====
READONLY_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE|RENAME|REPLACE|MERGE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)

def _get_conn(db: Optional[str] = None):
    """Create a MySQL connection, optionally selecting a DB."""
    return mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=db or MYSQL_DATABASE
    )

def _safe_select(sql: str) -> str:
    if ";" in sql.strip().rstrip(";"):
        raise ValueError("Only a single statement is allowed.")
    if READONLY_FORBIDDEN.search(sql):
        raise ValueError("Write/DDL statements are not allowed.")
    if not re.match(r"^\s*SELECT\b", sql, re.IGNORECASE):
        raise ValueError("Only SELECT queries are allowed.")
    return sql.strip()

def _ensure_limit(sql: str, limit: int) -> Tuple[str, int]:
    if re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
        return sql, limit
    return f"{sql} LIMIT {limit}", limit

# ===== TOOLS =====
@mcp.tool(description="List all tables in a database.")
def list_tables(input: DBInput) -> List[Dict[str, Any]]:
    q = """
    SELECT TABLE_NAME, TABLE_TYPE, ENGINE, TABLE_ROWS, CREATE_TIME, UPDATE_TIME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = %s
    ORDER BY TABLE_NAME
    """
    with _get_conn(input.database or MYSQL_DATABASE) as c, c.cursor(dictionary=True) as cur:
        cur.execute(q, (input.database or MYSQL_DATABASE,))
        return cur.fetchall()

@mcp.tool(description="Describe columns for a specific table (types, nullability, defaults).")
def describe_table(database: str, table: str) -> List[Dict[str, Any]]:
    if "`" in table:
        raise ValueError("Invalid table name.")
    q = """
    SELECT COLUMN_NAME, ORDINAL_POSITION, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT,
           COLUMN_KEY, EXTRA, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
    ORDER BY ORDINAL_POSITION
    """
    with _get_conn(database) as c, c.cursor(dictionary=True) as cur:
        cur.execute(q, (database, table))
        return cur.fetchall()

@mcp.tool(description="Get primary keys, foreign keys, and indexes for a database.")
def table_constraints(database: str) -> Dict[str, Any]:
    results = {"primary_keys": [], "foreign_keys": [], "indexes": []}

    pk_q = """
    SELECT tc.TABLE_NAME, kcu.COLUMN_NAME, kcu.ORDINAL_POSITION
    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
    JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
      ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
     AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
     AND tc.TABLE_NAME = kcu.TABLE_NAME
    WHERE tc.TABLE_SCHEMA = %s AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
    ORDER BY tc.TABLE_NAME, kcu.ORDINAL_POSITION
    """

    fk_q = """
    SELECT kcu.TABLE_NAME, kcu.COLUMN_NAME, kcu.REFERENCED_TABLE_NAME, kcu.REFERENCED_COLUMN_NAME,
           rc.UPDATE_RULE, rc.DELETE_RULE
    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
    JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
      ON kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
     AND kcu.CONSTRAINT_SCHEMA = rc.CONSTRAINT_SCHEMA
    WHERE kcu.TABLE_SCHEMA = %s AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
    ORDER BY kcu.TABLE_NAME, kcu.COLUMN_NAME
    """

    idx_q = """
    SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME, COLLATION, CARDINALITY
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = %s
    ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
    """

    with _get_conn(database) as c, c.cursor(dictionary=True) as cur:
        cur.execute(pk_q, (database,))
        results["primary_keys"] = cur.fetchall()
        cur.execute(fk_q, (database,))
        results["foreign_keys"] = cur.fetchall()
        cur.execute(idx_q, (database,))
        results["indexes"] = cur.fetchall()
    return results

@mcp.tool(description="Get a JSON schema of tables → columns → types for better SQL generation.")
def schema_snapshot(input: DBInput) -> Dict[str, Dict[str, str]]:
    q = """
    SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = %s
    ORDER BY TABLE_NAME, ORDINAL_POSITION
    """
    snapshot: Dict[str, Dict[str, str]] = {}
    with _get_conn(input.database or MYSQL_DATABASE) as c, c.cursor() as cur:
        cur.execute(q, (input.database or MYSQL_DATABASE,))
        for table, col, ctype in cur:
            snapshot.setdefault(table, {})[col] = ctype
    return snapshot

@mcp.tool(description=f"Execute a single SELECT query safely against the database {MYSQL_DATABASE}. "
                      f"Before writing the SQL, ALWAYS call schema_snapshot(database='{MYSQL_DATABASE}') "
                      "to know the exact tables and columns. Only SELECT is allowed.")
def run_sql(input: RunSQLInput) -> Dict[str, Any]:
    sql = _safe_select(input.sql)
    sql, limit = _ensure_limit(sql, input.limit)
    with _get_conn(input.database or MYSQL_DATABASE) as c, c.cursor(dictionary=True) as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return {
        "row_count": len(rows),
        "limit_applied": limit,
        "rows": rows,
    }

# ===== RESOURCE =====
@mcp.resource("schema/{database}", description="JSON schema snapshot for {database}")
def resource_schema(database: str) -> Tuple[str, bytes]:
    data = schema_snapshot(DBInput(database=database))
    return ("application/json", json.dumps(data, indent=2).encode("utf-8"))

# ===== MAIN =====
if __name__ == "__main__":
    # Start MCP server over stdio
    mcp.run()
