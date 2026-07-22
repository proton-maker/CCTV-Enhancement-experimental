# Winners — lab-002 (frame_002, visual review)

Picked from `compare/compare_all_frame_002.png` and `compare/focus_*_frame_002.png`.
**Do not treat as forensic evidence** — README goal still not achieved for plate/face OCR.

## Best frame

**`frame_002.png`** (`23:17.67`) — rider most centered, plate white patch visible below headlight.

| Frame | Why not winner |
|-------|----------------|
| frame_001 | Earlier; rider smaller in ROI |
| frame_003 | Similar but slightly more motion blur |

## Best stage per focus (from combined grid)

| Focus | Winner | Runner-up | Verdict |
|-------|--------|-----------|---------|
| **brighten** | `B04-clahe-brighten` | `B03-opencv-denoise` | B04 lifts dark scene; B03 alone too soft |
| **motor** | `C12-pytorch-sr-x2` | `B04` then `C12` chain | Sharpest fairing edges; use after B04 |
| **plate** | *(none)* | `B04` on correct crop (future) | C13 failed — crop hit **rear tire**, not front plate |
| **face** | `B04-clahe-brighten` | `C14` after crop fix | CodeFormer 0 detections; C14 gray = double-crop bug |
| **scene** | `C15-scene-pytorch-sr-x2` | baseline full | Marginal stall context improvement |

## Recommended chain for next lab (A→B→C→D)

```
motor:  A00 baseline → B04 CLAHE → C12 PyTorch SR x2     → final/
plate:  A00 plate crop → B04 CLAHE → C13 PyTorch SR x3   → final/  (fix crop first!)
face:   A00 face crop → B04 CLAHE → C14 PyTorch SR x2   → final/  (skip CodeFormer until detections work)
```

Optional Upscayl step (if installed): insert **between B and C** on motor ROI — `B04 → Upscayl Ultrasharp x2 → C12`.

## Known failures this lab

1. **Plate crop** pointed at rear wheel (`y 0.48–0.92`) — fixed in `scripts/focus_regions.py` + `meta.json focus_regions`.
2. **C14 focus grid** re-cropped an already face-cropped image → gray tiles — fixed in `build_focus_grid`.
3. **RVRT** skipped — MSVC `cl` not in PATH.
