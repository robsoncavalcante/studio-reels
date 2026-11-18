"""
Site → marca + reel.

`studio.py site <url>` abre o site num Chrome (Playwright), rola a página (dispara animações e contadores), extrai textos, seções,
logo, cores e fontes, grava a marca (brand.json) e as telas do site em formato celular (1080 px de largura) e monta um reel
com os layouts do motor. Funciona com qualquer site; nada é específico de uma empresa.

Regras da marca (aprendidas de capturas reais):
  • acento = a cor saturada que se repete em mais papéis (botão, link, título, fundo de seção), nunca o azul padrão de link
  • elementos de alerta/erro/sucesso/aviso não contam
  • fontes de ícone (Font Awesome, eicons, dashicons…) nunca são fonte de título nem de texto
  • fonte do site fora do catálogo é substituída por uma parecida do catálogo e a troca é avisada
"""
from __future__ import annotations

import colorsys
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from . import core

GENERIC = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "ui-sans-serif", "ui-serif", "ui-monospace", "-apple-system",
           "blinkmacsystemfont", "segoe ui", "arial", "helvetica", "helvetica neue", "times new roman", "roboto", "inherit"}
ICON_FONTS = re.compile(r"awesome|icomoon|eicons|dashicons|webflow-icons|material.?icons|glyphicons|fontello|elementor-icons|swiper|slick", re.I)
DEFAULT_LINKS = {"#0000EE", "#0000FF", "#551A8B", "#0645AD"}

JS_FIX = """() => {
  const css = document.createElement('style');
  css.textContent = '[class*=cookie],[id*=cookie],[class*=consent],[id*=consent],[class*=lgpd],[id*=lgpd],[class*=cmplz],#onetrust-consent-sdk,.cli-modal-backdrop{display:none!important}';
  document.head.appendChild(css);
  const W = innerWidth;
  document.querySelectorAll('*').forEach(el => {
    const cs = getComputedStyle(el);
    if (cs.position === 'fixed') {
      const r = el.getBoundingClientRect();
      if (r.width >= W * 0.9 && r.top < 90) { el.style.position = 'absolute'; } else { el.style.display = 'none'; }
    } else if (cs.position === 'sticky') { el.style.position = 'static'; }
  });
}"""

