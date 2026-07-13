# 300-30-3 — AI-Powered Employee Survey Chatbot

An end-to-end workplace survey platform. Admins build surveys visually, employees complete them through a conversational AI chat interface, and all responses are stored in PostgreSQL.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Components](#components)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Option A — Docker (recommended)](#option-a--docker-recommended)
  - [Option B — Local Development](#option-b--local-development)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Database Schema](#database-schema)
- [Question Types](#question-types)
- [Project Structure](#project-structure)

---

## Overview

**300-30-3** is a fully containerized survey platform built around a conversational chatbot. Instead of filling out a form, employees answer questions through a natural chat interface powered by OpenAI. The system understands natural language, validates answers by type, and guides employees through corrections when the format is wrong.

**Admin flow:** Build a survey → Click "Generate Chatbot" → Share the link with employees.

**Employee flow:** Open the link → Chat with the bot → Answers saved to DB automatically.

**Results flow:** Call one endpoint → Get all employee responses aggregated.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│            React Admin Generator  (port 3000)           │
│         Build surveys visually → POST /surveys          │
└────────────────────────┬────────────────────────────────┘
                         │ POST /surveys
                         ▼
┌─────────────────────────────────────────────────────────┐
│               FastAPI Backend  (port 8000)               │
│                                                         │
│  Routes → Orchestrator → LLM Facade → OpenAI API        │
│                       → Validator (deterministic)        │
│                       → PostgreSQL ORM                  │
└──────┬──────────────────────────────────────────────────┘
       │                         ▲
       ▼                         │ API calls
  PostgreSQL (port 5432)         │
                                 │
              ┌──────────────────┴──────────────────────┐
              │      Streamlit Employee UI  (port 8501)  │
              │  http://localhost:8501?survey_id=<uuid>  │
              └─────────────────────────────────────────┘
```

### How It Works

```
1. Admin   → POST /surveys        → DB: INSERT surveys + questions
2. Admin shares survey_url with employees
3. Employee → GET /surveys/{id}   → DB: SELECT surveys
4. Employee → POST /sessions      → DB: INSERT employees session
5. Employee → POST /sessions/{id}/message  (repeated per question)
              → OpenAI extracts answer
              → Validator checks format
              → DB: UPSERT responses + UPDATE employees
6. Admin   → GET /surveys/{id}/responses → DB: SELECT employees + responses
```

---

## Components

| Component           | Technology                 | Port   | Purpose                        |
| ------------------- | -------------------------- | ------ | ------------------------------ |
| **Backend**         | Python 3.12 / FastAPI      | `8000` | REST API, LLM pipeline, DB ORM |
| **Employee UI**     | Python / Streamlit         | `8501` | Conversational chat interface  |
| **Admin Generator** | React 19 / Vite / Tailwind | `3000` | Visual survey builder          |
| **Database**        | PostgreSQL 16              | `5432` | Persistent storage             |

---

## Prerequisites

### For Docker (recommended)

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- An OpenAI API key

### For Local Development

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- An OpenAI API key

---

## Installation

### Option A — Docker

This is the fastest way to get everything running. One command starts all services.

**1. Clone and navigate**

```bash
git clone <your-repo-url>
cd survey-generator
```

**2. Set up environment variables**

```bash
cp survey/.env.example survey/.env
```

Open `survey/.env` and fill in your OpenAI key. For Docker, that's the only value you need to set:

```env
OPENAI_API_KEY=sk-...         # required
OPENAI_MODEL=gpt-4o-mini      # optional, default: gpt-4o-mini
```

> **Database and service URLs are handled automatically.** `docker-compose.yml` runs a bundled PostgreSQL 16 container and injects the correct `DATABASE_URL`, `BACKEND_URL`, and `FRONTEND_URL` into each service — any values you put in `.env` for those are overridden for the Docker run, so you can leave them as-is.

**3. Build and start**

```bash
docker compose up --build
```

First build takes ~2 minutes. Subsequent starts are instant:

```bash
docker compose up
```

**4. Verify everything is running**

```bash
docker compose ps
```

All services should show `healthy` or `running`.

**Service URLs:**

| URL                        | Service                  |
| -------------------------- | ------------------------ |
| http://localhost:3000      | Admin survey generator   |
| http://localhost:8000/docs | Backend API (Swagger UI) |
| http://localhost:8501      | Employee chat UI         |

**Stop the services:**

```bash
docker compose down          # stop
docker compose down -v       # stop + delete data volumes
```

---

### Option B — Local Development

Run each component individually without Docker. Useful for active development.

**1. Clone and navigate**

```bash
git clone <your-repo-url>
cd survey-generator
```

**2. Set up environment variables**

```bash
cp survey/.env.example survey/.env
```

Edit `survey/.env`:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/survey
FRONTEND_URL=http://localhost:8501
BACKEND_URL=http://127.0.0.1:8000
```

**3. Create the database**

```bash
psql -U postgres -c "CREATE DATABASE survey;"
```

**4. Install Python dependencies**

```bash
cd survey
pip install -r requirements.txt
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv sync
```

**5. Start the backend** (Terminal 1)

```bash
cd survey
uvicorn backend.main:app --reload --port 8000
```

Tables are created automatically on first startup. Check http://localhost:8000/docs to confirm it's running.

**6. Start the employee UI** (Terminal 2)

```bash
cd survey
streamlit run frontend/streamlit_app.py
```

Available at http://localhost:8501.

**7. Start the admin generator** (Terminal 3)

```bash
cd "survey generator"
npm install
npm run dev
```

Available at http://localhost:5173.

---

### Running Tests

```bash
cd survey
uv run pytest
# or
pytest
```

Tests use fake mode and an in-memory store — no database or API key needed.

---

## Configuration

All configuration goes in `survey/.env`. Copy from `survey/.env.example` to get started.

| Variable         | Required | Default                                                | Description                                         |
| ---------------- | -------- | ------------------------------------------------------ | --------------------------------------------------- |
| `OPENAI_API_KEY` | Yes      | —                                                      | Your OpenAI API key                                 |
| `OPENAI_MODEL`   | No       | `gpt-4o-mini`                                          | OpenAI model to use                                 |
| `OPENAI_FAKE_MODE` | No     | `false`                                                | Skip real OpenAI calls (for local demos/tests)      |
| `DATABASE_URL`   | No       | `postgresql://postgres:postgres@localhost:5432/survey` | PostgreSQL connection string                        |
| `BACKEND_URL`    | No       | `http://127.0.0.1:8000`                                | Used by Streamlit to reach the backend              |
| `FRONTEND_URL`   | No       | `http://localhost:8501`                                | Used by the backend to build shareable survey links |

**Production note:** Set `FRONTEND_URL` to your public domain (e.g. `https://survey.yourcompany.com`) so the generated survey links are publicly accessible.

---

## Usage

### 1. Create a Survey (Admin)

Open http://localhost:3000 in your browser.

- Add questions using the form on the right
- Each question has a type, prompt, and options (when applicable)
- Click **"Generate Chatbot"** when done
- Copy the **survey URL** that appears — this is the link you share with employees

### 2. Share With Employees

The survey URL looks like:

```
http://localhost:8501?survey_id=550e8400-e29b-41d4-a716-446655440000
```

Each employee who opens this link gets their own independent session. They can:

- Answer questions one by one through the chat
- Type `go back to question 3` to edit a previous answer
- Type `help` to see the expected format again
- Type `show progress` to see how many questions are left
- Download their answers as JSON when complete

### 3. Retrieve Results (Admin)

```bash
curl http://localhost:8000/surveys/{survey_id}/responses
```

Or open http://localhost:8000/docs and call `GET /surveys/{survey_id}/responses` from the Swagger UI.

Returns all employee sessions with their answers, completion status, and timestamps.

---

## API Reference

Full interactive docs: **http://localhost:8000/docs**

### Surveys

| Method   | Endpoint                        | Description                           |
| -------- | ------------------------------- | ------------------------------------- |
| `POST`   | `/surveys`                      | Create a survey, returns `survey_url` |
| `GET`    | `/surveys/{id}`                 | Get survey metadata                   |
| `GET`    | `/surveys/{id}/questions`       | List all questions                    |
| `POST`   | `/surveys/{id}/questions`       | Append a question                     |
| `PUT`    | `/surveys/{id}/questions/{qid}` | Replace a question                    |
| `DELETE` | `/surveys/{id}/questions/{qid}` | Remove a question                     |
| `GET`    | `/surveys/{id}/responses`       | All employee responses aggregated     |

### Sessions (Employee)

| Method   | Endpoint                   | Description                        |
| -------- | -------------------------- | ---------------------------------- |
| `POST`   | `/sessions`                | Start a new session                |
| `GET`    | `/sessions/{id}`           | Get current session state          |
| `POST`   | `/sessions/{id}/message`   | Submit an employee message         |
| `GET`    | `/sessions/{id}/responses` | Get answers only (no chat history) |
| `DELETE` | `/sessions/{id}`           | Delete session and all answers     |

### Example: Create a Survey

```bash
curl -X POST http://localhost:8000/surveys \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Q1 2026 Workplace Survey",
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
  }'
```

**Response:**

```json
{
  "survey_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Q1 2026 Workplace Survey",
  "company_name": "Acme Corp",
  "total_questions": 1,
  "created_at": "2026-05-13T08:00:00+00:00",
  "survey_url": "http://localhost:8501?survey_id=550e8400-e29b-41d4-a716-446655440000"
}
```

---

## Database Schema

Four tables, created automatically on backend startup.

```sql
CREATE TABLE surveys (
    survey_id    VARCHAR(36) PRIMARY KEY,
    title        TEXT,
    company_name TEXT,
    created_at   VARCHAR(50) NOT NULL
);

CREATE TABLE questions (
    question_id       VARCHAR(36) PRIMARY KEY,   -- UUID per row
    question_key      VARCHAR(36) NOT NULL,       -- logical ID e.g. "q01"
    survey_id         VARCHAR(36) NOT NULL REFERENCES surveys(survey_id),
    position          INTEGER     NOT NULL,
    category          TEXT        NOT NULL,
    question_type     VARCHAR(30) NOT NULL,
    prompt            TEXT        NOT NULL,
    expected_format   TEXT        NOT NULL,
    options           JSONB       NOT NULL,
    min_value         FLOAT,
    max_value         FLOAT,
    max_choices       INTEGER,
    min_length        INTEGER     NOT NULL DEFAULT 2,
    distribution_mode VARCHAR(10)
);

CREATE TABLE employees (
    employee_id   VARCHAR(36) PRIMARY KEY,        -- UUID = session ID
    survey_id     VARCHAR(36) REFERENCES surveys(survey_id),
    name          TEXT,
    created_at    VARCHAR(50) NOT NULL,
    updated_at    VARCHAR(50) NOT NULL,
    current_index INTEGER     NOT NULL DEFAULT 0,
    completed     BOOLEAN     NOT NULL DEFAULT FALSE,
    editing       JSONB,
    chat_history  JSONB       NOT NULL
);

CREATE TABLE responses (
    response_id   VARCHAR(36) PRIMARY KEY,
    survey_id     VARCHAR(36) NOT NULL REFERENCES surveys(survey_id),
    question_id   VARCHAR(36) NOT NULL,
    employee_id   VARCHAR(36) NOT NULL REFERENCES employees(employee_id),
    question_type VARCHAR(30) NOT NULL,
    raw_answer    TEXT        NOT NULL,
    result        JSONB       NOT NULL,
    answered_at   VARCHAR(50) NOT NULL,
    CONSTRAINT uq_employee_question UNIQUE (employee_id, question_id)
);
```

---

## Question Types

The system supports 8 question types. Each has its own validation logic and format guide shown to the employee.

| Type                     | Employee Input Example        | Stored Result                                                                                                           |
| ------------------------ | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `rating`                 | `4`                           | `{"value": 4}`                                                                                                          |
| `number`                 | `25` or `25 minutes`          | `{"value": 25}`                                                                                                         |
| `percentage`             | `70%`                         | `{"value": 70, "unit": "%"}`                                                                                            |
| `single_selection`       | `Full-time` or `A`            | `{"value": "Full-time"}`                                                                                                |
| `multiple_selection`     | `A, D, E` or `Office, Home`   | `{"values": ["Office", "Home"]}`                                                                                        |
| `distribution (coded)`   | `A 40%, B 35%, C 25%`         | `{"A": 40, "B": 35, "C": 25}`                                                                                           |
| `distribution (labeled)` | `40% deep work, 60% meetings` | `{"entries": [{"label": "deep work", "percentage": 40}, ...]}`                                                          |
| `hours_distribution`     | `40, 50%, 30%, 20%`           | `{"hours_per_week": 40, "individual_work_percentage": 50, "collaborative_work_percentage": 30, "other_percentage": 20}` |
| `free_text`              | `Senior Financial Analyst`    | `{"value": "Senior Financial Analyst"}`                                                                                 |

**Validation rules:**

- `rating` / `number` — must be within `[min_value, max_value]`
- `percentage` — must be between 0 and 100
- `single_selection` / `multiple_selection` — fuzzy-matched against `options` (accepts typos and letter codes)
- `distribution` — all percentages must sum to exactly 100%
- `hours_distribution` — hours within range; 3 percentages must sum to exactly 100%
- `free_text` — must be at least `min_length` characters

---

## Project Structure

```
survey-generator/
├── docker-compose.yml
├── README.md
├── DOCS.md                          ← full technical reference
│
├── survey/                          ← backend + employee UI
│   ├── .env.example                 ← copy to .env and fill in
│   ├── requirements.txt
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   │
│   ├── backend/
│   │   ├── main.py                  ← FastAPI app + all routes
│   │   ├── models.py                ← Pydantic request/response schemas
│   │   └── services/
│   │       ├── chatbot.py           ← business logic + session state machine
│   │       ├── ai_service.py        ← LLM facade
│   │       ├── llm_service.py       ← OpenAI API calls + fake mode
│   │       ├── validator.py         ← deterministic answer validation
│   │       └── storage.py           ← PostgreSQL ORM + store protocols
│   │
│   ├── frontend/
│   │   └── streamlit_app.py         ← employee chat UI
│   │
│   └── tests/
│       ├── test_validator.py
│       └── test_chatbot_navigation.py
│
└── survey generator/                ← React admin UI (TypeScript + Vite)
    ├── src/
    │   ├── App.tsx
    │   ├── main.tsx
    │   ├── data/
    │   │   └── questionBank.ts       ← default 30-question set
    │   ├── types/
    │   │   └── models.ts
    │   └── components/
    │       ├── Header.tsx
    │       ├── QuestionList.tsx
    │       ├── QuestionCard.tsx
    │       ├── QuestionForm.tsx
    │       ├── QuestionLibrary.tsx
    │       ├── AddQuestionChoice.tsx
    │       └── GenerateChatbotModal.tsx
    └── Dockerfile
```
