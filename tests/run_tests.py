import subprocess
#!/usr/bin/env python3
"""Testes de fumaça do Studio Reels (sem pytest). Uso: python tests/run_tests.py
Cada cenário imprime OK/FALHA. Não testa provedores com rede (ElevenLabs, Whisper, Magnific)."""
import json, os, subprocess, sys, tempfile, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("STUDIO_PORTAO", "off")  # o portão tem testes próprios abaixo; nos demais cenários só atrasaria
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
    xml = (TMP / "stems" / "sequencia.xml").read_text()
    assert 'premiereTrackType="Stereo"' in xml and 'premiereChannelType="stereo"' in xml, "áudio deve entrar como estéreo"
    sr = int(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate", "-of", "csv=p=0", str(TMP / "stems" / "audio" / "voz.wav")],
                            capture_output=True, text=True).stdout.split()[0])
    assert f"<samplerate>{sr}</samplerate>" in xml, "taxa de amostragem deve ser a real do arquivo"
    from engine import export as ex
    sil = TMP / "silencio.wav"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "1", sil)
    assert ex._silent(sil) and not ex._silent(TMP / "stems" / "audio" / "voz.wav")


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



@case("autocut --camera: alterna plano a cada corte, mantém o tamanho e registra o plano")
def _():
    src = TMP / "cam.mp4"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=360x640:r=25:d=9",
       "-f", "lavfi", "-i", "sine=f=300:d=9,volume='if(lt(mod(t,3),2),1,0)':eval=frame", "-shortest", "-c:v", "libx264", "-c:a", "aac", src)
    studio("autocut", src, "--camera", "--ritmo", "suave")
    out = TMP / "cam_autocut.mp4"
    w, h = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(out)],
                          capture_output=True, text=True).stdout.strip().split("x")
    assert (w, h) == ("360", "640"), (w, h)
    plan = json.loads((TMP / "cam_autocut.mp4.cuts.json").read_text())["camera"]
    assert len(plan) >= 2 and plan[0][0] == 1.0 and plan[1][0] == 1.25, plan
    from engine import autocut as ac
    assert ac.camera_plan([(0, 1), (2, 3), (4, 5)], 1.3, .05) == [(1.0, 1.05), (1.3, 1.365), (1.0, 1.05)]


@case("legenda curta: até 3 palavras, 1 linha, sem terminar em palavra fraca")
def _():
    from engine import captions as c
    ws, t = [], 0.0
    for w in "Hoje eu vou mostrar como a gente faz um corte de vídeo que prende a atenção das pessoas".split():
        ws.append(dict(w=w, t0=round(t, 2), t1=round(t + .3, 2)))
        t += .32
    ch = c.chunks(ws, max_words=3, max_chars=22, avoid_weak=True, min_dur=.3)
    assert all(len(x) <= 3 for x in ch) and not any(c._weak(x[-1]) and len(x) > 1 for x in ch[:-1]), [[w["w"] for w in x] for x in ch]
    assp, _ = c.build_ass(ws, TMP / "curta.ass", style="curta", W=1080, H=1920)
    ass = assp.read_text()
    assert "\\N" not in ass and "Dialogue" in ass
    from engine import ffsetup as f
    f._HW["h264"] = True
    assert "h264_videotoolbox" in f.vcodec(True) and "libx264" in f.vcodec(False)
    f._HW["h264"] = False
    assert "libx264" in f.vcodec(True)
    f._HW.clear()


@case("reel: legenda com cor/posição próprias e --vocab aceito")
def _():
    (TMP / "cp.json").write_text(json.dumps({"scenes": [{"layout": "typographic", "dur": 2, "title": "Um"}, {"layout": "typographic", "dur": 2, "title": "Dois"}]}))
    (TMP / "cp.srt").write_text("1\n00:00:00,200 --> 00:00:01,800\nOla pessoal tudo bem\n\n2\n00:00:02,200 --> 00:00:03,800\nvamos testar hoje\n")
    voz = TMP / "voz3.wav"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=200:d=4", voz)
    studio("reel", "--content", TMP / "cp.json", "--theme", "criative-dark", "--voice", voz, "--words", TMP / "cp.srt", "--captions", "curta",
           "--cap-cor", "#FFD400", "--cap-pos", "0.7", "--cap-maiusculas", "--vocab", "Criative", "--preview", "--out", TMP / "cp.mp4")
    assert (TMP / "cp.mp4").exists()


