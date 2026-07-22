# cut2 bakeoff — results



Source: `Original/CUT/cut2.mkv` — 8 frames in `src/` (every ~30th frame).



## Winner (best of tested)



**`outputs/05-upscayl-ultrasharp-s2/`** — Upscayl Ultrasharp ×2 via upscayl-ncnn.



- Coherent full frames (no tile mosaic)

- Slight sharpening vs original

- **Does not** make face/plate readable — source blur is the limit



## Ranking



| Rank | Folder | Tool | Verdict |

|------|--------|------|---------|

| 1 | `05-upscayl-ultrasharp-s2` | Upscayl | Best coherent upscale |

| 2 | `06-upscayl-remacri-s2` | Upscayl | Similar, slightly softer |

| 3 | `07-upscayl-hifi-s2` | Upscayl | Similar |

| 4 | `08-upscayl-standard-s2` | Upscayl | Similar |

| — | `09-rvrt-deblur-gopro` | RVRT | Native-res deblur; slightly smoother; **no ID gain** |

| — | `10-rvrt-denoise-s10` | RVRT | Light denoise (σ=10); similar to deblur; **no ID gain** |

| — | `01-realesrgan-x4plus-s2` | Real-ESRGAN ncnn | **Failed** — tile mosaic on frame_007 |

| — | `02-realesrgan-x4plus-s4` | Real-ESRGAN ncnn | Heavy files, still blurry |

| — | `03-realesrgan-anime-s2` | Real-ESRGAN ncnn | Wrong model (waxy) |

| — | `04-realesrgan-animevid-s2` | Real-ESRGAN ncnn | Wrong model (waxy) |



Visual comparisons for GitHub: `docs/bakeoff/cut2/`.



## RVRT notes



- Tasks: GoPro deblur (`005_*`), DAVIS denoise σ=10 (`006_*`)

- Tile for RTX 3050 4GB: `8 256 256` / overlap `2 32 32`

- ~70–80 s for 8×1080p frames after `deform_attn` is compiled

- Reproduce: `scripts\run_rvrt_deblur.bat` then `scripts\run_rvrt_denoise.bat`

