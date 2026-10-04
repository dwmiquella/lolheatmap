# Contributing

Use Python 3.12 and the setup instructions in README.md. Work on a branch and keep
changes focused. Install requirements-dev.txt and run Ruff plus pytest before opening
a pull request. Describe the user-visible change and how it was checked.

When changing analytics, test the affected selection or calculation with small,
fictional fixtures. Preserve the same champion, role, queue, orientation, time
window, and position method in comparisons. Explain remaining cohort differences.

Do not commit API keys, `.env`, `.streamlit/secrets.toml`, cached player data, virtual
environments, or bytecode. Add screenshots or figures only when they explain a UI
change. Keep generated documentation examples free of real player identifiers.

Benchmark updates should state sample sizes, regions, patches, sampling method,
queue, and whether collection completed. Never label all lobby participants as
verified Master+ accounts. Restart the app after updating the benchmark bundle.
