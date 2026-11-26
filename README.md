
# ResolveAI — AI-Powered Support Ticket Resolution Copilot

ResolveAI is a full-stack AI-powered support operations platform designed to help support teams manage customer tickets, retrieve relevant knowledge-base information, and generate evidence-grounded resolutions using Large Language Models (LLMs).

It combines Retrieval-Augmented Generation (RAG), semantic search, role-based access control, and Human-in-the-Loop workflows to assist support agents while maintaining human oversight over AI-generated responses.

The platform supports ticket management, knowledge-base ingestion, AI-assisted classification and resolution, response validation, escalations, analytics, and role-based access to sensitive information.

## Live Demo

**Application:** https://resolve-ai-dun.vercel.app/login

**Backend API:** https://resolveai-skii.onrender.com

**API Documentation:** https://resolveai-skii.onrender.com/docs

**Health Check:** https://resolveai-skii.onrender.com/health

### Demo Walkthrough

The application supports three roles:

| Role | Access |
|---|---|
| Admin | User management, knowledge-base management, system status, tickets, AI review, and analytics |
| Agent | Ticket management, AI analysis, response review, approval, rejection, editing, notes, and escalations |
| Viewer | Read-only access with restricted customer information and internal notes |

Demo access should be provided through dedicated evaluation accounts with restricted permissions. Do not publish production credentials or unrestricted administrative passwords in this repository.

### Suggested Walkthrough

1. Sign in as an Agent and open an existing support ticket.
2. Run AI analysis to classify the ticket and generate a proposed resolution.
3. Review the retrieved evidence, citations, confidence heuristic, and escalation status.
4. Edit, approve, or reject the generated response.
5. Sign in as a Viewer to verify restricted access to customer information and internal notes.
6. Sign in as an Admin to explore knowledge-base management, user management, analytics, and system health.

Please use evaluation accounts only and avoid uploading sensitive or personally identifiable information.

---

## Key Features

### 1. Support Ticket Management

- Create, list, search, filter, and manage support tickets.
- Track ticket status, priority, and category.
- View individual ticket details and ticket history.
- Maintain internal notes for support-team collaboration.
- Support structured ticket workflows and escalations.

### 2. AI-Powered Ticket Analysis and Resolution

- Integrates Groq LLM inference for AI-assisted ticket analysis.
- Generates proposed ticket resolutions using retrieved knowledge.
- Supports ticket classification and resolution generation.
- Uses retrieved knowledge-base content as contextual evidence.
- Validates generated citations against retrieved document chunks.
- Applies confidence-based escalation for unsupported or uncertain responses.
- Keeps AI-generated responses separate from human-approved resolutions.

### 3. Knowledge Base and Retrieval-Augmented Generation

- Upload PDF, TXT, and Markdown documents.
- Extract text and divide documents into smaller chunks.
- Generate embeddings for semantic retrieval.
- Store and retrieve vector representations using Qdrant.
- Detect duplicate documents.
- Search indexed knowledge-base content.
- Includes six sample customer-support knowledge guides.

The RAG pipeline retrieves relevant knowledge-base content before passing contextual evidence to the LLM.

### 4. Human-in-the-Loop Workflow

- Review AI-generated ticket resolutions.
- Edit proposed responses before approval.
- Approve or reject AI-generated responses.
- Escalate low-confidence or unsupported resolutions.
- Maintain action history and authenticated agent attribution.

Human approval is a separate step from AI response generation.

### 5. Authentication and Authorization

- JWT-based authentication.
- Argon2 password hashing.
- Role-Based Access Control (RBAC).
- Admin, Agent, and Viewer roles.
- Protected API endpoints.
- Admin-only user-management operations.
- Database-backed JWT revocation using token identifiers.
- Role-based restrictions for customer information and internal notes.

### 6. Analytics Dashboard

- Ticket overview and operational metrics.
- Ticket trends.
- Category and priority distribution.
- SLA analytics.
- Approval and rejection analytics.
- Support activity metrics.

---

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React, Vite, JavaScript, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic |
| ORM | SQLAlchemy |
| Production Database | PostgreSQL |
| Local Development and Tests | SQLite |
| Vector Database | Qdrant |
| Embeddings | FastEmbed (ONNX Runtime) |
| LLM Inference | Groq |
| Authentication | JWT, Argon2 |
| Backend Testing | Pytest, HTTPX |
| Frontend Deployment | Vercel |
| Backend Deployment | Render |

