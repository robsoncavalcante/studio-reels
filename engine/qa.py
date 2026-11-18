"""
QA automático (determinístico) — a base objetiva que o Diretor de Criação usa antes de aprovar.

Checagens em peças estáticas / slides:
  • contraste REAL de cada texto contra o fundo renderizado (WCAG 4.5 corpo · 3.0 texto grande)
  • texto cortado/estourando o quadro, palavra quebrada no meio, fonte mínima legível
  • zonas seguras (story/reel: topo 250px, base 340px; feed: laterais 5%)
  • hierarquia (título ≥ 1.5× o segundo nível), densidade de texto, nº de famílias tipográficas
Checagens em reels: duração das cenas, hook, easing×duração, loudness (-14 LUFS) e pico.
"""
from __future__ import annotations

import io
import json
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import color as C
from . import core

INSPECT_JS = r"""
() => {
  const cv = document.querySelector('.canvas'); const cr = cv.getBoundingClientRect();
  const out = [];
  const walker = document.createTreeWalker(cv, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const n = walker.currentNode; const txt = n.textContent.replace(/\s+/g,' ').trim();
    if (!txt) continue;
    const el = n.parentElement; if (!el || el.closest('script,style')) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const range = document.createRange(); range.selectNodeContents(n);
    const rects = [...range.getClientRects()].filter(r => r.width > 1 && r.height > 1);
    if (!rects.length) continue;
    const L = Math.min(...rects.map(r => r.left)), T = Math.min(...rects.map(r => r.top));
    const R = Math.max(...rects.map(r => r.right)), B = Math.max(...rects.map(r => r.bottom));
    let op = 1, p = el; while (p && p !== document.body) { op *= parseFloat(getComputedStyle(p).opacity); p = p.parentElement; }
    // texto cortado por overflow:hidden de um ancestral
    let clipped = false; p = el;
    while (p && p !== cv.parentElement) {
      const s = getComputedStyle(p);
      if (/(hidden|clip)/.test(s.overflowX + s.overflowY)) { const pr = p.getBoundingClientRect(); const fs0 = parseFloat(cs.fontSize);
        const tx = Math.max(3, fs0 * 0.03), ty = fs0 * 0.3;
        if (L < pr.left - tx || R > pr.right + tx || T < pr.top - ty || B > pr.bottom + ty) clipped = true; }
      p = p.parentElement;
    }
    // palavra dividida em duas linhas?
    let broken = false; const re = /\S+/g; let m; const tc = n.textContent;
    while ((m = re.exec(tc))) {
      const wr = document.createRange(); wr.setStart(n, m.index); wr.setEnd(n, m.index + m[0].length);
      const tops = new Set([...wr.getClientRects()].filter(r => r.width > 1).map(r => Math.round(r.top / (parseFloat(cs.fontSize) * 0.45))));
      if (tops.size > 1) { broken = true; break; }
    }
    const words = txt.split(' ');
    let box = el; while (box && box !== cv && (getComputedStyle(box).display === 'inline')) box = box.parentElement;
    const bw = box ? box.getBoundingClientRect().width : (R - L);
    out.push({ text: txt.slice(0, 80), len: txt.length, words: words.length, cls: (el.className && el.className.toString ? el.className.toString() : '').slice(0, 40),
      l: L - cr.left, t: T - cr.top, r: R - cr.left, b: B - cr.top, fs: parseFloat(cs.fontSize), fw: parseInt(cs.fontWeight) || 400,
      family: cs.fontFamily.split(',')[0].replace(/["']/g, '').trim(), color: cs.color, fill: cs.webkitTextFillColor, stroke: cs.webkitTextStrokeColor,
      strokeW: parseFloat(cs.webkitTextStrokeWidth) || 0, opacity: op, clipped, broken, boxW: bw, lines: rects.length });
  }
  return { w: cr.width, h: cr.height, items: out, photos: cv.querySelectorAll('.ph').length, imgs: cv.querySelectorAll('img').length };
}
"""

HIDE_TEXT_CSS = "*{color:transparent!important;-webkit-text-fill-color:transparent!important;text-shadow:none!important;-webkit-text-stroke:0!important}"


