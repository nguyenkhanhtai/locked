# Locked - Study Toolkit

A local, distraction-free study and productivity toolkit tailored for Data Structures & Algorithms (IT003) and computer science coursework.

---

## Features

### 1. Task & Deadline Management
- **Task Organization**: Create, edit, and organize tasks with 5 levels of priority, custom label tags, and due dates.
- **Visual Calendar & Gantt Timeline**: Schedule view using an optimal **Greedy Interval Partitioning** algorithm implemented with a **Min-Heap** to lay out overlapping deadlines without collision in \(O(N \log N)\) time.
- **Search & Quick Filtering**: Filter by priority level, status, or labels.

### 2. Study Workspace
- **Project & Sub-project Hierarchy**: Multi-level tree structure with recursive breadcrumb navigation.
- **Problem Kanban Boards**: Deconstruct complex algorithmic and theoretical problems into columns (e.g. *Knowledge*, *Questions*, *Inferences*).
- **Rich Markdown Notes & LaTeX**: Write notes with full Markdown syntax and render mathematical equations via KaTeX (`$...$` for inline, `$$...$$` for display math).
- **Inline Mentions (`@`)**: Seamlessly cross-reference projects, problems, and notes with auto-completing search.

### 3. Focus Blocker (Hard Lock)
- **Unbreakable Commitment (Ulysses Contract)**: Block distracting websites and URLs for a dedicated period (up to 6 hours). Once activated, the backend strictly prevents cancellation or deletion until the timer reaches zero.
- **Granular Blocking Scopes**:
  - *Domain level*: Block entire websites (e.g. `facebook.com`, `tiktok.com`).
  - *Exact link / Path level*: Block specific sub-links (e.g. `youtube.com/shorts`) while retaining access to educational lectures.
- **Intervention Screen & Countdown**: Intercepts blocked visits with real-time countdown timers and motivational quotes.
- **Dual Enforcement Mechanisms**:
  - *Browser Extension (Chrome / Brave / Edge)*: Lightweight Manifest V3 extension in `./extension` with dynamic network request redirection.
  - *OS-Level Daemon (Linux)*: `sudo python3 scripts/blocker_daemon.py` to sync active locks directly into `/etc/hosts`.

---

## Getting Started

### Requirements
- Python `>= 3.10` (tested on Linux, macOS, and Windows)
- `uv` (recommended) or standard `python3 -m venv`

### Installation

```bash
# 1. Clone repository
git clone https://github.com/nguyenkhanhtai/locked.git
cd locked

# 2. Create virtual environment and install dependencies
uv venv
uv pip install -e .
# Or install directly with test tools:
uv pip install starlette uvicorn jinja2 python-multipart pytest httpx
```

### Running with Docker (Recommended)

To run the full suite (Web App + Background Blocker Daemon) in the background with Docker:

```bash
# Build and run all services in the background
docker compose up -d --build

# View live application and blocker daemon logs
docker compose logs -f

# Stop and cleanly restore hosts
docker compose down
```

When started with Docker Compose, the `blocker-daemon` automatically syncs active focus locks directly into `/etc/hosts` of your host machine, enforcing website blocking across all browsers on your computer without needing local systemd setup!

Open **`http://127.0.0.1:8765`** in your browser. All tasks, study notes, and settings are automatically persisted in `./backend/db` and `./backend/user`.

---

### Running the Application Manually

```bash
python backend/run.py
```
Then open your browser and navigate to:
**`http://127.0.0.1:8765`**

*(To change port, set `LOCKED_PORT=8080 python backend/run.py`)*

---

## Running the Automated Test Suite

Locked includes a comprehensive automated test suite covering database operations, referential integrity, and all REST API endpoints:

```bash
python -m pytest tests -v
```

---

## Architecture & Data Structures

- **Backend**: Python Starlette ASGI framework with clean async route handlers.
- **Database**: Embedded SQLite with `PRAGMA foreign_keys = ON` for ACID compliance and cascade deletions.
- **Algorithm**:
  - *Min-Heap / Priority Queue*: Interval Partitioning for timeline scheduling.
  - *Tree Traversal*: Hierarchical project path resolution.
- **Frontend**: Responsive HTML5, Vanilla JavaScript, CSS custom properties design tokens, and KaTeX for LaTeX formulas.
