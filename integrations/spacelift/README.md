# 🌊 Spacelift Integration for Port Ocean

This integration pulls **Spacelift CI/CD and infrastructure data** into your [Port](https://getport.io) Internal Developer Portal using the [Ocean SDK](https://ocean.getport.io). It ingests entities like:

- 🧱 Stacks
- 🛰️ Deployments (Runs)
- 📦 Spaces
- 🔐 Policies
- 👤 Users

Includes support for:
- ✅ Full and filtered sync
- ✅ Real-time ingestion via Spacelift Webhooks
- ✅ Token expiry handling
- ✅ Rate limit retry logic

---

## 🛠️ Setup Instructions

### 1. Clone and Install

```bash
git clone https://github.com/your-org/spacelift-ocean-integration.git
cd spacelift-ocean-integration
pip install -r requirements.txt
```

### 2. Environment Variables
Create a .env file or set env vars in your environment:

```bash
SPACELIFT_TOKEN=<your-api-token>
RUN_STATUS_FILTER=FINISHED        # Optional: QUEUED, FINISHED, etc.
RUN_DAYS_BACK=7                   # Optional: How many days of runs to sync
```

### ▶️ Running the Integration
Full Catalog Sync (Async)
```bash
python run_integration.py --full-sync
```
