# tools/ — local dependencies (gitignored)



Clone or download these into `tools/` on your machine. **This folder is not committed to GitHub.**



## Required for testing



| Tool | Install | Used for |

|------|---------|----------|

| **VRT** | `git clone --depth 1 https://github.com/JingyunLiang/VRT tools/VRT` | Video denoise/deblur (`scripts/restore_cctv.py`) |

| **RVRT** | `git clone --depth 1 https://github.com/JingyunLiang/RVRT tools/RVRT` | Lighter temporal deblur/denoise (`scripts/bakeoff_rvrt.py`) |

| **Real-ESRGAN ncnn** | [Real-ESRGAN-ncnn-vulkan releases](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases) → extract to `tools/realesgan/` | Frame upscale bakeoff |

| **Upscayl** | `git clone --depth 1 https://github.com/upscayl/upscayl tools/upscayl` | Extra ncnn models |

| **upscayl-ncnn** | [upscayl-ncnn releases](https://github.com/upscayl/upscayl-ncnn/releases) → `tools/upscayl-ncnn/` | Upscayl CLI (`upscayl-bin.exe`) |
| **CodeFormer** | `git clone --depth 1 https://github.com/sczhou/CodeFormer tools/CodeFormer` | Face restoration on zoomed ROI (`scripts/bakeoff_hybrid.py`) |



## RVRT on Windows (extra steps)



RVRT JIT-compiles a CUDA extension (`deform_attn`) on first import.



1. **CUDA Toolkit** — e.g. `winget install Nvidia.CUDA`

2. **MSVC** — Visual Studio Build Tools with “Desktop development with C++”

3. Run via `scripts\run_rvrt_deblur.bat` (sets `vcvars64` + `CUDA_HOME`)

4. Apply local patches documented in `.cursor/skills/rvrt-video-restoration/SKILL.md`



## Python deps (VRT / RVRT)



```bash

pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124

pip install -r tools/VRT/requirements.txt matplotlib pillow opencv-python

pip install -r tools/RVRT/requirements.txt

```



## CodeFormer (face restoration)

```bash
git clone --depth 1 https://github.com/sczhou/CodeFormer tools/CodeFormer
cd tools/CodeFormer
pip install -r requirements.txt
python basicsr/setup.py develop
python scripts/download_pretrained_models.py facelib
python scripts/download_pretrained_models.py CodeFormer
```

**Python 3.13:** patch `basicsr/setup.py` `get_version()` — see `.cursor/skills/codeformer/SKILL.md`.

Hybrid bakeoff:

```bash
python scripts/bakeoff_hybrid.py --bakeoff work/cut-motor-2308-bakeoff
```



## FFmpeg



```powershell

winget install Gyan.FFmpeg

```



## Licenses



- VRT / RVRT — CC-BY-NC

- Real-ESRGAN — BSD

- CodeFormer — NTU S-Lab License 1.0

- Upscayl / upscayl-ncnn — AGPL-3.0

