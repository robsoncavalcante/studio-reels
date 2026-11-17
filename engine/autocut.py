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

FILLERS = {"ahn", "ahnn", "hum", "hmm", "hm", "uh", "uhm", "um", "eh", "ééé", "éé", "ãh", "ah", "né"}


def word_cuts(words, fillers=True, repeats=True):
    """Intervalos a remover a partir de palavras com tempo: vícios de fala (ahn, hum...) e repetições (fica só a última vez)."""
    norm = lambda w: re.sub(r"[^\wÀ-ÿ]", "", w.lower())
    cuts = []
    for i, w in enumerate(words):
        n = norm(w["w"])
        if fillers and n in FILLERS and n != "né":
            cuts.append((w["t0"] - 0.03, w["t1"] + 0.05))
        elif repeats and i + 1 < len(words) and n and n == norm(words[i + 1]["w"]) and n not in FILLERS:
            cuts.append((w["t0"] - 0.02, words[i + 1]["t0"] - 0.02))
    return cuts


def keep_segments(src, ritmo="ritmo", words=None, fillers=True, repeats=True):
    c = RITMO[ritmo]; total = duration(src); rem = []
    for a, b in silences(src, c["min_sil"], c["db"]):
        a2, b2 = a + c["pad"], b - c["pad"]
        if b2 - a2 > 0.05: rem.append((a2, b2))
    if words:
        rem += word_cuts(words, fillers, repeats)
    rem.sort(); merged = []
    for a, b in rem:
        if merged and a <= merged[-1][1]: merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else: merged.append((max(0, a), min(total, b)))
    keep, cur = [], 0.0
    for a, b in merged:
        if a - cur > 0.15: keep.append((cur, a))
        cur = max(cur, b)
    if total - cur > 0.15: keep.append((cur, total))
    return keep

def camera_plan(keep, zoom=1.25, push=0.04):
    """Plano de câmera por trecho: alterna aberto (1,0) e fechado (`zoom`) a cada corte, com aproximação lenta (`push`) dentro de cada trecho.
    O corte sempre muda de plano, o que disfarça o jump cut. Retorna [(z0, z1)] por trecho."""
    plan = []
    for i in range(len(keep)):
        base = 1.0 if i % 2 == 0 else zoom
        plan.append((round(base, 4), round(base * (1 + push), 4)))
    return plan


def run(src, out, ritmo="ritmo", jcut=0.0, words=None, fillers=True, repeats=True, camera=False, zoom=1.25, push=0.04, fast=False):
    """jcut>0: o áudio de cada corte entra `jcut` s antes da imagem. camera: alterna plano aberto/fechado e aproxima devagar em cada trecho.
    fast: usa o codificador de hardware (rascunho)."""
    from . import ffsetup
    keep = keep_segments(src, ritmo, words, fillers, repeats); n = len(keep)
    has_v = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=index", "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout.strip()
    plan = camera_plan(keep, zoom, push) if camera else None
    W, H = size(src) if (camera and has_v) else (0, 0)

    def build(animated):
        parts = []
        for i, (a, b) in enumerate(keep):
            aa = max(0, a - jcut) if i else a
            parts.append(f"[0:a]atrim={aa:.3f}:{b:.3f},asetpts=PTS-STARTPTS[a{i}]")
            if has_v:
                cam = ""
                if camera:
                    z0, z1 = plan[i]
                    d = max(b - a, 0.1)
                    # recorte centralizado, um pouco acima do centro (onde costuma ficar o rosto)
                    if animated:  # escala variável no tempo (aproximação lenta)
                        sc = f"scale=w='trunc(iw*({z0}+({z1}-{z0})*min(if(gt(t,0),t,0)/{d:.3f},1))/2)*2':h=-2:eval=frame:flags=bicubic"
                    else:  # plano fixo por trecho: mais simples e à prova de versão do ffmpeg
                        sc = f"scale=w='trunc(iw*{z0}/2)*2':h=-2:flags=bicubic"
                    cam = f",{sc},crop={W}:{H}:x='(iw-ow)/2':y='(ih-oh)*0.4',setsar=1"
                parts.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS{cam}[v{i}]")
        cat = "".join((f"[v{i}]" if has_v else "") + f"[a{i}]" for i in range(n))
        parts.append(f"{cat}concat=n={n}:v={1 if has_v else 0}:a=1" + ("[v][a]" if has_v else "[a]"))
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-filter_complex", ";".join(parts)]
        return cmd + (["-map", "[v]", "-map", "[a]", *ffsetup.vcodec(fast, 18)] if has_v else ["-map", "[a]"]) + ["-c:a", "aac", str(out)]

    try:
        subprocess.run(build(True), check=True)
    except subprocess.CalledProcessError:
        if not (camera and has_v):
            raise
        print("! A aproximação lenta falhou neste ffmpeg; usando plano fixo por trecho (alterna aberto/fechado do mesmo jeito).")
        plan = [(z0, z0) for z0, _ in plan]
        subprocess.run(build(False), check=True)
    Path(str(out) + ".cuts.json").write_text(json.dumps({"ritmo": ritmo, "jcut": jcut, "camera": plan, "keep": keep, "original": duration(src), "final": duration(out)}, indent=1))
    return keep


def remap_words(words, keep):
    """Leva as palavras do vídeo original para a linha do tempo do vídeo cortado (descarta as que caíram fora dos trechos mantidos)."""
    out, acc = [], 0.0
    for a, b in keep:
        for w in words:
            mid = (w["t0"] + w["t1"]) / 2
            if a <= mid < b:
                out.append(dict(w=w["w"], t0=round(max(a, w["t0"]) - a + acc, 3), t1=round(min(b, w["t1"]) - a + acc, 3)))
        acc += b - a
    return out


def size(src):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:stream_tags=rotate:side_data=rotation", "-of", "json", str(src)], capture_output=True, text=True)
    st = json.loads(r.stdout)["streams"][0]
    w, h = int(st["width"]), int(st["height"])
    rot = abs(int(st.get("tags", {}).get("rotate", 0) or (st.get("side_data_list") or [{}])[0].get("rotation", 0) or 0))
    return (h, w) if rot in (90, 270) else (w, h)


def burn(src, ass, fontsdir, out, fast=False):
    from . import ffsetup
    if not ffsetup.has_filter("ass"):
        raise SystemExit("Seu ffmpeg não tem o filtro de legendas (ass). No Mac: brew install ffmpeg-full  (as legendas .srt já foram gravadas).")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", f"ass=filename={ass}:fontsdir={fontsdir}",
                    *ffsetup.vcodec(fast, 18), "-c:a", "copy", str(out)], check=True)
