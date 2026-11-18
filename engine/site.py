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
    const NUM = /^(n\.?\s?[ºo°]\s*)?[+\-]?\s*[\d.,]+\s*([%°kKmM+]|\s?(milh[ãõ][oe]s?|mil|bilh[ãõ][oe]s?|mi|bi))*$/i;
    const numEls = Array.from(s.querySelectorAll('*')).filter(e => e.children.length === 0 && NUM.test(txt(e)) && txt(e).length <= 18);
    const nums = numEls.map(txt);
    const stats = numEls.slice(0, 4).map(e => { let c = e.parentElement, label = '', text = '';
      for (let i = 0; i < 4 && c && c !== s; i++, c = c.parentElement) {
        const parts = Array.from(c.querySelectorAll('*')).filter(x => x.children.length === 0 && x !== e && vis(x) && txt(x)).map(txt)
          .filter(t => !NUM.test(t));
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
  const bodyText = (document.body.innerText || '').replace(/\s+/g, ' ').trim();
  return {bodyText: bodyText.slice(0, 1500), textLen: bodyText.length, pageBgSet, title: document.title, description: m('description') || m('og:description'), ogImage: m('og:image'), siteName: m('og:site_name'), lang: document.documentElement.lang,
          h1: h1 ? txt(h1) : '', pageBg, fonts, tally, sections, buttons, navBtn, hasLogo: !!logo, logoSrc: logoImg, style, height: document.documentElement.scrollHeight,
          loadedFonts: Array.from(document.fonts).filter(f => f.status === 'loaded').map(f => f.family.replace(/["']/g, ''))};
}"""


JS_MEDIA = r"""() => {
  const vis = e => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e); return r.width > 2 && r.height > 2 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const head = e => { const s = e.closest('section, [class*=section]'); const h = s && s.querySelector('h1,h2,h3'); return h ? (h.innerText || '').trim().slice(0, 90) : ''; };
  const out = []; let n = 0;
  document.querySelectorAll('video').forEach(v => { const src = v.currentSrc || v.src || ((v.querySelector('source') || {}).src); if (!src) return;
    const r = v.getBoundingClientRect(); out.push({kind: 'video', src, poster: v.poster || '', w: r.width, h: r.height, top: r.top + scrollY, head: head(v)}); });
  document.querySelectorAll('img').forEach(i => { const src = i.currentSrc || i.src; if (!src || src.startsWith('data:') || !i.naturalWidth || i.closest('header, footer, nav')) return;
    const r = i.getBoundingClientRect(); const big = i.naturalWidth >= 420 && i.naturalHeight >= 200;
    out.push({kind: big ? 'image' : 'icon', src, w: i.naturalWidth, h: i.naturalHeight, top: r.top + scrollY, alt: i.alt || '', head: head(i)}); });
  document.querySelectorAll('svg').forEach(v => { if (!vis(v) || v.closest('header, footer, nav, button, a[class*=btn]')) return; const r = v.getBoundingClientRect();
    if (r.width < 22 || r.width > 130 || r.height < 22 || r.height > 130) return; v.setAttribute('data-sr-ico', String(n)); out.push({kind: 'svg', idx: n, w: r.width, h: r.height, top: r.top + scrollY, head: head(v)}); n++; });
  return out;
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


JS_FONTFACES = r"""async () => {
  const out = [];
  const abs = (u, base) => { try { return new URL(u, base || location.href).href; } catch (e) { return ''; } };
  const walk = (rules, base) => { for (const r of rules) {
    if (r.type === 5) {
      const st = r.style, fam = (st.getPropertyValue('font-family') || '').replace(/["']/g, '').trim();
      const src = st.getPropertyValue('src') || '';
      const urls = [...src.matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g)].map(m => abs(m[1], base));
      out.push({family: fam, weight: st.getPropertyValue('font-weight') || '400', style: st.getPropertyValue('font-style') || 'normal', urls});
    } else if (r.cssRules) { try { walk(r.cssRules, base); } catch (e) {} }
  } };
  for (const sh of document.styleSheets) {
    let rules = null; try { rules = sh.cssRules; } catch (e) { rules = null; }
    if (rules) { walk(rules, sh.href || location.href); continue; }
    if (sh.href) { try { const t = await (await fetch(sh.href)).text(); const re = /@font-face\s*{([^}]*)}/g; let m;
      while ((m = re.exec(t))) { const b = m[1], g = k => { const x = new RegExp(k + '\\s*:\\s*([^;]+)').exec(b); return x ? x[1].trim() : ''; };
        out.push({family: g('font-family').replace(/["']/g, ''), weight: g('font-weight') || '400', style: g('font-style') || 'normal',
          urls: [...g('src').matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g)].map(x => abs(x[1], sh.href))}); } } catch (e) {} }
  }
  return out;
}"""


def _family(css: str) -> str:
    for part in (css or "").split(","):
        f = part.strip().strip("\"'").strip()
        if f and f.lower() not in GENERIC and not ICON_FONTS.search(f):
            return f
    return ""


FONT_EXT = {"woff2": ".woff2", "woff": ".woff", "ttf": ".ttf", "otf": ".otf", "truetype": ".ttf", "opentype": ".otf"}


def _site_families(data: dict) -> list:
    f = data.get("fonts", {})
    return [x for x in dict.fromkeys(_family(f.get(k)) for k in ("h1", "h2", "p", "body")) if x]


def save_site_fonts(pg, bodies: dict, families: list, out: Path, log=print) -> list:
    """Salva em out/fontes/ os arquivos das famílias que o site usa (display/corpo). Retorna lista de dicts
    {family, weight, style, file} (file relativo a `out`). Só entra o que foi realmente baixado pelo navegador."""
    try:
        faces = pg.evaluate(JS_FONTFACES)
    except Exception:  # noqa
        return []
    want = {f.lower() for f in families if f}
    res, seen = [], set()
    for fc in faces:
        fam = (fc.get("family") or "").strip()
        if fam.lower() not in want:
            continue
        for u in fc.get("urls", []):
            body = bodies.get(u)
            if not body or len(body) < 800:
                continue
            ext = Path(u.split("?")[0]).suffix.lower()
            if ext not in (".woff2", ".woff", ".ttf", ".otf"):
                continue
            w = str(fc.get("weight") or "400").split()[0]
            w = {"normal": "400", "bold": "700"}.get(w, w)
            sty = "italic" if "italic" in (fc.get("style") or "") else "normal"
            key = (fam, w, sty)
            if key in seen:
                break
            seen.add(key)
            d = out / "fontes"
            d.mkdir(exist_ok=True)
            fn_ = f"{re.sub(r'[^a-z0-9]+', '-', fam.lower()).strip('-')}-{w}-{sty}{ext}"
            (d / fn_).write_bytes(body)
            res.append(dict(family=fam, weight=w, style=sty, file=f"fontes/{fn_}"))
            break
    if res:
        log(f"  fontes reais do site: {', '.join(sorted({r['family'] for r in res}))} ({len(res)} arquivo(s))")
    return res


def pick_brand(data: dict, fonts_catalog=None, font_files=None) -> dict:
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
    have = {x["family"] for x in (font_files or [])}
    for fam in list(subs):  # fonte do site baixada de verdade: usa ela, sem troca
        if fam in have:
            subs.pop(fam)
            if fam == disp:
                out_d = disp
            if fam == body:
                out_b = body
    return dict(font_files=list(font_files or []), colors=dict(bg=bg, bg2=bg2, fg=ink, muted=muted, accent=accent, accent2=accent2), style=style, font_display=out_d or "Space Grotesk",
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


def _clip(m: dict):
    """Vídeo com som real no site entra como clipe com volume (a mixagem abaixa a trilha); mudo continua string simples."""
    return dict(src=m["file"], volume=0.9, loop=True) if m.get("sound") else m["file"]


def _ar(m: dict) -> float:
    try:
        return round(max(0.4, min(3.0, float(m.get("w", 0)) / float(m.get("h", 1)))), 3) if m.get("w") and m.get("h") else 0.8
    except Exception:  # noqa
        return 0.8


def build_scenes(data: dict, shots: list, logo: str | None, handle: str, max_scenes: int = 7, hero_bg: str | None = None, *,
                 handle_at: str = "", alt_theme: str | None = None, name: str = "", author: str = "", media: list | None = None, cta_bg: str | None = None) -> list:
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
    media = media or []
    hv = next((m for m in media if m["kind"] == "video" and m.get("top", 0) < 1400 and m.get("w", 0) >= 320), None)
    hi = None if hv else next((m for m in sorted(media, key=lambda x: x.get("top", 0)) if m["kind"] == "image" and m.get("top", 0) < 1100 and m.get("w", 0) >= 700), None)
    s0 = secs[0] if secs else {}
    ck = [dict(title=sentence(i["title"], names=True)) for i in s0.get("items", []) if i.get("title") and len(i["title"]) <= 44][:3]
    if hv:  # o vídeo do hero do próprio site abre o reel
        scenes = [dict(layout="site-video", kicker="", title=hl(h1), subtitle=sub, photos=[_clip(hv)], photo_meta=[dict(loop=True)])]
    elif hi:  # a foto real do hero, com benefícios e botão como na tela do site
        scenes = [dict(layout="site-cover", title=hl(h1), subtitle=sub, items=ck, cta=sentence(cta), photos=[hi["file"]])]
    else:
        scenes = [dict(layout="site-hero", kicker="", title=hl(h1), subtitle=sub, cta=sentence(cta), **tone)]
    body = []
    used = {m["file"] for m in (hv, hi) if m}

    def mine(head, kinds):
        h = (head or "")[:50].lower()
        return [m for m in media if m["kind"] in kinds and m["file"] not in used and (m.get("head") or "")
                and ((m["head"].lower().startswith(h) and h) or (h.startswith(m["head"][:50].lower()) and m["head"]))]

    for s in secs:
        head = sentence(s.get("heading", ""))
        if not head or head == h1:
            continue
        stats = [x for x in s.get("stats", []) if re.search(r"\d", x.get("number", "")) and (len(re.sub(r"\D", "", x.get("number", ""))) >= 2 or re.search(r"[+%×x]|mil|mi|k\b|º", x.get("number", ""), re.I)) and len(x.get("label", "")) >= 3]
        its = _items(s, 6)
        imgs, vids, icos = mine(head, ("image",)), mine(head, ("video",)), mine(head, ("icon", "svg"))
        if len(imgs) >= 2 and len(its) >= 2:
            for im, it in list(zip(imgs, its))[:3]:
                used.add(im["file"])
                body.append(dict(layout="site-showcase", kicker=sentence(head)[:26] if len(head) <= 26 else "", title=hl(sentence(it["title"], names=True)),
                                 subtitle=sentence(it.get("text", "")), photos=[im["file"]], photo_meta=[dict(ar=_ar(im))], _p=4))
            continue
        if len(imgs) >= 2 and len(its) < 2 and not s.get("quotes"):  # galeria sem textos: duas fotos em 3D com o título da seção (uma cena só)
            port = [m for m in imgs if _ar(m) < 1.3][:2]
            if len(port) == 2:
                for m in port:
                    used.add(m["file"])
                body.append(dict(layout="site-duo", kicker="", title=hl(head), subtitle="", photos=[m["file"] for m in port], _p=3))
            else:
                im = imgs[0]
                used.add(im["file"])
                body.append(dict(layout="site-showcase", kicker="", title=hl(head), subtitle="", photos=[im["file"]], photo_meta=[dict(ar=_ar(im))], _p=3))
            continue
        if vids and not s.get("quotes"):
            for v in vids[:1]:
                used.add(v["file"])
                body.append(dict(layout="site-video", kicker="Na prática", title=hl(sentence(head)), subtitle="", photos=[_clip(v)], photo_meta=[dict(loop=True)], _p=3))
            continue
        if len(its) >= 3 and len(icos) >= 3:
            rows = []
            for it, ic in zip(its[:4], icos):
                used.add(ic["file"])
                rows.append(dict(title=it["title"], text=_first(it.get("text", ""), 70), icon=ic["file"]))
            body.append(dict(layout="site-icons", kicker="", title=hl(head), items=rows, _p=3))
            continue
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
    scenes = spread_media(scenes, media, used)
    scenes = attach_icons(scenes, media, used)
    short = hero_sub if len(hero_sub) <= 70 else (re.split(r"(?<=[.!?])\s", hero_sub)[0] if re.split(r"(?<=[.!?])\s", hero_sub)[0] else hero_sub)
    scenes.append(dict(layout="site-cta", kicker="Próximo passo", title=hl(sentence(cta)) if len(cta.split()) >= 3 else f"*{sentence(cta)}*",
                       subtitle=short or sub, cta=sentence(cta), **({"theme": "brand-accent"} if cta_bg else tone)))
    for k, sc in enumerate(scenes):
        words = review.count_words({a: ([{x: y for x, y in i.items() if x != "icon"} for i in b] if a == "items" else b)
                                    for a, b in sc.items() if a not in ("layout", "photos", "photo_meta", "dur", "theme")})
        sc["dur"] = round(min(6.5, max(3.0, review.need_seconds(words) + 0.4)), 1)
        if k == 0:
            sc["dur"] = max(3.6, min(sc["dur"], 5.0))
        elif k == len(scenes) - 1:
            sc["dur"] = min(sc["dur"], 4.6)
    return scenes


def icons_pool(media: list, used: set) -> list:
    """Todos os ícones/SVGs do site e as imagens muito pequenas (até 180px): bons para figurar na frente de um item de lista."""
    pool = []
    for m in media:
        if m["file"] in used:
            continue
        if m["kind"] in ("icon", "svg"):
            pool.append(m)
        elif m["kind"] == "image" and m.get("w", 0) and m.get("w", 999) <= 180 and m.get("h", 999) <= 180:
            pool.append(m)
    return sorted(pool, key=lambda m: m.get("top", 0))


def attach_icons(scenes: list, media: list, used: set) -> list:
    """Nunca deixa 'bolinha vazia': ícones e miniaturas reais do site rodam pelas listas em ordem de aparição."""
    pool = icons_pool(media, used)
    if not pool:
        return scenes
    pi = 0
    for sc in scenes:
        if sc["layout"] not in ("site-list", "site-icons", "service-grid", "checklist", "step-process", "tips-list"):
            continue
        for it in (sc.get("items") or []):
            if it.get("icon"):
                continue
            m = pool[pi % len(pool)]
            it["icon"] = m["file"]
            used.add(m["file"])
            pi += 1
    return scenes


def spread_media(scenes: list, media: list, used: set, max_new: int = 4) -> list:
    """Mídia que não casou com nenhuma seção pelo título (comum em páginas de produto/carrossel) não pode ficar na pasta:
    antes de cada lista de texto entra uma cena com vídeo ou foto real do site, usando o 1º item da lista como título,
    e a lista segue com o restante. Alterna vídeo e foto, na ordem em que aparecem na página."""
    spare_v = sorted([m for m in media if m["kind"] == "video" and m["file"] not in used and m.get("w", 0) >= 320], key=lambda m: m.get("top", 0))
    spare_i = sorted([m for m in media if m["kind"] == "image" and m["file"] not in used and m.get("w", 0) >= 500 and m.get("h", 0) >= 300], key=lambda m: m.get("top", 0))
    out, added, turn = [], 0, 0
    for sc in scenes:
        its = sc.get("items") or []
        if sc["layout"] in ("site-list", "site-icons") and len(its) >= 3 and added < max_new and (spare_v or spare_i):
            use_v = bool(spare_v) and (turn % 2 == 0 or not spare_i)
            m = spare_v.pop(0) if use_v else spare_i.pop(0)
            used.add(m["file"])
            it = its[0]
            if use_v:
                out.append(dict(layout="site-video", kicker="", title=hl(it["title"]), subtitle=it.get("text", ""), photos=[_clip(m)], photo_meta=[dict(loop=True)]))
            else:
                out.append(dict(layout="site-showcase", kicker="", title=hl(it["title"]), subtitle=it.get("text", ""), photos=[m["file"]], photo_meta=[dict(ar=_ar(m))]))
            sc = dict(sc, items=its[1:])
            added += 1
            turn += 1
        out.append(sc)
    return out


PT_GLOSS = [
    (r"\bGet the highlights\b", "Veja os destaques"),
    (r"\bTake a closer look\b", "Dê uma olhada de perto"),
    (r"\bMade to be seen, heard,? and enjoyed\b", "Feito para ser visto, ouvido e curtido"),
    (r"\bEverything connected and under one roof\b", "Tudo conectado sob o mesmo teto"),
    (r"\bYour data is private property\b", "Seus dados são propriedade privada"),
    (r"\bExplore more Apple Home products\b", "Explore mais produtos Apple Home"),
    (r"\bWhy Apple is the best place to shop Apple Home\b", "Por que a Apple é o melhor lugar para comprar Apple Home"),
    (r"\bQuestions\?\s*Answers\.?", "Perguntas? Respostas."),
    (r"\bApple apps\b", "Apps da Apple"),
    (r"\bAdditional apps\b", "Mais apps"),
    (r"\bAstounding sound\b", "Som impressionante"),
    (r"\bSpatial Audio\b", "Áudio Espacial"),
    (r"\bIntegrated with the Home app\b", "Integrado ao app Casa"),
    (r"\bSee it all at a glance\b", "Veja tudo de relance"),
    (r"\bEnjoy peace of mind\b", "Tenha tranquilidade"),
    (r"\bStay caught up\b", "Fique sempre por dentro"),
    (r"\bMultiple users\b", "Vários usuários"),
    (r"\bSecure Exclaves\b", "Enclaves seguros"),
    (r"\bPersonal content\b", "Conteúdo pessoal"),
    (r"\bGuided Shopping\b", "Compra guiada"),
    (r"\bPersonal Setup\b", "Configuração pessoal"),
    (r"\bApple Card\b", "Apple Card"),
    (r"\bBuy\b", "Comprar"),
    (r"\bNext step\b", "Próximo passo"),
    (r"\bLearn more\b", "Saiba mais"),
    (r"\bWelcome,?\s*", "Boas-vindas, "),
]


def translate_pt(s: str) -> str:
    if not s:
        return s
    out = s
    for pat, rep in PT_GLOSS:
        out = re.sub(pat, rep, out, flags=re.I)
    return out


def translate_scene(sc: dict) -> dict:
    sc = dict(sc)
    for k in ("title", "subtitle", "kicker", "cta", "quote", "author", "role", "label"):
        if sc.get(k):
            sc[k] = translate_pt(sc[k])
    if sc.get("items"):
        sc["items"] = [dict(it, **{k: translate_pt(it.get(k, "")) for k in ("title", "text", "label") if it.get(k)}) for it in sc["items"]]
    return sc


def _square(src: Path, dst: Path, pad: float = 0.18):
    """Logo largo → quadrado transparente com margem, para o avatar redondo não cortar a marca."""
    from PIL import Image
    im = Image.open(src).convert("RGBA")
    side = int(max(im.size) * (1 + pad * 2))
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
    sq.save(dst)


# ------------------------------------------------------------------ captura
CLIMAS = {  # clima → (trilha, conjunto de transições, ritmo, sfx)
    "clean": ("corporate", "set:clean", "standard", "light"),
    "energetic": ("pop", "set:energetic", "snappy", "full"),
    "punch": ("hype", "set:punch", "hype", "full"),
    "cinematic": ("cinematic", "set:cinematic", "calm", "light"),
    "editorial": ("lofi", "set:editorial", "standard", "light"),
}


def pick_clima(brand: dict, media: list | None, url: str = "") -> dict:
    """Decisão do Diretor de Movimento: clima, trilha, tonalidade e ritmo vêm da marca e do material, não de um padrão fixo."""
    c = brand.get("colors", {})
    acc = c.get("accent", "#888888")
    sat = _saturated(acc)
    has_v = any(m["kind"] == "video" for m in (media or []))
    dark = _lum(c.get("bg", "#FFFFFF")) < .25
    clima = "cinematic" if dark and not sat else ("energetic" if (sat or has_v) else "clean")
    music, trans, pace, sfx = CLIMAS[clima]
    keys = ["C", "D", "E", "F", "G", "A", "B"]
    key = keys[sum(map(ord, _host(url) or "x")) % len(keys)]  # tom diferente por site: a trilha não repete sempre a mesma
    return dict(clima=clima, music=music, transition=trans, pace=pace, sfx=sfx, key=key)


def trim_bars(path: Path, log=print) -> bool:
    """Vídeos de sites às vezes trazem tarjas pretas gravadas (letterbox). Detecta com ffmpeg e recorta o arquivo."""
    import subprocess, collections
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-t", "6", "-vf", "cropdetect=24:2:0", "-f", "null", "-"], capture_output=True, text=True, timeout=90)
        m = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", r.stderr)
        if not m:
            return False
        w, h, x, y = collections.Counter(m).most_common(1)[0][0]
        w, h, x, y = int(w), int(h), int(x), int(y)
        pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=30)
        W, H = [int(v) for v in pr.stdout.strip().split(",")[:2]]
        if h >= H * 0.95 and w >= W * 0.95:
            return False
        w, h = w - w % 2, h - h % 2
        tmp = path.with_suffix(".trim.mp4")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path), "-vf", f"crop={w}:{h}:{x}:{y}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "copy", str(tmp)],
                       check=True, timeout=240)
        tmp.replace(path)
        log(f"  tarjas pretas removidas de {path.name} ({W}x{H} → {w}x{h})")
        return True
    except Exception as e:  # noqa
        log(f"! não consegui checar tarjas de {path.name} ({type(e).__name__})")
        return False


def has_sound(path: Path) -> bool:
    """O vídeo do site tem som de verdade (fala/música)? Faixa muda (-91 dB) não conta."""
    import subprocess
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-t", "20", "-af", "volumedetect", "-vn", "-f", "null", "-"], capture_output=True, text=True, timeout=60)
        m = re.search(r"mean_volume: (-?[\d.]+) dB", r.stderr)
        return bool(m) and float(m.group(1)) > -50
    except Exception:  # noqa
        return False


def harvest_media(ctx, pg, out: Path, log=print, tag: str = "", seen: set | None = None) -> list:
    """Baixa vídeos, imagens e ícones do próprio site (pasta `midia/`). Tudo é material real da marca."""
    import io
    from urllib.parse import urlparse
    d = out / "midia"
    d.mkdir(exist_ok=True)
    try:
        raw = pg.evaluate(JS_MEDIA)
    except Exception as e:  # noqa
        log(f"! mídia do site não lida ({type(e).__name__})")
        return []
    res = []
    seen = set() if seen is None else seen
    lim = {"video": 6, "image": 14, "icon": 10, "svg": 10}
    cnt = {k: 0 for k in lim}
    for m in sorted(raw, key=lambda x: x["top"]):
        k = m["kind"]
        if cnt[k] >= lim[k]:
            continue
        try:
            if k == "svg":
                el = pg.query_selector(f'[data-sr-ico="{m["idx"]}"]')
                name = f"icone{tag}-{cnt[k] + 1:02d}.png"
                el.screenshot(path=str(d / name), omit_background=True)
            else:
                src = m["src"]
                if src in seen:
                    continue
                seen.add(src)
                ext = Path(urlparse(src).path).suffix.lower() or (".mp4" if k == "video" else ".png")
                if ext not in (".mp4", ".webm", ".mov", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"):
                    ext = ".png"
                if ext == ".svg":
                    continue
                rsp = ctx.request.get(src, timeout=45000)
                if not rsp.ok:
                    continue
                body = rsp.body()
                if k == "video" and len(body) > 45_000_000:
                    continue
                if k != "video":
                    try:
                        from PIL import Image
                        im = Image.open(io.BytesIO(body))
                        if im.format == "GIF" and getattr(im, "n_frames", 1) > 1:
                            continue
                    except Exception:  # noqa
                        continue
                name = f"{ {'video': 'video', 'image': 'img', 'icon': 'icone-img'}[k] }{tag}-{cnt[k] + 1:02d}{ext}"
                (d / name).write_bytes(body)
                if k == "video":
                    trim_bars(d / name, log)
                    m["sound"] = has_sound(d / name)
                if k == "video" and m.get("poster"):
                    try:
                        pr = ctx.request.get(m["poster"], timeout=20000)
                        if pr.ok:
                            pn = f"video{tag}-{cnt[k] + 1:02d}-poster.png"
                            (d / pn).write_bytes(pr.body())
                            m["poster_file"] = f"midia/{pn}"
                    except Exception:  # noqa
                        pass
            cnt[k] += 1
            res.append({**{a: b for a, b in m.items() if a not in ("src", "poster")}, "file": f"midia/{name}", "src": m.get("src", "")})
        except Exception as e:  # noqa
            log(f"! mídia ignorada ({k}): {type(e).__name__}")
    log(f"  mídia do site: {cnt['video']} vídeo(s) · {cnt['image']} imagem(ns) · {cnt['icon'] + cnt['svg']} ícone(s)")
    return res


UA_DESK = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
UA_MOB = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
STEALTH = ("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});window.chrome=window.chrome||{runtime:{}};"
           "Object.defineProperty(navigator,'languages',{get:()=>['pt-BR','pt','en-US','en']});")
BLOCK_RE = re.compile(r"hubo un error|ocorreu um erro|erro ao (acessar|carregar)|error accediendo|access denied|acesso negado|forbidden|captcha|"
                      r"are you (a )?(robot|human)|verificando se voc|unusual traffic|just a moment|attention required|pardon our interruption|"
                      r"request (was )?blocked|something went wrong|p[aá]gina n[aã]o encontrada|page not found|service unavailable|\b40[134]\b|\b50[023]\b", re.I)


def blocked_reason(d: dict | None) -> str:
    """Vazio se a página parece real; senão, o motivo (página de erro/bloqueio, sem título, sem seções)."""
    if not d:
        return "sem dados"
    head = f"{d.get('title', '')} {d.get('h1', '')}"
    body = d.get("bodyText", "") or ""
    if BLOCK_RE.search(head):
        return f"título/h1 de erro: «{head.strip()[:80]}»"
    if len(body) < 1200 and BLOCK_RE.search(body):
        return f"texto de erro na página: «{body[:90]}»"
    if not (d.get("title") or d.get("h1")):
        return "sem título nem h1"
    if not [x for x in d.get("sections", []) if x.get("heading") or x.get("items")]:
        return "nenhuma seção com título"
    return ""


def assign_heads(media: list, sections: list):
    """Cada mídia herda o título da seção em que está (pela posição na MESMA página em que foi colhida)."""
    for m in media:
        t = m.get("top", 0)
        for s in sections:
            if s.get("heading") and s["top"] - 4 <= t < s["top"] + s["height"]:
                m["head"] = s["heading"][:90]
                m["sec"] = int(s["top"])
                break


def _logo(ctx, pg, data, out: Path, log) -> str | None:
    if not data.get("hasLogo"):
        return None
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
    return "logo.png" if got else None


def capture(url: str, out: Path, shots: int = 6, log=print) -> dict:
    """Abre o site, extrai os dados e grava telas/logo em `out`. Retorna dict com data, brand, shots, logo.
    Se a página desktop vier bloqueada/erro (ex.: Chrome headless barrado), usa a versão celular para TUDO
    (textos, cores, fontes, mídia). Se as duas vierem bloqueadas, para com erro claro: nada de reel genérico."""
    from playwright.sync_api import sync_playwright
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if not re.match(r"^https?://", url):
        url = "https://" + url
    pw = sync_playwright().start()
    kw = dict(args=["--no-sandbox", "--force-color-profile=srgb", "--disable-blink-features=AutomationControlled"])
    cp = core._chrome_path()
    if cp:
        kw["executable_path"] = cp
    br = pw.chromium.launch(**kw)
    common = dict(locale="pt-BR", timezone_id="America/Fortaleza", extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"})

    font_bodies: dict = {}

    def _on_resp(r):
        try:
            if r.request.resource_type == "font" and r.ok:
                font_bodies[r.url] = r.body()
        except Exception:  # noqa
            pass

    def open_page(ctx):
        ctx.add_init_script(STEALTH)
        ctx.on("response", _on_resp)
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
    warnings: list[str] = []
    seen: set = set()
    try:
        # ---- desktop (UA de Chrome de verdade; o padrão do headless diz "HeadlessChrome" e muitos sites barram)
        ctx = br.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1, user_agent=UA_DESK, **common)
        pg = open_page(ctx)
        data = pg.evaluate(JS_EXTRACT)
        why = blocked_reason(data)
        media, logo, font_files = [], None, []
        if why:
            log(f"! desktop bloqueado/erro ({why}) → uso a versão celular do site para textos, cores, fontes e mídia")
            warnings.append(f"desktop bloqueado: {why}")
            try:
                pg.screenshot(path=str(out / "site-desktop-BLOQUEADO.png"))
            except Exception:  # noqa
                pass
            ctx.close()
            data = None
        else:
            media = harvest_media(ctx, pg, out, log, seen=seen)
            assign_heads(media, data["sections"])
            logo = _logo(ctx, pg, data, out, log)
            font_files = save_site_fonts(pg, font_bodies, _site_families(data), out, log)
            try:
                pg.screenshot(path=str(out / "site-desktop.png"), full_page=True)
            except Exception:  # noqa
                pg.screenshot(path=str(out / "site-desktop.png"))
            ctx.close()
        # ---- celular: telas 9:16 do site, 1080 px de largura
        ctx = br.new_context(viewport={"width": 390, "height": 693}, device_scale_factor=1080 / 390, is_mobile=True, has_touch=True, user_agent=UA_MOB, **common)
        pm = open_page(ctx)
        mdata = pm.evaluate(JS_EXTRACT)
        mwhy = blocked_reason(mdata)
        if data is None and mwhy:
            raise RuntimeError(f"o site bloqueou a captura nas duas versões (desktop: {warnings[0][17:]}; celular: {mwhy}). "
                               f"Abra no seu Chrome, salve a página, ou rode em outra rede. Nada foi gerado para não entregar reel genérico.")
        if data is None:
            data = mdata
            logo = _logo(ctx, pm, mdata, out, log)
            font_files = save_site_fonts(pm, font_bodies, _site_families(mdata), out, log)
        if mwhy:
            warnings.append(f"celular bloqueado: {mwhy}")
        mm = harvest_media(ctx, pm, out, log, tag="-m", seen=seen) if not mwhy else []
        if mm:
            assign_heads(mm, mdata["sections"])
            have = {k: sum(1 for m in media if m["kind"] == k) for k in ("video", "image")}
            media += [m for m in mm if m["kind"] in ("icon", "svg") or have.get(m["kind"], 0) < 3 or not media]
        total = mdata["height"]
        ys = [0] + [int(x["top"]) for x in mdata["sections"] if x.get("heading") or x.get("items")]
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
        # fundo do hero: a imagem real do hero, se houver; senão a tela do hero sem textos
        hero_bg = None
        himg = next((m for m in sorted(media, key=lambda x: x.get("top", 0)) if m["kind"] == "image" and m.get("top", 0) < 1100 and m.get("w", 0) >= 700), None)
        if himg:
            try:
                from PIL import Image
                Image.open(out / himg["file"]).convert("RGB").save(out / "fundo-01.png")
                hero_bg = "fundo-01.png"
            except Exception:  # noqa
                hero_bg = None
        if not hero_bg:
            pm.evaluate("window.scrollTo(0,0)")
            pm.add_style_tag(content="h1,h2,h3,h4,h5,h6,p,a,button,header,nav,span,li,blockquote,label,input{visibility:hidden!important}")
            pm.wait_for_timeout(500)
            pm.screenshot(path=str(out / "fundo-01.png"))
            hero_bg = "fundo-01.png"
        ctx.close()
    finally:
        br.close()
        pw.stop()
    if not logo:  # logo não está no cabeçalho: usa a imagem larga (≥2,2:1) mais alta da página que pareça marca
        cand = [m for m in media if m["kind"] == "icon" and m.get("w", 0) >= 300 and 2.2 <= m.get("w", 1) / max(1, m.get("h", 1)) <= 6]
        if cand:
            try:
                from PIL import Image
                Image.open(out / sorted(cand, key=lambda x: x.get("top", 0))[0]["file"]).convert("RGBA").save(out / "logo.png")
                logo = "logo.png"
            except Exception:  # noqa
                pass
    if len(mdata["sections"]) >= len(data["sections"]):
        data["sections"] = mdata["sections"]
    data["media"] = media
    if not any(m["kind"] in ("video", "image") for m in media):
        warnings.append("nenhuma foto/vídeo do site foi colhida (cenas ficarão só de texto)")
    data["warnings"] = warnings
    res.update(data=data, shots=names, logo=logo, hero_bg=hero_bg, warnings=warnings, font_files=font_files)
    return res
