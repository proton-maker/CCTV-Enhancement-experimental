"""Forensic CCTV presets — minimize model hallucination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Backend = Literal["local", "colab"]


@dataclass(frozen=True)
class RestorePreset:
    name: str
    task: str
    sigma: int
    # fraction of ORIGINAL kept after each pass (anti-hallucination)
    blend_original: float
    two_pass: bool
    pass1_task: str
    pass1_sigma: int
    pass1_blend: float
    tile: tuple[int, int, int]
    tile_overlap: tuple[int, int, int]
    chunk_frames: int
    chunk_overlap: int
    max_side: int | None  # None = native
    num_workers: int
    crf: int


def _local(**kw) -> dict:
    return kw


def _colab(**kw) -> dict:
    return kw


PRESETS: dict[str, dict[Backend, RestorePreset]] = {
    # Blurry CCTV forensic: deblur only, strong original blend, NO upscaling
    "forensic-blur": {
        "local": RestorePreset(
            name="forensic-blur",
            task="006_VRT_videodeblurring_GoPro",
            sigma=0,
            blend_original=0.35,
            two_pass=True,
            pass1_task="008_VRT_videodenoising_DAVIS",
            pass1_sigma=10,
            pass1_blend=0.20,
            tile=(6, 128, 128),
            tile_overlap=(2, 16, 16),
            chunk_frames=48,
            chunk_overlap=6,
            max_side=960,
            num_workers=0,
            crf=15,
        ),
        "colab": RestorePreset(
            name="forensic-blur",
            task="006_VRT_videodeblurring_GoPro",
            sigma=0,
            blend_original=0.30,
            two_pass=True,
            pass1_task="008_VRT_videodenoising_DAVIS",
            pass1_sigma=10,
            pass1_blend=0.15,
            tile=(6, 192, 192),
            tile_overlap=(2, 16, 16),
            chunk_frames=32,
            chunk_overlap=6,
            max_side=None,
            num_workers=0,
            crf=15,
        ),
    },
    # Noisy but sharp CCTV: light denoise only
    "forensic-denoise": {
        "local": RestorePreset(
            name="forensic-denoise",
            task="008_VRT_videodenoising_DAVIS",
            sigma=10,
            blend_original=0.25,
            two_pass=False,
            pass1_task="",
            pass1_sigma=0,
            pass1_blend=0.0,
            tile=(6, 128, 128),
            tile_overlap=(2, 16, 16),
            chunk_frames=48,
            chunk_overlap=6,
            max_side=960,
            num_workers=0,
            crf=15,
        ),
        "colab": RestorePreset(
            name="forensic-denoise",
            task="008_VRT_videodenoising_DAVIS",
            sigma=10,
            blend_original=0.20,
            two_pass=False,
            pass1_task="",
            pass1_sigma=0,
            pass1_blend=0.0,
            tile=(6, 192, 192),
            tile_overlap=(2, 16, 16),
            chunk_frames=32,
            chunk_overlap=6,
            max_side=None,
            num_workers=0,
            crf=15,
        ),
    },
    # Faster preview (still no SR)
    "preview": {
        "local": RestorePreset(
            name="preview",
            task="006_VRT_videodeblurring_GoPro",
            sigma=0,
            blend_original=0.40,
            two_pass=False,
            pass1_task="",
            pass1_sigma=0,
            pass1_blend=0.0,
            tile=(4, 96, 96),
            tile_overlap=(2, 12, 12),
            chunk_frames=24,
            chunk_overlap=4,
            max_side=640,
            num_workers=0,
            crf=18,
        ),
        "colab": RestorePreset(
            name="preview",
            task="006_VRT_videodeblurring_GoPro",
            sigma=0,
            blend_original=0.35,
            two_pass=False,
            pass1_task="",
            pass1_sigma=0,
            pass1_blend=0.0,
            tile=(8, 192, 192),
            tile_overlap=(2, 16, 16),
            chunk_frames=48,
            chunk_overlap=6,
            max_side=960,
            num_workers=2,
            crf=18,
        ),
    },
}


def detect_runtime_backend() -> Backend:
    import os
    from pathlib import Path

    if os.environ.get("COLAB_GPU") or Path("/content").is_dir():
        return "colab"
    return "local"


def get_preset(name: str, backend: Backend | None = None) -> RestorePreset:
    if name not in PRESETS:
        known = ", ".join(sorted(PRESETS))
        raise ValueError(f"Unknown preset '{name}'. Choose: {known}")
    backend = backend or detect_runtime_backend()
    return PRESETS[name][backend]


FORENSIC_RULES = """
Forensic rules (no hallucination):
- NEVER use video super-resolution (×2/×4) — it invents pixels.
- Prefer σ=10 denoise; never σ≥30 on evidence footage.
- Always blend with original (--blend-original 0.15–0.40).
- Blur → two-pass: light denoise then deblur (preset forensic-blur).
- Colab: native resolution (max-side 0), larger tiles/chunks.
- Local 4GB: max-side 960, smaller tiles.
"""