JS_EXTRACT = r"""() => {
  const vis = el => { const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && cs.visibility !== 'hidden' && cs.display !== 'none' && parseFloat(cs.opacity) > 0.05; };
  const txt = el => (el.innerText || '').replace(/\s+/g, ' ').trim();
  const cls = el => (typeof el.className === 'string' ? el.className : (el.className && el.className.baseVal) || '');
  const ALERT = /alert|error|success|warning|notice|danger|invalid/i;
  const inAlert = el => { for (let e = el; e && e !== document.body; e = e.parentElement) { if (ALERT.test(cls(e))) return true; } return false; };
  const rgba = s => { const m = (s || '').match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
  const hex = c => '#' + [c.r, c.g, c.b].map(v => Math.round(v).toString(16).padStart(2, '0')).join('').toUpperCase();
  const tally = {bg: {}, text: {}, heading: {}, link: {}, button: {}};
  const add = (role, c, w) => { if (!c || c.a < 0.5 || !(w > 0)) return; const h = hex(c); tally[role][h] = (tally[role][h] || 0) + w; };
  const isBtn = el => el.tagName === 'BUTTON' || el.getAttribute('role') === 'button' || (/(^|[ _-])(btn|button|cta)([ _-]|$)/i.test(cls(el)) && el.tagName !== 'DIV');
  const all = Array.from(document.querySelectorAll('body *')).slice(0, 3500);
  for (const el of all) {
    if (!vis(el) || inAlert(el)) continue;
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el), bg = rgba(cs.backgroundColor);
    if (bg && bg.a >= 0.5) add(isBtn(el) ? 'button' : 'bg', bg, isBtn(el) ? 60 : Math.min(r.width * r.height / 1000, 2500));
    const direct = Array.from(el.childNodes).filter(n => n.nodeType === 3 && n.textContent.trim()).map(n => n.textContent.trim()).join(' ');
    if (direct.length > 1) {
      const c = rgba(cs.color), role = /^H[1-6]$/.test(el.tagName) ? 'heading' : (el.tagName === 'A' && !isBtn(el) ? 'link' : 'text');
      if (!isBtn(el)) add(role, c, direct.length);
    }
  }
  const pick = sel => { const e = document.querySelector(sel); return e && vis(e) ? getComputedStyle(e).fontFamily : ''; };
  const fonts = {h1: pick('h1'), h2: pick('h2'), h3: pick('h3'), body: getComputedStyle(document.body).fontFamily,
                 button: pick('button, .elementor-button, .btn, [class*=button]'), p: pick('p')};
  const bodyBg = rgba(getComputedStyle(document.body).backgroundColor), htmlBg = rgba(getComputedStyle(document.documentElement).backgroundColor);
  const pageBgSet = !!((bodyBg && bodyBg.a >= 0.5) || (htmlBg && htmlBg.a >= 0.5));
  const pageBg = (bodyBg && bodyBg.a >= 0.5) ? hex(bodyBg) : ((htmlBg && htmlBg.a >= 0.5) ? hex(htmlBg) : '#FFFFFF');
  // seções
  let cand = Array.from(document.querySelectorAll('.elementor-top-section, .e-con.e-parent, main > section, body > section, main > div > section, section'));
  cand = cand.filter(e => vis(e) && e.getBoundingClientRect().height > 180 && !e.closest('header, footer, nav, [class*=elementor-location-header], [class*=elementor-location-footer]'));
  cand = cand.filter(e => !cand.some(o => o !== e && o.contains(e)));
  if (cand.length < 2) cand = Array.from(document.body.children).filter(e => vis(e) && e.getBoundingClientRect().height > 180 && !/^(HEADER|FOOTER|NAV|SCRIPT|STYLE)$/.test(e.tagName));
  const headingOf = s => Array.from(s.querySelectorAll('h1, h2, .elementor-heading-title')).find(h => vis(h) && txt(h).length > 2);
  const descOf = h => { let e = h; for (let i = 0; i < 4 && e; i++, e = e.parentElement) {
      const p = Array.from(e.querySelectorAll('p')).find(x => vis(x) && txt(x).length > 15 && !x.contains(h) && !h.contains(x)); if (p) return txt(p); } return ''; };
  const sections = cand.slice(0, 16).map(s => {
    const r = s.getBoundingClientRect(), h = headingOf(s);
    const subs = Array.from(s.querySelectorAll('h3, h4, h5, .elementor-icon-box-title, .elementor-image-box-title')).filter(x => vis(x) && txt(x).length > 1 && txt(x).length < 70);
    const items = []; const seen = new Set();
    for (const x of subs) { const t = txt(x); if (seen.has(t)) continue; seen.add(t); items.push({title: t, text: descOf(x).slice(0, 260)}); if (items.length >= 6) break; }
    const quotes = Array.from(s.querySelectorAll('blockquote, [class*=testimonial] p, [class*=depoimento] p')).map(txt).filter(t => t.length > 40).slice(0, 3);
    const numEls = Array.from(s.querySelectorAll('*')).filter(e => e.children.length === 0 && /^[+\-]?\s*[\d.,]+\s*[%°kKmM+]*$/.test(txt(e)) && txt(e).length <= 9);
    const nums = numEls.map(txt);
    const stats = numEls.slice(0, 4).map(e => { let c = e.parentElement, label = '', text = '';
      for (let i = 0; i < 4 && c && c !== s; i++, c = c.parentElement) {
        const parts = Array.from(c.querySelectorAll('*')).filter(x => x.children.length === 0 && x !== e && vis(x) && txt(x)).map(txt)
          .filter(t => !/^[+\-]?\s*[\d.,]+\s*[%°kKmM+]*$/.test(t));
        if (parts.length) { label = parts[0]; text = parts.slice(1).join(' ').slice(0, 90); break; } }
      return {number: txt(e), label: label.slice(0, 40), text}; });
    const sub = Array.from(s.querySelectorAll('p, .elementor-widget-text-editor')).find(p => vis(p) && txt(p).length > 25);
    const bg = rgba(getComputedStyle(s).backgroundColor);
    return {top: r.top + scrollY, height: r.height, heading: h ? txt(h).slice(0, 140) : '', sub: sub ? txt(sub).slice(0, 220) : '',
            items, quotes, nums, stats, bg: bg && bg.a >= 0.5 ? hex(bg) : '', imgs: s.querySelectorAll('img').length};
  });
  const buttons = Array.from(document.querySelectorAll('a, button')).filter(e => vis(e) && isBtn(e) && !e.closest('header, nav') && txt(e).length > 1 && txt(e).length < 32).map(txt);
  const navBtn = Array.from(document.querySelectorAll('header a, header button')).filter(e => vis(e) && isBtn(e)).map(txt);
  // logo
  const logoSel = ['header img[class*=logo]', 'header [class*=logo] img', 'header [class*=logo] svg', '[class*=site-logo] img', 'a[class*=logo] img', 'header a img', 'header img', 'header svg'];
  let logo = null; for (const q of logoSel) { const e = Array.from(document.querySelectorAll(q)).find(vis); if (e) { logo = e; break; } }
  if (logo) { logo.setAttribute('data-sr-logo', '1'); }
  const m = n => { const e = document.querySelector(`meta[name="${n}"], meta[property="${n}"]`); return e ? e.content : ''; };
  const h1 = Array.from(document.querySelectorAll('h1')).find(vis);
  const hs = h1 ? getComputedStyle(h1) : null;
  const btnEl = Array.from(document.querySelectorAll('a, button')).find(e => vis(e) && isBtn(e) && !e.closest('header, nav'));
  const bs = btnEl ? getComputedStyle(btnEl) : null;
  const style = {hCase: hs ? hs.textTransform : '', hSpacing: hs ? hs.letterSpacing : '', hWeight: hs ? hs.fontWeight : '', hSize: hs ? parseFloat(hs.fontSize) : 0,
                 btnRadius: bs ? parseFloat(bs.borderRadius) || 0 : 0, btnH: bs ? parseFloat(bs.height) : 0, hColor: hs ? hex(rgba(hs.color) || {r:0,g:0,b:0,a:1}) : ''};
  const logoImg = logo && logo.tagName === 'IMG' ? (logo.currentSrc || logo.src) : '';
  return {pageBgSet, title: document.title, description: m('description') || m('og:description'), ogImage: m('og:image'), siteName: m('og:site_name'), lang: document.documentElement.lang,
          h1: h1 ? txt(h1) : '', pageBg, fonts, tally, sections, buttons, navBtn, hasLogo: !!logo, logoSrc: logoImg, style, height: document.documentElement.scrollHeight,
          loadedFonts: Array.from(document.fonts).filter(f => f.status === 'loaded').map(f => f.family.replace(/["']/g, ''))};
}"""


