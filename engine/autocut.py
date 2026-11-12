"""Autocut: remove silêncios de vídeos falados (talking head), com ritmo e J-cut. Original; usa só ffmpeg."""
import json, re, subprocess
from pathlib import Path

RITMO = {  # limite de pausa mantida (s), sensibilidade em dB, respiro deixado em cada corte (s)
    "suave": dict(min_sil=0.9, db=-34, pad=0.25),
    "ritmo": dict(min_sil=0.6, db=-32, pad=0.18),
    "dinamico": dict(min_sil=0.35, db=-30, pad=0.10),
}

def silences(src, min_sil, db):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-af", f"silencedetect=n={db}dB:d={min_sil}", "-f", "null", "-"],
                       capture_output=True, text=True)
    s = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    e = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(s, e))

def duration(src):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)], capture_output=True, text=True)
    return float(r.stdout.strip())

def keep_segments(src, ritmo="ritmo"):
    c = RITMO[ritmo]; total = duration(src); cur = 0.0; keep = []
    for a, b in silences(src, c["min_sil"], c["db"]):
        a2 = min(a + c["pad"], b)
        if a2 - cur > 0.15: keep.append((cur, a2))
        cur = max(b - c["pad"], a2)
    if total - cur > 0.15: keep.append((cur, total))
    return keep

def run(src, out, ritmo="ritmo", jcut=0.0):
    """jcut>0: o áudio de cada corte entra `jcut` s antes da imagem."""
    keep = keep_segments(src, ritmo); n = len(keep)
    has_v = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=index", "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout.strip()
    parts = []
    for i, (a, b) in enumerate(keep):
        aa = max(0, a - jcut) if i else a
        parts.append(f"[0:a]atrim={aa:.3f}:{b:.3f},asetpts=PTS-STARTPTS[a{i}]")
        if has_v: parts.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{i}]")
    cat = "".join((f"[v{i}]" if has_v else "") + f"[a{i}]" for i in range(n))
    parts.append(f"{cat}concat=n={n}:v={1 if has_v else 0}:a=1" + ("[v][a]" if has_v else "[a]"))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-filter_complex", ";".join(parts)]
    cmd += (["-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18"] if has_v else ["-map", "[a]"]) + ["-c:a", "aac", str(out)]
    subprocess.run(cmd, check=True)
    Path(str(out) + ".cuts.json").write_text(json.dumps({"ritmo": ritmo, "jcut": jcut, "keep": keep, "original": duration(src), "final": duration(out)}, indent=1))
    return keep
