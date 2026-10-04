# Apply this update to your existing checkout

The downloadable ZIP contains the complete updated source tree without `.git`,
local caches, secrets, or a virtual environment. It does not update GitHub by itself.

## 1. Protect your work

Open a terminal in your existing `lolheatmap` folder:

```bash
git status
```

Commit or otherwise back up any edits you want to retain before copying the update.
Then create a branch:

```bash
git switch -c improve/app-polish
```

## 2. Copy the updated files

Extract the ZIP. Copy the contents of its `lolheatmap` folder into your existing
checkout, replacing matching source files. Include `.github`, `.streamlit`,
`.gitignore`, and `.env.example`. Your existing `.git` directory and `.env` remain
in place because the ZIP contains neither.

Remove generated files from Git's index (this preserves the local files):

```bash
git rm -r --cached --ignore-unmatch cache __pycache__
```

The ignore rules prevent future additions. This removes cached data from the next
revision; it does not erase it from old Git history. No history rewrite is needed
for this update.

## 3. Install and try it

Create a Python 3.12 environment if needed:

```bash
python -m venv .venv
```

On Windows, these commands work without activating the environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m streamlit run app.py
```

On macOS/Linux use `.venv/bin/python` instead.

Choose **Explore demo**. Check Your heatmap, filter to Ahri, open Champions, and
reset filters. Then open Compare and try a matching champion/role. An equal start
and end time should show a helpful warning rather than an exception.

For your own games, copy `.env.example` to `.env` if you don't already have one,
set `RIOT_API_KEY`, and restart the app. Do not overwrite an existing configured
`.env`. You can also enter your key into the local app.

## 4. Review and publish your branch

```bash
git add .
git diff --cached --stat
git diff --cached -- app.py heatmap README.md
```

Expect many cache deletions; those are the repository cleanup. The old benchmark
is preserved. Verify no secrets or local cache additions appear in the staged diff.
Then commit and push:

```bash
git commit -m "Polish heatmap UX and correct benchmark comparisons"
git push -u origin improve/app-polish
```

Open a pull request for that branch on GitHub. Let the Checks workflow pass, review
the changes, and merge when ready.

## What changed

- Explicit matching comparison populations; separate comparison filters and windows.
- Sampled positions by default, with legacy reference interpolation disclosed.
- Shared comparison color scales, legends, empty states, and safe time bounds.
- Demo onboarding, readable labels, full-game statistic labels, reset controls,
  download buttons, and persistent loaded-player context.
- Modular analysis/client/cache/plot code, bounded chart cache, and atomic cache writes.
- Partial-result recovery and rate-limit status messages.
- Source-only repository hygiene, dependency locks, CI, tests, and documentation.
- More complete metadata for newly built reference bundles.

The reference was not re-fetched from Riot. Live authentication and API responses
need a real key to verify. License selection and public multi-user infrastructure
remain owner decisions; see README.md for the exact scope.
