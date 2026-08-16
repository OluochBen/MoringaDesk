# MoringaDesk

Curated knowledge for Moringa School learners. MoringaDesk keeps questions, answers, and community updates in one searchable, structured space so students can move from confusion to clarity faster.

---

## 🌍 Live Deployments

- **Web App:** https://moringadesk-gcvu.onrender.com/
- **API Health Check:** https://phase-5-group-7-moringadesk.onrender.com/ping
- **System Status:** `/status` rooted off the API base URL
- **API Reference:** `/api-docs`

---

## ✨ Why MoringaDesk?

### Problem
Learners repeatedly hit the same blockers during bootcamps and projects. Answers are scattered across Slack threads, mentor DMs, or forgotten Notion pages.

### Solution
MoringaDesk captures those questions and the best solutions in a single, API-first platform. Tagging, voting, and moderation ensure answers stay relevant and discoverable. Beyond Q&A, the platform surfaces FAQs, blog stories, and live service health to keep the community informed.

---

## 🧱 Architecture Overview

| Layer       | Technology                              |
|-------------|------------------------------------------|
| Frontend    | React 18, React Router, Tailwind/ShadCN  |
| Backend     | Flask 3, SQLAlchemy, Marshmallow         |
| Database    | PostgreSQL (SQLite locally)              |
| Auth        | JWT (password + Google/GitHub/Facebook)  |
| Realtime    | Flask-SocketIO (planned expansion)       |
| Testing     | Jest (frontend), Pytest (backend)        |
| CI/CD       | GitHub Actions                           |
| Design      | Figma (mobile-first system)              |

---

## 🚀 Core Capabilities

### For learners
- Sign in with email/password or social providers.
- Post questions tagged by topic and stage, add solutions, and vote on helpful answers.
- Follow discussions, receive notifications, and browse community-curated FAQs.
- Explore the public blog for success stories and platform updates.

### For facilitators & admins
- Manage users, moderate content, and curate the FAQ library.
- Publish blog posts and share upcoming changes with the community.
- Review dashboard insights (top contributors, unanswered threads, trending tags).
- Monitor system health via `/status` and share API changes through `/api-docs`.

### Platform highlights
- Fully documented REST API (`/api-docs`).
- Live system status dashboard (`/status`).
- Public feedback portal for bug reports and feature requests (`/feedback`).
- Newsletter capture, public stats, and extensible service checks.

---

## 🛠️ Getting Started

### 1. Prerequisites
- Python 3.8+
- Node.js 18+
- npm (or yarn)
- PostgreSQL (or rely on the default SQLite for local dev)

### 2. Clone the repository
```bash
git clone git@github.com:OluochBen/Phase-5-Group-7-MoringaDesk.git
cd Phase-5-Group-7-MoringaDesk
```

### 3. Backend setup
```bash
cd backend

# Virtualenv (optional but recommended)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

# Apply migrations & seed baseline data
flask db upgrade
python seed.py

# Launch API on http://127.0.0.1:5000
flask run
```

### 4. Frontend setup
```bash
cd ../frontend
npm install
npm run dev
```

Visit `http://localhost:5173` for the React app.

---

## 🔐 Environment Configuration

Copy `.env.example` to `.env` in both `backend/` and `frontend/`, then fill in values as needed:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Optional. Defaults to SQLite `instance/app.db` |
| `SECRET_KEY` / `JWT_SECRET_KEY` | Flask session + JWT signing keys. Both are mandatory in production; use independent, high-entropy values. |
| Social auth vars | `GOOGLE_...`, `GITHUB_...`, `FACEBOOK_...` enable OAuth sign-in |
| `SOCIAL_DEFAULT_REDIRECT` | Backend fallback redirect. It must also appear in `OAUTH_REDIRECT_ALLOWLIST`. |
| `OAUTH_REDIRECT_ALLOWLIST` | Comma-separated, exact frontend OAuth callback URLs. Production deployments must list every trusted frontend callback explicitly. |
| `VITE_API_BASE` | Frontend base URL for the API (default `http://localhost:5000`) |
| `VITE_SOCIAL_AUTH_CALLBACK_URL` | Frontend callback URL (default `http://localhost:5173/auth/callback`) |

```bash
cp .env.example .env
```

OAuth provider callbacks issue a short-lived, single-use exchange code. The frontend exchanges that code for a JWT through `/auth/oauth/exchange`; JWTs are never placed in redirect query strings.

---

## 🧪 Testing & Tooling

```bash
# Frontend tests
cd frontend
npm test

# Backend tests
cd ../backend
pytest
```

Continuous integration (GitHub Actions) runs linting and tests on every pull request.

---

## 📚 API & Integrations

- **REST reference:** `/api-docs` groups endpoints by domain with usage notes.
- **Status dashboard:** `/status` returns structured health checks suitable for uptime monitors.
- **Pagination:** Collection endpoints accept `page` & `per_page` parameters and respond with pagination metadata.
- **Blog API:** `/blog/posts` exposes public stories while authenticated admins can create, publish, and delete entries.

---

## 🤝 Contribution Flow

1. Create a feature branch: `git checkout -b feature/short-description`
2. Commit with clear, conventional messages.
3. Open a pull request describing the change and testing performed.
4. Ensure CI passes and request review from a maintainer.

We follow a lightweight Gitflow model and welcome issues/PRs that improve docs, tooling, or UX.

---

## 📄 License

Released under the MIT License. See `LICENSE` for details.
