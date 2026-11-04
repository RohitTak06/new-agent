# Frontend

React 18, Vite, TypeScript, Tailwind. Screens are chosen by role; the API enforces the same roles on every request.

```bash
npm install
npm run dev    # http://localhost:5173 (API at http://localhost:8000, override with VITE_API_BASE)
```

- `src/lib/`: API client, auth, shared UI, data hooks.
- `src/modules/agent/`: chat, reasoning trace, booking card.
- `src/modules/crm/`: login and staff screens.
- `src/modules/intel/`: knowledge and scoring components.
- `src/modules/channels/`: simulated WhatsApp and email views.

The login page lists the seed accounts in dev builds only. The token is kept in `localStorage`, which is acceptable for this demo; production should use an httpOnly cookie.
