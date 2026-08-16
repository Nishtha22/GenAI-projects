# 🗄️ Natural Language to SQL Query Interface

A powerful Streamlit application that converts natural language queries into SQL statements using Large Language Models (LLMs). Query your databases using plain English without writing SQL!

## ✨ Features

- **Natural Language Processing**: Convert English queries to SQL using state-of-the-art LLMs
- **Multi-Database Support**: Works with MySQL, SQLite, SQL Server, and Oracle
- **Multiple LLM Providers**: Supports OpenAI (GPT-4, GPT-4o, GPT-3.5), Google Gemini, and Anthropic Claude
- **Smart Retry Logic**: Automatically fixes and retries failed queries up to 3 times
- **Schema Profiling**: Automatically extracts and profiles your database schema
- **Query Optimization**: Built-in SQL query optimizer for performance improvements
- **Query History**: Track and review all executed queries
- **Data Export**: Download query results as CSV files
- **Verification System**: Ensures optimized queries return the same results as originals

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- pip package manager
- Docker (for running MySQL database)
- Access to at least one supported database
- API key for at least one LLM provider (OpenAI, Google, or Anthropic)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/NL-to-SQL-query.git
   cd NL-to-SQL-query
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   
   Create a `.env` file in the project root:
   ```env
   # OpenAI (required for OpenAI models)
   OPENAI_API_KEY=your_openai_api_key_here
   
   # Google (required for Gemini models)
   GOOGLE_API_KEY=your_google_api_key_here
   
   # Anthropic (required for Claude models)
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ```

5. **Run the application**
   ```bash
   streamlit run app.py
   ```

## 📦 Dependencies

Create a `requirements.txt` file with the following:

```
streamlit>=1.28.0
mysql-connector-python>=8.0.33
pandas>=2.0.0
openai>=1.0.0
python-dotenv>=1.0.0

# Optional: For additional database support
pyodbc>=4.0.39  # For SQL Server
cx_Oracle>=8.3.0  # For Oracle

# Optional: For additional LLM providers
anthropic>=0.3.0  # For Claude
google-generativeai>=0.3.0  # For Gemini
```

## 🎯 Usage

### 1. Add a Database Source

1. Navigate to **"Add New Source"** in the sidebar
2. Select your database type (MySQL, SQLite, SQL Server, or Oracle)
3. Enter connection details
4. Test the connection
5. Save the source

### 2. Update Schema & Data Profile

1. Go to **"Update Schema & Data Profile"**
2. Select your database source
3. Set sample size for data profiling (default: 2000 records)
4. Click **"Update Schema & Data Profile"**
5. Wait for the process to complete

This step extracts:
- Table structures and relationships
- Column names, data types, and constraints
- Sample data for better query generation

### 3. Query Your Database

1. Select **"User Query"** from the sidebar
2. Choose your database source
3. Select your preferred LLM model
4. Enter your query in plain English, for example:
   - "Show me all users who registered in the last 30 days"
   - "What are the top 10 products by sales?"
   - "Find customers with orders over $1000"
5. Click **"Generate & Execute Query"**
6. View results and download as CSV if needed

### 4. Optimize Queries

1. Navigate to **"Query Optimizer"**
2. Paste your SQL query
3. Click **"Optimize Query"**
4. Review the optimized version and explanation
5. Verify results match the original query

## 🔧 Configuration

### Supported Databases

| Database | Status | Additional Requirements |
|----------|--------|------------------------|
| MySQL | ✅ Built-in | None |
| SQLite | ✅ Built-in | None |
| SQL Server | ⚙️ Optional | `pip install pyodbc` |
| Oracle | ⚙️ Optional | `pip install cx_Oracle` |

### Supported LLM Models

| Provider | Models | API Key Required |
|----------|--------|-----------------|
| OpenAI | GPT-4o, GPT-4, GPT-3.5 Turbo | OPENAI_API_KEY |
| Google | Gemini 1.5 Flash, 1.5 Pro, 2.0 Flash | GOOGLE_API_KEY |
| Anthropic | Claude 3 Sonnet, Claude 3 Opus | ANTHROPIC_API_KEY |

## 📝 Example Queries

```
Natural Language → SQL

"Show all active users" 
→ SELECT * FROM users WHERE status = 'active';

"Top 5 products by revenue"
→ SELECT product_name, SUM(price * quantity) as revenue 
  FROM products 
  GROUP BY product_name 
  ORDER BY revenue DESC 
  LIMIT 5;

"Users who made purchases in the last week"
→ SELECT DISTINCT u.* 
  FROM users u 
  JOIN orders o ON u.id = o.user_id 
  WHERE o.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY);
```

## 🛠️ How It Works

1. **Schema Extraction**: The app connects to your database and extracts complete schema information including table structures, column types, and sample data.

2. **Prompt Engineering**: User queries are combined with schema information and sent to the selected LLM with carefully crafted prompts.

3. **SQL Generation**: The LLM generates SQL queries based on the natural language input and database schema.

4. **Execution & Retry**: Queries are executed against the database. If they fail, the system automatically attempts to fix errors and retry up to 3 times.

5. **Result Display**: Successful queries return data displayed in an interactive table with CSV export options.


## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request


## 🐛 Known Issues

- Very large databases may take time to profile

## 💡 Tips for Best Results

1. **Update schema regularly** when database structure changes
2. **Use specific queries** rather than vague requests
3. **Start with simple queries** to test the setup
4. **Review generated SQL** before running on production data
5. **Choose appropriate LLM models** - GPT-4 for complex queries, GPT-3.5 for simple ones




