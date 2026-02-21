# Raahi Dashboard

AI-powered crowd management and event safety platform.

## Quick Start

### 1. Install dependencies

```bash
cd dashboard
npm install
```

### 2. Configure environment

Edit `dashboard/.env.local` and set your Groq API key:

```
GROQ_API_KEY=your_actual_groq_key_here
```

### 3. Start all services

**Terminal 1 — Floor Planner backend (port 5000):**

```bash
cd floor_planner
python app.py
```

**Terminal 2 — Visualizer backend (port 5001):**

```bash
cd visualizer
python app.py
```

**Terminal 3 — Dashboard (port 3000):**

```bash
cd dashboard
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Pages

| Route            | Description                                                               |
| ---------------- | ------------------------------------------------------------------------- |
| `/`              | AI chat interface — describe your event and get crowd management guidance |
| `/floor-planner` | Indoor/outdoor floor plan editor (embeds Flask app on port 5000)          |
| `/visualizer`    | Crowd simulation visualizer (embeds Flask app on port 5001)               |
| `/monitoring`    | Live monitoring — under construction                                      |

## Architecture

```
dashboard/          → Next.js 14 frontend (port 3000)
floor_planner/      → Flask backend for venue layout editing (port 5000)
visualizer/         → Flask-SocketIO backend for crowd simulation (port 5001)
crowd_simulation/   → Python simulation engine
```

## API Routes

- `POST /api/chat` — Streaming chat with Groq LLM (SSE)
- `GET /api/health` — Health check for all backend services

## Tests

```bash
npm test           # Run all tests
npm run test:watch # Watch mode
```

## Tech Stack

- **Frontend:** Next.js 14, React 18, TailwindCSS, Lucide icons
- **AI:** Groq API (Llama 3.3 70B)
- **Backend:** Flask, Flask-SocketIO
- **Simulation:** Custom Python crowd dynamics engine
