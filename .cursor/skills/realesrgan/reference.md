# Real-ESRGAN reference

Paper: [arxiv:2107.10833](https://arxiv.org/abs/2107.10833)  
Repo: https://github.com/xinntao/Real-ESRGAN  
ncnn Vulkan: https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan  
Local portable: `tools/realesgan/` (this CCTV repo)

## Goal (this project)

Clarify CCTV: **faces** and **license plates** readable. Local ncnn only — no Colab.

## Models

### Bundled ncnn (`tools/realesgan/models`)

| `-n` | Use |
|------|-----|
| `realesrgan-x4plus` | **CCTV default** (real-world) |
| `realesrgan-x4plus-anime` | Anime stills only |
| `realesr-animevideov3` | Anime video only |

Not bundled here: `realesrnet-x4plus`, `realesr-general-x4v3` (Python / re-download zip).

### Upstream PyTorch extras

| Model | Notes |
|-------|-------|
| `RealESRGAN_x4plus` | General default |
| `RealESRGAN_x2plus` | ×2 native |
| `RealESRGAN_x4plus_anime_6B` | Anime images, small |
| `realesr-general-x4v3` | Tiny; `-dn` denoising strength |
| `realesr-animevideov3` | Anime video |

Weights: https://github.com/xinntao/Real-ESRGAN/releases

## Inference routes (this repo)

1. **Portable ncnn** — preferred (`tools/realesgan`)
2. Python `inference_realesrgan.py` in `tools/Real-ESRGAN` — optional

Do not use online Colab demos for this project’s workflow.

## Python CLI summary

```
python inference_realesrgan.py -n RealESRGAN_x4plus -i infile -o outfile [options]

  -i --input           Input image or folder
  -o --output          Output folder
  -n --model_name      Default RealESRGAN_x4plus
  -s --outscale        Final scale (default 4; use 2 for CCTV)
  --suffix             Output suffix (default out)
  -t --tile            Tile size; 0 = no tile
  --face_enhance       GFPGAN faces (cosmetic; avoid for evidence)
  --fp32               fp32 instead of fp16
  --ext                auto | jpg | png
```

## Bakeoff rule

Always compare a few frames under `work/realesrgan/` before full-video runs. Winner = most readable plate/face without plastic artifacts.

## Citation

```
@InProceedings{wang2021realesrgan,
    author    = {Xintao Wang and Liangbin Xie and Chao Dong and Ying Shan},
    title     = {Real-ESRGAN: Training Real-World Blind Super-Resolution with Pure Synthetic Data},
    booktitle = {International Conference on Computer Vision Workshops (ICCVW)},
    date      = {2021}
}
```
