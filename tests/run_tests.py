#!/usr/bin/env python3
"""Testes de fumaça do Studio Reels (sem pytest). Uso: python tests/run_tests.py
Cada cenário imprime OK/FALHA. Não testa provedores com rede (ElevenLabs, Whisper, Magnific)."""
import json, subprocess, sys, tempfile, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="sr_test_"))
results = []


def case(name):
    def deco(fn):
        try:
            fn()
            results.append((name, True, ""))
            print(f"OK     {name}")
        except Exception as e:  # noqa
            results.append((name, False, repr(e)))
            print(f"FALHA  {name}: {e!r}")
        return fn
    return deco


def sh(*a, **k):
    return subprocess.run([str(x) for x in a], capture_output=True, text=True, cwd=ROOT, **k)


def studio(*a):
    r = sh(sys.executable, "studio.py", *a)
    assert r.returncode == 0, r.stdout[-400:] + r.stderr[-400:]
    return r.stdout


def frame_diff(video, t1, t2):
    import numpy as np
    from PIL import Image
    ims = []
    for t in (t1, t2):
        p = TMP / f"f{t}.png"
        sh("ffmpeg", "-y", "-loglevel", "error", "-ss", t, "-i", video, "-frames:v", "1", "-vf", "scale=120:-1", p)
        ims.append(np.asarray(Image.open(p).convert("L"), dtype=float))
    return float(abs(ims[0] - ims[1]).mean())


@case("legenda: SRT vira palavras com tempo, sem sobreposição e em ≤2 linhas")
def _():
    from engine import captions as c
    srt = TMP / "a.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nSua empresa está pagando imposto demais hoje\n\n", encoding="utf-8")
    w = c.from_file(srt)
    assert len(w) == 7 and w[0]["t0"] == 0 and abs(w[-1]["t1"] - 2.0) < .01
    ass, _ = c.build_ass(w, TMP / "a.ass", style="karaoke", W=1080, H=1920, font_slug="space-grotesk")
    ev = [l for l in ass.read_text().splitlines() if l.startswith("Dialogue")]
    assert ev and all(e.count("\\N") <= 1 for e in ev)
    assert "\\pos(540,1228)" in ev[0]  # centro em 64% da altura


@case("autocut: remove vícios e repetições a partir de palavras com tempo")
def _():
    from engine import autocut
    w = [dict(w="olá", t0=0, t1=.4), dict(w="ahn", t0=.5, t1=.8), dict(w="ao", t0=1, t1=1.2), dict(w="ao", t0=1.3, t1=1.5), dict(w="canal", t0=1.6, t1=2)]
    cuts = autocut.word_cuts(w)
    assert len(cuts) == 2


@case("áudio: clean e levels (tom sintético)")
def _():
    from engine import audio
    src = TMP / "tom.wav"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=220:d=2", "-af", "volume=0.5", src)
    r = audio.clean_voice(src, TMP / "tom_l.wav")
    assert r["lufs"] is not None and r["lufs"] < -14 and audio.bar_len(120) == 2.0


@case("gráficos: três layouts renderizam")
def _():
    for l in ("chart-bars", "chart-donut", "chart-line"):
        studio("render", "--layout", l, "--theme", "criative-dark", "--format", "reel", "--sample", "--out", TMP / f"{l}.png")
        assert (TMP / f"{l}.png").stat().st_size > 20000


@case("vídeo no slot: clipe avança no tempo e o áudio entra na mixagem")
def _():
    clip = TMP / "clip.mp4"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=25:d=8", "-f", "lavfi", "-i", "sine=f=330:d=8", "-shortest", "-c:v", "libx264", "-c:a", "aac", clip)
    (TMP / "v.json").write_text(json.dumps({"scenes": [{"layout": "full-bleed-bottom", "dur": 4, "title": "Clipe", "photos": [{"src": str(clip), "start": 1, "volume": 1.0}]}]}))
    out = TMP / "v.mp4"
    studio("reel", "--content", TMP / "v.json", "--theme", "criative-dark", "--out", out)
    assert frame_diff(out, 0.6, 3.0) > 3
    vol = sh("ffmpeg", "-hide_banner", "-i", out, "-af", "volumedetect", "-f", "null", "-").stderr
    assert "mean_volume" in vol and float(vol.split("mean_volume: ")[1].split(" ")[0]) > -45


@case("reel: --human --exit pop --preview gera prévia 432x768")
def _():
    items = [{"title": str(a), "value": v} for a, v in ((2024, 40), (2025, 90), (2026, 130))]
    (TMP / "r.json").write_text(json.dumps({"scenes": [{"layout": "chart-bars", "dur": 3, "title": "A *B*", "items": items}, {"layout": "chart-line", "dur": 3, "title": "C *D*", "items": items}]}))
    out = TMP / "r.mp4"
    studio("reel", "--content", TMP / "r.json", "--theme", "criative-dark", "--human", "--exit", "pop", "--preview", "--out", out)
    d = sh("ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", out).stdout.split()[0]
    assert d == "432,768", d


@case("qa reel: roda e reporta zona da interface")
def _():
    (TMP / "q.json").write_text(json.dumps({"title": "Teste *QA*", "subtitle": "Texto"}))
    out = sh(sys.executable, "studio.py", "qa", "static", "--layout", "typographic", "--format", "reel", "--content", TMP / "q.json", "--theme", "criative-dark")
    assert out.returncode in (0, 1), out.stderr[-300:]


