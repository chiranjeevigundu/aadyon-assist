# Architecture

Two views of Aadyon Assist. GitHub renders the diagrams below inline; the same
content lives as standalone, editable sources you can open in mermaid.live, the VS Code
Mermaid extensions, or draw.io:

- High-level system map → [`architecture.mermaid`](../architecture.mermaid)
- Services / container detail → [`services-architecture.mermaid`](../services-architecture.mermaid)

> **Keep in sync:** the fenced blocks here mirror those two source files. When you edit a
> diagram, update both the `.mermaid` file and the matching block below.

---

## 1 · System map

Who talks to the API, the workers behind it, the portable storage seam, and the external
boundary. Teal marks the config-only storage switch (the thick teal fork is AWS ⇄ emulator);
dashed edges are secrets and push.

```mermaid
flowchart TB
  subgraph CLIENTS[" CLIENTS "]
    direction LR
    you["You — browser<br/>Net Worth · Tracker · Assistant"]
    phone["iPhone<br/>ntfy app"]
    dev["Dev machine<br/>localhost:8000"]
  end

  subgraph HOST[" ALWAYS-ON HOST · DOCKER COMPOSE "]
    api["api — FastAPI<br/>REST + dashboards · JWT"]
    db[("db — Postgres 16 + pgvector<br/>RLS per-user isolation")]
    briefing["briefing<br/>daily digest → md"]
    migrate["migrate<br/>yoyo DDL · one-shot"]
    backup["backup<br/>nightly pg_dump"]
    ntfy["ntfy<br/>self-hosted push"]
    secrets[/"secrets · Docker secrets<br/>db · jwt · openrouter · email · s3"/]
  end

  subgraph STORE[" OBJECT STORAGE — PORTABLE, CONFIG-ONLY "]
    direction LR
    storage["services/storage.py<br/>STORAGE_BACKEND=s3"]
    emu["Floci / LocalStack / MinIO<br/>emulator · :4566 · path-style"]
    aws["AWS S3 — real cloud<br/>virtual-host · IAM role"]
  end

  subgraph EXT[" EXTERNAL SERVICES "]
    direction LR
    openrouter["OpenRouter<br/>cloud LLM"]
    ollama["Ollama<br/>local tier · host:11434"]
    email["Email sources<br/>IMAP · Gmail · MS Graph"]
    resend["Resend<br/>outbound email"]
    github["GitHub Actions<br/>ruff · gitleaks · smoke · fuzz"]
  end

  you -->|"HTTPS · Tailscale"| api
  ntfy -.->|"push · stays on tailnet"| phone
  dev -->|"git push · PR"| github
  github -->|"pull --ff-only · just up"| HOST

  api -->|"scoped query"| db
  briefing --> db
  migrate -->|"apply migrations"| db
  backup -->|"pg_dump"| db
  briefing -->|"bills + net-worth digest"| ntfy

  api -->|"upload / download<br/>statements + receipts"| storage
  storage ==>|"S3_ENDPOINT_URL set"| emu
  storage ==>|"unset → real AWS"| aws

  api -->|"assistant · statement extract"| openrouter
  api --> ollama
  email -->|"read-only · LLM extract → review"| api
  api -->|"verify / reset mail"| resend

  secrets -.-> api
  secrets -.-> briefing
  secrets -.-> db

  classDef store fill:#e6f6f4,stroke:#0e8f9b,color:#0a5b62,stroke-width:1.5px;
  classDef dbc fill:#eef2f7,stroke:#7c8896,color:#1a2430;
  classDef sec fill:#f6f1e6,stroke:#c7ad72,color:#6a5626;
  class storage,emu,aws store;
  class db dbc;
  class secrets sec;
  linkStyle 10,11 stroke:#0e8f9b,stroke-width:2.5px;
```

---

## 2 · Services & deployment (C4 container view)

Every deployable container, the state it owns, and the systems it depends on. **Honest framing:**
this is a *modular monolith with sidecar workers*, not independent microservices — `api`,
`briefing`, and `migrate` are the **same image** (`code/api/Dockerfile`) run with different
entrypoints; `ntfy` and `backup` are stock upstream images. Teal marks first-party services.

```mermaid
flowchart LR
  subgraph CLIENTS[" CLIENTS "]
    direction TB
    web["Browser dashboards (PWA)<br/>Net Worth · Tracker · Assistant · Data"]
    phone["iPhone<br/>ntfy app"]
  end

  subgraph SVC[" APPLICATION SERVICES · Docker Compose "]
    direction TB
    api["api · FastAPI :8000<br/>REST + dashboards · JWT + RLS<br/>domains: auth · networth · bank · assistant<br/>email · documents · system · crud"]
    briefing["briefing<br/>daily digest → md + push"]
    migrate["migrate<br/>yoyo DDL · init job"]
    backup["backup<br/>nightly pg_dump · cron"]
    ntfy["ntfy :8090<br/>self-hosted push relay"]
  end

  subgraph DATA[" DATA & STATE "]
    direction TB
    pg[("Postgres 16 + pgvector :5432<br/>RLS isolation · pgdata volume")]
    s3[("Object storage · S3 API<br/>Floci/LocalStack :4566 — or — AWS S3")]
    secrets[/"Docker secrets<br/>db · jwt · s3 · resend"/]
    files[/"File volumes<br/>artifacts/ · data/exports/"/]
  end

  subgraph EXT[" EXTERNAL SYSTEMS "]
    direction TB
    llm["OpenRouter<br/>cloud LLM"]
    ollama["Ollama<br/>local tier :11434"]
    gmail["Gmail API · IMAP<br/>read-only"]
    msgraph["Microsoft Graph<br/>Outlook/365 · read-only"]
    resend["Resend<br/>outbound email"]
    ntfyup["ntfy.sh<br/>iOS push upstream"]
    gh["GitHub Actions<br/>CI/CD"]
  end

  web -->|"HTTPS/JSON · Tailscale"| api
  api -->|"SQL · RLS-scoped"| pg
  briefing --> pg
  migrate -->|"DDL · migrations"| pg
  backup -->|"pg_dump"| pg
  backup --> files
  api -->|"upload / download"| s3
  briefing -->|"briefing-*.md"| files
  api --> files

  api -->|"assistant · statement extract"| llm
  api --> ollama
  api -->|"fetch · LLM extract → review"| gmail
  api --> msgraph
  api -->|"verify / reset mail"| resend
  briefing --> ntfy
  ntfy --> ntfyup
  ntfyup -.->|"background push"| phone

  gh -->|"pull --ff-only · just up"| SVC
  secrets -.-> api
  secrets -.-> briefing

  classDef own fill:#e6f6f4,stroke:#0e8f9b,color:#0a5b62,stroke-width:1.4px;
  classDef store fill:#eef2f7,stroke:#7c8896,color:#1a2430;
  classDef ext fill:#f7f4ee,stroke:#c2b183,color:#5f5326;
  classDef sec fill:#f6f1e6,stroke:#c7ad72,color:#6a5626;
  class api,briefing,migrate own;
  class pg,s3,files store;
  class secrets sec;
  class llm,ollama,gmail,msgraph,resend,ntfyup,gh ext;
```

---

See also [`SYSTEM.md`](../SYSTEM.md) for the prose architecture, [`docs/CLOUD.md`](CLOUD.md) for the
managed-cloud migration path, and [`docs/cloud-storage.md`](cloud-storage.md) for the portable
object-storage details.