# ------------------------------------------------------------------ cores
def _rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, int(round(v)))):02X}" for v in rgb)


def _hls(h: str):
    r, g, b = (v / 255 for v in _rgb(h))
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    return hh * 360, l, s


def _lum(h: str) -> float:
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(v) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _mix(a: str, b: str, t: float) -> str:
    return _hex([x + (y - x) * t for x, y in zip(_rgb(a), _rgb(b))])


def _saturated(h: str) -> bool:
    _, l, s = _hls(h)
    return s >= 0.25 and 0.12 <= l <= 0.88 and h.upper() not in DEFAULT_LINKS


def _family(css: str) -> str:
    for part in (css or "").split(","):
        f = part.strip().strip("\"'").strip()
        if f and f.lower() not in GENERIC and not ICON_FONTS.search(f):
            return f
    return ""


def pick_brand(data: dict, fonts_catalog=None) -> dict:
    """Marca a partir dos dados extraídos: bg, bg2, fg, accent, accent2 e fontes."""
    t = data["tally"]
    bg = data.get("pageBg") or "#FFFFFF"
    bgs = sorted(t["bg"].items(), key=lambda kv: -kv[1])
    if not data.get("pageBgSet", True) and bgs and bgs[0][1] > 0:
        # página sem fundo definido no body: usa o fundo mais presente
        bg = bgs[0][0]
    texts = sorted(t["text"].items(), key=lambda kv: -kv[1])
    fg = next((c for c, _ in texts if _contrast(c, bg) >= 4.5), None) or ("#FFFFFF" if _lum(bg) < 0.35 else "#111111")
    score: dict = {}
    for role in ("button", "link", "heading", "text", "bg"):
        sat = {c: w for c, w in t[role].items() if _saturated(c)}
        tot = sum(sat.values())
        for c, w in sat.items():
            score[c] = score.get(c, 0) + (w / tot) * (1.5 if role == "button" else 1.0)
    ranked = sorted(score.items(), key=lambda kv: -kv[1])
    accent = ranked[0][0] if ranked else (next(iter(sorted(t["button"].items(), key=lambda kv: -kv[1])), (fg,))[0])
    accent2 = None
    for c, _ in ranked[1:]:
        if abs(_hls(c)[0] - _hls(accent)[0]) >= 25 or abs(_hls(c)[1] - _hls(accent)[1]) >= 0.18:
            accent2 = c
            break
    if not accent2:
        accent2 = _mix(accent, "#FFFFFF" if _lum(bg) < 0.35 else "#000000", 0.25)
    st_ = data.get("style") or {}
    hc = (st_.get("hColor") or "").upper()
    heads = sorted(t["heading"].items(), key=lambda kv: -kv[1])
    ink = next((c for c in ([hc] if hc else []) + [c for c, _ in heads] if _contrast(c, bg) >= 7 and not _saturated(c)), None) or fg
    muted = _mix(bg, ink, 0.55)
    if _contrast(muted, bg) < 4.5:
        muted = _mix(bg, ink, 0.7)
    bg2 = _mix(bg, fg, 0.07)
    style = {}
    cs = (st_.get("hCase") or "").lower()
    if cs in ("uppercase", "lowercase", "capitalize"):
        style["dcase"] = cs
    try:
        ls = float(str(st_.get("hSpacing", "")).replace("px", "")) / max(1.0, float(st_.get("hSize") or 0) or 1.0)
        style["dls"] = f"{max(-0.06, min(0.12, ls)):.3f}em"
    except Exception:  # noqa
        pass
    try:
        w = int(float(st_.get("hWeight") or 0))
        if 300 <= w <= 900:
            style["dw"] = w
    except Exception:  # noqa
        pass
    br = float(st_.get("btnRadius") or 0)
    bh = float(st_.get("btnH") or 0)
    if br:
        style["btn_radius"] = "999px" if bh and br >= bh / 2 - 1 else f"{min(br, 40) / 14.4:.2f}cqw"
    f = data.get("fonts", {})
    disp = _family(f.get("h1")) or _family(f.get("h2")) or _family(f.get("body"))
    body = _family(f.get("p")) or _family(f.get("body")) or disp
    subs = {}
    cat = fonts_catalog or {}
    out_d, out_b = disp, body
    if cat:
        if disp and disp not in cat:
            subs[disp] = "Space Grotesk"
            out_d = "Space Grotesk"
        if body and body not in cat:
            subs[body] = "DM Sans"
            out_b = "DM Sans"
    return dict(colors=dict(bg=bg, bg2=bg2, fg=ink, muted=muted, accent=accent, accent2=accent2), style=style, font_display=out_d or "Space Grotesk",
                font_body=out_b or "DM Sans", dark=_lum(bg) < 0.35, fonts_site=dict(display=disp, body=body), fonts_substituted=subs)


