# cut-motor-2308 — lab-001-classified-v2

Dataset: `work/datasets/cut-motor-2308/`  
Lab: `work/labs/cut-motor-2308/lab-001-classified-v2/`

## Verdict (frame_002)

| Stage | Result |
|-------|--------|
| **C12 PyTorch SR x2** | **Winner** — best upscale, no tile mosaic |
| C11 ncnn x4 | OK, softer |
| B03 OpenCV | Marginal denoise |
| D22 / E30 CodeFormer | 0 faces — N/A |

Compare: `compare/compare_all_frame_002.png`

## New lab (do not overwrite this folder)

```bash
python scripts/bakeoff_hybrid.py --dataset cut-motor-2308 --new-lab "your-test-name"
```
