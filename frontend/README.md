# Frontend

One person (suggest Riya) runs this once on Day 1 and pushes it, so everyone shares the same setup:

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install react-router-dom
npm run dev    # http://localhost:5173
```

Each person builds pages only inside their own folder under `src/modules/`:
`agent/` (Rohit), `crm/` (Dev), `intel/` (Guru), `channels/` (Riya).
Each module exports its pages; `src/App.tsx` just adds routes (small edits, so merge conflicts are easy to fix).