# ------------------------------------------------------------------ texto → cenas
def sentence(s: str, names: bool = False) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    if s and (s.isupper() or sum(c.isupper() for c in s) > 0.6 * max(1, sum(c.isalpha() for c in s))):
        s = s.title() if names and len(s.split()) <= 3 and len(s) <= 24 else s.lower().capitalize()
    return s


def hl(title: str) -> str:
    """Destaca a última palavra com *...* (o motor pinta de acento)."""
    w = title.split()
    if len(w) >= 3 and "*" not in title:
        w[-1] = "*" + w[-1].rstrip(".,!?") + "*" + (w[-1][-1] if w[-1][-1] in ".,!?" else "")
    return " ".join(w)


def clip(s: str, n: int) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0].rstrip(",;:-– ")
    return cut + "…"


def _host(u: str) -> str:
    return (urlparse(u if "://" in u else "https://" + u).hostname or "").replace("www.", "")


def is_local(h: str) -> bool:
    return bool(re.fullmatch(r"[\d.]+|localhost|\[?[0-9a-f:]+\]?", h or ""))


GLUED = re.compile(r"[a-zà-ú]{2}[A-ZÀ-Ú]{4,}|[A-ZÀ-Ú]{5,}[a-zà-ú]{3,}")


def glued(s: str) -> bool:
    """Texto com palavras coladas (ex.: «CRIATIVIDADEQUE TRANSFORMAIDEIAS» vindo de meta description mal escrita)."""
    return bool(GLUED.search(s or "")) or any(len(w) > 22 and w.isalpha() for w in (s or "").split())


def _first(t: str, mx: int = 110) -> str:
    """Primeira frase inteira (nunca corta no meio); se ela passa do limite, não usa texto de apoio."""
    t = (t or "").strip()
    if not t:
        return ""
    f = re.split(r"(?<=[.!?])\s", t)[0]
    return f if len(f) <= mx else ""


