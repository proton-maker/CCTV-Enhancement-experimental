# Colab + Cursor for CCTV / VRT

Run VRT video restore on **Google Colab GPU** from this repo terminal.

## Important: CLI session ≠ browser tab

`google-colab-cli` membuat **VM terpisah** bernama `cctv`.

| Yang kamu lihat | Apakah sama dengan job terminal? |
|-----------------|----------------------------------|
| Tab **Welcome to Colab** di browser | **BUKAN** — Resources/GPU di situ milik notebook lain |
| Terminal Cursor (`restore_cctv.py`) | **YA** — pantau log di sini |
| Folder Google Drive "CCTV" | Tidak otomatis ada |

Jadi kalau di browser GPU RAM = 0.0 GB, itu normal: kamu sedang melihat runtime yang salah.

## Peta folder

```
PC (Cursor)                          Colab VM (session "cctv")
─────────────────                    ─────────────────────────
Original/CUT/cut.mkv      upload →   /content/input/cut_f8.mkv
scripts + patches         upload →   /content/CCTV/...
work (temp frames)                   /content/work/vrt/
progress log                         /content/work/progress.txt
Restored/cut_forensic.mkv ← download /content/output/cut_forensic.mkv
```

Hasil akhir selalu di PC: `Restored\*.mkv` setelah step `[6/6] Downloading`.

## A) Fully automatic (terminal)

```powershell
# Auth sekali
.\tools\colab\auth.ps1

# Smoke 8 frame (~5–20 menit, ada heartbeat tiap 20s)
$env:PYTHONIOENCODING='utf-8'
python scripts\restore_cctv.py --input Original\CUT\cut.mkv --max-frames 8 --backend colab

# Full forensic (native res, bisa berjam-jam)
python scripts\restore_cctv.py --input Original\CUT\cut.mkv --backend colab

# Paksa local PC
python scripts\restore_cctv.py --input Original\CUT\cut.mkv --backend local
```

Tanda GPU benar-benar kerja di log:

```
... masih jalan | CUDA=True Tesla T4 | VRAM 4.2/15.0 GB | pid=...
downloading model ...
=== Chunk chunk_... ===
```

Kalau diam >2 menit tanpa heartbeat → session mati. Cek:

```powershell
python tools\colab\colab_win.py sessions
python tools\colab\colab_win.py status -s cctv
```

## B) Extension notebook (opsional)

File `colab/vrt_restore.ipynb` untuk eksperimen manual. Ini **bukan** path otomatis terminal.

## Commands

```powershell
.\tools\colab\colab.ps1 sessions
.\tools\colab\colab.ps1 status -s cctv
.\tools\colab\colab.ps1 stop -s cctv
```