def _rgba(s: str):
    m = re.findall(r"[\d.]+", s or "")
    if len(m) < 3:
        return None
    r, g, b = (float(x) for x in m[:3])
    a = float(m[3]) if len(m) > 3 else 1.0
    if (s or "").strip().startswith("color(") and "srgb" in s:  # valores 0–1
        r, g, b = r * 255, g * 255, b * 255
    return r, g, b, a


def _lum_arr(px: np.ndarray) -> np.ndarray:
    v = px / 255.0
    v = np.where(v <= 0.03928, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * v[..., 0] + 0.7152 * v[..., 1] + 0.0722 * v[..., 2]


def safe_zones(fmt: str, W: int, H: int) -> dict:
    if fmt in ("story", "reel"):
        return dict(top=250, bottom=340, side=int(W * .06))
    return dict(top=int(H * .04), bottom=int(H * .04), side=int(W * .045))


def check_static(page_html: str, fmt: str, renderer: core.Renderer, name: str = "peca", annotate: Path | None = None) -> dict:
    F = core.FORMATS[fmt]
    W, H = F["w"], F["h"]
    pg = renderer.load(page_html, W, H)
    data = pg.evaluate(INSPECT_JS)
    shot = pg.screenshot(type="png", clip={"x": 0, "y": 0, "width": W, "height": H})
    pg.add_style_tag(content=HIDE_TEXT_CSS)
    pg.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
    bgshot = pg.screenshot(type="png", clip={"x": 0, "y": 0, "width": W, "height": H})
    img_bg = np.asarray(Image.open(io.BytesIO(bgshot)).convert("RGB")).astype(np.float32)
    sz = safe_zones(fmt, W, H)
    issues: list[dict] = []

    def add(level, code, msg, item=None, fix=None):
        issues.append(dict(level=level, code=code, msg=msg, text=item["text"] if item else None, fix=fix,
                           box=[round(item["l"]), round(item["t"]), round(item["r"]), round(item["b"])] if item else None))

    items = data["items"]
    sizes = []
    fams = set()
    for it in items:
        L, T, R, B = max(0, int(it["l"])), max(0, int(it["t"])), min(W, int(it["r"])), min(H, int(it["b"]))
        # ---- contraste
        fill, stroke = _rgba(it["fill"]), _rgba(it["stroke"])
        col = fill if fill and fill[3] > .1 else (stroke if stroke and it["strokeW"] > 0 and stroke[3] > .1 else _rgba(it["color"]))
        if R - L > 2 and B - T > 2 and col:
            crop = img_bg[T:B, L:R]
            lum_bg = _lum_arr(crop)
            mean_bg = crop.reshape(-1, 3).mean(0)
            a = col[3] * it["opacity"]
            eff = [col[i] * a + mean_bg[i] * (1 - a) for i in range(3)]
            lt = float(_lum_arr(np.array(eff)[None, None, :])[0, 0])
            ratios = (np.maximum(lt, lum_bg) + .05) / (np.minimum(lt, lum_bg) + .05)
            worst = float(np.percentile(ratios, 10))
            it["contrast"] = round(worst, 2)
            large = it["fs"] >= 66 or (it["fs"] >= 50 and it["fw"] >= 700)
            need = 3.0 if large else 4.5
            if worst < need * .6:
                add("blocker", "contrast", f"contraste {worst:.1f}:1 (mín. {need}:1) — texto ilegível sobre o fundo", it,
                    "trocar cor do texto/fundo, escurecer a foto com overlay, ou usar tema de maior contraste")
            elif worst < need:
                add("warn", "contrast", f"contraste limítrofe {worst:.1f}:1 (mín. {need}:1)", it, "reforçar contraste (overlay/sombra/cor)")
        # ---- tamanho mínimo (px num quadro de 1080 de largura)
        px = it["fs"] * (1080 / W)
        sizes.append(px)
        fams.add(it["family"])
        if px < 24:
            add("blocker", "min-size", f"fonte {px:.0f}px: ilegível no celular (mín. 28px; ideal ≥32px)", it, "aumentar fonte ou reduzir quantidade de texto")
        elif px < 28:
            add("warn", "min-size", f"fonte {px:.0f}px: pequena para celular (ideal ≥32px)", it, "aumentar ou encurtar o texto")
        # ---- cortes / estouros
        if it["clipped"]:
            add("blocker", "clipped", "texto cortado pelo próprio container", it, "encurtar texto, reduzir fonte ou ampliar a caixa")
        if it["l"] < -2 or it["t"] < -2 or it["r"] > W + 2 or it["b"] > H + 2:
            add("blocker", "off-canvas", "texto fora do quadro", it, "reposicionar ou reduzir")
        if it["broken"]:
            add("warn", "word-break", "palavra não cabe na largura e é quebrada no meio", it, "diminuir fonte do título, trocar fonte mais estreita ou encurtar a palavra")
        # ---- zonas seguras
        if it["t"] < sz["top"] and it["cls"] and not re.search(r"pager|brand|handle", it["cls"]):
            add("warn", "safe-top", f"texto invade zona do topo ({sz['top']}px) coberta pela interface", it, "descer o bloco de texto")
        if it["b"] > H - sz["bottom"] and not re.search(r"pager|brand|handle", it["cls"]):
            add("warn", "safe-bottom", f"texto invade zona inferior ({sz['bottom']}px) coberta por legenda/botões", it, "subir o bloco de texto")
        if fmt == "reel" and it["b"] > H * .69 and not re.search(r"pager|brand|handle|cta|btn|button", it["cls"]):
            add("warn", "reel-ui-zone", "borda inferior do texto passa de ~69% da altura (boa prática, não é regra oficial: a interface do Instagram cobre a faixa inferior)", it, "subir o texto ou dividir em legendas de 2 linhas")
        if it["l"] < sz["side"] - 2 or it["r"] > W - sz["side"] + 2:
            add("warn", "safe-side", "texto muito próximo da borda lateral (corte no grid 3:4/ em telas diferentes)", it, "aumentar margem lateral")
    # ---- hierarquia
    big = sorted({round(s) for s in sizes}, reverse=True)
    if len(big) >= 2 and big[0] / max(1, big[1]) < 1.5 and len(items) > 2:
        issues.append(dict(level="warn", code="hierarchy", msg=f"hierarquia fraca: maior fonte {big[0]}px vs. segunda {big[1]}px (<1.5×)", text=None, box=None,
                           fix="aumentar o título ou diminuir o texto de apoio"))
    # ---- densidade
    chars = sum(i["len"] for i in items)
    lim = 260 if fmt in ("story", "reel") else 320
    if chars > lim:
        issues.append(dict(level="warn", code="density", msg=f"{chars} caracteres na peça (>{lim}): leitura pesada para redes", text=None, box=None,
                           fix="dividir em mais slides/cenas ou cortar texto"))
    # ---- famílias tipográficas
    if len(fams) > 3:
        issues.append(dict(level="warn", code="fonts", msg=f"{len(fams)} famílias na mesma peça ({', '.join(sorted(fams))}): usar no máx. 2 (+1 de destaque)", text=None, box=None, fix="padronizar com um par de fontes (studio.py fonts pair)"))
    # ---- título longo
    for it in items:
        if "t " in (it["cls"] + " ") and it["words"] > 9:
            add("info", "title-long", f"título com {it['words']} palavras: ideal ≤ 8 para parar o scroll", it, "reescrever mais curto")
    # ---- fotos
    if data["photos"] and not data["imgs"]:
        issues.append(dict(level="info", code="placeholder", msg=f"{data['photos']} espaço(s) de foto ainda são placeholders", text=None, box=None, fix="inserir fotos reais (studio.py stock search)"))
    if annotate:
        im = Image.open(io.BytesIO(shot)).convert("RGB")
        d = ImageDraw.Draw(im)
        colr = {"blocker": (255, 40, 40), "warn": (255, 170, 0), "info": (60, 140, 255)}
        for i in issues:
            if i["box"]:
                d.rectangle(i["box"], outline=colr[i["level"]], width=5)
        annotate.parent.mkdir(parents=True, exist_ok=True)
        im.save(annotate)
    blockers = sum(i["level"] == "blocker" for i in issues)
    warns = sum(i["level"] == "warn" for i in issues)
    score = max(0, 100 - 18 * blockers - 5 * warns)
    return dict(name=name, format=fmt, size=[W, H], score=score, blockers=blockers, warnings=warns,
                fonts=sorted(fams), min_font_px=round(min(sizes)) if sizes else None, chars=chars, issues=issues)


# ------------------------------------------------------------------ reels
def loudness(path: str) -> dict | None:
    r = subprocess.run([core._ffmpeg(), "-hide_banner", "-i", str(path), "-af", "ebur128=peak=true", "-vn", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"Integrated loudness:\s+I:\s+(-?[\d.]+) LUFS", r.stderr) or re.search(r"\bI:\s+(-?[\d.]+) LUFS", r.stderr)
    p = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)
    return dict(lufs=float(m.group(1)), peak=float(p[-1])) if m and p else None


def check_reel(timeline_path: str, video_path: str | None = None) -> dict:
    from . import motion
    tl = json.loads(Path(timeline_path).read_text())
    issues = []

    def add(level, code, msg, fix=None):
        issues.append(dict(level=level, code=code, msg=msg, fix=fix, box=None, text=None))

    total = tl["total"]
    if total > 90:
        add("blocker", "length", f"{total:.0f}s: acima de 90s (limite de Reels)")
    elif total < 5:
        add("warn", "length", f"{total:.1f}s: muito curto para contar algo")
    for s in tl["scenes"]:
        if s["dur"] < 1.2:
            add("warn", "scene-short", f"cena {s['i'] + 1} dura {s['dur']:.1f}s: texto não dá tempo de ler", "≥ 1.8s com texto curto; +0.3s por linha extra")
        if s["dur"] > 6.5:
            add("warn", "scene-long", f"cena {s['i'] + 1} dura {s['dur']:.1f}s: risco de queda de retenção", "dividir ou cortar")
    first = tl["scenes"][0]["dur"] if tl["scenes"] else 0
    if first > 3.5:
        add("warn", "hook", f"primeira cena com {first:.1f}s: o gancho precisa acontecer em 1–3s", "encurtar a abertura")
    for t in tl["transitions"]:
        if t["dur"] > .8:
            add("warn", "transition", f"transição de {t['dur']:.2f}s: lenta para social", "0.3–0.6s")
    if tl.get("ease"):
        w = motion.ease_check(tl["ease"], .7)
        if w:
            add("info", "ease", w)
    if tl.get("beat") and not tl.get("sync"):
        add("info", "sync", "há BPM mas o movimento não está sincronizado à batida", "usar --sync")
    if video_path and Path(video_path).exists():
        ld = loudness(video_path)
        if ld:
            if abs(ld["lufs"] + 14) > 2.5:
                add("warn", "loudness", f"loudness {ld['lufs']:.1f} LUFS (alvo ≈ -14)", "normalizar")
            if ld["peak"] > -1.0:
                add("warn", "peak", f"pico {ld['peak']:.1f} dBFS (> -1): risco de distorção após compressão da plataforma", "limitar o pico a -1.5 dBTP")
    from . import review
    issues += review.measure(tl, video_path)
    blockers = sum(i["level"] == "blocker" for i in issues)
    warns = sum(i["level"] == "warn" for i in issues)
    return dict(name=Path(timeline_path).stem, score=max(0, 100 - 18 * blockers - 5 * warns), blockers=blockers, warnings=warns, issues=issues)


def format_report(rep: dict) -> str:
    sym = {"blocker": "✗", "warn": "!", "info": "·"}
    lines = [f"QA · {rep['name']} · nota {rep['score']}/100 · {rep['blockers']} bloqueio(s) · {rep['warnings']} aviso(s)"]
    for i in sorted(rep["issues"], key=lambda x: ["blocker", "warn", "info"].index(x["level"])):
        t = f" «{i['text']}»" if i.get("text") else ""
        if i.get("t") is not None:
            t = f" @{i['t']:.1f}s{t}"
        f = f"\n      → {i['fix']}" if i.get("fix") else ""
        lines.append(f"  {sym[i['level']]} [{i['code']}]{t} {i['msg']}{f}")
    return "\n".join(lines)
