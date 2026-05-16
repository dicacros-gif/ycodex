# YouTube Shorts Trend Watch

This repository keeps a static `index.html` of trending YouTube Shorts candidates that match this target:

- background is mainly music
- no visible captions target
- one or two people target
- dance or short situation
- newer popular videos are placed above older links

The scheduled GitHub Actions workflow runs every day at 08:00 UTC, which is 17:00 in Asia/Seoul, and rewrites `index.html` from `shorts-data.json`.

## Update locally

```powershell
python -m pip install -r requirements.txt
python scripts/update_shorts.py
```

## Notes

Public trend sources do not reliably expose whether a Short has visible captions, spoken audio, or exactly one or two people. The updater therefore uses ranking data, titles, categories, and thumbnails to collect likely matches, then leaves a manual review note on each card.
