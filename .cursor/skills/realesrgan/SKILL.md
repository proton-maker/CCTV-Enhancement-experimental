---
name: realesrgan
description: >-
  Upscale and clarify CCTV stills/video with Real-ESRGAN (xinntao/Real-ESRGAN)
  via tools/realesgan ncnn-vulkan — faces, license plates, and general clarity.
  Prefer small-frame bakeoffs before full video. Use when the user asks for
  Real-ESRGAN, realesrgan, ESRGAN, ncnn-vulkan, plate/face clarity, or CCTV
  upscale restoration.
---

# Real-ESRGAN (CCTV)

**Goal:** make CCTV footage clearer — especially **faces** and **license plates** — using local Real-ESRGAN. Prefer this skill for upscale/clarity; use [codeformer](../codeformer/SKILL.md) for generative face restore on zoomed ROI; use [vrt-video-restoration](../vrt-video-restoration/SKILL.md) or [rvrt-video-restoration](../rvrt-video-restoration/SKILL.md) for denoise/deblur without upscaling. For the full chained adaptive flow (low-light → deblur → SR → face), see [cctv-adaptive-pipeline](../cctv-adaptive-pipeline/SKILL.md).

## Repo documentation

- **English only** for `README.md` and `work/*/RESULTS.md`.
- **Generic goal** in README — plates, faces, vehicles. No private case names or incident-specific narrative.
- **Surgical edits:** change only the lines/sections that need updating (one table row, one command, one verdict). Do **not** rewrite the whole README.
- **Grow downward:** append new bakeoff results or tools; avoid restructuring unrelated sections.
- **README images:** `![caption](work/bakeoff/...)` with files committed under `work/bakeoff/`. Never swap images for URL-only text. Raw URL list: `work/bakeoff/cut2/image_urls.md`. No emojis — text or shields.io badges for icons.
- After bakeoff: `python scripts/build_bakeoff_docs.py` then update only the image blocks in README.
- See this skill § “Repo documentation” for README edit rules (not in the public README).

