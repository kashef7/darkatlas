# DarkAtlas

DarkAtlas is an enterprise-grade Attack Surface Management (ASM) and asset management platform designed to map, track, and analyze organizational external assets and their complex relationship networks. Built on a high-performance modern Python stack utilizing **FastAPI**, **SQLAlchemy ORM**, **Alembic**, and **PostgreSQL**, it provides a resilient and secure solution for threat exposure analysis.

---

## 1. System Overview

DarkAtlas serves as a central registry for tracking assets (such as domains, subdomains, IP addresses, services, certificates, and software technologies) and the directional graph relationships between them. 

### Key Capabilities:
* **Asset Lifecycle Management:** Track first-seen/last-seen timestamps and manage state transitions (`active` -> `stale` -> `archived`) automatically upon asset re-sighting.
* **Fault-Tolerant Bulk Ingestion:** Scalable API to ingest thousands of scanned assets concurrently with item-level isolation.
* **Directional Graph Topology:** Link assets via structured relationships to build an interactive, traceable dependency graph of the attack surface.

---

## 2. Explicit Layered Topography

DarkAtlas strictly enforces an **Explicit Layered Topography** to maximize codebase readability, maintainability, and clean separation of concerns. To avoid confusion and namespace pollution, files follow strict prefixing/suffixing conventions:

```
app/
├── core/
│   └── security.py           # Shared encryption and token generation utilities
├── models/
│   ├── asset_model.py        # SQLAlchemy database model definition
│   ├── relationship_model.py # SQLAlchemy model for the relationship graph edges
│   └── user.py               # User model defining credentials and permissions
├── routers/
│   ├── assets_router.py      # HTTP endpoints exposing asset CRUD and bulk import
│   ├── auth_router.py        # Registration, login, and token generation endpoints
│   └── relationships_router.py # Graph querying and link establishment endpoints
├── schemas/
│   ├── asset_schema.py       # Pydantic validation schemas and aliasing logic
│   ├── auth_schema.py        # Pydantic schemas for authentication payloads
│   └── relationship_schema.py # Pydantic schemas for relationship and graph responses
├── services/
│   ├── asset_service.py      # Business logic: ingestion, deduplication, updates
│   └── relationship_service.py # Business logic: graph traversal, constraint checks
├── config.py                 # Pydantic Settings system configurations
└── database.py               # Database engine initialization and session management
```

### Why We Use Explicit Naming:
* **No Ambiguity:** A developer looking at an import instantly knows whether they are pulling an ORM model (`asset_model.py`), an API input/output DTO (`asset_schema.py`), or a business logic service (`asset_service.py`).
* **Framework Collision Avoidance:** `asset_schema.py` isolates Pydantic aliasing rules (`metadata` -> `asset_metadata`) away from SQLAlchemy's base metadata registry (`Base.metadata`), preventing compiler conflicts.

---

## 3. Core Engineering Deep Dives

### Stateless Cryptographic RBAC
Instead of querying the database on every HTTP request to check user permissions, DarkAtlas uses **Stateless Cryptographic Role-Based Access Control (RBAC)**.
1. When a user authenticates at `/auth/login`, a JSON Web Token (JWT) is issued.
2. The JWT payload encodes the user's role (`admin`, `editor`, or `viewer`) along with standard subject claims.
3. Protected endpoints verify the JWT signature using the server's `SECRET_KEY` and validate the claim state directly.
4. Access checks are completed in \(O(1)\) memory without database overhead, minimizing latency.

### Fault-Tolerant Bulk Ingestion
Ingestion of massive, automated scan logs is highly prone to network glitches or single-line validation failures. The `/assets/bulk-import` service employs **Nested Transactions (Savepoints)** via SQLAlchemy's `db.begin_nested()` context managers.

