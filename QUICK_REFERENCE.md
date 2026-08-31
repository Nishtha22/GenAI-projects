# Quick Reference: Multi-Source RAG Commands

## ⚡ Quick Start

### List available sources
```bash
python scripts/ingest_multi_source.py --list
```

### Ingest just Spark (single source)
```bash
python scripts/ingest_multi_source.py --source spark
```

### Ingest ALL sources
```bash
python scripts/ingest_multi_source.py --all
```

### Ingest without crawling (use existing data)
```bash
python scripts/ingest_multi_source.py --all --skip-crawl
```

### Restart API server
```bash
bash run_server.sh
```

---

## 📝 Adding New Sources

1. **Edit `configs/configs.yaml`**:
   ```yaml
   sources:
     mynewsource:
       base_url: "https://docs.mynewsource.com/"
       max_pages: 100
       rate_limit: 5
   ```

2. **Ingest the source**:
   ```bash
   python scripts/ingest_multi_source.py --source mynewsource
   ```

3. **Test a query**:
   ```bash
   curl -X POST http://127.0.0.1:8000/query \
     -H "Content-Type: application/json" \
     -d '{"question": "Your question about the new topic?"}'
   ```

---

## 📊 System Status

**Current Sources**: spark, hadoop, kubernetes, docker, python
**Index Location**: `data/faiss/`
**API Running**: `http://127.0.0.1:8000`

---

## 🔧 Common Workflows

### Workflow 1: Add a New Topic
```bash
# 1. Add to config
nano configs/configs.yaml

# 2. Ingest without disturbing existing index
python scripts/ingest_multi_source.py --source newtopic

# 3. Restart API
bash run_server.sh

# 4. Test
curl -X POST http://127.0.0.1:8000/query ...
```

### Workflow 2: Rebuild Everything Fresh
```bash
# Remove old index
rm -rf data/faiss/

# Ingest all sources
python scripts/ingest_multi_source.py --all

# Restart
bash run_server.sh
```

### Workflow 3: Update One Source
```bash
# Remove and rebuild just that source's data
rm -rf data/raw/spark

# Re-ingest (will crawl fresh)
python scripts/ingest_multi_source.py --source spark --skip-crawl

# Rebuild entire index
rm -rf data/faiss/
python scripts/ingest_multi_source.py --all --skip-crawl
```

---

## 📈 Monitoring

### Check vector store size
```bash
ls -lh data/faiss/
```

### Check number of documents
```bash
python -c "import pickle; print(len(pickle.load(open('data/faiss/documents.pkl', 'rb'))))"
```

### View server logs
```bash
tail -f server.log
```

---

**Question: "What can I ask now?"**
- Apache Spark: "What is Spark SQL?"
- Kubernetes: "How do I deploy on K8s?"
- Docker: "What's a Docker image?"
- Python: "What is a decorator?"
- Hadoop: "What is HDFS?"
- **And more as you add sources!** 🚀
