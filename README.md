# LoL Heatmaps

Heatmaps and stats for your League of Legends games on Summoner's Rift, with a
side-by-side comparison against Master+ players on the same champion and role.

- Time spent, kills, deaths and assists heatmaps (filter by champion, role, result, side, game minute)
- Win rate, KDA, CS/min, vision/min, kill participation, per-champion breakdown
- "Vs high elo" tab: your heatmap, the high-elo heatmap, and a difference map

## Quick start

```bash
git clone https://github.com/<you>/lolheat && cd lolheat
pip install -r requirements.txt
streamlit run app.py
```

Paste your Riot API key into the sidebar (get one free at https://developer.riotgames.com),
or put `RIOT_API_KEY=RGAPI-...` in a `.env` file. Dev keys expire every 24 hours.
Never commit your key; `.env` is already in `.gitignore`.

## Notes

- Everything fetched is cached in `./cache`, so repeat runs are fast. Delete it to refetch.
- A dev key allows ~100 requests per 2 minutes, so a first run of 30 games takes a few minutes.
  With a production key, set `RIOT_MIN_INTERVAL=0.1` to speed things up.
- The high-elo benchmark scans top players' recent games for your champion/role, so
  niche champions may need several minutes or return few games.
- Riot only records one position per minute; time-spent heatmaps interpolate between samples.

*This project isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games
or anyone officially involved in producing or managing Riot Games properties. Riot Games and all
associated properties are trademarks or registered trademarks of Riot Games, Inc.*

## Rebuilding the high-elo benchmark

`data/benchmark.npz` ships with the repo, so users get instant comparisons. To refresh it
(worth doing every patch or two, since the meta shifts):

```bash
python build_benchmark.py --platform na1 --platform euw1 --platform kr --matches 2000
git add data/benchmark.npz && git commit -m "Update benchmark"
```

It is resumable (Ctrl+C saves progress; re-run to continue from `./cache`). ~2,000 matches is
about 4,000 API requests, roughly 80 minutes per platform on a dev key. Champion/role combos
with fewer than `--min-games` samples are dropped and fall back to a slow live scan in the app.

By default the benchmark samples players at random from Master, Grandmaster and Challenger. Use `--tiers challenger,grandmaster` to narrow it.
