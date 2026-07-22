# VRT reference

Paper: [arxiv:2201.12288](https://arxiv.org/abs/2201.12288)  
Repo: https://github.com/JingyunLiang/VRT  
Models/results: https://github.com/JingyunLiang/VRT/releases  

Local-only workflow in this project (Colab tooling removed).

## Capabilities (SOTA margins from paper)

- Video SR (REDS, Vimeo90K, Vid4, UDM10): +0.33~0.51 dB
- Video deblurring (GoPro, DVD, REDS): +1.47~2.15 dB
- Video denoising (DAVIS, Set8): +1.56~2.16 dB
- Video frame interpolation: +0.28~0.45 dB
- Space-time video SR: +0.26~1.03 dB

## Architecture (short)

Multi-scale stack of:

1. **TMSA** — temporal mutual self-attention on short clips (joint motion / align / fuse) + self-attention for features; sequence shift every other layer for cross-clip interaction
2. **Parallel warping** — fuse neighbors via parallel feature warping

Parallel frame prediction + long-range temporal modelling (vs sliding-window or pure RNN).

## Task IDs

| ID | Task |
|----|------|
| 001 | VSR BI REDS 6 frames |
| 002 | VSR BI REDS 16 frames |
| 003 | VSR BI Vimeo 7 frames |
| 004 | VSR BD Vimeo 7 frames |
| 005 | Deblur DVD |
| 006 | Deblur GoPro |
| 007 | Deblur REDS |
| 008 | Denoise DAVIS (σ 0–50) |
| 009 | VFI Vimeo 4 frames |
| 010 | Space-time SR = compose 003 + 009 |

## Official test examples

```bash
cd tools/VRT
pip install -r requirements.txt

# 001 REDS VSR 6f
python main_test_vrt.py --task 001_VRT_videosr_bi_REDS_6frames --folder_lq testsets/REDS4/sharp_bicubic --folder_gt testsets/REDS4/GT --tile 40 128 128 --tile_overlap 2 20 20 --save_result

# 008 Denoise
python main_test_vrt.py --task 008_VRT_videodenoising_DAVIS --sigma 10 --folder_lq testsets/Set8 --folder_gt testsets/Set8 --tile 12 256 256 --tile_overlap 2 20 20 --save_result

# Custom folder (no GT)
python main_test_vrt.py --task 001_VRT_videosr_bi_REDS_6frames --folder_lq testsets/your/own --tile 40 128 128 --tile_overlap 2 20 20 --save_result
```

`main_test_vrt.py` auto-downloads pretrained weights and many test sets (not full Vimeo-90K).

## License

CC-BY-NC (non-commercial). Portions from KAIR (MIT), BasicSR / Video Swin / mmediting (Apache 2.0).

## Citation

```
@article{liang2022vrt,
  title={VRT: A Video Restoration Transformer},
  author={Liang, Jingyun and Cao, Jiezhang and Fan, Yuchen and Zhang, Kai and Ranjan, Rakesh and Li, Yawei and Timofte, Radu and Van Gool, Luc},
  journal={arXiv preprint arXiv:2201.12288},
  year={2022}
}
```
