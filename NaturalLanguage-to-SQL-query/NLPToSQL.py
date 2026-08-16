import streamlit as st
import mysql.connector
import sqlite3
import json
import os
import re
import pandas as pd
from datetime import datetime
from openai import OpenAI
import traceback
import logging
from typing import Optional, Tuple, List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Optional imports for additional database support
try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False

try:
    import cx_Oracle
    ORACLE_AVAILABLE = True
except ImportError:
    ORACLE_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('db_query_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Database Query Interface",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'sources' not in st.session_state:
    st.session_state.sources = {}
if 'schemas' not in st.session_state:
    st.session_state.schemas = {}
if 'data_profiles' not in st.session_state:
    st.session_state.data_profiles = {}
if 'query_history' not in st.session_state:
    st.session_state.query_history = []

# Supported LLM models
LLM_MODELS = {
    "OpenAI GPT-4o": {
        "provider": "openai",
        "model": "gpt-4o",
        "api_key_env": "OPENAI_API_KEY"
    },
    "OpenAI GPT-4": {
        "provider": "openai", 
        "model": "gpt-4",
        "api_key_env": "OPENAI_API_KEY"
    },
    "OpenAI GPT-3.5 Turbo": {
        "provider": "openai",
        "model": "gpt-3.5-turbo",
        "api_key_env": "OPENAI_API_KEY"
    },
    "Google Gemini 1.5 Flash": {
        "provider": "google",
        "model": "gemini-1.5-flash",
        "api_key_env": "GOOGLE_API_KEY"
    },
    "Google Gemini 1.5 Pro": {
        "provider": "google",
        "model": "gemini-1.5-pro",
        "api_key_env": "GOOGLE_API_KEY"
    },
    "gemini 2.0 flash": {
        "provider": "google",
        "model": "gemini-2.0-flash",
        "api_key_env": "GOOGLE_API_KEY"
    },
    "Claude 3 Sonnet": {
        "provider": "anthropic",
        "model": "claude-3-sonnet-20240229",
        "api_key_env": "ANTHROPIC_API_KEY"
    },
    "Claude 3 Opus": {
        "provider": "anthropic", 
        "model": "claude-3-opus-20240229",
        "api_key_env": "ANTHROPIC_API_KEY"
    }
}

# Optional imports for additional LLM providers
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

@st.cache_resource
def get_llm_client(model_config):
    """Get LLM client based on provider."""
    try:
        provider = model_config["provider"]
        api_key = os.getenv(model_config["api_key_env"])
        
        if not api_key:
            st.error(f"API key not found for {provider}. Please set {model_config['api_key_env']} environment variable.")
            return None
            
        if provider == "openai":
            return OpenAI(api_key=api_key)
        elif provider == "anthropic" and ANTHROPIC_AVAILABLE:
            return anthropic.Anthropic(api_key=api_key)
        elif provider == "google" and GOOGLE_AVAILABLE:
            genai.configure(api_key=api_key)
            return genai
        else:
            st.error(f"Provider {provider} not available or not installed")
            return None
    except Exception as e:
        st.error(f"Error creating LLM client: {str(e)}")
        logger.error(f"Error creating LLM client: {str(e)}")
        return None

def log_query_attempt(user_query: str, sql_query: str, success: bool, error: str = None, attempt: int = 1):
    """Log query attempt details."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_query": user_query,
        "sql_query": sql_query,
        "success": success,
        "error": error,
        "attempt": attempt
    }
    
    # Add to session state history
    st.session_state.query_history.append(log_entry)
    
    # Log to file
    if success:
        logger.info(f"Query successful (attempt {attempt}): {sql_query[:100]}...")
    else:
        logger.error(f"Query failed (attempt {attempt}): {error}. Query: {sql_query[:100]}...")

# Database connection functions (unchanged from original)
def connect_to_mysql(config):
    """Connect to MySQL database."""
    try:
        mysql_config = {
            'host': config['host'],
            'port': config['port'],
            'user': config['user'],
            'password': config['password'],
            'database': config['database']
        }
        connection = mysql.connector.connect(**mysql_config)
        logger.info(f"Connected to MySQL database: {config['database']}")
        return connection
    except Exception as e:
        logger.error(f"MySQL connection error: {str(e)}")
        st.error(f"MySQL connection error: {str(e)}")
        return None

def connect_to_sqlite(config):
    """Connect to SQLite database."""
    try:
        connection = sqlite3.connect(config['database'])
        logger.info(f"Connected to SQLite database: {config['database']}")
        return connection
    except Exception as e:
        logger.error(f"SQLite connection error: {str(e)}")
        st.error(f"SQLite connection error: {str(e)}")
        return None

def connect_to_sqlserver(config):
    """Connect to SQL Server database."""
    if not PYODBC_AVAILABLE:
        st.error("SQL Server support requires pyodbc. Please install it with: pip install pyodbc")
        return None
    try:
        conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={config['host']},{config['port']};DATABASE={config['database']};UID={config['user']};PWD={config['password']}"
        connection = pyodbc.connect(conn_str)
        logger.info(f"Connected to SQL Server database: {config['database']}")
        return connection
    except Exception as e:
        logger.error(f"SQL Server connection error: {str(e)}")
        st.error(f"SQL Server connection error: {str(e)}")
        return None

def connect_to_oracle(config):
    """Connect to Oracle database."""
    if not ORACLE_AVAILABLE:
        st.error("Oracle support requires cx_Oracle. Please install it with: pip install cx_Oracle")
        return None
    try:
        dsn = cx_Oracle.makedsn(config['host'], config['port'], service_name=config['service_name'])
        connection = cx_Oracle.connect(user=config['user'], password=config['password'], dsn=dsn)
        logger.info(f"Connected to Oracle database: {config['service_name']}")
        return connection
    except Exception as e:
        logger.error(f"Oracle connection error: {str(e)}")
        st.error(f"Oracle connection error: {str(e)}")
        return None

def get_connection(db_type, config):
    """Get database connection based on type."""
    connections = {
        'MySQL': connect_to_mysql,
        'SQLite': connect_to_sqlite,
        'SQL Server': connect_to_sqlserver,
        'Oracle': connect_to_oracle
    }
    return connections.get(db_type, lambda x: None)(config)

def get_schema_info(db_type, connection, database_name):
    """Get schema information for all tables in the database."""
    try:
        cursor = connection.cursor()
        
        if db_type == 'MySQL':
            query = """
            SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, 
                   COLUMN_KEY, EXTRA, CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME, ORDINAL_POSITION
            """
            cursor.execute(query, (database_name,))
            
        elif db_type == 'SQL Server':
            query = """
            SELECT t.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.IS_NULLABLE, 
                   c.COLUMN_DEFAULT, '' as COLUMN_KEY, '' as EXTRA, c.CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.TABLES t
            JOIN INFORMATION_SCHEMA.COLUMNS c ON t.TABLE_NAME = c.TABLE_NAME
            WHERE t.TABLE_SCHEMA = 'dbo'
            ORDER BY t.TABLE_NAME, c.ORDINAL_POSITION
            """
            cursor.execute(query)
            
        elif db_type == 'SQLite':
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            schema_info = []
            
            for table in tables:
                table_name = table[0]
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                for col in columns:
                    schema_info.append((
                        table_name, col[1], col[2], 'YES' if col[3] == 0 else 'NO',
                        col[4], 'PRIMARY KEY' if col[5] == 1 else '', '', None
                    ))
            return schema_info
            
        elif db_type == 'Oracle':
            query = """
            SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, NULLABLE, DATA_DEFAULT,
                   '' as COLUMN_KEY, '' as EXTRA, DATA_LENGTH
            FROM USER_TAB_COLUMNS
            ORDER BY TABLE_NAME, COLUMN_ID
            """
            cursor.execute(query)
        
        results = cursor.fetchall()
        cursor.close()
        return results
        
    except Exception as e:
        logger.error(f"Error fetching schema: {str(e)}")
        st.error(f"Error fetching schema: {str(e)}")
        return []

def get_data_profile(connection, db_type, table_name, sample_size=2000):
    """Get data profile for a table."""
    try:
        cursor = connection.cursor()
        
        if db_type == 'MySQL':
            query = f"SELECT * FROM {table_name} LIMIT {sample_size}"
        elif db_type == 'SQL Server':
            query = f"SELECT TOP {sample_size} * FROM {table_name}"
        elif db_type == 'Oracle':
            query = f"SELECT * FROM {table_name} WHERE ROWNUM <= {sample_size}"
        else:  # SQLite
            query = f"SELECT * FROM {table_name} LIMIT {sample_size}"
            
        cursor.execute(query)
        data = cursor.fetchall()
        
        if not data:
            return {"record_count": 0, "sample_data": []}
            
        columns = [desc[0] for desc in cursor.description]
        
        sample_records = []
        for i, record in enumerate(data[:5]):
            sample_records.append(dict(zip(columns, record)))
            
        profile = {
            "record_count": len(data),
            "sample_data": sample_records,
            "column_count": len(columns),
            "columns": columns
        }
        
        cursor.close()
        return profile
        
    except Exception as e:
        logger.error(f"Error creating data profile for {table_name}: {str(e)}")
        st.error(f"Error creating data profile for {table_name}: {str(e)}")
        return {"record_count": 0, "sample_data": []}

def save_metadata_to_file(source_name, schemas, profiles):
    """Save schema and data profile metadata to a file."""
    metadata = {
        "schemas": schemas,
        "data_profiles": profiles,
        "last_updated": datetime.now().isoformat()
    }
    
    filename = f"{source_name}_metadata.json"
    try:
        with open(filename, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        logger.info(f"Metadata saved to {filename}")
        return filename
    except Exception as e:
        logger.error(f"Error saving metadata: {str(e)}")
        st.error(f"Error saving metadata: {str(e)}")
        return None

def load_metadata_from_file(source_name):
    """Load schema and data profile metadata from a file."""
    filename = f"{source_name}_metadata.json"
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                metadata = json.load(f)
            logger.info(f"Metadata loaded from {filename}")
            return metadata
        return None
    except Exception as e:
        logger.error(f"Error loading metadata: {str(e)}")
        st.error(f"Error loading metadata: {str(e)}")
        return None

def clean_sql_query(raw_query):
    """Remove markdown or extra text from the generated SQL query."""
    if not raw_query:
        return None
    cleaned_query = re.sub(r'```sql\s*|\s*```', '', raw_query, flags=re.MULTILINE)
    cleaned_query = cleaned_query.strip()
    if not cleaned_query.endswith(';'):
        cleaned_query += ';'
    return cleaned_query

def generate_sql_with_llm(client, model_config, prompt):
    """Generate SQL using specified LLM provider."""
    try:
        provider = model_config["provider"]
        model = model_config["model"]
        
        if provider == "openai":
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a SQL query generator. Generate only valid SQL queries without any markdown, code blocks, or explanations."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000
            )
            return response.choices[0].message.content.strip()
            
        elif provider == "anthropic":
            response = client.messages.create(
                model=model,
                max_tokens=1000,
                system="You are a SQL query generator. Generate only valid SQL queries without any markdown, code blocks, or explanations.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text.strip()
            
        elif provider == "google":
            # Configure generation parameters
            generation_config = {
                "temperature": 0.7,
                "top_p": 1,
                "top_k": 32,
                "max_output_tokens": 1000,
            }

            # Set safety settings to block none (for SQL generation)
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                },
            ]

            # Create the model
            model = client.GenerativeModel(
                model_name=model,
                generation_config=generation_config,
                safety_settings=safety_settings
            )

            # Generate content
            response = model.generate_content(
                f"""You are a SQL query generator. Generate only valid SQL queries without any markdown, code blocks, or explanations.
                
                {prompt}
                
                Important: Return only the SQL query. No explanations or markdown formatting.
                """
            )
            
            # Extract the SQL query from the response
            if response.text:
                return response.text.strip()
            else:
                raise Exception("No SQL query generated by Gemini")
            
    except Exception as e:
        logger.error(f"Error generating SQL with {provider}: {str(e)}")
        raise e

def generate_sql_query_with_retry(user_query, schema_info, data_profiles, db_type, model_config, max_retries=3):
    """Generate SQL query with retry logic for failures."""
    client = get_llm_client(model_config)
    if not client:
        return None, []
    
    # Format schema information
    schema_text = f"Database Type: {db_type}\n\nTables and Columns:\n"
    current_table = ""
    
    for schema_row in schema_info:
        table_name = schema_row[0]
        if table_name != current_table:
            current_table = table_name
            schema_text += f"\nTable: {table_name}\n"
            
            if table_name in data_profiles:
                profile = data_profiles[table_name]
                schema_text += f"  Record Count: ~{profile['record_count']}\n"
                if profile.get('sample_data'):
                    schema_text += "  Sample Data:\n"
                    for sample in profile['sample_data'][:2]:
                        schema_text += f"    {sample}\n"
        
        column_name = schema_row[1]
        data_type = schema_row[2]
        is_nullable = schema_row[3]
        column_key = schema_row[5] if len(schema_row) > 5 else ""
        
        schema_text += f"  - {column_name}: {data_type}"
        if column_key:
            schema_text += f" ({column_key})"
        if is_nullable == 'NO':
            schema_text += " NOT NULL"
        schema_text += "\n"
    
    retry_attempts = []
    
    for attempt in range(1, max_retries + 1):
        try:
            # Build prompt based on attempt
            if attempt == 1:
                prompt = f"""
                Given the following database schema and sample data, generate a valid SQL query to answer the user's request. 
                Return only the SQL query without any explanation, markdown, or additional text.

                {schema_text}

                User Request: {user_query}
                
                Important: Generate only a valid {db_type} SQL query. No explanations or markdown formatting.
                """
            else:
                # Include previous failures in prompt for correction
                previous_failures = "\n\nPrevious failed attempts:\n"
                for prev_attempt in retry_attempts:
                    previous_failures += f"Attempt {prev_attempt['attempt']}: {prev_attempt['sql_query']}\n"
                    previous_failures += f"Error: {prev_attempt['error']}\n\n"
                
                prompt = f"""
                Given the following database schema and sample data, generate a valid SQL query to answer the user's request.
                Learn from the previous failed attempts and fix the errors.

                {schema_text}
                {previous_failures}
                
                User Request: {user_query}
                
                Important: 
                1. Generate only a valid {db_type} SQL query
                2. Fix the errors from previous attempts
                3. No explanations or markdown formatting
                4. Ensure the query syntax is correct for {db_type}
                """
            
            logger.info(f"Generating SQL query (attempt {attempt})")
            raw_query = generate_sql_with_llm(client, model_config, prompt)
            sql_query = clean_sql_query(raw_query)
            
            if not sql_query:
                raise Exception("Empty or invalid SQL query generated")
            
            # Test the query by attempting to execute it
            return sql_query, retry_attempts
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"SQL generation attempt {attempt} failed: {error_msg}")
            
            retry_attempts.append({
                "attempt": attempt,
                "sql_query": sql_query if 'sql_query' in locals() else "Failed to generate",
                "error": error_msg
            })
            
            if attempt == max_retries:
                logger.error(f"All {max_retries} attempts failed")
                return None, retry_attempts
    
    return None, retry_attempts

def execute_query_with_retry(connection, sql_query, db_type, user_query, schema_info, data_profiles, model_config, max_retries=3):
    """Execute SQL query with retry logic for failures."""
    retry_attempts = []
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Executing SQL query (attempt {attempt}): {sql_query[:100]}...")
            
            cursor = connection.cursor()
            cursor.execute(sql_query)
            
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            results = cursor.fetchall()
            cursor.close()
            
            log_query_attempt(user_query, sql_query, True, attempt=attempt)
            logger.info(f"Query executed successfully on attempt {attempt}")
            
            return columns, results, retry_attempts
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Query execution attempt {attempt} failed: {error_msg}")
            
            log_query_attempt(user_query, sql_query, False, error_msg, attempt)
            
            retry_attempts.append({
                "attempt": attempt,
                "sql_query": sql_query,
                "error": error_msg
            })
            
            if attempt < max_retries:
                # Generate corrected query
                logger.info(f"Attempting to fix SQL query (attempt {attempt + 1})")
                corrected_query, generation_attempts = generate_corrected_sql_query(
                    user_query, schema_info, data_profiles, db_type, model_config,
                    sql_query, error_msg, retry_attempts
                )
                
                if corrected_query:
                    sql_query = corrected_query
                else:
                    logger.error("Failed to generate corrected query")
                    break
            else:
                logger.error(f"All {max_retries} execution attempts failed")
    
    return [], [], retry_attempts

def generate_corrected_sql_query(user_query, schema_info, data_profiles, db_type, model_config, 
                                failed_query, error_msg, previous_attempts):
    """Generate a corrected SQL query based on the error."""
    client = get_llm_client(model_config)
    if not client:
        return None, []
    
    # Format schema information
    schema_text = f"Database Type: {db_type}\n\nTables and Columns:\n"
    current_table = ""
    
    for schema_row in schema_info:
        table_name = schema_row[0]
        if table_name != current_table:
            current_table = table_name
            schema_text += f"\nTable: {table_name}\n"
            
            if table_name in data_profiles:
                profile = data_profiles[table_name]
                schema_text += f"  Record Count: ~{profile['record_count']}\n"
        
        column_name = schema_row[1]
        data_type = schema_row[2]
        is_nullable = schema_row[3]
        column_key = schema_row[5] if len(schema_row) > 5 else ""
        
        schema_text += f"  - {column_name}: {data_type}"
        if column_key:
            schema_text += f" ({column_key})"
        if is_nullable == 'NO':
            schema_text += " NOT NULL"
        schema_text += "\n"
    
    # Build error context
    error_context = f"\nFailed Query: {failed_query}\nError Message: {error_msg}\n"
    
    # Include previous attempts
    if previous_attempts:
        error_context += "\nPrevious attempts:\n"
        for prev in previous_attempts:
            error_context += f"  SQL: {prev['sql_query']}\n  Error: {prev['error']}\n"
    
    prompt = f"""
    Fix the SQL query that failed with an error. Generate a corrected version that addresses the specific error.

    {schema_text}
    
    User Request: {user_query}
    {error_context}
    
    Common {db_type} issues to check:
    - Column names and table names (case sensitivity, typos)
    - Data types and casting
    - Syntax specific to {db_type}
    - JOIN conditions and table aliases
    - Function names and syntax
    
    Generate ONLY the corrected SQL query without explanations or markdown.
    """
    
    try:
        raw_query = generate_sql_with_llm(client, model_config, prompt)
        corrected_query = clean_sql_query(raw_query)
        logger.info(f"Generated corrected query: {corrected_query[:100]}...")
        return corrected_query, []
    except Exception as e:
        logger.error(f"Error generating corrected query: {str(e)}")
        return None, []


# Add this new function to your existing code
def optimize_query_with_llm(client, model_config, original_query, schema_info, data_profiles, db_type):
    """Optimize a SQL query using LLM."""
    try:
        provider = model_config["provider"]
        model = model_config["model"]
        
        # Format schema information
        schema_text = f"Database Type: {db_type}\n\nTables and Columns:\n"
        current_table = ""
        
        for schema_row in schema_info:
            table_name = schema_row[0]
            if table_name != current_table:
                current_table = table_name
                schema_text += f"\nTable: {table_name}\n"
                
                if table_name in data_profiles:
                    profile = data_profiles[table_name]
                    schema_text += f"  Record Count: ~{profile['record_count']}\n"
                    if profile.get('sample_data'):
                        schema_text += "  Sample Data:\n"
                        for sample in profile['sample_data'][:2]:
                            schema_text += f"    {sample}\n"
            
            column_name = schema_row[1]
            data_type = schema_row[2]
            is_nullable = schema_row[3]
            column_key = schema_row[5] if len(schema_row) > 5 else ""
            
            schema_text += f"  - {column_name}: {data_type}"
            if column_key:
                schema_text += f" ({column_key})"
            if is_nullable == 'NO':
                schema_text += " NOT NULL"
            schema_text += "\n"
        
        prompt = f"""
        Analyze and optimize the following SQL query for better performance. 
        Provide the optimized query and a brief explanation of the optimizations made.
        The optimized query should produce exactly the same results as the original.

        Database Schema:
        {schema_text}

        Original Query:
        {original_query}

        Important:
        1. The optimized query must be semantically equivalent to the original
        2. Include specific optimizations for {db_type}
        3. Format the response as:
           OPTIMIZED QUERY:
           ```sql
           [optimized query here]
           ```
           
           OPTIMIZATION EXPLANATION:
           [explanation here]
        """
        
        if provider == "openai":
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a SQL query optimizer. Analyze and optimize SQL queries for better performance while maintaining the same results."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000
            )
            response_text = response.choices[0].message.content.strip()
            
        elif provider == "anthropic":
            response = client.messages.create(
                model=model,
                max_tokens=1000,
                system="You are a SQL query optimizer. Analyze and optimize SQL queries for better performance while maintaining the same results.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            response_text = response.content[0].text.strip()
            
        elif provider == "google":
            generation_config = {
                "temperature": 0.7,
                "top_p": 1,
                "top_k": 32,
                "max_output_tokens": 1000,
            }

            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]

            model = client.GenerativeModel(
                model_name=model,
                generation_config=generation_config,
                safety_settings=safety_settings
            )

            response = model.generate_content(prompt)
            response_text = response.text.strip()
        
        # Extract the optimized query and explanation
        optimized_query = None
        explanation = None
        
        # Try to extract from markdown code block
        optimized_match = re.search(r'```sql\n(.*?)\n```', response_text, re.DOTALL)
        if optimized_match:
            optimized_query = optimized_match.group(1).strip()
        
        # Try to extract explanation
        explanation_match = re.search(r'OPTIMIZATION EXPLANATION:\s*(.*)', response_text, re.DOTALL)
        if explanation_match:
            explanation = explanation_match.group(1).strip()
        
        return optimized_query, explanation
        
    except Exception as e:
        logger.error(f"Error optimizing query with {provider}: {str(e)}")
        raise e

# Add this new function to verify query results match
def verify_query_results_match(connection, original_query, optimized_query, db_type):
    """Verify that the original and optimized queries return the same results."""
    try:
        # Execute original query
        cursor = connection.cursor()
        cursor.execute(original_query)
        original_results = cursor.fetchall()
        original_columns = [desc[0] for desc in cursor.description] if cursor.description else []
        cursor.close()
        
        # Execute optimized query
        cursor = connection.cursor()
        cursor.execute(optimized_query)
        optimized_results = cursor.fetchall()
        optimized_columns = [desc[0] for desc in cursor.description] if cursor.description else []
        cursor.close()
        
        # Compare column names
        if original_columns != optimized_columns:
            return False, "Column names don't match"
        
        # Compare row counts
        if len(original_results) != len(optimized_results):
            return False, f"Row count mismatch (original: {len(original_results)}, optimized: {len(optimized_results)})"
        
        # Compare each row
        for i, (orig_row, opt_row) in enumerate(zip(original_results, optimized_results)):
            if orig_row != opt_row:
                return False, f"Row {i+1} content doesn't match"
        
        return True, "Results match exactly"
        
    except Exception as e:
        logger.error(f"Error verifying query results: {str(e)}")
        return False, f"Verification error: {str(e)}"


# Streamlit UI
def main():
    st.title("🗄️ Natural Language Query Interface")
    
    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        option = st.radio(
            "Select an option:",
            ["User Query", "Query Optimizer", "Update Schema & Data Profile", "Add New Source", "Query History & Logs"]
        )
        
        # Model selection
        st.header("LLM Model Selection")
        available_models = []
        for model_name, config in LLM_MODELS.items():
            if config["provider"] == "openai" or (config["provider"] == "anthropic" and ANTHROPIC_AVAILABLE) or (config["provider"] == "google" and GOOGLE_AVAILABLE):
                if os.getenv(config["api_key_env"]):
                    available_models.append(model_name)
        
        if available_models:
            selected_model = st.selectbox("Select LLM Model:", available_models, index=0)
            st.session_state.selected_model = selected_model
        else:
            st.error("No LLM models available. Please set API keys.")
            st.session_state.selected_model = None
    
    # Main content area
    if option == "User Query":
        user_query_interface()
    elif option == "Query Optimizer":
        query_optimizer_interface()
    elif option == "Update Schema & Data Profile":
        update_schema_interface()
    elif option == "Add New Source":
        add_source_interface()
    elif option == "Query History & Logs":
        query_history_interface()

def user_query_interface():
    st.header(" Natural Language Database Query")
    
    if not st.session_state.sources:
        st.warning("No database sources configured. Please add a source first.")
        return
    
    if not st.session_state.get('selected_model'):
        st.warning("No LLM model selected. Please check your API keys and select a model.")
        return
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        source_names = list(st.session_state.sources.keys())
        selected_source = st.selectbox("Select Database Source:", source_names)
        
        if selected_source:
            source_config = st.session_state.sources[selected_source]
            st.info(f"**Type:** {source_config['type']}")
            st.info(f"**Database:** {source_config['database']}")
            st.info(f"**Model:** {st.session_state.selected_model}")
    
    with col2:
        user_query = st.text_area(
            "Enter your query in natural language:",
            placeholder="e.g., Show me all users with Pro subscription who made payments in the last 30 days",
            height=100
        )
        
        # Advanced options
        with st.expander("Advanced Options"):
            max_retries = st.slider("Max Retry Attempts:", 1, 5, 3)
            show_retry_details = st.checkbox("Show Retry Details", value=True)
        
        if st.button("Generate & Execute Query", type="primary"):
            if user_query and selected_source:
                # Load metadata
                metadata = load_metadata_from_file(selected_source)
                if not metadata:
                    st.error("No metadata found for this source. Please update schema first.")
                    return
                
                # Get connection
                source_config = st.session_state.sources[selected_source]
                connection = get_connection(source_config['type'], source_config)
                
                if not connection:
                    return
                
                model_config = LLM_MODELS[st.session_state.selected_model]
                
                with st.spinner("Generating SQL query..."):
                    # Generate initial SQL query
                    sql_query, generation_attempts = generate_sql_query_with_retry(
                        user_query, 
                        metadata['schemas'], 
                        metadata['data_profiles'], 
                        source_config['type'],
                        model_config,
                        max_retries=max_retries
                    )
                
                if sql_query:
                    st.subheader("Generated SQL Query:")
                    st.code(sql_query, language='sql')
                    
                    with st.spinner("Executing query with retry logic..."):
                        # Execute query with retry
                        columns, results, retry_attempts = execute_query_with_retry(
                            connection, sql_query, source_config['type'],
                            user_query, metadata['schemas'], metadata['data_profiles'],
                            model_config, max_retries=max_retries
                        )
                    
                    if results:
                        st.subheader("Query Results:")
                        
                        df = pd.DataFrame(results, columns=columns)
                        st.dataframe(df, use_container_width=True)
                        
                        st.success(f"✅ Found {len(results)} record(s)")
                        
                        csv = df.to_csv(index=False)
                        st.download_button(
                            label="Download results as CSV",
                            data=csv,
                            file_name=f"query_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning("No results found or query failed.")
                    
                    # Show retry details if enabled
                    if show_retry_details and (generation_attempts or retry_attempts):
                        st.subheader("Execution Details:")
                        
                        if generation_attempts:
                            st.write("**Generation Attempts:**")
                            for attempt in generation_attempts:
                                with st.expander(f"Generation Attempt {attempt['attempt']}"):
                                    st.code(attempt['sql_query'], language='sql')
                                    st.error(f"Error: {attempt['error']}")
                        
                        if retry_attempts:
                            st.write("**Execution Attempts:**")
                            for attempt in retry_attempts:
                                with st.expander(f"Execution Attempt {attempt['attempt']}"):
                                    st.code(attempt['sql_query'], language='sql')
                                    st.error(f"Error: {attempt['error']}")
                
                else:
                    st.error("Failed to generate valid SQL query after all attempts.")
                
                connection.close()


# Add this new interface function
def query_optimizer_interface():
    st.header("SQL Query Optimizer")
    
    if not st.session_state.sources:
        st.warning("No database sources configured. Please add a source first.")
        return
    
    if not st.session_state.get('selected_model'):
        st.warning("No LLM model selected. Please check your API keys and select a model.")
        return
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        source_names = list(st.session_state.sources.keys())
        selected_source = st.selectbox("Select Database Source:", source_names)
        
        if selected_source:
            source_config = st.session_state.sources[selected_source]
            st.info(f"**Type:** {source_config['type']}")
            st.info(f"**Database:** {source_config['database']}")
            st.info(f"**Model:** {st.session_state.selected_model}")
    
    with col2:
        sql_query = st.text_area(
            "Enter SQL query to optimize:",
            placeholder="SELECT * FROM users WHERE created_at > '2023-01-01' ORDER BY last_name",
            height=150
        )
        
        if st.button("Optimize Query", type="primary"):
            if sql_query and selected_source:
                # Load metadata
                metadata = load_metadata_from_file(selected_source)
                if not metadata:
                    st.error("No metadata found for this source. Please update schema first.")
                    return
                
                # Get connection
                source_config = st.session_state.sources[selected_source]
                connection = get_connection(source_config['type'], source_config)
                
                if not connection:
                    return
                
                model_config = LLM_MODELS[st.session_state.selected_model]
                client = get_llm_client(model_config)
                
                if not client:
                    return
                
                with st.spinner("Analyzing and optimizing query..."):
                    try:
                        optimized_query, explanation = optimize_query_with_llm(
                            client,
                            model_config,
                            sql_query,
                            metadata['schemas'],
                            metadata['data_profiles'],
                            source_config['type']
                        )
                        
                        if optimized_query:
                            st.subheader("Optimized Query")
                            st.code(optimized_query, language='sql')
                            
                            if explanation:
                                st.subheader("Optimization Explanation")
                                st.write(explanation)
                            
                            # Verify results match
                            with st.spinner("Verifying results match..."):
                                match, message = verify_query_results_match(
                                    connection,
                                    sql_query,
                                    optimized_query,
                                    source_config['type']
                                )
                                
                                if match:
                                    st.success("✅ Verification: Results match exactly")
                                else:
                                    st.warning(f"⚠️ Verification: {message}")
                                    st.warning("The optimized query may not be semantically equivalent to the original")
                        
                        else:
                            st.error("Failed to generate optimized query")
                    
                    except Exception as e:
                        st.error(f"Error optimizing query: {str(e)}")
                        logger.error(f"Error optimizing query: {str(e)}")
                    
                    finally:
                        connection.close()

def query_history_interface():
    st.header("Query History & Logs")
    
    if not st.session_state.query_history:
        st.info("No query history available.")
        return
    
    # Display query history
    st.subheader("Recent Queries")
    
    for i, entry in enumerate(reversed(st.session_state.query_history[-20:])):  # Show last 20
        with st.expander(f"Query {len(st.session_state.query_history) - i}: {entry['timestamp'][:19]}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**User Query:**")
                st.write(entry['user_query'])
                st.write(f"**Status:** {'✅ Success' if entry['success'] else '❌ Failed'}")
                st.write(f"**Attempt:** {entry['attempt']}")
            
            with col2:
                st.write("**Generated SQL:**")
                st.code(entry['sql_query'], language='sql')
                if entry['error']:
                    st.error(f"Error: {entry['error']}")
    
    # Clear history button
    if st.button("Clear History"):
        st.session_state.query_history = []
        st.success("Query history cleared!")
        st.rerun()
    
    # Log file download
    if os.path.exists('db_query_app.log'):
        with open('db_query_app.log', 'r') as f:
            log_content = f.read()
        
        st.subheader("Application Logs")
        st.download_button(
            label="Download Log File",
            data=log_content,
            file_name=f"db_query_app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            mime="text/plain"
        )
        
        # Show recent log entries
        log_lines = log_content.split('\n')[-50:]  # Last 50 lines
        st.text_area("Recent Log Entries", '\n'.join(log_lines), height=300)

def update_schema_interface():
    st.header("Update Schema & Data Profile")
    
    if not st.session_state.sources:
        st.warning("No database sources configured. Please add a source first.")
        return
    
    source_names = list(st.session_state.sources.keys())
    selected_source = st.selectbox("Select Database Source to Update:", source_names)
    
    if selected_source:
        source_config = st.session_state.sources[selected_source]
        
        st.info(f"**Type:** {source_config['type']}")
        st.info(f"**Database:** {source_config['database']}")
        
        sample_size = st.number_input("Sample Size for Data Profiling:", min_value=100, max_value=10000, value=2000)
        
        if st.button("Update Schema & Data Profile", type="primary"):
            if not selected_source:
                st.error("Please select a source")
                return
                
            source_config = st.session_state.sources[selected_source]
            
            st.info(f"Connecting to {source_config['type']} database: {source_config['database']}")
            logger.info(f"Starting schema update for {selected_source}")
            
            with st.spinner("Connecting to database..."):
                connection = get_connection(source_config['type'], source_config)
            
            if not connection:
                st.error("Failed to connect to database. Please check your connection settings.")
                return
            
            try:
                with st.spinner("Fetching schema information..."):
                    schema_info = get_schema_info(source_config['type'], connection, source_config['database'])
                
                if not schema_info:
                    st.error("No schema information found. Please check if the database contains tables.")
                    return
                    
                st.success(f"Found {len(schema_info)} columns across tables")
                logger.info(f"Schema info retrieved: {len(schema_info)} columns")
                
                tables = list(set([row[0] for row in schema_info]))
                st.info(f"Found {len(tables)} tables: {', '.join(tables[:5])}{' ...' if len(tables) > 5 else ''}")
                
                with st.spinner("Creating data profiles..."):
                    data_profiles = {}
                    progress_bar = st.progress(0)
                    
                    for i, table in enumerate(tables):
                        st.text(f"Processing table: {table}")
                        profile = get_data_profile(connection, source_config['type'], table, sample_size)
                        data_profiles[table] = profile
                        progress_bar.progress((i + 1) / len(tables))
                        logger.info(f"Data profile created for table {table}: {profile['record_count']} records")
                
                filename = save_metadata_to_file(selected_source, schema_info, data_profiles)
                
                if filename:
                    st.success(f"✅ Metadata saved to {filename}")
                    logger.info(f"Metadata saved successfully to {filename}")
                    
                    st.subheader("📊 Schema Summary")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Tables", len(tables))
                    with col2:
                        st.metric("Columns", len(schema_info))
                    with col3:
                        total_records = sum([profile['record_count'] for profile in data_profiles.values()])
                        st.metric("Sample Records", total_records)
                    
                    with st.expander("📋 Table Details"):
                        for table in tables:
                            st.write(f"**{table}**")
                            table_columns = [row for row in schema_info if row[0] == table]
                            profile = data_profiles.get(table, {})
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"Columns: {len(table_columns)}")
                                st.write(f"Records: ~{profile.get('record_count', 0)}")
                            
                            with col2:
                                if profile.get('sample_data'):
                                    st.write("Sample data:")
                                    st.json(profile['sample_data'][0] if profile['sample_data'] else {})
                else:
                    st.error("Failed to save metadata")
                    
            except Exception as e:
                error_msg = f"Error during schema update: {str(e)}"
                st.error(error_msg)
                st.error(f"Details: {traceback.format_exc()}")
                logger.error(f"{error_msg}\n{traceback.format_exc()}")
            finally:
                connection.close()

def add_source_interface():
    st.header("Add New Database Source")
    
    available_types = ["MySQL", "SQLite"]
    if PYODBC_AVAILABLE:
        available_types.append("SQL Server")
    if ORACLE_AVAILABLE:
        available_types.append("Oracle")
    
    db_type = st.selectbox("Database Type:", available_types)
    
    if not PYODBC_AVAILABLE and db_type == "SQL Server":
        st.warning("SQL Server support requires additional dependencies. Install with: `pip install pyodbc`")
    if not ORACLE_AVAILABLE and db_type == "Oracle":
        st.warning("Oracle support requires additional dependencies. Install with: `pip install cx_Oracle`")
    
    source_name = st.text_input("Source Name:", placeholder="e.g., Production_DB")
    
    # Database-specific configuration
    if db_type == "MySQL":
        col1, col2 = st.columns(2)
        with col1:
            host = st.text_input("Host:", value="localhost")
            user = st.text_input("Username:", value="root")
        with col2:
            port = st.number_input("Port:", value=3306)
            password = st.text_input("Password:", type="password")
        database = st.text_input("Database Name:")
        
        config = {
            'type': db_type,
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'database': database
        }
    
    elif db_type == "SQLite":
        database = st.text_input("Database File Path:", placeholder="e.g., /path/to/database.db")
        config = {
            'type': db_type,
            'database': database
        }
    
    elif db_type == "SQL Server":
        col1, col2 = st.columns(2)
        with col1:
            host = st.text_input("Server:", placeholder="localhost")
            user = st.text_input("Username:")
        with col2:
            port = st.number_input("Port:", value=1433)
            password = st.text_input("Password:", type="password")
        database = st.text_input("Database Name:")
        
        config = {
            'type': db_type,
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'database': database
        }
    
    elif db_type == "Oracle":
        col1, col2 = st.columns(2)
        with col1:
            host = st.text_input("Host:", value="localhost")
            user = st.text_input("Username:")
        with col2:
            port = st.number_input("Port:", value=1521)
            password = st.text_input("Password:", type="password")
        service_name = st.text_input("Service Name:")
        
        config = {
            'type': db_type,
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'service_name': service_name,
            'database': service_name
        }
    
    # Test connection and save
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Test Connection"):
            if not source_name:
                st.error("Please enter a source name")
            elif not all(value for key, value in config.items() if key != 'type'):
                st.error("Please fill in all required fields")
            else:
                with st.spinner("Testing connection..."):
                    st.info(f"Attempting to connect to {db_type} database: {config.get('database', 'N/A')}")
                    logger.info(f"Testing connection to {db_type} database: {config.get('database', 'N/A')}")
                    
                    connection = get_connection(db_type, config)
                    if connection:
                        try:
                            cursor = connection.cursor()
                            if db_type == 'MySQL':
                                cursor.execute("SELECT 1")
                            elif db_type == 'SQLite':
                                cursor.execute("SELECT 1")
                            elif db_type == 'SQL Server':
                                cursor.execute("SELECT 1")
                            elif db_type == 'Oracle':
                                cursor.execute("SELECT 1 FROM DUAL")
                            
                            cursor.fetchone()
                            cursor.close()
                            connection.close()
                            st.success("✅ Connection successful!")
                            logger.info(f"Connection test successful for {source_name}")
                        except Exception as e:
                            connection.close()
                            error_msg = f"Connection test failed: {str(e)}"
                            st.error(error_msg)
                            logger.error(f"Connection test failed for {source_name}: {str(e)}")
                    else:
                        st.error("❌ Connection failed!")
    
    with col2:
        if st.button("Save Source", type="primary"):
            if not source_name:
                st.error("Please enter a source name")
            elif not all(value for key, value in config.items() if key != 'type'):
                st.error("Please fill in all required fields")
            else:
                if source_name in st.session_state.sources:
                    st.warning("Source name already exists!")
                else:
                    st.session_state.sources[source_name] = config
                    st.success(f"✅ Source '{source_name}' saved successfully!")
                    st.info("💡 Don't forget to update the schema and data profile for this source.")
                    logger.info(f"Database source '{source_name}' saved successfully")
    
    # Show existing sources
    if st.session_state.sources:
        st.subheader("Existing Sources")
        for name, config in st.session_state.sources.items():
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.write(f"**{name}**")
            with col2:
                st.write(f"{config['type']} - {config['database']}")
            with col3:
                if st.button("Delete", key=f"del_{name}"):
                    del st.session_state.sources[name]
                    logger.info(f"Database source '{name}' deleted")
                    st.rerun()

if __name__ == "__main__":
    main()