**Embeddings:** The backend uses **FastEmbed** (`fastembed`) running the `sentence-transformers/all-MiniLM-L6-v2` model through ONNX Runtime. Document ingestion and query embedding share the same model instance, producing 384-dimensional dense vectors for semantic retrieval in Qdrant.

---

## System Architecture

```mermaid
flowchart TD
    UI[React Frontend] --> API[FastAPI Backend]

    API --> AUTH[JWT Authentication and RBAC]
    AUTH --> DB[(PostgreSQL)]

    API --> TICKET[Ticket Management]
    API --> KB[Knowledge Base Service]

    KB --> EXTRACT[Document Text Extraction]
    EXTRACT --> CHUNK[Text Chunking]
    CHUNK --> EMB[Embedding Generation (FastEmbed)]
    EMB --> Q[(Qdrant Vector Database)]

    TICKET --> RAG[RAG Pipeline]
    Q --> RAG

    RAG --> LLM[Groq LLM]
    LLM --> VALIDATE[Evidence and Citation Validation]

    VALIDATE --> DECISION{Confidence and Evidence Check}

    DECISION -->|Supported| REVIEW[Human Review]
    DECISION -->|Low Confidence| ESCALATE[Escalation]

    REVIEW --> APPROVE[Approve / Edit / Reject]
    ESCALATE --> REVIEW

    APPROVE --> DB
```

### Request and Resolution Flow

1. A support agent opens a ticket.
2. The backend retrieves the ticket information.
3. The RAG pipeline converts the query into an embedding using FastEmbed.
4. Qdrant performs semantic retrieval over indexed knowledge chunks.
5. Relevant evidence is passed to the Groq LLM.
6. The generated response is checked against retrieved evidence.
7. Confidence and escalation rules determine whether additional human attention is required.
8. The agent reviews, edits, approves, or rejects the proposed response.
9. The resulting workflow action is recorded.

---

## AI Safety and Grounding

ResolveAI incorporates safeguards designed to improve the reliability of AI-assisted support workflows.

- Uploaded documents are treated as untrusted reference material.
- Retrieved content is used as contextual evidence rather than trusted system instructions.
- Generated citations are checked against retrieved knowledge chunks.
- Unsupported or low-confidence responses can be escalated for human review.
- Confidence is a heuristic and not a calibrated probability.
- Citation validation does not independently guarantee factual correctness.
- AI-generated responses do not automatically become human-approved resolutions.
- Human review remains part of the resolution workflow.

These controls reduce the risk of unsupported AI responses but do not eliminate hallucinations or all prompt-injection risks.

---

## Authentication and Security

The application uses multiple security mechanisms:

| Security Area | Implementation |
|---|---|
| Authentication | JWT |
| Password Storage | Argon2 hashing |
| Token Revocation | Database-backed token revocation |
| Authorization | Role-Based Access Control |
| API Protection | Authenticated and role-restricted endpoints |
| Database Queries | SQLAlchemy ORM |
| CORS | Configurable allowed origins |
| File Uploads | File validation and upload restrictions |
| Privacy | Role-based restrictions and PII redaction |

### Security Considerations

- Never commit `.env` files, API keys, database credentials, or JWT secrets.
- Use dedicated credentials for demo environments.
- Do not reuse demo passwords in production.
- Restrict administrative operations in public evaluation environments.
- Configure production CORS with trusted frontend origins only.
- Use HTTPS for deployed services.
- Keep database and vector-database credentials private.
- Configure appropriate request-size limits.
- Avoid uploading real customer information into public demo environments.

Security controls should be validated against the deployed application and current configuration. A security feature being implemented does not automatically establish that the entire application is secure.

---

## Project Structure

The following is a high-level view of the application structure.

```text
ResolveAI/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── rag/
│   │   ├── services/
│   │   └── ...
│   │
│   ├── tests/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── .env.example
│   └── ...
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── context/
│   │   └── ...
│   │
│   ├── package.json
│   ├── .env.example
│   └── ...
│
├── data/
├── evaluation/
├── render.yaml
└── README.md
```

---

## Knowledge Base Documents

The repository includes six sample Markdown support guides:

- `password_and_login.md`
- `billing_and_payments.md`
- `invoices_and_verification.md`
- `refund_policy.md`
- `subscriptions_and_cancellation.md`
- `technical_troubleshooting.md`

An Admin can upload supported documents through the Knowledge Base interface.

The ingestion pipeline processes documents, extracts text, creates chunks, generates embeddings, and indexes the content in Qdrant.

---

## API Overview

The backend exposes REST APIs through FastAPI.

