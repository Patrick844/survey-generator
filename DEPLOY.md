# Deploying to a Public Server (EC2)

This guide deploys the whole stack — database, backend, employee chat UI, and
admin generator — to a single Linux server using the same Docker Compose setup
you run locally. It uses plain HTTP and the server's public IP, which is enough
to share a working demo. See [Adding HTTPS + a domain](#optional-adding-https--a-domain)
for the production upgrade.

---

## 1. Launch the server

- **AMI:** Ubuntu 22.04 LTS
- **Size:** `t3.small` (2 GB RAM) or larger
- **Security group — inbound rules:**

  | Port | Source            | Purpose               |
  | ---- | ----------------- | --------------------- |
  | 22   | your IP only      | SSH                   |
  | 3000 | 0.0.0.0/0         | Admin survey builder  |
  | 8000 | 0.0.0.0/0         | Backend API           |
  | 8501 | 0.0.0.0/0         | Employee chat UI      |

> Ports 3000, 8000, and 8501 must all be public: the admin's browser calls the
> backend (8000) directly, and employees open the chat UI (8501) directly.

Note the instance's **public IP** — it's used everywhere below as `<PUBLIC_HOST>`.

## 2. Install Docker

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker            # apply the group change without logging out
```

## 3. Get the code and set secrets

```bash
git clone <your-repo-url>
cd survey-generator

# OpenAI key (and any model/fake-mode settings) live here:
cp survey/.env.example survey/.env
nano survey/.env          # set OPENAI_API_KEY=sk-...
```

## 4. Point the app at the server's public address

```bash
cp .env.prod.example .env.prod
nano .env.prod            # replace <PUBLIC_HOST> with the instance's public IP
```

`.env.prod` should end up looking like:

```env
VITE_API_BASE=http://203.0.113.10:8000
FRONTEND_URL=http://203.0.113.10:8501
```

- `VITE_API_BASE` — baked into the React admin bundle so the browser calls the
  right backend.
- `FRONTEND_URL` — the backend stamps this into the shareable employee links it
  returns to the admin.

## 5. Build and start

```bash
docker compose --env-file .env.prod up -d --build
```

`--env-file .env.prod` feeds the two public URLs into the build and runtime.
Everything else (database, internal service wiring) is handled automatically.

Check it's healthy:

```bash
docker compose ps
```

## 6. Use it

| URL                              | For       |
| -------------------------------- | --------- |
| `http://<PUBLIC_HOST>:3000`      | Admin — build a survey, click **Generate Chatbot** |
| `http://<PUBLIC_HOST>:8501`      | Employees — the link the admin shares lands here    |
| `http://<PUBLIC_HOST>:8000/docs` | Backend API docs                                    |

The employee link the admin copies will already point at
`http://<PUBLIC_HOST>:8501?survey_id=...`, so it's shareable as-is.

## Updating a running deployment

```bash
git pull
docker compose --env-file .env.prod up -d --build
```

## Stopping

```bash
docker compose down          # stop (keeps the database volume)
docker compose down -v       # stop and wipe all survey data
```

---

## Optional: adding HTTPS + a domain

Raw IP over HTTP is fine for a demo but not for real use (no encryption, ugly
URLs, and some browsers warn on HTTP form input). To upgrade:

1. Point a domain (or three subdomains — e.g. `admin.`, `api.`, `survey.`) at
   the instance's IP.
2. Put [Caddy](https://caddyserver.com/) in front as a reverse proxy — it fetches
   and renews Let's Encrypt certificates automatically.
3. Route `admin.` → generator (`:80`), `api.` → backend (`:8000`), `survey.` →
   Streamlit (`:8501`), and update `VITE_API_BASE` / `FRONTEND_URL` to the
   `https://` addresses, then rebuild.

> Streamlit uses WebSockets, so its proxy block needs WebSocket pass-through
> (Caddy handles this by default with a plain `reverse_proxy`).
