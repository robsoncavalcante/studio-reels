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


_HW = {}


def hw_h264() -> bool:
    """True se este ffmpeg tem h264_videotoolbox (Mac) e ele realmente codifica (testado 1x). STUDIO_HW=0 desliga."""
    if os.environ.get("STUDIO_HW") == "0" or not shutil.which("ffmpeg"):
        return False
    if "h264" not in _HW:
        ok = False
        try:
            enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
            if "h264_videotoolbox" in enc:
                r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x240:d=0.2", "-c:v", "h264_videotoolbox",
                                    "-pix_fmt", "yuv420p", "-f", "null", "-"], capture_output=True)
                ok = r.returncode == 0
        except OSError:
            ok = False
        _HW["h264"] = ok
    return _HW["h264"]


def vcodec(fast: bool = False, crf: int = 18, mbps: float = 8.0) -> list:
    """Argumentos do codificador de vídeo. fast=True (prévias/rascunhos) usa o hardware quando houver; o final sai sempre em libx264."""
    if fast and hw_h264():
        return ["-c:v", "h264_videotoolbox", "-b:v", f"{mbps:g}M", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p"]