| Area | Main Endpoints |
|---|---|
| Authentication | `POST /api/auth/login`<br>`POST /api/auth/logout` |
| Tickets | `GET /api/tickets`<br>`POST /api/tickets`<br>`GET /api/tickets/{ticket_id}`<br>`PATCH /api/tickets/{ticket_id}/status` |
| Ticket History | `GET /api/tickets/{ticket_id}/history`<br>`GET /api/tickets/{ticket_id}/action-history` |
| AI Analysis | `POST /api/ai/analyze/{ticket_id}` |
| AI Resolution | `POST /api/ai/resolve/{ticket_id}` |
| AI Results | `GET /api/ai/result/{ticket_id}` |
| Knowledge Base | `GET /api/knowledge/documents`<br>`DELETE /api/knowledge/documents/{document_id}` |
| Document Upload | `POST /api/knowledge/upload` |
| Knowledge Search | `POST /api/knowledge/search` |
| Escalations | `GET /api/agents/escalated` |
| Approval | `POST /api/agents/{ticket_id}/approve` |
| Rejection | `POST /api/agents/{ticket_id}/reject` |
| Edit Response | `POST /api/agents/{ticket_id}/edit-response` |
| Agent Notes | `POST /api/agents/{ticket_id}/notes` |
| Analytics | `GET /api/analytics/overview` |
| Categories | `GET /api/analytics/categories` |
| Priorities | `GET /api/analytics/priorities` |
| Trends | `GET /api/analytics/trends` |
| SLA | `GET /api/analytics/sla` |
| Approvals | `GET /api/analytics/approvals` |
| Support Activity | `GET /api/analytics/support-activity` |
| User Management | `GET /api/users`<br>`POST /api/users`<br>`PATCH /api/users/{user_id}/role`<br>`PATCH /api/users/{user_id}/status` |
| System Health | `GET /health` |
| System Status | `GET /api/system/status` |

Protected endpoints require a valid JWT Bearer token and enforce role-based permissions.

Interactive API documentation is available through FastAPI Swagger UI at `/docs`.

---

## Requirements

- Python 3.12.4
- Node.js 20 or newer
- npm
- PostgreSQL for production deployment
- Groq API key for AI-powered operations
- Qdrant Cloud credentials for hosted vector storage, if using cloud mode

SQLite is supported for local development and automated tests.

---

## Local Installation and Setup

### 1. Clone the Repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd ResolveAI
```

Replace `YOUR_GITHUB_REPOSITORY_URL` with the actual repository URL.

### 2. Backend Setup

Open PowerShell:

```powershell
cd backend

python -m venv .venv

.\.venv\Scripts\Activate.ps1

pip install -r requirements-dev.txt

Copy-Item .env.example .env
```

Configure the following environment variables in `backend/.env`:

| Variable | Description |
|---|---|
| `DATABASE_URL` | Database connection string |
| `GROQ_API_KEY` | Groq API key |
| `JWT_SECRET_KEY` | Strong secret used for JWT signing |
| `ADMIN_EMAIL` | Initial Admin email |
| `ADMIN_PASSWORD` | Initial Admin password |
| `ADMIN_FULL_NAME` | Initial Admin display name |
| `QDRANT_PATH` | Local Qdrant storage path |
| `QDRANT_URL` | Qdrant Cloud endpoint |
| `QDRANT_API_KEY` | Qdrant Cloud API key |
| `CORS_ORIGINS` | Allowed frontend origins |

Use a strong, unique JWT secret of at least 32 characters.

For local SQLite development, retain the default SQLite configuration in `.env.example`.

For PostgreSQL, configure `DATABASE_URL` using the appropriate SQLAlchemy connection format.

Example:

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
```

For hosted PostgreSQL providers requiring SSL, configure the appropriate SSL connection options.

Never commit the actual `.env` file.

### 3. Qdrant Configuration

The application supports local vector storage and Qdrant Cloud.

For local development, configure the local storage path:

```env
QDRANT_PATH=./qdrant_storage
```

For Qdrant Cloud, configure:

```env
QDRANT_URL=YOUR_QDRANT_ENDPOINT
QDRANT_API_KEY=YOUR_QDRANT_API_KEY
```

Use the configuration supported by your current application settings.

### 4. Start the Backend

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

Backend:

```text
http://localhost:8000
```

Swagger documentation:

```text
http://localhost:8000/docs
```

Health check:

```text
http://localhost:8000/health
```

The initial Admin account is bootstrapped from environment variables during application startup.

Use unique local development credentials.

### 5. Frontend Setup

Open a separate terminal:

