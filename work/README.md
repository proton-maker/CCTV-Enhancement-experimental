# work/ — testing layout

**Rule:** source frames and test runs are **never mixed**.

```
work/
├── README.md
├── datasets/              # immutable reference frames (committed)
│   ├── cut2/
│   │   ├── src/           # extracted PNGs
│   │   └── crops/
│   └── cut-motor-2308/
│       ├── src/           # zoomed ROI
│       ├── full/          # matching 1080p frames
│       ├── crops/
│       └── meta.json
├── labs/                  # one folder per test session (never overwrite)
│   ├── cut2/
│   │   ├── lab-001-historical-upscayl/
│   │   │   ├── manifest.json
│   │   │   ├── outputs/   # A00, B01, C12, …
│   │   │   ├── compare/   # grids for this lab only
│   │   │   └── RESULTS.md
│   │   └── lab-002-…/
│   └── cut-motor-2308/
│       └── lab-001-classified-v2/
└── bakeoff/               # promoted images for public README (optional)
```

## Quick commands

```powershell
# New test session (creates lab-002-my-test automatically)
python scripts/bakeoff_hybrid.py --dataset cut-motor-2308 --new-lab "pytorch-sr-tune"

# Re-run compare on existing lab
python scripts/bakeoff_hybrid.py --dataset cut-motor-2308 --lab lab-001-classified-v2 --compare-only

# RVRT on a lab
python scripts/bakeoff_rvrt.py --dataset cut2 --lab lab-001-historical-upscayl --task deblur
```

## Migration from old `*-bakeoff/` folders

```bash
python scripts/migrate_work_layout.py
```

Old paths (`work/cut2-bakeoff/`, `work/cut-motor-2308-bakeoff/`) become stub READMEs pointing here.

## What goes where

| Content | Location | Overwrite? |
|---------|----------|------------|
| Source PNGs | `datasets/<name>/src/` | Never |
| One test run | `labs/<name>/lab-NNN-slug/` | Never — create `--new-lab` |
| Comparison grids | `labs/.../compare/` | Per lab only |
| README heroes | `work/bakeoff/` | Promote best lab manually |

See `.cursor/skills/testing-lab/SKILL.md` and `cctv-adaptive-pipeline/SKILL.md`.
