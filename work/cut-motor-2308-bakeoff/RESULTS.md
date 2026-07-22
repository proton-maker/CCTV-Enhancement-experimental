# cut-motor bakeoff — ROI source frames

Source: `Original/CUT/cut.mkv` **23:17.33–23:18** (red bike + rider at food stall).

Template / reference: `crops/motor_src.png`.

Approach/passing frames (23:15–23:17) are **excluded** — they boxed the wrong distant/blurred bike.

## Layout

| Path | Purpose |
|------|---------|
| `src/` | **Zoomed ROI** (×2 LANCZOS) — bakeoff input |
| `full/` | Matching full 1080p frames |
| `crops/motor_ref.png` | Same as `motor_src.png` |
| `crops/motor_src.png` | User reference crop |
| `crops/box_*.png` | Full frame + green ROI box |
| `meta.json` | Per-frame timestamps and boxes |

## Frame timeline

| Frame | Video time | Scene |
|-------|------------|-------|
| `frame_001` | 23:17.33 | Red bike at stall |
| `frame_002` | 23:17.67 | Rider visible |
| `frame_003` | 23:18.00 | Target moment |

## Regenerate

```bash
python scripts/extract_roi_bakeoff.py \
  --template work/cut-motor-2308-bakeoff/crops/motor_src.png \
  --out work/cut-motor-2308-bakeoff \
  --start 23:17.33 --end 23:18 --frames 3 --upscale 2 --dense-fps 15
```