@case("SFX: sem sons do mesmo tipo empilhados e no máximo 3 camadas por instante")
def _():
    from engine.core import tidy_sfx
    ev = [dict(t=1.0, kind="whoosh", vol=.5), dict(t=1.05, kind="whoosh", vol=.9), dict(t=1.0, kind="pop", vol=.7),
          dict(t=1.02, kind="riser", vol=.6), dict(t=1.1, kind="shimmer", vol=.3), dict(t=5.0, kind="pop", vol=.7)]
    out = tidy_sfx(ev)
    assert sum(1 for e in out if e["kind"] == "whoosh") == 1 and [e["vol"] for e in out if e["kind"] == "whoosh"] == [.9]
    assert len([e for e in out if abs(e["t"] - 1.0) < .25]) <= 3 and not any(e["kind"] == "shimmer" for e in out) and len(out) == 4, out


@case("autocut --camera: vídeo de celular com rotação (4K vertical gravado deitado) mantém o tamanho certo")
def _():
    base = TMP / "rot_base.mp4"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=6",
       "-f", "lavfi", "-i", "sine=f=300:d=6,volume='if(lt(mod(t,3),2),1,0)':eval=frame", "-shortest", "-c:v", "libx264", "-c:a", "aac", base)
    rot = TMP / "rot.mov"
    sh("ffmpeg", "-y", "-loglevel", "error", "-display_rotation", "90", "-i", base, "-c", "copy", rot)
    from engine import autocut as ac
    assert tuple(ac.size(rot)) == (360, 640), ac.size(rot)
    studio("autocut", rot, "--camera", "--ritmo", "suave")
    w, h = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(TMP / "rot_autocut.mp4")],
                          capture_output=True, text=True).stdout.strip().split("x")
    assert (w, h) == ("360", "640"), (w, h)


@case("autocut --min-trecho remove fiapos e legenda curta não pisca em palavra relâmpago")
def _():
    src = TMP / "mt.mp4"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=360x640:r=25:d=9",
       "-f", "lavfi", "-i", "sine=f=300:d=9,volume='if(lt(mod(t,3),2)+between(t,5.3,5.6),1,0)':eval=frame", "-shortest", "-c:v", "libx264", "-c:a", "aac", src)
    from engine import autocut as ac
    a = ac.keep_segments(src, "suave", None, True, True, 0.0)
    b = ac.keep_segments(src, "suave", None, True, True, 0.6)
    assert len(b) < len(a) and all(y - x >= 0.6 for x, y in b), (a, b)
    from engine import captions as c
    ws = [dict(w="Procure", t0=0.0, t1=.46), dict(w="o", t0=.46, t1=.52), dict(w="nosso", t0=.52, t1=.9)]
    ass = c.build_ass(ws, TMP / "fl.ass", style="curta", W=1080, H=1920)[0].read_text()
    assert ass.count("Dialogue") == 2, ass


@case("legenda: guardas — lixo ♪/� acima de 20% falha; silêncio final não vira «Obrigado»; legenda não nasce no 0 s; scrim vira caixa")
def _():
    from engine import captions as c
    ws = [dict(w="ola", t0=.2, t1=.5), dict(w="♪", t0=.5, t1=.7), dict(w="♪", t0=.7, t1=.9), dict(w="vamos", t0=.9, t1=1.2)]
    try:
        c.clean_words(ws)
        raise AssertionError("deveria falhar com 50% de lixo")
    except SystemExit:
        pass
    ok = [dict(w=f"p{i}", t0=i * .3, t1=i * .3 + .25) for i in range(9)] + [dict(w="�", t0=2.8, t1=2.9)]
    assert len(c.clean_words(ok)) == 9
    wav = TMP / "tail.wav"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=300:d=2", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=2", "-filter_complex", "[0][1]concat=n=2:v=0:a=1", wav)
    tw = [dict(w="fala", t0=.2, t1=1.0), dict(w="Obrigado", t0=2.6, t1=3.0)]
    assert [w["w"] for w in c.clean_words(tw, str(wav))] == ["fala"]
    a = c.build_ass([dict(w="Oi", t0=0.0, t1=.6)], TMP / "g0.ass", style="karaoke")[0].read_text()
    assert "Dialogue: 0,0:00:00.10" in a, a
    b = c.build_ass([dict(w="Oi", t0=0.5, t1=1.1)], TMP / "g1.ass", style="karaoke", scrim=True)[0].read_text()
    assert ",0,0,0,100,100,0,0,3," in b and "&H99000000" in b, b


