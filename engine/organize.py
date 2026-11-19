"""Organização da pasta de cada site: um lugar para cada tipo de arquivo.

  midia/        mídia extraída do site + fundo-01.png
  referencias/  capturas de tela (tela-NN.png, site-desktop*.png) — só para os agentes consultarem
  storyboard/   storyboard-AAAAMMDD-HHMMSS.png (+ .md) — só as KEEP mais recentes
  reels/        reel-AAAAMMDD-HHMMSS.mp4 (+ timeline/partido/content) — só as KEEP mais recentes
"""
from __future__ import annotations
import re
import shutil
from pathlib import Path

KEEP = 2
_STAMP = re.compile(r"(\d{8}-\d{6})")


def prune(folder: Path, keep: int = KEEP) -> list[str]:
    """Mantém só os `keep` carimbos mais recentes na pasta; apaga o resto (incluindo arquivos irmãos)."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    stamps = sorted({m.group(1) for f in folder.iterdir() if (m := _STAMP.search(f.name))}, reverse=True)
    drop = set(stamps[keep:])
    gone = []
    for f in folder.iterdir():
        m = _STAMP.search(f.name)
        if m and m.group(1) in drop and f.is_file():
            f.unlink()
            gone.append(f.name)
    return gone


def organize(out: Path) -> list[str]:
    """Migra pastas antigas para o modelo novo. Idempotente."""
    out = Path(out)
    log: list[str] = []

    def mv(src: Path, dst: Path):
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst.unlink()
        shutil.move(str(src), str(dst))
        log.append(f"{src.name} → {dst.parent.name}/")

    for f in sorted(out.glob("tela-*.png")) + sorted(out.glob("site-desktop*.png")):
        mv(f, out / "referencias" / f.name)
    f = out / "fundo-01.png"
    if f.exists():
        mv(f, out / "midia" / f.name)
    old = out / "versoes"
    if old.is_dir():
        (out / "reels").mkdir(exist_ok=True)
        for f in old.iterdir():
            mv(f, out / "reels" / f.name)
        old.rmdir()
        log.append("versoes/ → reels/")
    sb = out / "storyboard.png"
    if sb.exists():
        sb.unlink()
        log.append("storyboard.png antigo removido (descartado)")
    for d in (".storyboard-thumbs",):
        if (out / d).is_dir():
            shutil.rmtree(out / d, ignore_errors=True)
    for d in ("reels", "storyboard"):
        gone = prune(out / d)
        if gone:
            log.append(f"{d}/: {len(gone)} arquivo(s) antigo(s) apagado(s) (ficam as {KEEP} versões mais recentes)")
    return log
