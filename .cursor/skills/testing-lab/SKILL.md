---
name: testing-lab
description: >-
  CCTV testing lab: datasets vs numbered labs, README focus goals (plate, face,
  motor, scene, brighten), linear A→B→C→D chains with final outputs. Default
  mode is chains (not 13 parallel folders). Verify plate/face crops before SR.
---

# Testing Lab Layout

**Problem:** 13+ parallel `outputs/` folders are confusing — no clear A→B→C→D flow, no final result, plate crop can hit the wrong region (tire).

**Solution:** default **`--mode chains`** — one linear pipeline per goal → `outputs/chains/` + `outputs/final/`.

## README goals → chains (mandatory)

| Focus | Chain (read left → right) | Final output |
|-------|---------------------------|--------------|
| **plate** | crop plate → CLAHE → PyTorch SR ×3 | `outputs/final/plate_frame_XXX.png` |
| **face** | crop face → CLAHE → SR ×2 → CodeFormer (optional) | `outputs/final/face_frame_XXX.png` |
| **motor** | baseline → CLAHE → **Upscayl** (optional) → SR ×2 | `outputs/final/motor_frame_XXX.png` |
| **scene** | full 1080p → SR ×2 | `outputs/final/scene_frame_XXX.png` |
| **brighten** | baseline → CLAHE | `outputs/final/brighten_frame_XXX.png` |

Full matrix (old style): `--mode explore` → `outputs/explore/` only when user explicitly wants tool comparison.

## Verify crops BEFORE any lab run

**Agent must check images — never assume fractions are correct.**

```
work/datasets/<dataset>/crops/
  plate_ref.png      ← must show FRONT plate below headlight
  face_ref.png       ← rider head at TOP of ROI
  regions_overlay.png ← green=plate, cyan=face
```

Regions live in `meta.json` → `focus_regions`. Source: `scripts/focus_regions.py`.

### cut-motor-2308 plate trap

Rider faces camera on red scooter. Plate is **front fender below headlight** (`y 0.55–0.73`), **NOT** rear tire (`y 0.85+`). Lab-002 failed because old crop hit the wheel.

## Layout

```
work/datasets/<dataset>/
  src/               ← ROI frames (immutable)
  full/              ← 1080p (scene goal)
  crops/plate_ref.png  ← QA before lab
  meta.json          ← focus_regions

work/labs/<dataset>/lab-NNN-<slug>/
  CHAIN.md           ← A→B→C→D per goal
  WINNERS.md         ← best frame + best stage (after visual review)
  RESULTS.md         ← status table
  outputs/
    chains/<goal>/01-A-.../02-B-.../03-C-.../04-final/
    final/           ← one PNG per goal (THE answer)
  compare/
    chain_<goal>_frame_XXX.png   ← linear step comparison
    compare_finals_frame_XXX.png ← all goals side-by-side
    focus_<goal>_frame_XXX.png   ← per-goal patch zoom
```

## Commands

```powershell
# Default: linear chains + finals (recommended)
python scripts/bakeoff_hybrid.py --dataset cut-motor-2308 --new-lab "chains-v3" --goals plate,face,motor

# Full tool matrix (only when user asks to compare all tools)
python scripts/bakeoff_hybrid.py --dataset cut-motor-2308 --new-lab "explore-all" --mode explore

# Rebuild compare/ only
python scripts/bakeoff_hybrid.py --dataset cut-motor-2308 --lab lab-003-chains-v3 --compare-only
```

## After visual review

1. Pick best **frame** (usually `frame_002` for cut-motor-2308).
2. Pick best **chain step** per goal → write `WINNERS.md`.
3. Promote `compare/chain_*` or `outputs/final/*` → `work/bakeoff/` for README.

## Agent rules

1. **New experiment → `--new-lab`** — never overwrite.
2. **Default `--mode chains`** — not explore, unless user wants full matrix.
3. **Check `crops/plate_ref.png`** before plate chain — if tire visible, fix `meta.json` first.
4. **Never write into `datasets/`** except via extract scripts.
5. Document `WINNERS.md` + `RESULTS.md` every lab.
6. **Brighten before upscale**; Upscayl optional between B and C on motor chain.
7. Compare labs via `outputs/final/` — not by mixing chain folders.

## Related

- Regions: `scripts/focus_regions.py`, `scripts/work_lab.py` → `PIPELINE_CHAINS`
- Runner: `scripts/bakeoff_hybrid.py`
- Pipeline: [cctv-adaptive-pipeline](../cctv-adaptive-pipeline/SKILL.md)