def _items(s: dict, n: int) -> list:
    out = []
    for i in s.get("items", []):
        if i.get("title"):
            out.append(dict(title=sentence(i["title"], names=True), text=_first(sentence(i.get("text", "")))))
        if len(out) >= n:
            break
    for i in out:
        if i["title"].isupper() or i["title"].lower() == i["title"] and False:
            i["title"] = i["title"].title()
    return out


def build_scenes(data: dict, shots: list, logo: str | None, handle: str, max_scenes: int = 7, hero_bg: str | None = None, *,
                 handle_at: str = "", alt_theme: str | None = None, name: str = "", author: str = "") -> list:
    """Cenas fiéis ao site: títulos e textos completos (nada cortado com «…»), números com rótulo, sem prints como foto.
    Texto longo ganha mais tempo de tela, nunca é cortado. Hero e CTA podem usar o tema alternativo (ex.: versão escura)."""
    from . import review
    secs = [s for s in data["sections"] if s.get("heading") or s.get("items") or s.get("quotes") or s.get("stats")]
    cta = next((b for b in data.get("buttons", []) if len(b) < 26), None) or next(iter(data.get("navBtn", [])), None) or "Saiba mais"
    h1 = sentence(data.get("h1") or (secs[0]["heading"] if secs else data.get("title", "")))
    hero_sub = sentence(secs[0].get("sub", "")) if secs else ""
    desc = sentence(data.get("description") or "")
    sub = hero_sub or ("" if glued(data.get("description") or "") else desc)
    tone = {"theme": alt_theme} if alt_theme else {}
    scenes = [dict(layout="site-hero", kicker="", title=hl(h1), subtitle=sub, cta=sentence(cta), **tone)]
    body = []
    for s in secs:
        head = sentence(s.get("heading", ""))
        if not head or head == h1:
            continue
        stats = [x for x in s.get("stats", []) if re.search(r"\d", x.get("number", ""))]
        its = _items(s, 6)
        if s.get("quotes"):
            body.append(dict(layout="testimonial", kicker="Clientes", quote=s["quotes"][0], author=author or "Cliente", role=name, rating=5, photos=[], _p=3))
        elif len(stats) >= 2 and not any(b["layout"] == "site-stats" for b in body):
            body.append(dict(layout="site-stats", kicker=head if len(head) <= 26 else "", title=hl(head) if len(head) > 26 else "Em *números*",
                             items=[dict(number=x["number"].replace(" ", ""), title=sentence(x.get("label", "")) or "", text=sentence(x.get("text", ""))) for x in stats[:3]], _p=2))
        elif len(its) >= 3:
            rows = its[:5] if any(i["text"] for i in its) else its[:6]
            if len(rows) > 4:
                rows = [dict(title=r["title"], text="") for r in rows]
            body.append(dict(layout="site-list", kicker="", title=hl(head), items=rows, _p=2))
    keep = max(0, max_scenes - 2)
    top = sorted(sorted(range(len(body)), key=lambda i: -body[i]["_p"])[:keep])  # os mais relevantes, na ordem do site
    for i in top:
        scenes.append({k: v for k, v in body[i].items() if k != "_p"})
    short = hero_sub if len(hero_sub) <= 70 else (re.split(r"(?<=[.!?])\s", hero_sub)[0] if re.split(r"(?<=[.!?])\s", hero_sub)[0] else hero_sub)
    scenes.append(dict(layout="site-cta", kicker="Próximo passo", title=hl(sentence(cta)) if len(cta.split()) >= 3 else f"*{sentence(cta)}*",
                       subtitle=short or sub, cta=sentence(cta), **tone))
    for k, sc in enumerate(scenes):
        words = review.count_words({a: b for a, b in sc.items() if a not in ("layout", "photos", "dur", "theme")})
        sc["dur"] = round(min(6.5, max(3.0, review.need_seconds(words) + 0.4)), 1)
        if k == 0:
            sc["dur"] = max(3.6, min(sc["dur"], 5.0))
        elif k == len(scenes) - 1:
            sc["dur"] = min(sc["dur"], 4.6)
    return scenes


def _square(src: Path, dst: Path, pad: float = 0.18):
    """Logo largo → quadrado transparente com margem, para o avatar redondo não cortar a marca."""
    from PIL import Image
    im = Image.open(src).convert("RGBA")
    side = int(max(im.size) * (1 + pad * 2))
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
    sq.save(dst)


