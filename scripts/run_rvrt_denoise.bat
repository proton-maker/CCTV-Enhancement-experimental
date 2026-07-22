@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"
set CUDA_HOME=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.3
set CUDA_PATH=%CUDA_HOME%
set DISTUTILS_USE_SDK=1
set CCCL_IGNORE_MSVC_TRADITIONAL_PREPROCESSOR_WARNING=1
cd /d "%~dp0.."
python scripts\bakeoff_rvrt.py --task denoise --tile 8 256 256 --tile-overlap 2 32 32 %*
