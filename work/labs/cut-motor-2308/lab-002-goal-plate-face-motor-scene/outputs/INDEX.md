# Classified bakeoff outputs

Each folder = **one tool role**. Do not compare across categories blindly.

| Cat | Folder | Role |
|-----|--------|------|
| **A** | `A00-baseline-src/` | Original zoomed ROI |
| **B** | `B01-rvrt-deblur/` | Temporal deblur |
| **B** | `B02-rvrt-denoise/` | Temporal denoise |
| **B** | `B03-opencv-denoise/` | Forensic denoise |
| **B** | `B04-clahe-brighten/` | Lift shadows — all goals |
| **C** | `C11-realesrgan-s4/` | ncnn upscale x4 |
| **C** | `C12-pytorch-sr-x2/` | Motor ROI upscale |
| **C** | `C13-plate-pytorch-sr-x3/` | Plate-zoom → PyTorch SR |
| **C** | `C14-face-pytorch-sr-x2/` | Face-zoom → PyTorch SR |
| **C** | `C15-scene-pytorch-sr-x2/` | Full 1080p upscale |
| **D** | `D20-rvrt-then-sr/` | Hybrid deblur then SR |
| **D** | `D22-pytorch-sr-codeformer/` | Face path hybrid |
| **E** | `E30-codeformer-facezoom/` | Generative face restore |

## Category guide

| Cat | Tools | Use for |
|-----|-------|---------|
| **A** | — | Baseline ROI |
| **B** | RVRT | Temporal denoise/deblur at **native** resolution (safest) |
| **C** | Real-ESRGAN ncnn | Upscale plates/texture — **no** face invention |
| **D** | RVRT→SR, SR→CodeFormer | Chained pipelines (preferred over single tool) |
| **E** | CodeFormer | Generative face only — on **zoomed face crop** or post-SR |

## Anti-patterns (do NOT repeat)

1. CodeFormer on full 1080p — face too small, 0 detections.
2. CodeFormer alone on ROI without upscale — often 0 faces, passthrough garbage.
3. ncnn Real-ESRGAN x2 on small ROI — **tile mosaic** (use PyTorch SR or ncnn x4).
4. Treating `final_results/` as success when `restored_faces/` is empty.

## Run metrics

```json
{
  "dataset": "cut-motor-2308",
  "lab": "lab-002-goal-plate-face-motor-scene",
  "stages": {
    "A00-baseline-src": {
      "status": "ok",
      "frames": 3
    },
    "B01-rvrt-deblur": {
      "status": "failed",
      "error": "Command '['C:\\\\Users\\\\kenwi\\\\AppData\\\\Local\\\\Programs\\\\Python\\\\Python313\\\\python.exe', 'C:\\\\Users\\\\kenwi\\\\Documents\\\\GitHub\\\\CCTV\\\\scripts\\\\bakeoff_rvrt.py', '--dataset', 'cut-motor-2308', '--lab', 'lab-002-goal-plate-face-motor-scene', '--task', 'deblur', '--out-subdir', 'B01-rvrt-deblur']' returned non-zero exit status 1."
    },
    "B02-rvrt-denoise": {
      "status": "failed",
      "error": "Command '['C:\\\\Users\\\\kenwi\\\\AppData\\\\Local\\\\Programs\\\\Python\\\\Python313\\\\python.exe', 'C:\\\\Users\\\\kenwi\\\\Documents\\\\GitHub\\\\CCTV\\\\scripts\\\\bakeoff_rvrt.py', '--dataset', 'cut-motor-2308', '--lab', 'lab-002-goal-plate-face-motor-scene', '--task', 'denoise', '--out-subdir', 'B02-rvrt-denoise']' returned non-zero exit status 1."
    },
    "B03-opencv-denoise": {
      "status": "ok"
    },
    "B04-clahe-brighten": {
      "status": "ok"
    },
    "C11-realesrgan-s4": {
      "status": "ok",
      "scale": 4,
      "backend": "ncnn"
    },
    "C12-pytorch-sr-x2": {
      "status": "ok",
      "scale": 2,
      "backend": "pytorch"
    },
    "C13-plate-pytorch-sr-x3": {
      "status": "ok",
      "scale": 3,
      "focus": "plate"
    },
    "C14-face-pytorch-sr-x2": {
      "status": "ok",
      "scale": 2,
      "focus": "face"
    },
    "C15-scene-pytorch-sr-x2": {
      "status": "ok",
      "scale": 2,
      "focus": "scene"
    },
    "D20-rvrt-then-sr": {
      "status": "skipped",
      "reason": "RVRT output missing"
    },
    "D22-pytorch-sr-codeformer": {
      "status": "ok",
      "faces_restored": 0,
      "face_files": []
    },
    "E30-codeformer-facezoom": {
      "status": "ok",
      "faces_restored": 0,
      "face_files": []
    }
  }
}
```

Regenerate: `python scripts/bakeoff_hybrid.py --dataset cut-motor-2308 --lab lab-002-goal-plate-face-motor-scene`