@case("revisão: folhas de contato, REVIEW.md, leitura mínima e trecho parado")
def _():
    from engine import review
    assert review.count_words({"title": "Oi *mundo* lindo", "photos": ["a b.jpg"], "items": [{"t": "um dois"}]}) == 5
    assert review.need_seconds(2) == .4 and abs(review.need_seconds(10) - 3.5) < 1e-9
    (TMP / "rv.json").write_text(json.dumps({"scenes": [{"layout": "typographic", "dur": 1.6, "content": {"title": "Uma frase com muitas palavras para ler rapido demais agora mesmo"}},
                                                          {"layout": "typographic", "dur": 2.2, "content": {"title": "Fim"}}]}))
    studio("reel", "--content", TMP / "rv.json", "--theme", "criative-dark", "--preview", "--out", TMP / "rv.mp4")
    tl = json.loads((TMP / "rv.timeline.json").read_text())
    assert all("words" in s for s in tl["scenes"]) and tl["scenes"][0]["words"] >= 10
    out = studio("qa", "review", TMP / "rv.timeline.json", "--video", TMP / "rv.mp4", "--out", TMP / "revisao")
    for f in ("sheet_cenas.png", "sheet_celular.png", "REVIEW.md"):
        assert (TMP / "revisao" / f).exists(), f
    assert "line_unread" in out and "P1" in (TMP / "revisao" / "REVIEW.md").read_text()
    still = TMP / "still.mp4"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x336699:s=180x320:r=10:d=5", "-pix_fmt", "yuv420p", still)
    m = review.measure(dict(total=5, scenes=[dict(i=0, start=0, dur=5)], transitions=[]), str(still))
    assert any(i["code"] == "dead_stretch" for i in m), m


@case("movimento: ease por papel, saída mais curta, grade de batida sem deriva")
def _():
    from engine import motion as m
    assert m.role_ease("arrival") == "out-expo" and m.role_ease("exit") == "in-cubic"
    assert m.exit_duration(.6) < .6 * .6 + 1e-9 and m.exit_duration(.1) == .13
    b = m.beat_times(128, 33, 30)
    assert b[32] == round(32 * 30 * 60 / 128) / 30 == 15.0, b[32]
    assert m.hold_for(1) == .4 and m.hold_for(1, last_line=True) == 2.0 and abs(m.hold_for(6) - 2.3) < 1e-9
    assert .3 <= (m.overlap_start(0, 1, .9) - 0) <= .5 and len(m.TELLS) >= 6


@case("câmera 3D + foco sequencial (determinístico)")
def _():
    from engine import core
    items = [dict(title=f"Item {i}", text="descrição curta") for i in range(1, 5)]
    html = core.page_html(core.slide_canvas("site-list", "criative-light", "reel", dict(kicker="K", title="Como *fazemos*", items=items),
                                            reel=dict(motion="fade-up", scene_dur=5.0, camera="orbit", exit_at=4.5)), reel=True)
    with core.Renderer(0.3) as r:
        pg = r.load(html, 1080, 1920)
        def probe(t):
            pg.evaluate("async t=>{await __seek(t)}", t)
            return pg.evaluate("()=>({tr:document.querySelector('.content').style.transform,fo:[...document.querySelectorAll('[data-focus]>.item')].map(e=>parseFloat(e.style.getPropertyValue('--fo')))})")
        a, b, c = probe(2000), probe(3000), probe(2000)
        assert "rotateY" in a["tr"], a
        assert a == c, "câmera/foco não é determinístico (mesmo t, estados diferentes)"
        assert a["fo"].index(max(a["fo"])) != b["fo"].index(max(b["fo"])), (a, b)  # o foco passa de um item para o seguinte


@case("site → marca + cenas (fixture local)")
def _():
    import http.server, socketserver, threading, functools
    H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "tests/fixtures/site-demo"))
    class Q(H.func):
        def log_message(self, *a): pass
    srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT / "tests/fixtures/site-demo")))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    out = TMP / "site"
    try:
        o = studio("site", f"http://127.0.0.1:{srv.server_address[1]}/", "--out", out, "--name", "Casa Verde")
    finally:
        srv.shutdown()
    b = json.loads((out / "brand.json").read_text())
    c = b["colors"]["accent"].lstrip("#")
    r, g, bl = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    assert abs(r - 0x0E) < 24 and abs(g - 0x7C) < 24 and abs(bl - 0x66) < 24, b["colors"]
    assert not b.get("handle"), b.get("handle")  # nunca inventa @ do Instagram a partir do domínio
    assert "Zorblax" in o and "Space Grotesk" in o, o[-400:]
    sc = json.loads((out / "content.json").read_text())["scenes"]
    assert len(sc) >= 3 and sc[0]["layout"] == "site-hero" and sc[-1]["layout"] == "site-cta", [s["layout"] for s in sc]
    assert not any("…" in json.dumps(x, ensure_ascii=False) for x in sc), "texto cortado com reticências"
    assert not any(x.get("photos") and any("tela-" in p for p in x["photos"]) for x in sc), "print do site usado como foto"
    from PIL import Image
    shots = sorted(out.glob("tela-*.png"))
    assert len(shots) >= 3 and Image.open(shots[0]).width == 1080
    assert (out / "logo.png").exists() and (out / "logo-avatar.png").exists() and (out / "site.json").exists()



