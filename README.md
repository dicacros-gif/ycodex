# YouTube Shorts Trend Watch

This repository keeps a static `index.html` of trending YouTube Shorts candidates that match this target:

- background is mainly music
- no visible captions target
- one or two people target
- dance or short situation
- video duration up to 40 seconds
- videos are prioritized by a combined views + likes signal
- newer popular videos are accumulated above older links
- videos are globally deduplicated, so the same YouTube ID appears in only one tab
- all candidates are accumulated only from 10,000 views and up

The scheduled GitHub Actions workflow runs every day at 20:00 UTC and retries at 21:30 UTC, which is 05:00 and 06:30 in Asia/Seoul. It updates `shorts-data.json`, `insights-data.json`, and `index.html` on a GitHub-hosted runner.

## Region Tabs

`index.html` renders separate tabs for 글로벌, KR, US, JP, 멕시코, 독일, 브라질, 인도네시아, 아르헨티나, 필리핀, 스페인, 이탈리아, 프랑스, 우즈베키스탄, 알제리, 카자흐스탄, and 베트남.

## Sources

- Vidirun Top 50 Short-Form Videos
- Playboard Most Viewed YouTube Shorts
- RedToolBox Top Shorts
- TubeTrending 48H new Shorts
- YTTrack regional/category trend charts
- Chartika regional charts
- TrendsFox Trending Shorts
- Top1Trend YouTube Trending
- YouTube Data API official search
- YouTube Shorts keyword searches through `yt-dlp`

## Manual server run

Use the `Update YouTube Shorts` workflow's `workflow_dispatch` button in GitHub Actions. The repository is not intended to depend on a local scheduled job.

## Notes

Public trend sources do not reliably expose whether a Short has visible captions, spoken audio, or exactly one or two people. The updater therefore uses ranking data, titles, categories, thumbnails, views, likes, duration, and publish dates to collect likely matches and write trend-based analysis.
