# CCTV Enhancement (experimental)

Public **testing repo** for trying to sharpen real CCTV footage — especially clips where details matter (e.g. identifying a **lost motorcycle**: plate, rider, vehicle shape).

> **Honest status:** Nothing in this repo has produced a result that is clearly and reliably better than the originals for that goal. Outputs can look smoother or sharper at a glance but often **lose detail, add artifacts, or hallucinate** — not acceptable for evidence-style use. Treat everything here as **work in progress**, not a finished product.

Contributions, ideas, and comparison PRs are welcome.

## The problem we're trying to solve

Typical issues in our sample footage (`Original/`):

- Heavy blur and compression (HEVC/H.264, low bitrate)
- Night / uneven lighting
- Small license plates and distant subjects
- Long clips (tens of minutes) on modest GPUs (e.g. RTX 3050 4GB)

**Goal:** make plates, faces, and vehicle outlines **more readable** without inventing pixels. So far, we have **not** reached that bar.

## What we tried (and what happened)

| Approach | Tool in repo | Intent | Result so far |
|----------|--------------|--------|----------------|
| Denoise + deblur (no upscale) | [VRT](https://github.com/JingyunLiang/VRT) via `scripts/restore_cctv.py` | Reduce noise/motion blur without SR | Slightly cleaner in places; **no meaningful gain** on plate/motor ID |
| Upscale (×2 / ×4) | [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) ncnn (`tools/realesgan/`) | Sharper plates/faces | Bakeoffs on `cut2.mkv` frames — **plastic look / no real plate recovery** |
| Forensic presets | `.cursor/skills/vrt-video-restoration/scripts/forensic_presets.py` | Low σ, blend with original, avoid SR | Safer for evidence, but **still not “clear enough”** |

Restored outputs live under `Restored/` and `work/` — both **gitignored**. We are **not** publishing “before/after wins” because there aren’t any we’d stand behind yet.

## Sample footage

| File | Notes |
|------|--------|
| `Original/CUT/cut.mkv`, `cut2.mkv` | Shorter clips; good for quick bakeoffs |
| `Original/ch07.mp4` | ~54 min, 1080p — **gitignored** (too large); use `Original/packs/ch07.mp4/` |
| `Original/ch09.mp4` | ~54 min, 1080p + audio |

Unpack large files:

```bash
python scripts/pack_original.py --unpack Original/packs/ch07.mp4
```

### Forensic rule

**Do not re-encode or rewrite files under `Original/`.** For GitHub size limits, only use lossless packing:

```bash
python scripts/pack_original.py Original/ch07.mp4 Original/ch09.mp4
```

ZIP_STORED + split parts; SHA-256 verified on unpack. See `scripts/pack_original.py`.

## Repo layout

| Path | Purpose |
|------|---------|
| `Original/` | Source CCTV (bit-exact) |
| `Original/packs/` | GitHub-safe archives for large files |
| `scripts/restore_cctv.py` | VRT restore (presets: `forensic-blur`, `forensic-denoise`, `preview`) |
| `scripts/pack_original.py` | Pack/unpack originals without tampering |
| `tools/realesgan/` | Portable Real-ESRGAN ncnn-vulkan (no CUDA required) |
| `tools/VRT/` | Clone [JingyunLiang/VRT](https://github.com/JingyunLiang/VRT) locally (gitignored) |
| `.cursor/skills/vrt-video-restoration/` | VRT workflow + forensic notes |
| `.cursor/skills/realesrgan/` | Real-ESRGAN bakeoff workflow |

## Quick start (reproduce our tests)

### 1. VRT (denoise / deblur, no upscale)

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
git clone --depth 1 https://github.com/JingyunLiang/VRT tools/VRT
pip install -r tools/VRT/requirements.txt matplotlib

# Smoke test (first N frames only)
python scripts/restore_cctv.py --input Original/CUT/cut2.mkv --preset forensic-blur --max-frames 24
```

On 4GB VRAM, expect small tiles and/or downscaling — see `.cursor/skills/vrt-video-restoration/SKILL.md`.

### 2. Real-ESRGAN (upscale — compare frames first)

Always run a **small-frame bakeoff** before full video:

```powershell
# Extract ~8 frames, run ×2 and ×4, compare under work/realesrgan/
# Full commands: .cursor/skills/realesrgan/SKILL.md
tools\realesgan\realesrgan-ncnn-vulkan.exe -i work\realesrgan\bakeoff\src -o work\realesrgan\bakeoff\x4plus_s2 -n realesrgan-x4plus -s 2 -g 1 -f png
```

Default model: `realesrgan-x4plus` at **scale 2** (scale 4 often looks worse on CCTV).

## Ideas we want help with

If you contribute, please focus on **measurable readability** (can you read the plate? see distinct vehicle parts?) — not just “looks sharper.”

### Pipelines worth trying

1. **Temporal methods** — align and average/stack frames across seconds of stable video before SR (motion compensation, optical flow).
2. **Plate-specific models** — LPR / license-plate super-resolution or detection+zoom workflows instead of general SR.
3. **Classical deblur** — blind deconvolution, Wiener/Richardson–Lucy on cropped plate regions (no GAN hallucination).
4. **Lighter video transformers** — [RVRT](https://github.com/JingyunLiang/RVRT) (successor to VRT; better VRAM/runtime).
5. **Two-pass hybrid** — VRT denoise/deblur at native resolution, then **mild** upscale only on cropped ROIs (plate/face), not full frame.
6. **Preprocessing** — deinterlace, stabilize, exposure normalization; document if it helps or hurts OCR.
7. **Evaluation** — script that runs plate OCR (e.g. EasyOCR/PaddleOCR) on before/after crops and reports character confidence.

### What to avoid (for this use case)

- Full-frame ×4 GAN upscale as “evidence enhancement”
- Face-only models (GFPGAN, CodeFormer) on full CCTV without clear labeling — they **invent** facial detail
- Re-encoding `Original/` to “fit GitHub” — use `pack_original.py` only

### How to contribute

1. **Open an issue** with: clip name, method, settings, and **side-by-side crops** (plate/vehicle), not only full frames.
2. **PRs welcome** for: reproducible scripts under `scripts/`, docs, evaluation harnesses, new bakeoff presets.
3. If you beat our baseline, describe **what became readable** that wasn’t before.

No CLA required for small fixes; keep PRs focused.

## Git / large files

| File | Policy |
|------|--------|
| `Original/ch07.mp4` | gitignored — commit `Original/packs/ch07.mp4/*` |
| `Original/ch09.mp4` | can commit raw or packed |
| `Restored/`, `work/` | gitignored |

## License notes

- This repo’s scripts/docs: use and contribute freely; add a license file if you need one for your fork.
- **VRT** is [CC-BY-NC](https://github.com/JingyunLiang/VRT) (non-commercial).
- **Real-ESRGAN** — see [xinntao/Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN).

## Citation (VRT)

```
@article{liang2022vrt,
  title={VRT: A Video Restoration Transformer},
  author={Liang, Jingyun and Cao, Jiezhang and Fan, Yuchen and Zhang, Kai and Ranjan, Rakesh and Li, Yawei and Timofte, Radu and Van Gool, Luc},
  journal={arXiv preprint arXiv:2201.12288},
  year={2022}
}
```

---

**TL;DR:** Public experiment to clarify CCTV for a lost-motorcycle case. **No winning pipeline yet.** Help us find one — with honest comparisons and forensic-safe handling of `Original/`.
