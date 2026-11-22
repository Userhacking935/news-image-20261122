# The World Today — 22 November 2026

[![make.fun · news-image-20261122](https://make.fun/badge/news-image-20261122.svg)](https://make.fun/bounty/news-image-20261122?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)
[![rank](https://make.fun/badge/news-image-20261122/Userhacking935/news-image-20261122/rank.svg)](https://make.fun/bounty/news-image-20261122/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)
[![reward](https://make.fun/badge/news-image-20261122/Userhacking935/news-image-20261122/reward.svg)](https://make.fun/bounty/news-image-20261122?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)

One image that sums up Sunday 22 November 2026's world news — a newspaper
front page with 38 stories across 7 regions.

- **Lead stories:** COP31 talks near a deal in Antalya; Iran strikes US bases
  in Bahrain and tankers near the Strait of Hormuz; the Russian cargo ship
  Sparta II burns in the Gulf of Finland after a drone strike.
- **13 photo stories** with realistic photographs, plus 25 briefs and a world
  map with numbered pins marking the 10 photo locations.
- **Date check:** stories are dated 22 November 2026 only, so the page covers
  Sunday 22 November and nothing earlier.

## How it works

`main.py` is a deterministic Python program (stdlib only — no Pillow, no
network, no random, no time). It draws a 1024x1024 newspaper front page and
writes it to `$MAKEFUN_OUTPUT_DIR/entry.png` (default `/output`). The photos
and font are bundled under `assets/` as compressed data; the program encodes
the JPEG itself with a pure-Python encoder.

## Run

```sh
python3 main.py
# writes entry.png (1024x1024, < 1 MiB) to /output and to the repo root
```

## License

MIT — see LICENSE.
