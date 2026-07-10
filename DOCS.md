# 300-30-3 Employee Survey Chatbot — Full Reference

---

## Table of Contents

1. [Database Schema & API Reference](#1-database-schema--api-reference)
   - [PostgreSQL Schema](#11-postgresql-schema)
   - [API Endpoints](#12-api-endpoints)
   - [result JSONB shapes per question type](#13-result-jsonb-shape-per-question-type)
2. [Service Overview](#2-service-overview)
3. [Architecture](#3-architecture)
4. [Project Structure](#4-project-structure)
5. [Question Types](#5-question-types)
6. [LLM Pipeline](#6-llm-pipeline)
7. [How to Run](#7-how-to-run)
8. [Environment Variables](#8-environment-variables)

---

## 1. Database Schema & API Reference

### 1.1 PostgreSQL Schema

Create tables in this order (FK dependencies):
`surveys` → `questions` → `employees` → `responses`

```sql
CREATE TABLE surveys (
    survey_id    VARCHAR(36) PRIMARY KEY,
    title        TEXT,
    company_name TEXT,
    created_at   VARCHAR(50) NOT NULL
);
```

```sql
CREATE TABLE questions (
    question_id       VARCHAR(36) PRIMARY KEY,   -- UUID, unique across all surveys
    question_key      VARCHAR(36) NOT NULL,       -- logical ID e.g. "q01", scoped to survey
    survey_id         VARCHAR(36) NOT NULL REFERENCES surveys(survey_id),
    position          INTEGER     NOT NULL,        -- 0-based display order
    category          TEXT        NOT NULL,
    question_type     VARCHAR(30) NOT NULL,        -- one of 8 types (see §5)
    prompt            TEXT        NOT NULL,
    expected_format   TEXT        NOT NULL,
    options           JSONB       NOT NULL,        -- list[str], empty [] when unused
    min_value         FLOAT,
    max_value         FLOAT,
    max_choices       INTEGER,
    min_length        INTEGER     NOT NULL DEFAULT 2,
    distribution_mode VARCHAR(10)                  -- "coded" | "labeled" | null
);
```

```sql
CREATE TABLE employees (
    employee_id   VARCHAR(36) PRIMARY KEY,         -- UUID, this is the session_id
    survey_id     VARCHAR(36) REFERENCES surveys(survey_id),
    name          TEXT,                            -- optional name typed at start
    created_at    VARCHAR(50) NOT NULL,
    updated_at    VARCHAR(50) NOT NULL,
    current_index INTEGER     NOT NULL DEFAULT 0,  -- 0-based pointer to current question
    completed     BOOLEAN     NOT NULL DEFAULT FALSE,
    editing       JSONB,                           -- null unless mid-edit
    chat_history  JSONB       NOT NULL             -- list[{role, content}]
);
```

```sql
CREATE TABLE responses (
    response_id   VARCHAR(36) PRIMARY KEY,
    survey_id     VARCHAR(36) NOT NULL REFERENCES surveys(survey_id),
    question_id   VARCHAR(36) NOT NULL,            -- the question_key e.g. "q01"
    employee_id   VARCHAR(36) NOT NULL REFERENCES employees(employee_id),
    question_type VARCHAR(30) NOT NULL,
    raw_answer    TEXT        NOT NULL,             -- verbatim text the employee typed
    result        JSONB       NOT NULL,             -- validated typed answer (shape varies by type)
    answered_at   VARCHAR(50) NOT NULL,
    CONSTRAINT uq_employee_question UNIQUE (employee_id, question_id)
);
```

**Notes:**
- `employees.survey_id` is nullable — null means the session uses the default in-memory question set
- `UNIQUE(employee_id, question_id)` on responses enforces one answer per employee per question; editing upserts the existing row
- All timestamps are ISO-8601 strings e.g. `"2026-05-13T09:00:00+00:00"`
- `editing` JSONB shape: `{"target_index": 2, "return_index": 7, "was_completed": true}`

---

### 1.2 API Endpoints

**Base URL:** `http://localhost:8000`
**Swagger UI:** `http://localhost:8000/docs`

---

#### `GET /health`

Health check.

```json
// Response
{ "status": "ok" }
```

---

#### `POST /surveys`

Create a new survey. Returns a shareable employee link.

```json
// Request body
{
  "title": "Q1 2026 Survey",
  "company_name": "Acme Corp",
  "questions": [
    {
      "id": "q01",
      "category": "Employee Profile",
      "question_type": "single_selection",
      "prompt": "What is your employment type?",
      "expected_format": "Full-time",
      "options": ["Full-time", "Part-time", "Contract", "Casual"],
      "min_value": null,
      "max_value": null,
      "max_choices": null,
      "min_length": 2,
      "distribution_mode": null
    }
  ]
}
```

```json
// Response 201
{
  "survey_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Q1 2026 Survey",
  "company_name": "Acme Corp",
  "total_questions": 1,
  "created_at": "2026-05-13T08:00:00+00:00",
  "survey_url": "http://localhost:8501?survey_id=550e8400-e29b-41d4-a716-446655440000"
}
```

**DB writes:** inserts 1 row into `surveys`, inserts N rows into `questions`.

---

#### `GET /surveys/{survey_id}`

Get survey metadata (no question details).

```json
// Response
{
  "survey_id": "550e8400...",
  "title": "Q1 2026 Survey",
  "company_name": "Acme Corp",
  "total_questions": 30,
  "created_at": "2026-05-13T08:00:00+00:00",
  "survey_url": "http://localhost:8501?survey_id=550e8400..."
}
```

**DB reads:** `surveys` + count of `questions`.

---

#### `GET /surveys/{survey_id}/questions`

Get the full ordered question list for a survey.

```json
// Response
{
  "survey_id": "550e8400...",
  "questions": [
    {
      "id": "q01",
      "category": "Employee Profile",
      "question_type": "single_selection",
      "prompt": "What is your employment type?",
      "expected_format": "Full-time",
      "options": ["Full-time", "Part-time", "Contract", "Casual"],
      "min_value": null,
      "max_value": null,
      "max_choices": null,
      "min_length": 2,
      "distribution_mode": null
    }
  ]
}
```

**DB reads:** `surveys` + `questions` ordered by `position`.

---

#### `POST /surveys/{survey_id}/questions`

Append a question to a survey.

```json
// Request body — single Question object
{
  "id": "q31",
  "category": "Satisfaction",
  "question_type": "rating",
  "prompt": "Rate your overall satisfaction from 1 to 5.",
  "expected_format": "4",
  "options": [],
  "min_value": 1,
  "max_value": 5,
  "max_choices": null,
  "min_length": 2,
  "distribution_mode": null
}
```

```json
// Response 201
{
  "survey_id": "550e8400...",
  "questions": [ ...all questions including new one... ]
}
```

**DB writes:** deletes + re-inserts all `questions` rows for the survey.

---

#### `PUT /surveys/{survey_id}/questions/{question_id}`

Replace a question in the survey. `question_id` in the path is the logical key e.g. `q01`.

```json
// Request body — full updated Question object
{
  "id": "q01",
  "category": "Employee Profile",
  "question_type": "rating",
  "prompt": "Rate your experience from 1 to 10.",
  "expected_format": "7",
  "options": [],
  "min_value": 1,
  "max_value": 10,
  "max_choices": null,
  "min_length": 2,
  "distribution_mode": null
}
```

```json
// Response
{
  "survey_id": "550e8400...",
  "question": { ...updated question... }
}
```

**DB writes:** deletes + re-inserts all `questions` rows for the survey.

---

#### `DELETE /surveys/{survey_id}/questions/{question_id}`

Remove a question from the survey.

```json
// Response
{ "survey_id": "550e8400...", "total": 29 }
```

**DB writes:** deletes + re-inserts all `questions` rows for the survey (minus removed one).

---

#### `GET /surveys/{survey_id}/responses`

Aggregated view of all employee sessions and their answers for a survey.

```json
// Response
{
  "survey_id": "550e8400...",
  "total_respondents": 12,
  "completed_count": 9,
  "sessions": [
    {
      "session_id": "abc123...",
      "employee_id": "Alice",
      "completed": true,
      "progress": 30,
      "started_at": "2026-05-13T09:00:00+00:00",
      "updated_at": "2026-05-13T09:45:00+00:00",
      "responses": {
        "q01": {
          "question_id": "q01",
          "question_type": "single_selection",
          "raw_answer": "Full-time",
          "response": { "value": "Full-time" },
          "answered_at": "2026-05-13T09:01:00+00:00"
        },
        "q02": {
          "question_id": "q02",
          "question_type": "rating",
          "raw_answer": "4",
          "response": { "value": 4 },
          "answered_at": "2026-05-13T09:02:00+00:00"
        }
      }
    }
  ]
}
```

**DB reads:** `employees` filtered by `survey_id` + all their `responses`.

---

#### `POST /sessions`

Start a new employee survey session. Returns the first question and opening message.

```json
// Request body
{
  "employee_id": "Alice",          // optional display name
  "survey_id": "550e8400..."       // optional — omit to use the default 30-question set
}
```

```json
// Response 201
{
  "session_id": "abc123...",
  "completed": false,
  "progress": 0,
  "total_questions": 30,
  "assistant_message": "Hi! Thanks for taking the time to complete this survey...",
  "current_question": {
    "id": "q01",
    "number": 1,
    "total": 30,
    "category": "Employee Profile",
    "question_type": "single_selection",
    "prompt": "What is your employment type?",
    "expected_format": "Full-time",
    "options": ["Full-time", "Part-time", "Contract", "Casual"],
    "min_value": null,
    "max_value": null,
    "max_choices": null
  },
  "chat_history": [
    { "role": "assistant", "content": "Hi! Thanks for taking the time..." }
  ],
  "responses": {}
}
```

**DB writes:** inserts 1 row into `employees`.

---

#### `POST /sessions/{session_id}/message`

**The main interaction endpoint.** Submit an employee message. Triggers the full LLM pipeline — intent detection, answer extraction, validation, and saving.

```json
// Request body
{ "message": "Full-time" }
```

```json
// Response — updated session state
{
  "session_id": "abc123...",
  "completed": false,
  "progress": 1,
  "total_questions": 30,
  "assistant_message": "Got it! Now for question 2 of 30...",
  "current_question": {
    "id": "q02",
    "number": 2,
    "total": 30,
    "category": "Commute",
    "question_type": "number",
    "prompt": "How long does your commute take one way, in minutes?",
    "expected_format": "25",
    "options": [],
    "min_value": 0,
    "max_value": 300,
    "max_choices": null
  },
  "chat_history": [
    { "role": "assistant", "content": "Hi! Thanks for taking the time..." },
    { "role": "user",      "content": "Full-time" },
    { "role": "assistant", "content": "Got it! Now for question 2 of 30..." }
  ],
  "responses": {
    "q01": {
      "question_id": "q01",
      "question_type": "single_selection",
      "raw_answer": "Full-time",
      "response": { "value": "Full-time" },
      "answered_at": "2026-05-13T09:01:00+00:00"
    }
  }
}
```

**DB writes (every message):** upserts `employees` row (current_index, chat_history, updated_at).
**DB writes (valid answer only):** upserts `responses` row for that question.
**DB writes (invalid answer):** only `employees` is updated (chat_history); no response row written.

**Navigation messages** the employee can type instead of an answer:

| Employee types | Effect |
|---|---|
| `"go back to question 3"` | Jump to Q3 for editing |
| `"back"` / `"previous"` | Go to previous question |
| `"show progress"` | Returns how many answered |
| `"help"` | Repeats current question + expected format |
| `"cancel edit"` | Exits edit mode without saving |

---

#### `GET /sessions/{session_id}`

Get the current session state without advancing anything.

```json
// Response — same shape as POST /sessions response
```

**DB reads:** `employees` + `responses` for this session.

---

#### `GET /sessions/{session_id}/responses`

Get only the recorded answers for a session (no chat history).

```json
// Response
{
  "session_id": "abc123...",
  "survey_id": "550e8400...",
  "employee_id": "Alice",
  "completed": false,
  "progress": 5,
  "total_questions": 30,
  "responses": {
    "q01": {
      "question_id": "q01",
      "question_type": "single_selection",
      "raw_answer": "Full-time",
      "response": { "value": "Full-time" },
      "answered_at": "2026-05-13T09:01:00+00:00"
    }
  }
}
```

**DB reads:** `employees` + `responses`.

---

#### `DELETE /sessions/{session_id}`

Permanently delete a session and all its answers.

```json
// Response
{ "status": "deleted" }
```

**DB writes:** deletes all `responses` rows for employee, then deletes `employees` row.

---

### 1.3 `result` JSONB Shape per Question Type

The `result` column in `responses` stores the validated, typed answer. Shape depends on `question_type`:

| Type | `result` shape | Example |
|---|---|---|
| `single_selection` | `{"value": str}` | `{"value": "Full-time"}` |
| `multiple_selection` | `{"values": list[str]}` | `{"values": ["Office", "Home"]}` |
| `rating` | `{"value": int}` | `{"value": 4}` |
| `number` | `{"value": int \| float}` | `{"value": 25}` |
| `percentage` | `{"value": float, "unit": "%"}` | `{"value": 70, "unit": "%"}` |
| `distribution (coded)` | `{code: float, ...}` | `{"A": 20, "B": 30, "C": 50}` |
| `distribution (labeled)` | `{"entries": [{label, percentage}]}` | `{"entries": [{"label": "Marketing", "percentage": 30}]}` |
| `hours_distribution` | `{hours_per_week, individual_work_percentage, collaborative_work_percentage, other_percentage}` | `{"hours_per_week": 40, "individual_work_percentage": 50, "collaborative_work_percentage": 30, "other_percentage": 20}` |
| `free_text` | `{"value": str}` | `{"value": "Senior Financial Analyst"}` |

---

## 2. Service Overview

**300-30-3** is a 4-component AI-powered workplace survey platform.

| Component | Technology | Port | Role |
|---|---|---|---|
| **Backend** | Python / FastAPI | `8000` | REST API + LLM pipeline + DB ORM |
| **Employee UI** | Python / Streamlit | `8501` | Conversational chat survey interface |
| **Admin Generator** | React / Vite | `3000` | Visual survey builder for admins |
| **Database** | PostgreSQL | `5432` | Persistent storage |

### End-to-End Flow

```
1. Admin opens http://localhost:3000
   → builds a question set visually in the React generator
   → clicks "Generate Chatbot"
   → POST /surveys  { title, company_name, questions: [...] }
       DB WRITE → INSERT INTO surveys (1 row)
       DB WRITE → INSERT INTO questions (1 row per question)
   ← returns { survey_id, survey_url }

2. Admin shares the survey_url with employees
   → format: http://localhost:8501?survey_id=<uuid>

3. Employee opens the URL
   → GET /surveys/{survey_id}
       DB READ  → SELECT FROM surveys WHERE survey_id = ?
   ← returns { title, company_name, total_questions }

   → Employee clicks "Start Survey"
   → POST /sessions  { employee_id, survey_id }
       DB READ  → SELECT FROM questions WHERE survey_id = ? ORDER BY position
       DB WRITE → INSERT INTO employees (session row, current_index=0)
   ← returns { session_id, first assistant message, current_question }

4. Employee types each answer
   → POST /sessions/{session_id}/message  { message: "..." }
       DB READ  → SELECT FROM questions WHERE survey_id = ?  (fetch question list)
       DB READ  → SELECT FROM employees WHERE employee_id = ?
       → OpenAI intent detection + answer extraction
       → AnswerValidator checks format
       if valid:
         DB WRITE → UPSERT INTO responses (question_id, result, raw_answer)
         DB WRITE → UPDATE employees SET current_index, chat_history, updated_at
       if invalid:
         DB WRITE → UPDATE employees SET chat_history, updated_at  (no response row)
   ← returns { assistant_message, progress, current_question, responses }

   → repeated for each question until completed = true

5. Admin retrieves all answers
   → GET /surveys/{survey_id}/responses
       DB READ  → SELECT FROM employees WHERE survey_id = ?
       DB READ  → SELECT FROM responses WHERE employee_id = ?  (for each employee)
   ← returns { total_respondents, completed_count, sessions: [...] }
```

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────┐
│            React Admin Generator  (port 3000)           │
│   builds surveys → POST /surveys → gets survey_url      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│               FastAPI Backend  (port 8000)               │
│                                                         │
│  main.py        → route definitions                     │
│  chatbot.py     → orchestrator / state machine          │
│  ai_service.py  → LLM facade                            │
│  llm_service.py → OpenAI API (intent + wording)         │
│  validator.py   → deterministic answer validation       │
│  storage.py     → PostgreSQL ORM                        │
└──────┬──────────────────────────────────────────────────┘
       │
  ┌────┴──────────────────┐
  ▼                       ▼
PostgreSQL            OpenAI API
(port 5432)           (external)

  ▲
  │
┌─┴──────────────────────────────────────────────────────┐
│           Streamlit Employee UI  (port 8501)            │
│   chat interface → POST /sessions/{id}/message          │
└────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| File | Role |
|---|---|
| `main.py` | HTTP routing only — thin decorators, no logic |
| `chatbot.py` | State machine — session flow, question order, edit mode |
| `ai_service.py` | Thin facade — single call site between chatbot and LLM/validator |
| `llm_service.py` | All OpenAI calls — intent detection + message composition. Has `OPENAI_FAKE_MODE` for tests |
| `validator.py` | Deterministic format validation — no external I/O, fully testable |
| `storage.py` | PostgreSQL ORM — `PgSessionStore` + `PgSurveyStore` behind protocol interfaces |

---

## 4. Project Structure

```
300-30-3/
├── docker-compose.yml
├── DOCS.md                          ← this file
├── INSTRUCTION.md                   ← extended technical reference
│
├── survey/                          ← backend + employee UI
│   ├── .env.example
│   ├── .env
│   ├── requirements.txt
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   │
│   ├── backend/
│   │   ├── main.py                  ← FastAPI app + all routes
│   │   ├── models.py                ← all Pydantic schemas
│   │   ├── questions.py             ← default 30-question set
│   │   └── services/
│   │       ├── chatbot.py           ← business logic orchestrator
│   │       ├── ai_service.py        ← LLM facade
│   │       ├── llm_service.py       ← OpenAI API calls
│   │       ├── validator.py         ← answer validation
│   │       └── storage.py           ← DB ORM + store protocols
│   │
│   ├── frontend/
│   │   └── streamlit_app.py         ← employee chat UI
│   │
│   └── tests/
│       ├── test_validator.py
│       └── test_chatbot_navigation.py
│
└── survey generator/                ← React admin UI
    ├── src/
    │   ├── App.jsx
    │   └── components/
    │       ├── Header.jsx
    │       ├── QuestionList.jsx
    │       ├── QuestionCard.jsx
    │       ├── QuestionForm.jsx
    │       └── GenerateChatbotModal.jsx
    └── Dockerfile
```

---

## 5. Question Types

All 8 supported types with their validation rules and expected employee input:

| Type | Employee input example | Validation rules |
|---|---|---|
| `rating` | `"4"` | Integer within `[min_value, max_value]` |
| `number` | `"25 minutes"` | Float/int within range; strips units |
| `percentage` | `"70%"` | Float 0–100 (or custom range) |
| `single_selection` | `"Full-time"` or `"A"` | Fuzzy-matched against `options` (cutoff 0.82) |
| `multiple_selection` | `"A, D, E"` or `"Office, Home"` | Each fuzzy-matched; count ≤ `max_choices` |
| `distribution (coded)` | `"A 20%, B 30%, C 50%"` | Codes in `options`; sum must equal 100 |
| `distribution (labeled)` | `"30% Marketing, 70% external"` | Free labels; sum must equal 100 |
| `hours_distribution` | `"40, 50, 30, 20"` | 4 numbers: hours + 3 percentages summing to 100 |
| `free_text` | `"Senior Financial Analyst"` | Length ≥ `min_length` characters |

### Question Object Fields

| Field | Required | Description |
|---|---|---|
| `id` | Yes | Logical key e.g. `"q01"` — scoped within the survey |
| `category` | Yes | Thematic group e.g. `"Commute"` |
| `question_type` | Yes | One of the 8 types above |
| `prompt` | Yes | Full question text shown to the employee |
| `expected_format` | Yes | Human-readable format hint |
| `options` | No | List of valid options (empty `[]` when unused) |
| `min_value` | No | Min numeric value (rating / number / hours) |
| `max_value` | No | Max numeric value |
| `max_choices` | No | Max selections allowed (multiple_selection only) |
| `min_length` | No | Min character count (free_text, default 2) |
| `distribution_mode` | No | `"coded"` or `"labeled"` (distribution type only) |

---

## 6. LLM Pipeline

Triggered by every call to `POST /sessions/{session_id}/message`.

```
Employee types a message
        │
        ▼
OpenAI intent detection (structured output)
        │
        ▼
LLMUserMessageAnalysis {
    intent:           "answer_current_question" | "go_to_question" |
                      "previous_question" | "show_progress" |
                      "help" | "cancel_edit" | "unknown"
    question_number:  int | null   (for go_to_question)
    extracted_answer: typed answer | null
    confidence:       0.0 – 1.0
}
        │
        ├── intent ≠ answer → route to navigation/help handler
        │                   → generate response, return (no DB write for responses)
        │
        ▼
    intent == answer_current_question
        │
        ▼
AnswerValidator.validate_structured(extracted_answer, question)
        │
        ├── invalid → LLM composes error message, return (no response row written)
        │
        ▼
    valid
        │
        ├── write to responses table
        ├── advance current_index
        ├── LLM composes next question message
        │
        ▼
update employees table + return SessionResponse
```

**OPENAI_FAKE_MODE=true** replaces all OpenAI calls with fast regex-based logic — no API key needed, used for tests and local dev.

---

## 7. How to Run

### Docker (recommended)

```bash
cd services/300-30-3
cp survey/.env.example survey/.env
# add OPENAI_API_KEY to survey/.env

docker compose up --build
```

| URL | Service |
|---|---|
| `http://localhost:3000` | Admin survey generator |
| `http://localhost:8000/docs` | Backend Swagger UI |
| `http://localhost:8501?survey_id=<uuid>` | Employee chat |

### Local (no Docker)

```bash
cd services/300-30-3/survey
cp .env.example .env                        # set OPENAI_API_KEY + DATABASE_URL

pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000   # terminal 1
streamlit run frontend/streamlit_app.py          # terminal 2

cd "../survey generator"
npm install && npm run dev                        # terminal 3 → http://localhost:5173
```

### Tests

```bash
cd services/300-30-3/survey
uv run pytest
```

---

## 8. Environment Variables

All go in `survey/.env`.

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Model to use |
| `DATABASE_URL` | No | `postgresql://postgres:postgres@localhost:5432/survey` | PostgreSQL connection string |
| `BACKEND_URL` | No | `http://127.0.0.1:8000` | Used by Streamlit to reach the backend |
| `FRONTEND_URL` | No | `http://localhost:8501` | Used by backend to build `survey_url` |

In Docker, `DATABASE_URL` and `FRONTEND_URL` are overridden by `docker-compose.yml`. For production set `FRONTEND_URL` to your real domain so the returned `survey_url` is publicly accessible.
