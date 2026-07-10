# Task: Add click-to-answer to the employee survey

## Goal

Right now an employee can **only answer by typing** into the chat box. Your job is to
add **click capabilities** on top of the existing chat, so the survey works like a normal
form *and* a chat:

- For **single-choice** questions: show the options as clickable buttons. Clicking one
  submits it as the answer and moves to the next question.
- For **multiple-choice** questions: let the employee click several options (toggle on/off),
  then click a **Next** button to submit all selected options at once and move on.
- The chat box stays — typing must keep working exactly as it does today. Buttons are an
  *additional* way to answer, not a replacement.

## The one important thing to understand first

You do **not** need to change the backend. The backend already accepts any text message at
`POST /sessions/{session_id}/message` and figures out the answer with an LLM pipeline
(see `DOCS.md` §6). So a button click just needs to **build the same string a user would
have typed** and send it through the code path that already exists.

Examples of the string a click should produce:

| Question type | User clicks | String you send |
|---|---|---|
| `single_selection` | "Full-time" | `Full-time` |
| `multiple_selection` | "Office" + "Home" then **Next** | `Office, Home` |
| `rating` (1–5) | the "4" button | `4` |

That string goes through the **exact same function the chat box uses today**:
`queue_user_message(...)` followed by `st.rerun()`. Trace how the chat input does it in
`main()` and reuse that path — do not invent a second way to talk to the backend.

## Where to work

- **File:** `survey/frontend/streamlit_app.py` — this is the entire employee UI (Streamlit).
  All your changes go here. You should not need to touch the backend or the React generator.
- Read `DOCS.md` §2 and §5 first to understand the question types and the data you get back.

## What data you have to work with

Every API response contains `session["current_question"]`, which looks like:

```json
{
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
}
```

- `question_type` tells you which UI to render (the 8 types are listed in `DOCS.md` §5).
- `options` is the list of clickable choices (empty `[]` for free-text / number questions).
- `max_choices` (multiple_selection only) caps how many can be selected — enforce it.
- `min_value` / `max_value` (rating) give you the button range.

## Requirements

1. **Single selection** (`single_selection`): render each option in `options` as a button.
   One click = submit that option as the answer and advance.
2. **Multiple selection** (`multiple_selection`): render each option as a **toggle**
   (clicking selects/deselects, with a clear visual difference between selected and not).
   A **Next** button submits the selected options joined as a comma-separated string.
   - Respect `max_choices` — don't let them select more than allowed.
   - The Next button should be disabled (or warn) if nothing is selected.
3. **Rating** (`rating`): render one button per integer from `min_value` to `max_value`.
   Clicking submits that number.
4. **All other types** (`number`, `percentage`, `free_text`, `distribution`,
   `hours_distribution`): leave them as chat-only — just the existing typing box is fine.
   Do **not** try to build special widgets for these.
5. **Typing must still work** for every question type, including the ones with buttons.
   An employee should be able to ignore the buttons and type instead.
6. Buttons must be **disabled while waiting** for the assistant's reply
   (look at how `is_waiting_for_response` is used today and follow the same pattern).
7. When the survey is `completed`, no answer buttons should show (the completion screen
   already handled in `render_completion` stays as is).

## Things to watch out for (Streamlit specifics)

- Streamlit reruns the whole script on every interaction. Per-question UI state (like "which
  options are currently selected" for a multiple-choice question) must live in
  `st.session_state`, and you must **reset it when the question changes** — otherwise
  selections from question 3 leak into question 4. Keying that state by the question `id`
  is a clean way to do this.
- Give every button a unique `key=` (e.g. include the question id and option text) or
  Streamlit will complain about duplicate widget IDs.
- Don't bypass the existing send flow. Reuse `queue_user_message()` + `st.rerun()` exactly
  like the chat input does in `main()`.

## Out of scope (do NOT do these)

- No backend / API changes.
- No changes to the React survey generator.
- No new question types or validation logic.
- No styling overhaul — basic, clean buttons are enough.

## How to run and test it

From the repo root:

```bash
cp survey/.env.example survey/.env     # then set OPENAI_FAKE_MODE=true so you don't need an API key
docker compose up --build
```

Then:

1. Open the generator at <http://localhost:3000>, build a survey that includes at least one
   `single_selection`, one `multiple_selection`, and one `rating` question, and click
   "Generate Chatbot" to get a `survey_url`.
2. Open that survey URL (it points at <http://localhost:8501?survey_id=...>) and start it.
3. Verify:
   - Clicking a single-choice option advances to the next question.
   - You can select/deselect multiple options, `max_choices` is respected, and **Next**
     submits them all.
   - Rating buttons submit the right number.
   - Typing still works on every question.
   - Selections don't carry over between questions.
   - Buttons are disabled while the assistant is "thinking".

> Tip: setting `OPENAI_FAKE_MODE=true` in `survey/.env` runs the backend without any OpenAI
> key (regex-based fake answers — see `DOCS.md` §6), which is perfect for developing this.

## Definition of done

- [ ] Single-selection, multiple-selection, and rating questions are answerable by clicking.
- [ ] Multiple-selection supports multi-select + a Next button, respecting `max_choices`.
- [ ] Typing still works for all question types.
- [ ] Per-question selection state resets correctly between questions.
- [ ] Buttons disable while waiting for the assistant.
- [ ] Manually tested end-to-end with the steps above.
- [ ] Only `survey/frontend/streamlit_app.py` was changed.
