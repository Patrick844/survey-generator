# Survey Employee UI (React)

A React + Vite + Tailwind replacement for the Streamlit employee chat. It talks to
the same FastAPI backend and renders an interactive widget for every question type
(selection, rating, distribution, number, percentage, free text) plus a chat input —
both paths run the same server-side validation.

## Run it locally

```bash
npm install
npm run dev
```

Then open the app with a real survey id in the URL:

```
http://localhost:5173?survey_id=<a-survey-id>
```

Get a `survey_id` by creating a survey in the admin generator (it's the `survey_id`
in the shareable link it produces).

## Backend it talks to

Configured via `VITE_API_BASE` in `.env` (copy from `.env.example`):

- **Live instance:** `http://13.49.227.37:8000` (default in `.env` — lets you test
  without running the backend yourself)
- **Local backend:** `http://localhost:8000` (if you run the stack locally)

CORS on the backend already allows any origin, so the local dev server can call
either.

## Build

```bash
npm run build     # tsc + vite build → dist/
npm run preview   # serve the production build
```

> Not wired into the Docker deploy yet — this is a standalone local app for now.
