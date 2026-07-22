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

**Goal:** make CCTV footage clearer — especially **faces** and **license plates** — using local Real-ESRGAN. Prefer this skill for upscale/clarity; use [vrt-video-restoration](../vrt-video-restoration/SKILL.md) for denoise/deblur without upscaling.

Upstream: [paper](https://arxiv.org/abs/2107.10833), [repo](https://github.com/xinntao/Real-ESRGAN).  
**Runtime in this repo:** portable ncnn at `tools/realesgan/` — no CUDA, no PyTorch, **no Colab**.

## Project layout

| Path | Role |
|------|------|
| `tools/realesgan/realesrgan-ncnn-vulkan.exe` | Main binary (preferred) |
| `tools/realesgan/models/` | ncnn `.bin` / `.param` |
| `tools/Real-ESRGAN/` | Optional Python clone (full features) |
| `Original/` | Source — **never re-encode / rewrite** |
| `work/realesrgan/` | Extracted frames + bakeoff outputs |
| `Restored/` | Final images/videos |

## Models in `tools/realesgan` — pick for CCTV

| `-n` name | Bundled? | CCTV faces / plates |
|-----------|----------|---------------------|
| **`realesrgan-x4plus`** | Yes | **Default / best for real CCTV** |
| `realesrgan-x4plus-anime` | Yes | Avoid (cartoon look) |
| `realesr-animevideov3` | Yes | Avoid (anime video) |
| `realesrnet-x4plus` | No | Softer; download if needed |
| `realesr-general-x4v3` | No | Tiny + `-dn` (Python only) |

**Default for this project:** `-n realesrgan-x4plus -s 2` (×2 is usually enough for plates/faces; ×4 often oversmoothes).

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
$WORK = "work\realesrgan\bakeoff_cut2"
New-Item -ItemType Directory -Force -Path "$WORK\src","$WORK\x4plus_s2","$WORK\x4plus_s4" | Out-Null

# ~8 evenly spaced frames (fast)
& $FFMPEG -y -i $IN -vf "select=not(mod(n\,30))" -vsync vfr -q:v 2 "$WORK\src\frame_%03d.png"

# Candidates — realesrgan-x4plus only for CCTV (anime models skipped)
# -g 1 = NVIDIA when GPU 0 is Intel iGPU (check with -v)
& $EXE -i "$WORK\src" -o "$WORK\x4plus_s2" -n realesrgan-x4plus -s 2 -g 1 -f png -v
& $EXE -i "$WORK\src" -o "$WORK\x4plus_s4" -n realesrgan-x4plus -s 4 -g 1 -f png -v
```

Optional extra candidates (if user wants):

```powershell
& $EXE -i "$WORK\src" -o "$WORK\anime_s2" -n realesrgan-x4plus-anime -s 2 -g 1 -f png
& $EXE -i "$WORK\src" -o "$WORK\animevid_s2" -n realesr-animevideov3 -s 2 -g 1 -f png
```

Compare: `work/realesrgan/bakeoff_*/src` vs each output folder. Prefer the run where **plate characters** and **facial landmarks** are most readable without plastic artifacts.

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