```
       [ Bulk Import Request ]
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
    [Item 1]            [Item 2]     ...
        │                   │
  begin_nested()      begin_nested()
   Savepoint 1         Savepoint 2
        │                   │
   ┌────┴────┐          ┌───┴───┐
   ▼         ▼          ▼       ▼
[Pass]     [Fail]    [Pass]   [Fail]
  │          │          │       │
SP.commit()  │      SP.commit() │
             ▼                  ▼
        SP.rollback()      SP.rollback()
        (Log Failure)      (Log Failure)
                  │
                  ▼
         [ Main DB Commit ]
```

Each asset payload in the batch is processed in isolation:
* If validation or insertion succeeds, its savepoint is committed to the parent transaction.
* If an item is malformed or violates unique constraints, only its savepoint is rolled back. The other valid items in the batch are preserved and committed.
* The API returns a `201 Created` status with a detailed error array specifying which indices failed and why.

### Directional Graph Constraints
To prevent nonsense relationship configurations (such as pointing a domain to a subdomain or linking an IP address to a physical technology), DarkAtlas restricts edges to a predefined directional rules matrix:

| Source Asset Type | Direction | Target Asset Type | Relationship Context |
|:---|:---:|:---|:---|
| `subdomain` | ──► | `domain` | Canonical domain hierarchy |
| `service` | ──► | `ip_address` | Service hosted on target host |
| `ip_address` | ──► | `subdomain` | Reverse DNS / IP resolution |
| `subdomain` | ──► | `ip_address` | Forward DNS / host resolution |
| `certificate` | ──► | `domain` | SSL/TLS certificate scope |
| `certificate` | ──► | `subdomain` | SSL/TLS subdomain coverage |
| `technology` | ──► | `subdomain` | Software identified on host |
| `technology` | ──► | `service` | Specific port software version |

Attempts to establish relationships outside of this matrix are instantly rejected with a `400 Bad Request`.

---

## 4. Polyglot Test Strategy

A major challenge when developing for PostgreSQL is testing: spin-up times for local test containers or remote testing databases slow down local development cycles and increase CI complexity.

DarkAtlas resolves this using custom **SQLAlchemy Compilation Hooks** and **DBAPI Adapters** inside [tests/conftest.py](file:///c:/Users/youss/Desktop/college/Projects/darkatlas/tests/conftest.py). This allows tests to run instantly on an in-memory **SQLite** database, while production runs on **PostgreSQL**.

### How it Works:
1. **DDL Type Rewriting:** SQLite does not natively support PostgreSQL's `ARRAY` and `JSONB` columns. The `@compiles` decorators dynamically map these column types to SQLite's standard `JSON` text representation during DDL compilation.
2. **DBAPI Level Serialization:** Adapters serialize Python `list` and `dict` types to JSON strings automatically on writes:
   ```python
   sqlite3.register_adapter(list, lambda v: json.dumps(v))
   sqlite3.register_adapter(dict, lambda v: json.dumps(v))
   ```
3. **Execution:** The full 62-test automation suite compiles and executes in under 15 seconds without requiring an active PostgreSQL service.

---

## 5. Quick-Start Deployment Instructions

### Prerequisites
* Python 3.12+
* Docker & Docker Compose (optional, for containerized deployment)
* PostgreSQL 16 (optional, for non-containerized production run)

### Local Environment Setup
1. Copy the example environment template to create your local `.env`:
   ```bash
   cp example.env .env
   ```
2. Open `.env` and fill in your actual credentials (ensure `.env` remains ignored by git):
   ```env
   DB_URL=postgresql://postgres:your_secure_password@localhost:5432/darkatlas
   SECRET_KEY=generate_a_secure_random_string_here
   ```

### Running Locally (Without Docker)
1. Initialize virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Apply migrations:
   ```bash
   alembic upgrade head
   ```
3. Seed default administrative and viewer users:
   ```bash
   python seed.py
   ```
4. Start the application:
   ```bash
   uvicorn app.main:app --reload
   ```

### Running with Docker Compose (Persistent Stack)
Ensure your `.env` contains the required database settings:
```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=darkatlas
```
Launch the multi-container stack:
```bash
docker-compose up --build
```
This automatically boots up the PostgreSQL 16 service, runs Alembic migrations, and binds the Uvicorn web server to your configured port.
