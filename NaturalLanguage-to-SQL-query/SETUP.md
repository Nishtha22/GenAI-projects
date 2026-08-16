# Complete Setup Guide

## 🚀 Quick Setup (5 Minutes)

### Step 1: Clone and Install
```bash
git clone https://github.com/yourusername/nl-to-sql-query.git
cd nl-to-sql-query
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2: Start MySQL with Docker
```bash
docker-compose up -d
```

This will start MySQL on `localhost:3306` with:
- **Root Password**: `rootpassword`
- **Database**: `nlp_database`
- **App User**: `app_user`
- **App Password**: `apppassword`

### Step 3: Configure Environment Variables
```bash
cp .env.example .env
# Edit .env and add your API keys
```

### Step 4: Run the Application
```bash
streamlit run app.py
```

Visit `http://localhost:8501` in your browser!

---

## 🔧 Detailed Setup

### MySQL Docker Container

#### Option 1: Using Docker Compose (Recommended)

1. **Start MySQL**:
   ```bash
   docker-compose up -d
   ```

2. **Check if it's running**:
   ```bash
   docker-compose ps
   ```

3. **View logs**:
   ```bash
   docker-compose logs -f mysql
   ```

4. **Stop MySQL**:
   ```bash
   docker-compose down
   ```

5. **Stop and remove data**:
   ```bash
   docker-compose down -v
   ```

#### Option 2: Using Docker CLI

```bash
docker run --name mysql-nlp \
  -e MYSQL_ROOT_PASSWORD=rootpassword \
  -e MYSQL_DATABASE=nlp_database \
  -e MYSQL_USER=app_user \
  -e MYSQL_PASSWORD=apppassword \
  -p 3306:3306 \
  -d mysql:latest
```

### Customizing MySQL Configuration

Create a `docker-compose.override.yml` file (this is gitignored):

```yaml
version: '3.8'

services:
  mysql:
    environment:
      MYSQL_ROOT_PASSWORD: my_secure_password
      MYSQL_DATABASE: my_database
    ports:
      - "3307:3306"  # Change host port if 3306 is in use
```

Then run:
```bash
docker-compose up -d
```

### Loading Sample Data

1. **Create a SQL dump file** (`sample_data.sql`):
   ```sql
   CREATE TABLE users (
     id INT PRIMARY KEY AUTO_INCREMENT,
     name VARCHAR(100),
     email VARCHAR(100),
     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );

   INSERT INTO users (name, email) VALUES
     ('John Doe', 'john@example.com'),
     ('Jane Smith', 'jane@example.com');
   ```

2. **Import into Docker MySQL**:
   ```bash
   docker exec -i mysql-nlp mysql -uroot -prootpassword nlp_database < sample_data.sql
   ```

   Or with docker-compose:
   ```bash
   docker-compose exec -T mysql mysql -uroot -prootpassword nlp_database < sample_data.sql
   ```

### Accessing MySQL Shell

```bash
# Using docker
docker exec -it mysql-nlp mysql -uroot -prootpassword

# Using docker-compose
docker-compose exec mysql mysql -uroot -prootpassword

# Then you can run SQL commands:
USE nlp_database;
SHOW TABLES;
SELECT * FROM users;
```

---

## 🔑 API Keys Setup

### OpenAI
1. Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Create a new key
3. Add to `.env`: `OPENAI_API_KEY=sk-...`

### Google Gemini
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create API key
3. Add to `.env`: `GOOGLE_API_KEY=...`

### Anthropic Claude
1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Create API key
3. Add to `.env`: `ANTHROPIC_API_KEY=sk-ant-...`

---

## 📊 First-Time Usage

### 1. Add Database Source
1. Open the app at `http://localhost:8501`
2. Go to **"Add New Source"** in sidebar
3. Enter MySQL details:
   - **Source Name**: `Local MySQL`
   - **Database Type**: `MySQL`
   - **Host**: `localhost`
   - **Port**: `3306`
   - **Username**: `root` (or `app_user`)
   - **Password**: `rootpassword` (or `apppassword`)
   - **Database Name**: `nlp_database`
4. Click **"Test Connection"**
5. Click **"Save Source"**

### 2. Update Schema
1. Go to **"Update Schema & Data Profile"**
2. Select your database source
3. Click **"Update Schema & Data Profile"**
4. Wait for completion

### 3. Run Your First Query
1. Go to **"User Query"**
2. Select your database
3. Try: `"Show me all users"`
4. Click **"Generate & Execute Query"**

---

## 🐛 Troubleshooting

### Port 3306 Already in Use
```bash
# Change port in docker-compose.yml
ports:
  - "3307:3306"

# Then update app connection to use port 3307
```

### Can't Connect to MySQL
```bash
# Check if container is running
docker ps

# Check MySQL logs
docker logs mysql-nlp

# Restart container
docker restart mysql-nlp
```

### Permission Denied
```bash
# On Linux/Mac, you might need sudo
sudo docker-compose up -d
```

### Python Package Issues
```bash
# Upgrade pip
pip install --upgrade pip

# Install packages individually
pip install streamlit
pip install mysql-connector-python
# ... etc
```



