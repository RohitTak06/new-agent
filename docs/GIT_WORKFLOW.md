# Git workflow (read once, follow always)

One shared repo. `main` always works. Nobody pushes to `main` directly.

## Daily routine
```bash
git checkout main && git pull                 # start of day
git checkout feature/<yourname>               # your long-lived branch
git merge main                                # bring in others' work (or: git rebase main)
# ...code...
git add . && git commit -m "intel: add chunking"
git push -u origin feature/<yourname>
# open a Pull Request on GitHub, a teammate reviews, then merge
```
Open a PR at least once a day. Small PRs rarely conflict.

## Rules
1. Edit only your own module folders. The only shared files are `contracts/`, `main.py`, `README.md`, `docker-compose.yml`, `frontend/src/App.tsx`.
2. Changing `contracts/` needs approval from all 4.
3. Commit message starts with your module: `agent:`, `crm:`, `intel:`, `sched:`.
4. Never commit `.env`. Share API keys privately, not in the repo.
5. Before merging, run `uvicorn app.main:app` and check `/docs` loads.
6. Day 8 is feature freeze. After that only bug-fix PRs.
7. Broke `main`? Whoever broke it fixes it first, before anything else.