@case("site com mídia → vídeo/imagens/ícones reais viram cenas 3D e clima decide trilha")
def _():
    import http.server, socketserver, threading, functools
    d = str(ROOT / "tests/fixtures/site-media")
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Q, directory=d))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    out = TMP / "site-media"
    try:
        o = studio("site", f"http://127.0.0.1:{srv.server_address[1]}/", "--out", out, "--name", "Loja Demo")
    finally:
        srv.shutdown()
    sc = json.loads((out / "content.json").read_text())["scenes"]
    lay = [x["layout"] for x in sc]
    assert lay[0] == "site-video" and "site-showcase" in lay and "site-icons" in lay and lay[-1] == "site-cta", lay
    assert (out / "midia" / "video-01.mp4").exists() and len(list((out / "midia").glob("img-*.png"))) == 3
    ic = next(x for x in sc if x["layout"] == "site-icons")
    assert all(i.get("icon") and (out / i["icon"]).exists() for i in ic["items"]), ic
    assert "clima (Diretor de Movimento)" in o and "set:energetic" in o, o[-500:]


@case("portão dos agentes: bloqueia sem parecer, libera com parecer completo")
def _():
    out = TMP / "gate" / "peca.png"
    out.parent.mkdir()
    env = dict(os.environ, STUDIO_PORTAO="on")
    r = subprocess.run([sys.executable, "studio.py", "render", "--layout", "ds-cover", "--theme", "criative-light", "--brand", "criative", "--sample",
                        "--format", "post", "--out", str(out)], capture_output=True, text=True, cwd=ROOT, env=env)
    assert r.returncode == 0 and "PORTÃO DOS AGENTES" in r.stdout, r.stdout[-300:] + r.stderr[-300:]
    ad = out.parent / "peca.agentes"
    assert (ad / "gate.json").exists() and (ad / "CHECKLIST.md").exists() and (ad / "parecer.modelo.json").exists()
    assert sh(sys.executable, "studio.py", "agentes", out).returncode == 2
    assert sh(sys.executable, "studio.py", "entregar", out, "--para", TMP / "ent").returncode != 0 and not (TMP / "ent").exists()
    g = json.loads((ad / "gate.json").read_text())
    par = json.loads((ad / "parecer.modelo.json").read_text())
    for k, v in par["roles"].items():
        v.update(veredito="ok", visto=[f.name for f in ad.iterdir() if f.suffix == ".png"][:1], notas=["P2 · geral · ok"])
    par["diretor"] = dict(decisao="aprovar", nota=8.5, resumo="teste")
    (ad / "parecer.json").write_text(json.dumps(par))
    if g["blockers"]:
        assert sh(sys.executable, "studio.py", "agentes", out).returncode == 2
    else:
        assert sh(sys.executable, "studio.py", "agentes", out).returncode == 0
        assert sh(sys.executable, "studio.py", "entregar", out, "--para", TMP / "ent").returncode == 0 and (TMP / "ent" / "peca.png").exists()
        out.write_bytes(out.read_bytes() + b"x")  # peça alterada depois do parecer
        assert sh(sys.executable, "studio.py", "agentes", out).returncode == 2


@case("portão: logo clara some em fundo claro? o motor ajusta; print como foto é bloqueado")
def _():
    from engine import logo, gate
    from PIL import Image
    p = TMP / "wl.png"
    im = Image.new("RGBA", (400, 120), (0, 0, 0, 0))
    for x in range(120, 380):
        for y in range(40, 80):
            im.putpixel((x, y), (255, 255, 255, 255))
    for x in range(20, 100):
        for y in range(20, 100):
            im.putpixel((x, y), (200, 0, 7, 255))
    im.save(p)
    assert logo.analyze(p, "#F3F1F3")["readable"] < 0.8
    q = logo.fit(p, "#F3F1F3", ink="#0C090C")
    assert logo.analyze(q, "#F3F1F3")["readable"] > 0.95
    assert gate.PHOTO_BAD.search("tela-03.png") and gate.PHOTO_BAD.search("site-desktop.png") and not gate.PHOTO_BAD.search("fachada.jpg")


print(f"\n{sum(1 for _, ok, _ in results if ok)}/{len(results)} cenários OK")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