@case("mídia: GIF, MOV com alpha e Lottie renderizam e animam")
def _():
    gif, mov, lot = TMP / "a.gif", TMP / "b.mov", TMP / "l.json"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=160x160:r=10:d=3", "-vf", "format=rgb8", gif)
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0xff3300:s=200x200:r=25:d=2,format=yuva444p,geq=lum='lum(X,Y)':cb='cb(X,Y)':cr='cr(X,Y)':a='if(lt(hypot(X-100,Y-100),60),255,0)'", "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", mov)
    lot.write_text(json.dumps({"v": "5.5.7", "fr": 30, "ip": 0, "op": 60, "w": 200, "h": 200, "nm": "t", "ddd": 0, "assets": [], "layers": [{"ddd": 0, "ind": 1, "ty": 4, "nm": "r", "sr": 1, "ks": {"o": {"a": 0, "k": 100}, "r": {"a": 1, "k": [{"t": 0, "s": [0], "i": {"x": [0.5], "y": [1]}, "o": {"x": [0.5], "y": [0]}}, {"t": 60, "s": [360]}]}, "p": {"a": 0, "k": [100, 100, 0]}, "a": {"a": 0, "k": [0, 0, 0]}, "s": {"a": 0, "k": [100, 100, 100]}}, "ao": 0, "shapes": [{"ty": "gr", "it": [{"ty": "rc", "d": 1, "s": {"a": 0, "k": [100, 100]}, "p": {"a": 0, "k": [0, 0]}, "r": {"a": 0, "k": 12}}, {"ty": "fl", "c": {"a": 0, "k": [1, 0.2, 0, 1]}, "o": {"a": 0, "k": 100}}, {"ty": "tr", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [100, 100]}, "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": 100}}]}], "ip": 0, "op": 60, "st": 0}]}))
    for name, f in (("gif", gif), ("mov", mov), ("lottie", lot)):
        (TMP / f"{name}.json").write_text(json.dumps({"scenes": [{"layout": "full-bleed-bottom", "dur": 2, "title": name, "photos": [str(f)]}]}))
        out = TMP / f"{name}.mp4"
        studio("reel", "--content", TMP / f"{name}.json", "--theme", "criative-dark", "--preview", "--out", out)
        dd = frame_diff(out, 0.9, 1.6); assert dd > 0.1, (name, dd)


@case("--fit-voice: duração das cenas segue a locução")
def _():
    voz = TMP / "voz.wav"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=200:d=6", voz)
    (TMP / "fv.json").write_text(json.dumps({"scenes": [{"layout": "typographic", "title": "Curta"}, {"layout": "typographic", "title": "Esta cena tem bem mais palavras para falar na locução hoje"}]}))
    out = TMP / "fv.mp4"
    studio("reel", "--content", TMP / "fv.json", "--theme", "criative-dark", "--voice", voz, "--fit-voice", "--preview", "--out", out)
    d = float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out).stdout)
    assert 5.5 < d < 7.5, d


@case("Premiere: --stems gera sequencia.xml válido (vídeo, áudio, marcadores)")
def _():
    import xml.dom.minidom as md
    (TMP / "ex.json").write_text(json.dumps({"scenes": [{"layout": "typographic", "dur": 2, "title": "Um"}, {"layout": "typographic", "dur": 2, "title": "Dois"}]}))
    voz = TMP / "voz2.wav"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=200:d=3", voz)
    studio("reel", "--content", TMP / "ex.json", "--theme", "criative-dark", "--voice", voz, "--preview", "--stems", TMP / "stems", "--out", TMP / "ex.mp4")
    d = md.parse(str(TMP / "stems" / "sequencia.xml"))
    assert len(d.getElementsByTagName("clipitem")) >= 3 and len(d.getElementsByTagName("marker")) == 2


@case("transcrição: aceita o comando whisper (openai-whisper) como alternativa")
def _():
    from engine import captions as c
    fb = TMP / "fakebin"
    fb.mkdir()
    (fb / "whisper").write_text('#!/usr/bin/env python3\nimport sys,json,os\na=sys.argv;od=a[a.index("--output_dir")+1]\n'
                                'json.dump({"segments":[{"words":[{"word":" Oi","start":0.1,"end":0.4}]}]},open(os.path.join(od,"x.json"),"w"))\n')
    (fb / "whisper").chmod(0o755)
    import os
    old = os.environ["PATH"]
    os.environ["PATH"] = f"{fb}:{old}"
    try:
        w = c.transcribe(TMP / "voz.wav" if (TMP / "voz.wav").exists() else TMP / "a.wav")
    finally:
        os.environ["PATH"] = old
    assert w and w[0]["w"] == "Oi"


@case("autocut --captions: gera SRT e vídeo legendado, frases separadas por pausa")
def _():
    src = TMP / "ac.mp4"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=360x640:r=25:d=6", "-f", "lavfi", "-i", "sine=f=300:d=6", "-shortest", "-c:v", "libx264", "-c:a", "aac", src)
    (TMP / "ac.srt").write_text("1\n00:00:00,200 --> 00:00:02,000\nOla pessoal tudo bem\n\n2\n00:00:03,500 --> 00:00:05,500\nvamos testar hoje\n")
    studio("autocut", src, "--words", TMP / "ac.srt", "--captions", "karaoke")
    srt = (TMP / "ac_autocut.srt").read_text()
    assert (TMP / "ac_autocut_legendado.mp4").exists() and srt.count("-->") == 2, srt


print(f"\n{sum(1 for _, ok, _ in results if ok)}/{len(results)} cenários OK")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