```powershell
cd frontend

npm install

Copy-Item .env.example .env
```

Configure the frontend environment:

```env
VITE_API_URL=http://localhost:8000
```

Start the frontend:

```powershell
npm run dev
```

Open:

```text
http://localhost:5173
```

If the backend uses another address or port, update `VITE_API_URL` accordingly.

---

## Testing

ResolveAI includes an automated backend regression test suite using Pytest and HTTPX.

### Install Development Dependencies

```powershell
cd backend

pip install -r requirements-dev.txt
```

### Run Backend Tests

To run the backend test suite in Windows PowerShell, activate the virtual environment and invoke pytest:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

During test suite verification, 135 tests were collected across the test files. However, the full regression suite could not be completed because the test environment attempted to connect to the configured PostgreSQL database during application setup, resulting in a connection failure in the isolated test environment. Note that activating the virtual environment alone does not resolve database isolation. Full backend test verification is currently pending.

### Frontend Production Build

```powershell
cd frontend

npm install

npm run build
```

### Important Testing Areas

The application testing process covers:

- Authentication and authorization.
- Role-based API access.
- Ticket management.
- Knowledge-base document processing.
- Vector retrieval.
- AI resolution workflows.
- Human approval and rejection.
- Analytics.
- Security validation.
- Frontend user journeys.

Automated test results and live third-party AI service validation are separate. Passing a test suite does not by itself establish live LLM accuracy or production security.

---

## Deployment

### Backend — Render

The backend is deployed on Render.

Production services include:

- Python 3.12.4.
- FastAPI and Uvicorn.
- PostgreSQL through `DATABASE_URL`.
- Qdrant Cloud for vector storage.
- Groq API for LLM inference.
- Environment-based Admin account bootstrap.
- Configurable CORS origins.

The repository includes `render.yaml` for backend service configuration.

Configure production secrets through the Render Dashboard:

```text
DATABASE_URL
QDRANT_URL
QDRANT_API_KEY
GROQ_API_KEY
JWT_SECRET_KEY
ADMIN_EMAIL
ADMIN_PASSWORD
ADMIN_FULL_NAME
CORS_ORIGINS
```

Do not store production secrets in the repository or source code.

### Frontend — Vercel

The frontend is deployed on Vercel.

Live application:

https://resolve-ai-dun.vercel.app

Configure:

```text
VITE_API_URL
```

Set this variable to the deployed backend URL.

Configure backend `CORS_ORIGINS` to allow only the actual frontend deployment origin and any explicitly required trusted origins.

### Deployment Architecture

- Frontend hosted on Vercel.
- Backend hosted on Render.
- PostgreSQL hosted through a managed database provider.
- Qdrant Cloud used for vector storage.
- Groq used for LLM inference.

Managed data services separate application hosting from persistent storage. Actual scaling capacity depends on application state management, connection handling, resource limits, and deployment configuration.

---

## Current Project Status

ResolveAI is deployed and publicly accessible through the Live Demo link.

The application includes:

- Full-stack ticket management.
- JWT authentication and role-based authorization.
- Knowledge-base document ingestion.
- Semantic vector search.
- RAG-based AI resolution generation.
- Evidence and citation validation.
- Confidence-based escalation.
- Human-in-the-Loop approval workflows.
- Analytics dashboards.
- Production deployment.

Development is focused on final security verification, integration testing, AI output validation, performance evaluation, and production reliability checks.

---

## Future Improvements

Potential future engineering work includes:

- Multi-tenant organisation support.
- Advanced ticket sorting and reporting.
- Automated cleanup of expired revoked-token records.
- More extensive LLM evaluation and regression datasets.
- Expanded observability and monitoring.
- Performance testing under concurrent workloads.
- Automated backup and recovery validation.

Multi-tenancy is intentionally outside the current single-tenant architecture.

---

## Engineering Highlights

- Designed a full-stack architecture integrating React, FastAPI, PostgreSQL, and Qdrant.
- Implemented semantic document retrieval for knowledge-grounded AI responses.
- Integrated Groq LLM inference into support-ticket workflows.
- Built citation validation and confidence-based escalation mechanisms.
- Implemented JWT authentication, Argon2 password hashing, and role-based authorization.
- Developed human approval workflows to maintain oversight of AI-generated resolutions.
- Deployed the application using Vercel, Render, PostgreSQL, and Qdrant Cloud.

---

## License

Add your chosen project license here before publishing the repository.

---

**ResolveAI — Bringing knowledge-grounded AI assistance and human oversight to customer support operations.**
