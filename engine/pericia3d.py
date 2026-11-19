"""Perícia de referência 3D e folha de revisão (Studio Reels).

`pericia(ref, destino)`  mede um vídeo ou imagem de referência e escreve MEDIDO.md + FICHA.md (a preencher).
`folha(video, saida)`    folha de quadros de um mp4 para revisar movimento antes de entregar.
"""
from __future__ import annotations
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

IMG = (".jpg", ".jpeg", ".png", ".webp")


def _probe(p: Path) -> dict:
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate:format=duration",
                        "-of", "json", str(p)], capture_output=True, text=True).stdout
    j = json.loads(o or "{}")
    st = (j.get("streams") or [{}])[0]
    n, d = (st.get("r_frame_rate") or "30/1").split("/")
    return dict(w=st.get("width"), h=st.get("height"), fps=float(n) / float(d or 1), dur=float((j.get("format") or {}).get("duration") or 0))


def _frames(p: Path, fps: float, w: int, tmp: Path) -> list[Path]:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(p), "-vf", f"fps={fps},scale={w}:-2", str(tmp / "f%04d.jpg")], check=True)
    return sorted(tmp.glob("f*.jpg"))


def _lum(a: np.ndarray) -> np.ndarray:
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def _palette(arrs: list[np.ndarray], k=6) -> list[str]:
    px = np.concatenate([a.reshape(-1, 3)[::37] for a in arrs]).astype(np.uint8)
    im = Image.fromarray(px.reshape(-1, 1, 3)).quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    pal = im.getpalette()[: k * 3]
    cnt = sorted(im.getcolors(), reverse=True)
    return ["#%02X%02X%02X" % tuple(pal[i * 3: i * 3 + 3]) for _, i in cnt]