# ------------------------------------------------------------------ captura
def capture(url: str, out: Path, shots: int = 6, log=print) -> dict:
    """Abre o site, extrai os dados e grava telas/logo em `out`. Retorna dict com data, brand, shots, logo."""
    from playwright.sync_api import sync_playwright
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not re.match(r"^https?://", url):
        url = "https://" + url
    pw = sync_playwright().start()
    kw = dict(args=["--no-sandbox", "--force-color-profile=srgb"])
    cp = core._chrome_path()
    if cp:
        kw["executable_path"] = cp
    br = pw.chromium.launch(**kw)

    def open_page(ctx):
        pg = ctx.new_page()
        pg.goto(url, wait_until="load", timeout=60000)
        try:
            pg.wait_for_load_state("networkidle", timeout=8000)
        except Exception:  # noqa
            pass
        h = pg.evaluate("document.documentElement.scrollHeight")
        y = 0
        while y < h:  # rolagem: dispara animações de entrada, carga preguiçosa e contadores
            pg.evaluate(f"window.scrollTo(0,{y})")
            pg.wait_for_timeout(140)
            y += 500
            h = pg.evaluate("document.documentElement.scrollHeight")
        pg.wait_for_timeout(900)
        pg.evaluate("window.scrollTo(0,0)")
        pg.wait_for_timeout(400)
        pg.evaluate(JS_FIX)
        return pg

    res: dict = {"url": url}
    try:
        ctx = br.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        pg = open_page(ctx)
        data = pg.evaluate(JS_EXTRACT)
        logo = None
        if data.get("hasLogo"):
            got = False
            src = data.get("logoSrc") or ""
            if src and not src.startswith("data:") and not src.lower().split("?")[0].endswith(".svg"):
                try:  # arquivo original (PNG/JPG/WebP com transparência), não um print do cabeçalho
                    rsp = ctx.request.get(src, timeout=20000)
                    if rsp.ok:
                        from PIL import Image
                        import io
                        Image.open(io.BytesIO(rsp.body())).convert("RGBA").save(out / "logo.png")
                        got = True
                except Exception as e:  # noqa
                    log(f"! logo original não baixou ({type(e).__name__}); uso a captura")
            if not got:
                try:
                    el = pg.query_selector("[data-sr-logo]")
                    el.screenshot(path=str(out / "logo.png"), omit_background=True)
                    got = True
                except Exception as e:  # noqa
                    log(f"! logo não capturado: {type(e).__name__}")
            if got:
                logo = "logo.png"
        try:
            pg.screenshot(path=str(out / "site-desktop.png"), full_page=True)
        except Exception:  # noqa
            pg.screenshot(path=str(out / "site-desktop.png"))
        ctx.close()
        # celular: telas 9:16 do site, 1080 px de largura
        ctx = br.new_context(viewport={"width": 390, "height": 693}, device_scale_factor=1080 / 390, is_mobile=True, has_touch=True,
                             user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
        pm = open_page(ctx)
        mdata = pm.evaluate(JS_EXTRACT)
        total = mdata["height"]
        ys = [0] + [int(s["top"]) for s in mdata["sections"] if s.get("heading") or s.get("items")]
        ys = [min(y, max(0, total - 693)) for y in ys]
        picked, last = [], -9999
        for y in ys:
            if y - last >= 500 and len(picked) < shots:
                picked.append(y)
                last = y
        names = []
        for i, y in enumerate(picked, 1):
            pm.evaluate(f"window.scrollTo(0,{y})")
            pm.wait_for_timeout(750)
            n = f"tela-{i:02d}.png"
            pm.screenshot(path=str(out / n))
            names.append(n)
        # fundo do hero sem textos (o reel põe o título por cima)
        pm.evaluate("window.scrollTo(0,0)")
        pm.add_style_tag(content="h1,h2,h3,h4,h5,h6,p,a,button,header,nav,span,li,blockquote,label,input{visibility:hidden!important}")
        pm.wait_for_timeout(500)
        pm.screenshot(path=str(out / "fundo-01.png"))
        ctx.close()
    finally:
        br.close()
        pw.stop()
    data["sections"] = mdata["sections"] if len(mdata["sections"]) >= len(data["sections"]) else data["sections"]
    res.update(data=data, shots=names, logo=logo, hero_bg="fundo-01.png")
    return res
