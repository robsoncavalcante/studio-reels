"""Escolhe um ffmpeg que tenha o filtro `ass` (legendas queimadas).
O ffmpeg padrão do Homebrew (2026) vem enxuto, sem libass; o `ffmpeg-full` (keg-only) tem. Se o ffmpeg do PATH não tiver o filtro
e o ffmpeg-full estiver instalado, ele passa a ser usado só neste processo."""
from __future__ import annotations

import os
import shutil
import subprocess

CANDIDATES = ["/opt/homebrew/opt/ffmpeg-full/bin", "/usr/local/opt/ffmpeg-full/bin", "/opt/homebrew/opt/ffmpeg@7/bin"]


def has_filter(name: str, ffmpeg: str = "ffmpeg") -> bool:
    try:
        out = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    except OSError:
        return False
    return any(len(l.split()) > 1 and l.split()[1] == name for l in out.splitlines())


def prefer_ffmpeg_with_ass() -> None:
    if not shutil.which("ffmpeg") or has_filter("ass"):
        return
    for d in ([os.environ["STUDIO_FFMPEG_DIR"]] if os.environ.get("STUDIO_FFMPEG_DIR") else []) + CANDIDATES:
        ff = os.path.join(d, "ffmpeg")
        if os.path.exists(ff) and has_filter("ass", ff):
            os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
            return
