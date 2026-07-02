# Deploy BenchPilot to lipskerov.github.io

The static build lives in `bench-to-decision/site/` — pure HTML/CSS/JS, no server.
It runs entirely in the browser (static-backend.js reimplements the API; data is JSON).

## Steps (host at https://lipskerov.github.io/benchpilot/)
1. Rebuild if data changed:  `python3 web-build/build_static.py`
2. Copy the build into your personal-site repo:
     cp -R site/  /path/to/lipskerov.github.io/benchpilot
3. In the lipskerov.github.io repo:  git add benchpilot && git commit -m "add BenchPilot" && git push
4. It goes live at:  https://lipskerov.github.io/benchpilot/
   (GitHub Pages is already on for username.github.io repos.)

## Notes
- All asset paths are relative, so the /benchpilot/ subpath works out of the box.
- `.nojekyll` is included so Pages serves files verbatim.
- Edits (new tasks/projects, drag status, uploaded photos) persist in the visitor's
  localStorage; clear it to reset to the seeded demo.
- Engine is offline (BM25 + templates) — no watsonx keys are exposed.
