# SchemaPilot MCP

An MCP (Model Context Protocol) server that exposes MySQL database metadata and safe read-only query capabilities to AI assistants such as GitHub Copilot.

The server enables AI agents to inspect database schemas, discover tables, understand relationships, and execute read-only SQL queries while enforcing safety guardrails.

This project demonstrates how MCP can be used to provide structured database access to AI-powered tools.

---

## Overview

SchemaPilot MCP exposes MySQL databases as MCP tools and resources.

Instead of manually writing SQL, an MCP-compatible client can:

1. Discover available tables.
2. Inspect column definitions.
3. Understand primary keys, foreign keys, and indexes.
4. Retrieve schema snapshots.
5. Generate SQL using database context.
6. Execute safe SELECT queries.

The server prevents all write operations and restricts execution to read-only queries.

---

## Features

### Database Discovery

- List tables in a database
- Inspect table structures
- View column metadata
- Explore schema information

### Relationship Analysis

- Primary keys
- Foreign keys
- Indexes
- Table constraints

### Safe Query Execution

- Only SELECT statements allowed
- Blocks:
  - INSERT
  - UPDATE
  - DELETE
  - CREATE
  - ALTER
  - DROP
  - TRUNCATE
  - RENAME
  - GRANT
  - REVOKE

### MCP Resource Support

- Schema snapshots exposed as MCP resources
- JSON-based schema representation

### AI-Friendly Design

The MCP tools are designed specifically to help AI assistants understand database structure before generating SQL.

---

## Architecture

```text
+--------------------------+
| GitHub Copilot / Agent   |
+------------+-------------+
             |
             | MCP Protocol
             |
+------------v-------------+
|      SchemaPilot MCP     |
+------------+-------------+
             |
             |
+------------v-------------+
|         MySQL            |
+--------------------------+
```

---

## MCP Tools

### list_tables

Lists all tables available in a database.

#### Example

```json
{
  "database": "sales_db"
}
```

Returns:

```json
[
  {
    "TABLE_NAME": "customers",
    "TABLE_TYPE": "BASE TABLE"
  }
]
```

---

### describe_table

Returns column definitions for a table.

#### Example

```json
{
  "database": "sales_db",
  "table": "customers"
}
```

Returns:

```json
[
  {
    "COLUMN_NAME": "customer_id",
    "COLUMN_TYPE": "int"
  }
]
```

---

### table_constraints

Returns:

- Primary Keys
- Foreign Keys
- Indexes

Useful for understanding relationships between tables.

---

### schema_snapshot

Returns a simplified schema structure:

```json
{
  "customers": {
    "customer_id": "int",
    "customer_name": "varchar(255)"
  }
}
```

This tool is particularly useful for AI-generated SQL.

---

### run_sql

Executes a safe read-only SQL query.

#### Example

```json
{
  "sql": "SELECT * FROM customers",
  "limit": 10
}
```

Returns:

```json
{
  "row_count": 10,
  "rows": [...]
}
```

---

## MCP Resource

### schema/{database}

Provides a JSON schema snapshot of the specified database.

Example:

```text
schema/sales_db
```

Returns:

```json
{
  "customers": {
    "customer_id": "int",
    "customer_name": "varchar(255)"
  }
}
```

---

## Security Guardrails

To ensure safe usage, the server enforces:

### Allowed

```sql
SELECT *
FROM customers;
```

### Blocked

```sql
INSERT INTO customers ...
UPDATE customers ...
DELETE FROM customers ...
DROP TABLE customers ...
ALTER TABLE customers ...
```

Additional protections:

- Single statement only
- Automatic LIMIT enforcement
- Database name validation
- Table name validation

---

## Environment Variables

Configure database connectivity using environment variables.

```bash
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=password
MYSQL_DATABASE=sales_db
```

---

## Installation

### Clone Repository

```bash
git clone https://github.com/<username>/schemapilot-mcp.git
cd schemapilot-mcp
```

### Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:

```text
mysql-connector-python
pydantic
mcp
```

---

## Running the Server

```bash
python server.py
```

The MCP server starts using stdio transport and becomes available to MCP-compatible clients.

---

## Example Workflow

### Step 1

Agent requests schema information:

```text
List available tables.
```

### Step 2

Agent calls:

```text
list_tables()
```

### Step 3

Agent inspects schema:

```text
describe_table()
```

or

```text
schema_snapshot()
```

### Step 4

Agent generates SQL:

```sql
SELECT customer_name,
       COUNT(*) AS orders
FROM orders
GROUP BY customer_name;
```

### Step 5

Agent executes query using:

```text
run_sql()
```

### Step 6

Results returned to user.

---

## Learning Objectives

This project demonstrates:

- MCP Server Development
- FastMCP Tool Registration
- Resource Exposure in MCP
- AI-Assisted Database Exploration
- Secure Query Execution
- Database Metadata Discovery
- Read-Only Database Access Patterns

---

## Future Enhancements

- PostgreSQL support
- SQL validation using LLMs
- Query execution plans
- Query cost estimation
- Databricks integration
- Snowflake integration
- Role-based access control
- Query auditing
- Natural Language → SQL MCP Tool

---

## Technologies Used

- Python
- FastMCP
- Pydantic
- MySQL
- MCP (Model Context Protocol)
- GitHub Copilot

---

## Disclaimer

This project is intended for educational and demonstration purposes. The server is designed as a read-only database access layer and should be further secured before production deployment.
