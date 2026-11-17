"""
Exportação para edição: leva o que o motor gerou para o Premiere / After Effects / CapCut / DaVinci.

pasta/
  cenas/cena_01.mp4 …   cada cena renderizada (com a sobreposição da transição incluída)
  audio/mix.wav, musica.wav, voz.wav, sfx.wav   trilhas separadas (stems)
  legendas.srt, legendas.ass, palavras.json     legendas por palavra
  sequencia.edl         lista de cortes CMX3600 (Premiere/Resolve importam: File > Import)
  sequencia.xml         sequência completa (vídeo + stems + marcadores) em XML do Final Cut 7: Premiere/Resolve abrem com File > Import
  marcadores.json / .csv  início de cada cena, transições, SFX e batidas
  projeto.json          tudo isso em um arquivo (tema, movimento, ritmo, tempos)
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
from urllib.parse import quote
from xml.sax.saxutils import escape
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


def _probe(path: Path, entries: str) -> list[str]:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", entries, "-of", "csv=p=0:s=,", str(path)], capture_output=True, text=True)
    return r.stdout.strip().split(",")


def _url(p: Path) -> str:
    return "file://localhost" + quote(str(Path(p).resolve()))


def _silent(path: Path, limit: float = 1e-4) -> bool:
    """True se o wav não tem som (pico abaixo de ~-80 dBFS); se não der para ler, considera com som."""
    try:
        import wave
        import numpy as np
        with wave.open(str(path), "rb") as w:
            raw = w.readframes(w.getnframes())
            width = w.getsampwidth()
        if width != 2:
            return False
        return float(np.abs(np.frombuffer(raw, dtype="<i2")).max(initial=0)) / 32768 < limit
    except Exception:
        return False


def xmeml(path: Path, out_dir: Path, names: list[str], starts: list[float], durs: list[float], tdur: float, fps: int,
          stems: list[str], marks: list[dict], title="Studio Reels"):
    """Sequência no formato XML do Final Cut Pro 7 (xmeml v4), importável no Premiere (File > Import) e no DaVinci.
    Vídeo: cenas alternando V1/V2 (a sobreposição é a transição); áudio: um stem por faixa; marcadores na sequência."""
    fr = lambda t: int(round(t * fps))
    w, h = (int(x) for x in _probe(out_dir / "cenas" / names[0], "stream=width,height")[:2])
    total = fr(starts[-1] + durs[-1])
    rate = f"<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>"
    v = []
    for tr in (0, 1):
        items = []
        for i, name in enumerate(names):
            if i % 2 != tr:
                continue
            d = durs[i] + (tdur if i < len(names) - 1 else 0.0)
            f = out_dir / "cenas" / name
            a, b = fr(starts[i]), fr(starts[i] + d)
            items.append(
                f'<clipitem id="v{i + 1}"><name>{escape(name)}</name><enabled>TRUE</enabled><duration>{b - a}</duration>{rate}'
                f'<start>{a}</start><end>{b}</end><in>0</in><out>{b - a}</out>'
                f'<file id="fv{i + 1}"><name>{escape(name)}</name><pathurl>{escape(_url(f))}</pathurl>{rate}<duration>{b - a}</duration>'
                f'<media><video><samplecharacteristics>{rate}<width>{w}</width><height>{h}</height></samplecharacteristics></video></media></file></clipitem>')
        v.append(f"<track>{''.join(items)}</track>")
    au = []
    for k, stem in enumerate(stems):
        f = out_dir / "audio" / stem
        try:
            dur = float(_probe(f, "format=duration")[0])
            sr, ch = (int(x) for x in _probe(f, "stream=sample_rate,channels")[:2])
        except Exception:
            continue
        if _silent(f):
            continue  # stem sem som (ex.: sem locução): não ocupa faixa na sequência
        n = fr(dur)
        st = ch >= 2
        tattr = ' currentExplodedTrackIndex="0" totalExplodedTrackCount="2" premiereTrackType="Stereo"' if st else ""
        cattr = ' premiereChannelType="stereo"' if st else ""
        au.append(
            f'<track{tattr}><clipitem id="a{k + 1}"{cattr}><name>{escape(stem)}</name><enabled>TRUE</enabled><duration>{n}</duration>{rate}'
            f'<start>0</start><end>{n}</end><in>0</in><out>{n}</out>'
            f'<file id="fa{k + 1}"><name>{escape(stem)}</name><pathurl>{escape(_url(f))}</pathurl>{rate}<duration>{n}</duration>'
            f'<media><audio><samplecharacteristics><depth>16</depth><samplerate>{sr}</samplerate></samplecharacteristics><channelcount>{ch}</channelcount></audio></media></file>'
            f'<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack></clipitem></track>')
    mk = "".join(f"<marker><name>{escape(m['nome'])}</name><comment>{escape(m['tipo'])}</comment><in>{fr(m['t'])}</in><out>-1</out></marker>"
                 for m in marks if m["tipo"] == "cena")
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="seq1"><name>{escape(title)}</name>'
           f'<duration>{total}</duration>{rate}<timecode>{rate}<string>00:00:00:00</string><frame>0</frame><displayformat>NDF</displayformat></timecode>'
           f'{mk}<media><video><format><samplecharacteristics>{rate}<width>{w}</width><height>{h}</height><pixelaspectratio>square</pixelaspectratio></samplecharacteristics></format>'
           f'{"".join(v)}</video><audio>{"".join(au)}</audio></media></sequence></xmeml>')
    path.write_text(xml, encoding="utf-8")


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
    stems = [f"{k}.wav" for k in ("voz", "musica", "sfx") if (out_dir / "audio" / f"{k}.wav").exists()] or (["mix.wav"] if (out_dir / "audio" / "mix.wav").exists() else [])
    xmeml(out_dir / "sequencia.xml", out_dir, names, starts, durs, tdur, fps, stems,
          [dict(t=round(st, 3), tipo="cena", nome=f"Cena {i + 1}") for i, st in enumerate(starts)])
    (out_dir / "marcadores.json").write_text(json.dumps(marks, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(out_dir / "marcadores.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Marker Name", "Description", "In", "Out", "Duration", "Marker Type"])
        for m in marks:
            w.writerow([m["nome"], m["tipo"], tc(m["t"], fps), tc(m["t"], fps), "00:00:00:00", "Comment"])
    (out_dir / "projeto.json").write_text(json.dumps(dict(timeline=timeline, spec=spec or {}), ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return out_dir
