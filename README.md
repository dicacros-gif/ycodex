# YouTube Shorts Trend Watch

This repository keeps a static `index.html` of trending YouTube Shorts candidates that match this target:

- background is mainly music
- no visible captions target
- one or two people target
- dance or short situation
- newer popular videos are placed above older links

The scheduled GitHub Actions workflow runs every day at 08:00 UTC, which is 17:00 in Asia/Seoul, and rewrites `index.html` from `shorts-data.json` on a GitHub-hosted runner.

## Sources

- Vidirun Top 50 Short-Form Videos
- Playboard Most Viewed YouTube Shorts
- RedToolBox Top Shorts
- TrendsFox Trending Shorts
- Top1Trend YouTube Trending
- YouTube Shorts keyword searches through `yt-dlp`

## Manual server run

Use the `Update YouTube Shorts` workflow's `workflow_dispatch` button in GitHub Actions. The repository is not intended to depend on a local scheduled job.

## Notes

Public trend sources do not reliably expose whether a Short has visible captions, spoken audio, or exactly one or two people. The updater therefore uses ranking data, titles, categories, and thumbnails to collect likely matches, then leaves a manual review note on each card.