def _sheet(imgs: list[Path], out: Path, cols=6, w=240, labels=None):
    ims = [Image.open(i).convert("RGB") for i in imgs]
    if not ims:
        return
    h = int(ims[0].height * w / ims[0].width)
    rows = (len(ims) + cols - 1) // cols
    sh = Image.new("RGB", (cols * w, rows * (h + 18)), (24, 24, 28))
    d = ImageDraw.Draw(sh)
    for i, im in enumerate(ims):
        x, y = (i % cols) * w, (i // cols) * (h + 18)
        sh.paste(im.resize((w, h)), (x, y + 18))
        d.text((x + 4, y + 3), (labels[i] if labels else f"{i}"), fill=(230, 230, 235))
    out.parent.mkdir(parents=True, exist_ok=True)
    sh.save(out, quality=88)


FICHA = """# Ficha 3D (preencher antes de construir; o Motion 3D só começa depois dela)

Modo: fidelidade | estilo            Referência: {ref}
Mecanismo (uma frase que um espectador diria):
Momentos (3 a 6, com janela em segundos):
Câmera: ortográfica | perspectiva · lente ≈ ° · altura ≈ ° · parada | órbita | aproxima
Luz: de onde vem · razão claro÷sombra no objeto principal · sombra dura | média | macia
Materiais: objeto principal (fosco | verniz | metal | vidro) · apoio
Cor (medida em MEDIDO.md): fundo {fundo} · acento {acento} · quando o acento aparece
Ritmo: pausa e estalo | travelling | contínuo · onde está o soco: __ s
Nunca faz (3 itens):
Troca (o que é da referência e NÃO entra → o que é da marca):
"""


def pericia(ref: str | Path, destino: str | Path) -> Path:
    ref, dest = Path(ref), Path(destino)
    dest.mkdir(parents=True, exist_ok=True)
    lines = [f"# Medido: {ref.name}", ""]
    tmp = Path(tempfile.mkdtemp(prefix="per3d-"))
    if ref.suffix.lower() in IMG:
        im = Image.open(ref).convert("RGB")
        a = np.asarray(im.resize((320, int(320 * im.height / im.width)))).astype(float)
        arrs, motion, cuts, info = [a], [], [], dict(w=im.width, h=im.height, fps=0, dur=0)
        (dest / "quadro.jpg").write_bytes(ref.read_bytes()) if ref.suffix.lower() in (".jpg", ".jpeg") else im.save(dest / "quadro.jpg")
        lines.append(f"Imagem {im.width}×{im.height}. Movimento: **proposta sua** (imagem não mostra movimento).")
    else:
        info = _probe(ref)
        fr = _frames(ref, 4, 320, tmp)
        arrs = [np.asarray(Image.open(f)).astype(float) for f in fr]
        motion = [float(np.abs(arrs[i] - arrs[i - 1]).mean()) for i in range(1, len(arrs))]
        med = float(np.median(motion)) if motion else 0
        cuts = [round((i + 1) / 4, 2) for i, m in enumerate(motion) if m > max(18, med * 6)]
        lines.append(f"Vídeo {info['w']}×{info['h']} · {info['dur']:.1f} s · {info['fps']:.0f} fps")
        _sheet(fr[::4], dest / "folha-1fps.jpg", labels=[f"{i}s" for i in range(len(fr[::4]))])
        keys = [fr[min(len(fr) - 1, int(len(fr) * q))] for q in (.1, .35, .6, .85)]
        for i, k in enumerate(keys, 1):
            Image.open(k).save(dest / f"chave-{i}.jpg")
    L = np.concatenate([_lum(a).ravel() for a in arrs])
    p5, p50, p95 = np.percentile(L, [5, 50, 95])
    sat = float(np.mean([(a.max(-1) - a.min(-1)).mean() for a in arrs]))
    pal = _palette(arrs)
    lines += ["", "## Cor", f"- Luminância p5 / p50 / p95: {p5:.0f} / {p50:.0f} / {p95:.0f} (0–255)",
              f"- Saturação média: {sat:.0f}", f"- Paleta (mais frequente primeiro): {' '.join(pal)}",
              f"- Fundo provável: {pal[0]} · acento provável: {next((c for c in pal[1:] if max(int(c[i:i+2], 16) for i in (1, 3, 5)) - min(int(c[i:i+2], 16) for i in (1, 3, 5)) > 60), pal[min(1, len(pal)-1)])}"]
    if motion:
        m = np.array(motion)
        calm = float((m < max(1.0, np.median(m) * .35)).mean() * 100)
        top = [round((int(i) + 1) / 4, 2) for i in np.argsort(m)[-3:][::-1]]
        fam = "pausa e estalo" if calm > 35 and m.max() > 6 * max(np.median(m), .1) else ("contínuo" if calm < 15 else "travelling")
        lines += ["", "## Movimento", f"- Cortes secos prováveis (s): {cuts or 'nenhum'}", f"- Quadros quase parados: {calm:.0f}%",
                  f"- Picos de movimento em (s): {top}", f"- Família de ritmo sugerida: **{fam}** (confirme no olho)"]
        (dest / "movimento.json").write_text(json.dumps(dict(motion=[round(x, 2) for x in motion], cuts=cuts), indent=1))
    lines += ["", "## O que a medição NÃO diz (olhe a folha e preencha a ficha)", "- lente e altura da câmera, direção e dureza da luz, materiais, proporções, mecanismo"]
    (dest / "MEDIDO.md").write_text("\n".join(lines), encoding="utf-8")
    fundo, acento = pal[0], pal[1] if len(pal) > 1 else pal[0]
    (dest / "FICHA.md").write_text(FICHA.format(ref=ref.name, fundo=fundo, acento=acento), encoding="utf-8")
    return dest / "MEDIDO.md"


def folha(video: str | Path, saida: str | Path, cada: float = 0.5) -> Path:
    video, saida = Path(video), Path(saida)
    info = _probe(video)
    tmp = Path(tempfile.mkdtemp(prefix="fol3d-"))
    fr = _frames(video, 1 / cada, 240, tmp)
    _sheet(fr, saida, cols=8, w=200, labels=[f"{i * cada:.1f}s" for i in range(len(fr))])
    return saida
