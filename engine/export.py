"""
Exportação para edição: leva o que o motor gerou para o Premiere / After Effects / CapCut / DaVinci.

pasta/
  cenas/cena_01.mp4 …   cada cena renderizada (com a sobreposição da transição incluída)
  audio/mix.wav, musica.wav, voz.wav, sfx.wav   trilhas separadas (stems)
  legendas.srt, legendas.ass, palavras.json     legendas por palavra
  sequencia.edl         lista de cortes CMX3600 (Premiere/Resolve importam: File > Import)
  marcadores.json / .csv  início de cada cena, transições, SFX e batidas
  projeto.json          tudo isso em um arquivo (tema, movimento, ritmo, tempos)
"""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


def tc(t: float, fps: int) -> str:
    f = int(round(t * fps))
    return f"{f // (fps * 3600):02d}:{f // (fps * 60) % 60:02d}:{f // fps % 60:02d}:{f % fps:02d}"


def edl(path: Path, clips: list[str], starts: list[float], durs: list[float], tdur: float, fps: int, title="STUDIO_REELS"):
    lines = [f"TITLE: {title}", "FCM: NON-DROP FRAME", ""]
    for i, name in enumerate(clips):
        d = durs[i] + (tdur if i < len(clips) - 1 else 0.0)
        a, b = starts[i], starts[i] + d
        lines.append(f"{i + 1:03d}  AX       V     C        {tc(0, fps)} {tc(d, fps)} {tc(a, fps)} {tc(b, fps)}")
        lines.append(f"* FROM CLIP NAME: {name}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def export_all(out_dir, *, clips: list[Path], durs: list[float], starts: list[float], tdur: float, fps: int, timeline: dict,
               audio_stems: dict[str, Path], caption_files: dict[str, Path] | None = None, spec: dict | None = None) -> Path:
    out_dir = Path(out_dir)
    (out_dir / "cenas").mkdir(parents=True, exist_ok=True)
    (out_dir / "audio").mkdir(exist_ok=True)
    names = []
    for i, c in enumerate(clips, 1):
        dst = out_dir / "cenas" / f"cena_{i:02d}.mp4"
        shutil.copy(c, dst)
        names.append(dst.name)
    for k, p in audio_stems.items():
        if p and Path(p).exists():
            shutil.copy(p, out_dir / "audio" / f"{k}.wav")
    for k, p in (caption_files or {}).items():
        if p and Path(p).exists():
            shutil.copy(p, out_dir / f"{k}")
    edl(out_dir / "sequencia.edl", names, starts, durs, tdur, fps)
    marks = [dict(t=round(s, 3), tipo="cena", nome=f"Cena {i + 1}", layout=timeline["scenes"][i]["layout"]) for i, s in enumerate(starts)]
    marks += [dict(t=tr["at"], tipo="transição", nome=tr["type"]) for tr in timeline.get("transitions", [])]
    marks += [dict(t=round(e["t"], 3), tipo="sfx", nome=e.get("kind", "sfx")) for e in timeline.get("sfx_events", [])]
    marks.sort(key=lambda m: m["t"])
    (out_dir / "marcadores.json").write_text(json.dumps(marks, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(out_dir / "marcadores.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Marker Name", "Description", "In", "Out", "Duration", "Marker Type"])
        for m in marks:
            w.writerow([m["nome"], m["tipo"], tc(m["t"], fps), tc(m["t"], fps), "00:00:00:00", "Comment"])
    (out_dir / "projeto.json").write_text(json.dumps(dict(timeline=timeline, spec=spec or {}), ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return out_dir
