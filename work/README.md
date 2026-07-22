# work/ — local test outputs (gitignored)

All enhancement experiments live here. **Not pushed to GitHub.**

## Layout

```
work/
├── README.md                 ← this file
├── cut2-bakeoff/             ← main frame bakeoff (cut2.mkv)
│   ├── src/                  ← source frames (8 PNGs)
│   ├── crops/                ← face/plate crops for comparison
│   ├── outputs/              ← one folder per method (numbered)
│   └── RESULTS.md            ← winner + ranking
└── archive/                  ← older runs (VRT, Colab, hybrid, benches)
```

## Quick find

| Question | Where |
|----------|--------|
| Original extracted frames | `cut2-bakeoff/src/` |
| Best upscale so far | `cut2-bakeoff/outputs/05-upscayl-ultrasharp-s2/` |
| Which method won? | `cut2-bakeoff/RESULTS.md` |
| README comparison images | `docs/bakeoff/cut2/` (committed) |
| Old experiments | `archive/` |

## Re-run bakeoff

```bash
python scripts/bakeoff_upscayl.py
```

Requires local `tools/` setup — see root `README.md` and `tools/README.md`.