Upstream: [paper](https://arxiv.org/abs/2107.10833), [repo](https://github.com/xinntao/Real-ESRGAN).  
**Runtime:** portable ncnn in `tools/realesgan/` (gitignored — see [`tools/README.md`](../../../tools/README.md)). For extra models, use [Upscayl](https://github.com/upscayl/upscayl) via `scripts/bakeoff_upscayl.py`.

## Project layout

| Path | Role |
|------|------|
| `tools/realesgan/realesrgan-ncnn-vulkan.exe` | Main binary (install locally) |
| `tools/realesgan/models/` | ncnn `.bin` / `.param` |
| `tools/upscayl/` + `tools/upscayl-ncnn/` | Upscayl models + CLI (bakeoff) |
| `Original/` | Source — **never re-encode / rewrite** |
| `work/datasets/cut2/src/` | Extracted bakeoff frames (indoor face) |
| `work/datasets/cut-motor-2308/src/` | Motorcycle ROI — `cut.mkv` **23:17.33–23:18** |
| `work/labs/<dataset>/lab-NNN-*/outputs/` | Per-lab classified outputs (A/B/C/D/E) |
| `work/labs/cut2/lab-001-historical-upscayl/` | Historical cut2 winner lab |
| `work/bakeoff/cut2/` | README comparison images (committed) |
| `Restored/` | Final videos (gitignored) |

## Models in `tools/realesgan` — pick for CCTV

| `-n` name | Bundled? | CCTV faces / plates |
|-----------|----------|---------------------|
| **`realesrgan-x4plus`** | Yes | **Default / best for real CCTV** |
| `realesrgan-x4plus-anime` | Yes | Avoid (cartoon look) |
| `realesr-animevideov3` | Yes | Avoid (anime video) |
| `realesrnet-x4plus` | No | Softer; download if needed |
| `realesr-general-x4v3` | No | Tiny + `-dn` (Python only) |

**Default for this project:** `-n realesrgan-x4plus -s 2` (×2 is usually enough for plates/faces; ×4 often oversmoothes).

## README focus goals (which SR path?)

| Goal | When to use Real-ESRGAN | Stage in bakeoff |
|------|-------------------------|------------------|
| **plate** | After `B04-clahe-brighten`; on **plate-zoom** crop from `meta.json` | `chains/plate/03-C-sr-x3` |
| **face** | After brighten; on **face-zoom** crop only | `chains/face/03-C-sr-x2` |
| **motor** | On full ROI after brighten (+ optional Upscayl) | `chains/motor/04-C-sr-x2` |
| **scene** | On `datasets/*/full/` 1080p frames | `chains/scene/02-C-sr-x2` |
| **brighten** | **Not SR** — use `B04-clahe-brighten` first | Chain step 02-B |

**Plate crop trap (cut-motor-2308):** plate is front fender `y 0.55–0.73`, NOT rear tire. Check `crops/plate_ref.png` before any lab.

See [testing-lab](../testing-lab/SKILL.md) for chain layout and `outputs/final/`.

**Small ROI warning (< ~1000px wide):** ncnn **×2 produces tile-mosaic grids** on motor/face crops. Use instead:
- ncnn **×4** (`-s 4`) — softer but no grid, or
- **PyTorch** Real-ESRGAN x2 via `scripts/bakeoff_hybrid.py` → `C12-pytorch-sr-x2` (uses CodeFormer weights path).

Classified bakeoff (chains): `python scripts/bakeoff_hybrid.py --dataset cut-motor-2308 --new-lab "name" --mode chains`

## Mandatory: small-frame bakeoff first

Never run full-video Real-ESRGAN until the user has compared a few frames. Always:

1. Extract a **small** set of frames (≈4–12), preferably where a face or plate is visible.
2. Run candidate models / scales into side-by-side folders.
3. Let the user pick the winner.
4. Only then process the full clip (or more frames).

### Quick bakeoff (PowerShell, from repo root)

```powershell
$FFMPEG = "$env:LOCALAPPDATA\Microsoft\WinGet\Links\ffmpeg.exe"
$EXE = "tools\realesgan\realesrgan-ncnn-vulkan.exe"
$IN = "Original\CUT\cut2.mkv"
$WORK = "work\cut2-bakeoff"
New-Item -ItemType Directory -Force -Path "$WORK\src","$WORK\outputs\01-realesrgan-x4plus-s2","$WORK\outputs\02-realesrgan-x4plus-s4" | Out-Null

# ~8 evenly spaced frames
& $FFMPEG -y -i $IN -vf "select=not(mod(n\,30))" -vsync vfr -q:v 2 "$WORK\src\frame_%03d.png"

& $EXE -i "$WORK\src" -o "$WORK\outputs\01-realesrgan-x4plus-s2" -n realesrgan-x4plus -s 2 -g 1 -f png -t 128 -v
& $EXE -i "$WORK\src" -o "$WORK\outputs\02-realesrgan-x4plus-s4" -n realesrgan-x4plus -s 4 -g 1 -f png -t 128 -v
```

Upscayl candidates: `python scripts/bakeoff_upscayl.py` → `outputs/05-upscayl-ultrasharp-s2` etc.

Compare: `work/cut2-bakeoff/src` vs each folder under `outputs/`. Update `work/cut2-bakeoff/RESULTS.md` with the winner.

### After winner chosen — full video

```powershell
$FFMPEG = "$env:LOCALAPPDATA\Microsoft\WinGet\Links\ffmpeg.exe"
$EXE = "tools\realesgan\realesrgan-ncnn-vulkan.exe"
$WORK = "work\realesrgan\cut2_full"
New-Item -ItemType Directory -Force -Path "$WORK\tmp_frames","$WORK\out_frames" | Out-Null

& $FFMPEG -y -i Original\CUT\cut2.mkv -qscale:v 1 -qmin 1 -qmax 1 -fps_mode passthrough "$WORK\tmp_frames\frame%08d.jpg"
& $EXE -i "$WORK\tmp_frames" -o "$WORK\out_frames" -n realesrgan-x4plus -s 2 -g 1 -f jpg
& $FFMPEG -y -i "$WORK\out_frames\frame%08d.jpg" -i Original\CUT\cut2.mkv `
  -map 0:v:0 -map 1:a:0? -c:a copy -c:v libx264 -pix_fmt yuv420p Restored\cut2_realesrgan.mkv
```

Keep work folders under `work/` — never under `Original/`.

## ncnn CLI

```
realesrgan-ncnn-vulkan.exe -i infile -o outfile [options]

  -i input-path     image or directory
  -o output-path    image or directory
  -s scale          2 | 3 | 4 (default 4; prefer 2 for CCTV)
  -t tile-size      >=32 / 0=auto
  -m model-path     default=models
  -n model-name     realesrgan-x4plus | realesrgan-x4plus-anime | realesr-animevideov3
  -g gpu-id         auto or 0,1,2
  -j load:proc:save threads (default 1:2:2)
  -x                TTA (slower, slightly better)
  -f format         jpg | png | webp
  -v                verbose
```

**Caveat:** ncnn tiles then stitches — possible block seams; results can differ from PyTorch.

## Optional: Python path (`tools/Real-ESRGAN`)

Only if ncnn is insufficient (e.g. need `realesr-general-x4v3` + `-dn`, or `--outscale` fractional):

```bash
cd tools/Real-ESRGAN
pip install basicsr facexlib gfpgan
pip install -r requirements.txt
python setup.py develop
# download weights into weights/
python inference_realesrgan.py -n RealESRGAN_x4plus -i inputs --outscale 2
```

`--face_enhance` (GFPGAN) invents face detail — skip for forensic evidence unless the user explicitly wants cosmetic enhancement.

## Workflow checklist

```
Real-ESRGAN CCTV:
- [ ] Goal = clearer faces / plates (not anime)
- [ ] Never write into Original/
- [ ] Extract small frame set first
- [ ] Bakeoff: realesrgan-x4plus @ -s 2 vs -s 4 (add anime only if asked)
- [ ] User picks winner
- [ ] Full video only after pick
- [ ] Output under Restored/
```

## Related

- Denoise/deblur without SR: [vrt-video-restoration](../vrt-video-restoration/SKILL.md)
- Upstream model zoo / FAQ: see [reference.md](reference.md)
