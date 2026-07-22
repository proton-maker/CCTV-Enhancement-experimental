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



## FFmpeg



```powershell

winget install Gyan.FFmpeg

```



## Licenses



- VRT / RVRT — CC-BY-NC

- Real-ESRGAN — BSD

- Upscayl / upscayl-ncnn — AGPL-3.0

