# Runtime libraries are bundled; model weights and user data are deliberately absent.
from pathlib import Path
import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

root = Path(SPECPATH).parent
# Do not collect DLLs from unrelated developer tools (e.g. Poppler's ICU).
os.environ["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), sys.base_prefix,
    str(Path(os.environ["SystemRoot"]) / "System32"), os.environ["SystemRoot"]])
fun_datas, fun_binaries, fun_imports = collect_all("funasr")
whisper_datas, whisper_binaries, whisper_imports = collect_all("faster_whisper")
ct2_datas, ct2_binaries, ct2_imports = collect_all("ctranslate2")
av_datas, av_binaries, av_imports = collect_all("av")
datas = fun_datas + whisper_datas + ct2_datas + av_datas + collect_data_files("imageio_ffmpeg")
binaries = fun_binaries + whisper_binaries + ct2_binaries + av_binaries
hiddenimports = fun_imports + whisper_imports + ct2_imports + av_imports
for package in ("funasr", "modelscope", "modelscope-hub", "torch", "torchaudio", "transformers", "huggingface-hub", "tokenizers", "safetensors", "tqdm", "regex", "packaging", "PyYAML", "numpy", "requests", "faster-whisper", "ctranslate2", "av"):
    datas += copy_metadata(package)
datas += [(str(root / "assets"), "assets"), (str(root / "prompts"), "prompts")]
a = Analysis([str(root / "app.py")], pathex=[str(root)], binaries=binaries,
    datas=datas, hiddenimports=hiddenimports,
    excludes=["tkinter", "IPython", "pytest", "matplotlib", "tensorboard", "tensorboardX"],
    noarchive=False)
# Qt's Windows ICU API is provided by the OS, not a third-party ICU build.
a.binaries = [item for item in a.binaries if Path(item[0]).name.lower() not in {"icuuc.dll", "icuin.dll", "icu.dll"}]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Lingyezhou", debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    icon=str(root / "assets/lingyezhou.ico"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Lingyezhou")
