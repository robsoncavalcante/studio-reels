"""
STUDIO REELS — core
Motor local: layouts (HTML/Jinja) x temas (JSON) x movimentos (CSS) -> PNG / MP4.
"""
from __future__ import annotations

import copy
import json
import math
import os
import re
import shutil
import subprocess
import uuid
from html import escape as hesc
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from . import ffsetup

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "library"
CACHE = ROOT / ".cache"
CACHE.mkdir(exist_ok=True)

FORMATS = {
    "story": dict(w=1080, h=1920, label="Story 9:16"),
    "reel": dict(w=1080, h=1920, label="Reel 9:16"),
    "post": dict(w=1080, h=1350, label="Post 4:5"),
    "square": dict(w=1080, h=1080, label="Quadrado 1:1"),
    "grid": dict(w=1080, h=1440, label="Capa de grid 3:4"),
}
STATIC_FORMATS = ["story", "post", "square", "grid"]

OVER_DECOR = {"grain", "vignette", "scanlines", "film-edge", "lightleak", "glass-shine", "noise-soft", "paper", "corner-marks"}

# transições suportadas pelo ffmpeg xfade (verificadas em runtime pelo comando `doctor`)
TRANSITIONS = [
    "fade", "fadeblack", "fadewhite", "dissolve", "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown", "smoothleft", "smoothright", "smoothup", "smoothdown",
    "circleopen", "circleclose", "circlecrop", "rectcrop", "vertopen", "vertclose", "horzopen", "horzclose",
    "radial", "pixelize", "diagtl", "diagtr", "diagbl", "diagbr", "hlslice", "hrslice", "vuslice", "vdslice",
    "squeezeh", "squeezev", "zoomin", "distance", "hblur",
]
TRANSITION_POOL = ["slideleft", "smoothleft", "wipeleft", "circleopen", "zoomin", "radial", "slideup", "fade", "pixelize", "diagtl", "hlslice", "squeezeh"]
# conjuntos por clima (use --transition set:NOME); cada transição conhece o SFX que combina com ela
TRANSITION_SETS = {
    "clean": ["smoothleft", "fade", "slideup", "wipeleft", "smoothup"],
    "energetic": ["slideleft", "hblur", "zoomin", "wipeleft", "squeezeh", "slideup", "coverleft"],
    "cinematic": ["fadeblack", "fade", "circleopen", "revealleft", "fadegrays", "vertopen"],
    "editorial": ["wipeleft", "wiperight", "slideup", "coverup", "revealup", "hlslice"],
    "punch": ["zoomin", "hblur", "squeezev", "circlecrop", "fadewhite", "distance"],
}
TRANSITION_SFX = {
    "slideleft": "whoosh", "slideright": "whoosh", "slideup": "swipe", "slidedown": "swipe", "smoothleft": "whoosh", "smoothup": "swipe",
    "hblur": "whoosh", "wipeleft": "swipe", "wiperight": "swipe", "coverleft": "whoosh", "coverup": "swipe", "revealleft": "swipe", "revealup": "swipe",
    "zoomin": "impact", "squeezeh": "swipe", "squeezev": "swipe", "circlecrop": "pop", "circleopen": "shimmer", "fadewhite": "shimmer",
    "fadeblack": "riser", "fade": None, "fadegrays": None, "dissolve": None, "distance": "whoosh", "vertopen": "swipe", "hlslice": "swipe",
}


# --------------------------------------------------------------------------- registry
def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


class Registry:
    def __init__(self):
        self.reload()

    def reload(self):
        self.layouts = {l["id"]: l for l in _load(LIB / "layouts.json")}
        self.themes = {}
        for f in sorted((LIB / "themes").glob("*.json")):
            for t in _load(f):
                self.themes[t["id"]] = t
        self.carousels = {c["id"]: c for c in _load(LIB / "carousels.json")}
        self.reels = {r["id"]: r for r in _load(LIB / "reels.json")}
        self.motions = {m["id"]: m for m in _load(LIB / "motions.json")}
        self.bridges = _load(LIB / "bridges.json")


REG = Registry()


# --------------------------------------------------------------------------- texto
def rich(text) -> Markup:
    """Escapa, converte \\n em <br> e *palavra* em <em>. (Em reels o JS envolve cada palavra em .w/.wi.)"""
    if text is None:
        return Markup("")
    out = []
    for seg in re.split(r"(\*[^*]+\*)", str(text)):
        if not seg:
            continue
        em = seg.startswith("*") and seg.endswith("*") and len(seg) > 2
        if em:
            seg = seg[1:-1]
        h = hesc(seg).replace("\n", "<br>")
        out.append(f"<em>{h}</em>" if em else h)
    return Markup("".join(out))


def plain(text) -> str:
    return re.sub(r"\*", "", str(text or ""))


def _lum(hexcolor: str) -> float:
    m = re.fullmatch(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", (hexcolor or "").strip())
    if not m:
        return 0.0
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def on_color(bg: str) -> str:
    # escolhe a cor de texto (branco/quase-preto) com MAIOR contraste, não um limiar fixo
    lb = _lum(bg)
    cw = 1.05 / (lb + 0.05)
    cd = (lb + 0.05) / (_lum("#111111") + 0.05)
    return "#ffffff" if cw >= cd else "#111111"


# --------------------------------------------------------------------------- tema
def bg_css(t: dict) -> str:
    k = t.get("bg_kind", "solid")
    a = t.get("angle", "160deg")
    if k == "solid":
        return "var(--bg)"
    if k == "linear":
        return f"linear-gradient({a},var(--bg),var(--bg2))"
    if k == "radial":
        return "radial-gradient(130% 90% at 20% 8%,var(--bg2),var(--bg) 68%)"
    if k == "mesh":
        return ("radial-gradient(60% 45% at 0% 0%,color-mix(in srgb,var(--accent) 55%,transparent),transparent 70%),"
                "radial-gradient(55% 45% at 100% 20%,color-mix(in srgb,var(--accent2) 50%,transparent),transparent 70%),"
                "radial-gradient(70% 50% at 50% 110%,color-mix(in srgb,var(--bg2) 90%,transparent),transparent 70%),var(--bg)")
    if k == "sunset":
        return f"linear-gradient({a},var(--bg),var(--bg2) 62%,color-mix(in srgb,var(--bg2) 72%,var(--accent)))"
    if k == "conic":
        return "conic-gradient(from 210deg at 50% 60%,var(--bg),var(--bg2),var(--accent),var(--bg))"
    if k == "split":
        return "linear-gradient(180deg,var(--bg) 0 50%,var(--bg2) 50% 100%)"
    if k == "custom":
        return t["bg_custom"]
    return "var(--bg)"


def resolve_theme(theme_id: str, brand: dict | None = None) -> dict:
    if theme_id not in REG.themes:
        raise SystemExit(f"Tema '{theme_id}' não existe. Use: studio.py list themes")
    t = copy.deepcopy(REG.themes[theme_id])
    brand = brand or {}
    colors = brand.get("colors", {}) or {}
    if t.get("brand") or brand.get("override_theme"):
        for k in ("bg", "bg2", "fg", "muted", "accent", "accent2", "line", "surface"):
            if colors.get(k):
                t[k] = colors[k]
        if brand.get("font_display"):
            t["font_display"] = brand["font_display"]
        if brand.get("font_body"):
            t["font_body"] = brand["font_body"]
    if theme_id == "brand-accent":  # fundo na cor forte do próprio site (ex.: amarelo do rodapé); texto escuro/claro conforme o contraste
        from .color import contrast as _ct, hex_rgb as _hx, rgb_hex as _rh
        _mx = lambda a, b, k: _rh(*[round(x + (y - x) * k) for x, y in zip(_hx(a), _hx(b))])
        bgc = colors.get("cta_bg") or colors.get("accent2") or colors.get("accent") or t["bg"]
        ink = "#111111" if _ct(bgc, "#111111") >= _ct(bgc, "#FFFFFF") else "#FFFFFF"
        ac = colors.get("accent") or ink
        t.update(bg=bgc, bg2=bgc, fg=ink, muted=_mx(bgc, ink, 0.62), accent=ac if _ct(ac, bgc) >= 3 else ink, accent2=ink)
    st = brand.get("style") or {}
    if t.get("brand") or brand.get("override_theme"):
        for k in ("dw", "dcase", "dls", "dlh", "card_radius", "btn_radius", "ph_radius"):
            if st.get(k) is not None:
                t[k] = st[k]
    # segurança de legibilidade: o 2º tom do fundo nunca pode enfraquecer o texto principal
    try:
        if t.get("bg2") and t.get("fg", "").startswith("#"):
            t["bg2"] = ensure_contrast(t["bg2"], t["fg"], 4.0)
    except Exception:
        pass
    if brand.get("font_pair"):
        from . import fonts as _fonts
        pr = _fonts.resolve_pair(brand["font_pair"])
        if not pr:
            raise SystemExit(f"Par de fontes '{brand['font_pair']}' não existe. Use: studio.py fonts pair")
        t["font_display"], t["font_body"] = pr["display"], pr["body"]
        if pr.get("adjust"):
            t["body_adjust"] = pr["adjust"]
    return t


try:
    from .color import ensure_contrast
except Exception:
    ensure_contrast = lambda f, b, r=4.5: f


def theme_css_vars(t: dict) -> str:
    fg = t.get("fg", "#ffffff")
    accent = t.get("accent", "#ff3366")
    accent2 = t.get("accent2", accent)
    v = {
        "--bg": t.get("bg", "#111111"),
        "--bg2": t.get("bg2", t.get("bg", "#111111")),
        "--fg": fg,
        "--muted": t.get("muted", "color-mix(in srgb,var(--fg) 84%,transparent)"),
        "--accent": accent,
        "--accent2": accent2,
        "--accent-text": ensure_contrast(accent, t.get("bg", "#111111"), 4.5),
        "--accent2-text": ensure_contrast(accent2, t.get("bg", "#111111"), 4.5),
        "--line": t.get("line", "color-mix(in srgb,var(--fg) 22%,transparent)"),
        "--surface": t.get("surface", "color-mix(in srgb,var(--fg) 7%,transparent)"),
        "--on-accent": t.get("on_accent", on_color(accent)),
        "--on-accent2": t.get("on_accent2", on_color(accent2)),
        "--font-display": f"'{t.get('font_display', 'Inter')}'",
        "--font-body": f"'{t.get('font_body', 'Inter')}'",
        "--body-adjust": t.get("body_adjust", "none"),
        "--dw": t.get("dw", 800),
        "--dcase": t.get("dcase", "none"),
        "--dls": t.get("dls", "-0.01em"),
        "--dlh": t.get("dlh", 1.02),
        "--ph-radius": t.get("ph_radius", "2.2cqw"),
        "--ph-border": t.get("ph_border", "0"),
        "--ph-shadow": t.get("ph_shadow", "none"),
        "--ph-filter": t.get("ph_filter", "none"),
        "--btn-radius": t.get("btn_radius", "99cqw"),
        "--btn-shadow": t.get("btn_shadow", "none"),
        "--card-radius": t.get("card_radius", "3cqw"),
        "--bg-css": bg_css(t),
    }
    return ";".join(f"{k}:{val}" for k, val in v.items())


# --------------------------------------------------------------------------- conteúdo
VIDEO_EXT = (".mp4", ".mov", ".webm", ".m4v")


def resolve_media(p, base_dir: Path | None) -> str | None:
    if not p:
        return None
    p = str(p)
    if re.match(r"^(https?:|data:|file:)", p):
        return p
    path = Path(p).expanduser()
    if not path.is_absolute():
        cand = (base_dir or Path.cwd()) / path
        if not cand.exists() and (LIB.parent / path).exists():
            cand = LIB.parent / path  # relativo à raiz do motor (marcas/logos da biblioteca)
        path = cand
    elif not path.exists() and "library" in path.parts:
        alt = LIB.parent / Path(*path.parts[path.parts.index("library"):])
        if alt.exists():
            path = alt  # caminho absoluto de outra máquina -> raiz atual do motor
    if not path.exists():
        print(f"  ! mídia não encontrada: {path}")
        return None
    path = _prepare_media(path)
    return path.resolve().as_uri()


def is_lottie(path) -> bool:
    try:
        if str(path).lower().split("?")[0].endswith(".json"):
            d = json.loads(Path(str(path).replace("file://", "")).read_text(encoding="utf-8"))
            return all(k in d for k in ("fr", "ip", "op", "layers"))
    except Exception:
        pass
    return False


def _prepare_media(path: Path) -> Path:
    """GIF e vídeos com alpha (MOV ProRes 4444) viram WebM VP9 com transparência, que o Chrome toca e busca por tempo."""
    import hashlib, subprocess, tempfile
    ext = path.suffix.lower()
    if ext not in (".gif", ".apng", ".mov"):
        return path
    if ext == ".mov":
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=pix_fmt", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
        pf = r.stdout.strip()
        if not any(k in pf for k in ("yuva", "rgba", "argb", "bgra", "gbra")):
            return path
    key = hashlib.md5(f"{path.resolve()}{path.stat().st_mtime}".encode()).hexdigest()[:12]
    outp = Path(tempfile.gettempdir()) / f"sr_media_{key}.webm"
    if not outp.exists():
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "30",
               "-auto-alt-ref", "0", "-an", str(outp)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  ! não consegui converter {path.name}: {r.stderr[-200:]}")
            return path
    return outp


def normalize_content(content: dict, base_dir: Path | None) -> dict:
    c = dict(content or {})
    if "text" in c and "body" not in c:
        c["body"] = c["text"]
    metas = []
    plist = []
    given = [m if isinstance(m, dict) else {} for m in (c.get("photo_meta") or [])]
    for n_, p in enumerate(c.get("photos") or []):
        if isinstance(p, dict):  # clipe: {"src","start","dur","speed","volume","loop"}
            metas.append({k: v for k, v in p.items() if k != "src"})
            plist.append(resolve_media(p.get("src"), base_dir))
        else:
            metas.append(dict(given[n_]) if n_ < len(given) else {})
            plist.append(resolve_media(p, base_dir))
    c["photos"] = plist
    c["photo_meta"] = metas
    if c.get("cutout"):
        c["cutout"] = resolve_media(c["cutout"], base_dir)
    items = []
    for i in (c.get("items") or []):
        it = dict(i) if isinstance(i, dict) else {"title": str(i)}
        if it.get("icon") and not re.match(r"^(https?:|data:|file:)", str(it["icon"])):
            it["icon"] = resolve_media(it["icon"], base_dir) or it["icon"]
        items.append(it)
    c["items"] = items
    return c


SIL_SVG = ('<svg viewBox="0 0 400 640" xmlns="http://www.w3.org/2000/svg" style="height:100%;width:auto"><defs>'
           '<linearGradient id="sg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".96"/><stop offset="1" stop-color="#fff" stop-opacity=".72"/></linearGradient></defs>'
           '<circle cx="200" cy="168" r="98" fill="url(#sg)"/><path d="M26 640 C26 452 112 372 200 372 S374 452 374 640Z" fill="url(#sg)"/></svg>')
PH_ICON = '<svg viewBox="0 0 64 64" class="phi"><circle cx="46" cy="18" r="6"/><path d="M4 56 L24 28 L38 46 L46 36 L60 56 Z"/></svg>'


def make_helpers(c: dict):
    photos = c.get("photos", [])

    def photo(i=0, cls="", style=""):
        src = photos[i] if i < len(photos) else None
        if src:
            m = (c.get("photo_meta") or [{}] * (i + 1))[i] if i < len(c.get("photo_meta") or []) else {}
            if is_lottie(src):
                data = Path(src.replace("file://", "")).read_text(encoding="utf-8")
                c["_lottie"] = True
                cls += " ov"
                safe = data.replace("</", "<\\/")
                inner = (f'<div class="lot" data-speed="{float(m.get("speed", 1))}" data-loop="{1 if m.get("loop", True) else 0}"></div>'
                         f'<script type="application/json" class="lotdata">{safe}</script>')
            elif src.lower().split("?")[0].endswith(VIDEO_EXT):
                if m.get("overlay") or Path(src.replace("file://", "")).name.startswith("sr_media_"):
                    cls += " ov"
                inner = (f'<video src="{src}" muted playsinline preload="auto" data-start="{float(m.get("start", 0))}" '
                         f'data-speed="{float(m.get("speed", 1))}" data-loop="{1 if m.get("loop", True) else 0}"></video>')
            else:
                inner = f'<img src="{src}" alt="">'
        else:
            inner = f'<div class="ph ph{i % 4}">{PH_ICON}</div>'
        return Markup(f'<div class="photo {cls}" style="{style}">{inner}</div>')

    def cutout(cls="", style=""):
        src = c.get("cutout")
        inner = f'<img src="{src}" alt="">' if src else SIL_SVG
        return Markup(f'<div class="cutout {cls}" style="{style}">{inner}</div>')

    def stars(n=5):
        return Markup("★" * int(n) + "☆" * (5 - int(n)))

    def icon(name, cls="", sw=1.75):
        f = LIB / "icons" / "lucide" / f"{name}.svg"
        if not f.exists():
            return Markup("")
        svg = re.sub(r"<!--.*?-->|\s+class=\"[^\"]*\"|\s+width=\"24\"|\s+height=\"24\"", "", f.read_text(encoding="utf-8"), flags=re.S)
        svg = re.sub(r'stroke-width="[^"]*"', f'stroke-width="{sw}"', svg)
        svg = svg.replace("<svg", f'<svg class="ico {cls}"', 1)
        return Markup(re.sub(r"\s+", " ", svg))

    return dict(photo=photo, cutout=cutout, stars=stars, rich=rich, plain=plain, icon=icon)


_env = Environment(loader=FileSystemLoader(str(LIB / "layouts")), autoescape=True, trim_blocks=True, lstrip_blocks=True)


# --------------------------------------------------------------------------- HTML
PREP_JS = r"""
window.__prep=function(){
  const cv=document.querySelector('.canvas');
  document.querySelectorAll('.fit').forEach(el=>{
    const blocky=[...el.children].some(c=>{const d=getComputedStyle(c).display;return d!=='inline'&&d!=='inline-block'&&c.tagName!=='BR'&&c.tagName!=='EM'});
    let inner=null;
    if(!blocky){inner=document.createElement('span');inner.className='fit-in';while(el.firstChild)inner.appendChild(el.firstChild);el.appendChild(inner);}
    let fs=parseFloat(getComputedStyle(el).fontSize),min=fs*0.32,n=0;
    const brokenWord=()=>{ if(!el.classList.contains('t')) return false;
      const w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);
      while(w.nextNode()){const n=w.currentNode,re=/\S+/g;let m;
        while((m=re.exec(n.textContent))){const r=document.createRange();r.setStart(n,m.index);r.setEnd(n,m.index+m[0].length);
          const tops=new Set([...r.getClientRects()].filter(q=>q.width>1).map(q=>Math.round(q.top/(fs*0.45))));
          if(tops.size>1) return true;}}
      return false;};
    const over=()=>brokenWord()||(inner?(inner.offsetHeight>el.clientHeight+2||inner.scrollWidth>el.clientWidth+2):(el.scrollHeight>el.clientHeight+Math.max(2,fs*0.03)||el.scrollWidth>el.clientWidth+2));
    while(over()&&fs>min&&n++<70){fs*=0.95;el.style.fontSize=fs+'px';}
  });
  /* auto-fit v4.4: subtítulo/corpo/kicker sem .fit encolhem se vazarem a área segura do canvas */
  (function(){
    const cr=cv.getBoundingClientRect(), isReel=cv.classList.contains('reel')||cv.classList.contains('story');
    const maxB=cr.top+cr.height*(isReel?0.93:0.96), maxR=cr.left+cr.width*0.97, minL=cr.left+cr.width*0.02;
    document.querySelectorAll('.canvas .s,.canvas .b,.canvas .k,.canvas .cta').forEach(el=>{
      if(el.classList.contains('fit')) return;
      let fs=parseFloat(getComputedStyle(el).fontSize),min=fs*0.6,n=0;
      const out=()=>{const r=el.getBoundingClientRect();return r.height>0&&(r.bottom>maxB||r.right>maxR||r.left<minL||el.scrollWidth>el.clientWidth+2&&getComputedStyle(el).overflow!=='visible')};
      while(out()&&fs>min&&n++<25){fs*=0.95;el.style.fontSize=fs+'px';}
    });
  })();
  if(cv.classList.contains('reel')&&cv.classList.contains('mw')){
    const wrap=(node)=>{
      [...node.childNodes].forEach(ch=>{
        if(ch.nodeType===3){
          const parts=ch.textContent.split(/(\s+)/);const f=document.createDocumentFragment();
          parts.forEach(p=>{ if(!p) return; if(/^\s+$/.test(p)){f.appendChild(document.createTextNode(' '));}
            else if(cv.classList.contains('mc')){const nb=document.createElement('span');nb.className='nb';
              [...p].forEach(chr=>{const w=document.createElement('span');w.className='w';const wi=document.createElement('span');wi.className='wi';wi.textContent=chr;w.appendChild(wi);nb.appendChild(w);});f.appendChild(nb);}
            else{const w=document.createElement('span');w.className='w';const wi=document.createElement('span');wi.className='wi';wi.textContent=p;w.appendChild(wi);f.appendChild(w);} });
          node.replaceChild(f,ch);
        }else if(ch.nodeType===1&&ch.tagName!=='BR'){wrap(ch);}
      });
    };
    document.querySelectorAll('.canvas .t').forEach(wrap);
    if(cv.classList.contains('mc')){ /* reajusta títulos depois de envolver letras (palavra inteira não quebra) */
      document.querySelectorAll('.canvas .t.fit').forEach(el=>{
        const inner=el.querySelector('.fit-in');let fs=parseFloat(getComputedStyle(el).fontSize),n=0;
        const over=()=>(inner?inner.offsetHeight>el.clientHeight+2:el.scrollHeight>el.clientHeight+2)||el.scrollWidth>el.clientWidth+2;
        while(over()&&n++<60){fs*=0.95;el.style.fontSize=fs+'px';}
      });
    }
  }
  if(cv.classList.contains('reel')){
    const words=cv.classList.contains('mw');
    const sel='.k,.t,.s,.b,.photo,.item,.badge,.cta,.sticker,.chip,.surface,[data-a]';
    let i=0;
    const jit=(el,n)=>{ if(!cv.classList.contains('hm')) return; const r=Math.sin((n+1)*12.9898+7.13)*43758.5453; const f=r-Math.floor(r); el.style.setProperty('--j',((f-.5)*.12).toFixed(3)+'s'); };
    cv.querySelectorAll(sel).forEach(el=>{
      if(el.closest('.no-anim')||el.parentElement.closest('.photo')) return;
      if(words&&el.classList.contains('t')){
        el.querySelectorAll('.w').forEach(w=>{w.style.setProperty('--i',i);w.setAttribute('data-i','');jit(w,i);i++;});
      }else{el.style.setProperty('--i',i);el.setAttribute('data-i','');jit(el,i);i++;}
    });
  }
  const counters=[];
  if(cv.classList.contains('cu')){
    cv.querySelectorAll('.t.num,[data-count]').forEach(el=>{
      const tgt=el.querySelector('.fit-in')||el;const m=tgt.textContent.trim().match(/^(\D*)(\d[\d.,]*)(.*)$/);
      if(!m) return; const raw=m[2];const dec=(raw.split(/[.,]/)[1]||'').length;const sep=raw.includes(',')&&!raw.includes('.')?',':'.';
      const val=parseFloat(raw.replace(',','.'));counters.push({el:tgt,pre:m[1],suf:m[3],val,dec,sep,orig:tgt.textContent});
    });
  }
  const exm=(cv.className.match(/ex-(\w+)/)||[])[1];
  if(exm){
    const at=parseFloat(getComputedStyle(cv).getPropertyValue('--exit-at'));
    if(at>0.6){
      const els=[...document.querySelectorAll('[data-i]')].filter(e=>!e.parentElement.closest('[data-i]'));
      const dur=.42,stg=Math.min(.09,Math.max(.03,(at-1.2)/Math.max(1,els.length)/2)),n=els.length;
      const KF={
        pop:[{opacity:1,scale:'1'},{opacity:1,scale:'1.07',offset:.3},{opacity:0,scale:'.15'}],
        fade:[{opacity:1,translate:'0 0'},{opacity:0,translate:'0 -2.2cqw'}],
        slide:[{opacity:1,translate:'0 0'},{opacity:0,translate:'-14cqw 0'}],
        drop:[{opacity:1,translate:'0 0'},{opacity:0,translate:'0 9cqw'}],
        blur:[{opacity:1,filter:'blur(0)'},{opacity:0,filter:'blur(2.4cqw)'}]
      }[exm]||null;
      if(KF) els.forEach((el,k)=>{
        const start=Math.max(.4,at-dur-(n-1-k)*stg);
        el.animate(KF,{duration:dur*1000,delay:start*1000,fill:'forwards',easing:'cubic-bezier(.5,0,.75,0)'});
      });
    }
  }
  const lots=[...document.querySelectorAll('.lot')].map(el=>{
    const d=JSON.parse(el.parentElement.querySelector('.lotdata').textContent);
    const anim=window.lottie.loadAnimation({container:el,renderer:'svg',loop:false,autoplay:false,animationData:d,rendererSettings:{preserveAspectRatio:'xMidYMid meet'}});
    return {el,anim,fr:d.fr,ip:d.ip,op:d.op,sp:parseFloat(el.dataset.speed||1),lp:el.dataset.loop!=='0'};
  });
  const vids=[...document.querySelectorAll('video')];
  window.__vidready=Promise.all(vids.map(v=>v.readyState>=1?1:new Promise(r=>{v.addEventListener('loadedmetadata',r,{once:true});setTimeout(r,4000)})));
  window.__seek=function(t){
    const ps=[];
    vids.forEach(v=>{
      const st=parseFloat(v.dataset.start||0),sp=parseFloat(v.dataset.speed||1),lp=v.dataset.loop!=='0';
      let tt=st+(t/1000)*sp; const d=v.duration||0;
      if(d>0){ if(lp){const span=Math.max(.05,d-st);tt=st+(((t/1000)*sp)%span);} else tt=Math.min(tt,d-.05); }
      if(Math.abs(v.currentTime-tt)>0.001){ps.push(new Promise(r=>{const f=()=>{v.removeEventListener('seeked',f);r()};v.addEventListener('seeked',f);setTimeout(r,1500);v.currentTime=tt;}));}
    });
    lots.forEach(L=>{const n=L.op-L.ip;let f=(t/1000)*L.sp*L.fr;f=L.lp?(f%n):Math.min(f,n-.01);L.anim.goToAndStop(L.ip+f,true);});
    document.getAnimations().forEach(a=>{a.pause();a.currentTime=t;});
    counters.forEach(c=>{
      const host=c.el.closest('[data-i]')||c.el;const dl=parseFloat(getComputedStyle(host).animationDelay)||0;
      const p=Math.min(1,Math.max(0,(t-dl)/1.1));const e=1-Math.pow(1-p,3);
      c.el.textContent=p>=1?c.orig:c.pre+(c.val*e).toFixed(c.dec).replace('.',c.sep)+c.suf;
    });

    /* ---- câmera 3D + foco sequencial (determinístico: só depende de t) ---- */
    (function(){
      const cm=([...cv.classList].find(c=>c.indexOf('cam-')===0)||'').slice(4);
      const sd=parseFloat(getComputedStyle(cv).getPropertyValue('--sd'))||3.2, ts=t/1000, p=Math.min(1,Math.max(0,ts/sd));
      const sm=x=>x*x*(3-2*x), clamp=(x,a,b)=>Math.min(b,Math.max(a,x));
      let ty=0, ry=0, rx=0, sc=1, tx=0; const H=cv.clientHeight;
      const groups=[...document.querySelectorAll('[data-focus]')];
      groups.forEach(g=>{
        const its=[...g.children].filter(e=>e.classList.contains('item'));
        const n=its.length; if(!n) return;
        const last=its[n-1], ld=(parseFloat(getComputedStyle(last).animationDelay)||0)+(parseFloat(getComputedStyle(last).animationDuration)||.7);
        const t0=Math.min(sd*.55, ld+.15), t1=Math.max(t0+.6, sd-.35), slot=(t1-t0)/n;
        const gate=sm(clamp((ts-(t0-.15))/.4,0,1));
        let fy=0, tot=0;
        its.forEach((el,i)=>{
          const c=t0+slot*(i+.5), d=Math.abs(ts-c)/(slot*.62), fo=gate*(1-sm(clamp(d,0,1)));
          const sw=clamp((ts-(c-slot*.5))/(slot*.9),0,1);
          const lead=(i===0&&ts<t0)?0:fo;
          el.style.setProperty('--fo',lead.toFixed(3)); el.style.setProperty('--dim',(gate*.42*(1-fo)).toFixed(3)); el.style.setProperty('--sw',sw.toFixed(3));
          el.style.scale=(1+.045*fo).toFixed(4); el.style.rotate='0 1 0 '+(-4.5*fo).toFixed(3)+'deg'; el.style.translate='0 0 '+(3.2*fo).toFixed(3)+'cqw';
          let top=0,e=el; while(e&&e!==cv){top+=e.offsetTop;e=e.offsetParent;}
          const cy=top+el.offsetHeight/2-H/2; fy+=fo*cy; tot+=fo;
        });
        if(tot>0){ty+=-fy/Math.max(tot,.001)*.07;}
      });
      if(cm==='push'){sc=1+.035*sm(p); rx=1.0*Math.sin(Math.PI*p); ry=-1.2+2.4*sm(p);}
      else if(cm==='orbit'){ry=-3+6*sm(p); rx=1.6*Math.sin(Math.PI*p); sc=1.012+.02*Math.sin(Math.PI*p); tx=-1.2+2.4*sm(p);}
      else if(cm==='drift'){ry=1.8*Math.sin(2*Math.PI*p*.5); rx=.9*Math.cos(2*Math.PI*p*.5); sc=1.015;}
      else if(cm==='dolly'){sc=1.05-.05*sm(p); rx=2.2*(1-sm(p)); ry=0;}
      const W=cv.clientWidth, cl=(v,m)=>Math.max(-m,Math.min(m,v));
      const content=cv.querySelector('.content');
      if(content&&cm){
        content.style.transform='perspective('+(1.25*W).toFixed(0)+'px) translate3d('+(tx*W/100).toFixed(1)+'px,'+cl(ty,H*.035).toFixed(1)+'px,0) rotateX('+rx.toFixed(3)+'deg) rotateY('+ry.toFixed(3)+'deg) scale('+sc.toFixed(4)+')';
        const par=(-ry*.9)+'cqw';
        cv.querySelectorAll('.dc.under,.bgph').forEach(e=>{e.style.translate=((-ry*.45)).toFixed(2)+'cqw '+(rx*.45).toFixed(2)+'cqw';});
      }
    })();
    return Promise.all(ps);
  };
  return true;
};
"""


def decor_html(t: dict, enabled=True) -> tuple[str, str]:
    if not enabled:
        return "", ""
    under, over = [], []
    for d in t.get("decor", []):
        cls = f"dc dc-{d} " + ("over" if d in OVER_DECOR else "under")
        (over if d in OVER_DECOR else under).append(f'<div class="{cls}"></div>')
    return "".join(under), "".join(over)


def brandbar_html(brand: dict | None, base_dir, bg: str | None = None, ink: str = "#111111") -> str:
    if not brand:
        return ""
    name, handle, logo = brand.get("name"), brand.get("handle"), resolve_media(brand.get("logo"), base_dir)
    if logo and bg and str(bg).startswith("#") and len(str(bg)) == 7:
        try:  # a logo sempre precisa aparecer: ajusta ao fundo onde ela fica
            from . import logo as _logo
            logo = Path(_logo.fit(logo, bg, ink if str(ink).startswith("#") and len(str(ink)) == 7 else "#111111")).as_uri()
        except Exception:
            pass
    if not (name or handle or logo):
        return ""
    left = (f'<img src="{logo}" alt="">' if logo else "") + (f"<span>{hesc(name)}</span>" if name and not logo else "")
    right = f'<span class="bh">{hesc(handle)}</span>' if handle else ""
    return f'<div class="brandbar"><div class="bn">{left}</div>{right}</div>'


def pager_html(idx: int, total: int, label="Arraste") -> str:
    if total <= 1:
        return ""
    dots = "".join(f'<i class="{"on" if i == idx else ""}"></i>' for i in range(total))
    last = idx == total - 1
    right = "" if last else f'<span class="sw">{hesc(label)} <span class="arrow"></span></span>'
    return f'<div class="pager"><span>{idx + 1:02d}/{total:02d}</span><span class="dots">{dots}</span>{right or "<span></span>"}</div>'


def head_html(reel=False) -> str:
    css = [f'<link rel="stylesheet" href="{(ROOT / "fonts" / "fonts.css").as_uri()}">',
           f'<link rel="stylesheet" href="{(ROOT / "engine" / "base.css").as_uri()}">']
    if reel:
        css.append(f'<link rel="stylesheet" href="{(ROOT / "engine" / "easings.css").as_uri()}">')
        css.append(f'<link rel="stylesheet" href="{(ROOT / "engine" / "motions.css").as_uri()}">')
        css.append(f'<link rel="stylesheet" href="{(ROOT / "engine" / "human.css").as_uri()}">')
        css.append(f'<link rel="stylesheet" href="{(ROOT / "engine" / "camera.css").as_uri()}">')
    return '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">' + "".join(css)


def brand_fonts_css(brand: dict | None, base_dir: Path | None) -> str:
    """@font-face das fontes reais do site (brand['font_files']), para usar a tipografia original da marca."""
    ff = (brand or {}).get("font_files") or []
    rules = []
    for f in ff:
        pth = Path(f.get("file", ""))
        if not pth.is_absolute():
            pth = (base_dir or Path.cwd()) / pth
        if not pth.exists():
            continue
        fmt = {".woff2": "woff2", ".woff": "woff", ".ttf": "truetype", ".otf": "opentype"}.get(pth.suffix.lower(), "woff2")
        rules.append(f"@font-face{{font-family:'{f['family']}';font-weight:{f.get('weight', '400')};font-style:{f.get('style', 'normal')};"
                     f"font-display:block;src:url('{pth.resolve().as_uri()}') format('{fmt}')}}")
    return f"<style>{''.join(rules)}</style>" if rules else ""


def slide_canvas(layout_id: str, theme_id: str, fmt: str, content: dict, brand: dict | None = None, *,
                 base_dir: Path | None = None, reel: dict | None = None, pager: tuple | None = None,
                 decor=True, transparent=False, sample=False, show_brand=True) -> str:
    """Retorna o HTML do <div class=canvas> (sem <html>)."""
    if layout_id not in REG.layouts:
        raise SystemExit(f"Layout '{layout_id}' não existe. Use: studio.py list layouts")
    lay = REG.layouts[layout_id]
    t = resolve_theme(theme_id, brand)
    F = FORMATS[fmt]
    c = normalize_content(content if not sample else {**lay.get("sample", {}), **content}, base_dir)
    ctx = dict(c=c, fmt=fmt, brand=brand or {}, theme=t, **make_helpers(c))
    inner = _env.get_template(f"{layout_id}.html.j2").render(**ctx)
    under, over = decor_html(t, decor)
    under = brand_fonts_css(brand, base_dir) + under
    classes = ["canvas", f"fmt-{fmt}", f"fx-{t.get('title_fx', 'plain')}", f"L-{layout_id}"]
    style = f"--W:{F['w']}px;--H:{F['h']}px;" + theme_css_vars(t)
    if transparent:
        classes.append("transparent")
    if reel:
        m = REG.motions[reel.get("motion", "fade-up")]
        from . import motion as _motion
        xc, xs = _motion.style_for(m, reel)
        classes += ["reel", f"m-{m['id']}"] + (["mw"] if m.get("words") else []) + (["mc"] if m.get("chars") else []) + xc
        style += xs
    over_photo = ("scrim" in inner) or ("bgph" in inner and "ondark" in inner)
    bar = brandbar_html(brand, base_dir, "#101010" if over_photo else t.get("bg"), t.get("fg", "#111111")) if show_brand else ""
    pg = pager_html(*pager) if pager else ""
    return f'<div class="{" ".join(classes)}" style="{style}">{under}<div class="content">{inner}</div>{bar}{pg}{over}</div>'


def _lottie_lib(html: str) -> str:
    if 'class="lot"' not in html:
        return ""
    return "<script>" + (LIB / "vendor" / "lottie_light.min.js").read_text(encoding="utf-8") + "</script>"


def page_html(canvas_html: str, reel=False) -> str:
    return head_html(reel) + f"</head><body>{canvas_html}{_lottie_lib(canvas_html)}<script>{PREP_JS}</script></body></html>"


# --------------------------------------------------------------------------- navegador
def _chrome_path():
    for p in (os.environ.get("CHROME_PATH"), "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if p and Path(p).exists():
            return p
    return None


class Renderer:
    """Mantém um Chrome aberto e renderiza HTML -> PNG/JPEG/MP4."""

    def __init__(self, scale: float = 1.0):
        self.scale = scale
        self._pw = self._browser = self._ctx = self._page = None
        self._tmp = CACHE / f"r_{uuid.uuid4().hex[:8]}.html"

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        kw = dict(args=["--no-sandbox", "--font-render-hinting=none", "--force-color-profile=srgb", "--allow-file-access-from-files"])
        cp = _chrome_path()
        if cp:
            kw["executable_path"] = cp
        self._browser = self._pw.chromium.launch(**kw)
        self._ctx = self._browser.new_context(device_scale_factor=self.scale, viewport={"width": 1080, "height": 1920})
        self._page = self._ctx.new_page()
        return self

    def __exit__(self, *a):
        try:
            self._browser.close()
            self._pw.stop()
        finally:
            self._tmp.unlink(missing_ok=True)

    def load(self, html: str, w: int, h: int):
        self._page.set_viewport_size({"width": w, "height": h})
        self._tmp.write_text(html, encoding="utf-8")
        self._page.goto(self._tmp.as_uri(), wait_until="load")
        self._page.evaluate("document.fonts.ready.then(()=>true)")
        self._page.evaluate("Promise.all([...document.images].map(i=>i.decode().catch(()=>0)))")
        self._page.evaluate("window.__prep()")
        return self._page

    def shoot(self, html, out, w, h, kind="png", quality=92, clip=None):
        pg = self.load(html, w, h)
        opts = dict(path=str(out), type=kind, clip=clip or {"x": 0, "y": 0, "width": w, "height": h})
        if kind == "jpeg":
            opts["quality"] = quality
        pg.screenshot(**opts)
        return out


# --------------------------------------------------------------------------- API: estático
def render_static(layout, theme, fmt, content, out, *, brand=None, base_dir=None, scale=1.0, sample=False, renderer=None, kind="png"):
    F = FORMATS[fmt]
    html = page_html(slide_canvas(layout, theme, fmt, content, brand, base_dir=base_dir, sample=sample))
    own = renderer is None
    r = renderer or Renderer(scale).__enter__()
    try:
        r.shoot(html, out, F["w"], F["h"], kind=kind)
    finally:
        if own:
            r.__exit__()
    return out


# --------------------------------------------------------------------------- API: carrossel
def plan_carousel(recipe_id: str, content: dict) -> list[dict]:
    rec = REG.carousels[recipe_id]
    body_layouts = rec["body"]
    slides = content.get("slides") or []
    plan = []
    if content.get("cover", True) is not False:
        cover = {k: content.get(k) for k in ("kicker", "title", "subtitle", "body", "badge", "cta", "photos", "cutout", "date", "place", "number", "label") if content.get(k) is not None}
        cover.setdefault("handle", None)
        plan.append(dict(layout=content.get("cover_layout") or rec["cover"], content=cover))
    total_body = len(slides)
    for i, s in enumerate(slides):
        d = dict(s)
        lay = d.pop("layout", None) or body_layouts[i % len(body_layouts)]
        if lay in ("ds-point", "ds-myth") or (lay == "tip-single"):
            d.setdefault("number", f"{i + 1:02d}")
            d.setdefault("total", f"{total_body:02d}")
        plan.append(dict(layout=lay, content=d))
    end = content.get("end", content.get("cta"))
    if end is not False and rec.get("end"):
        e = dict(end) if isinstance(end, dict) else {}
        e.setdefault("title", "Gostou? *Salve* e compartilhe")
        e.setdefault("cta", "Seguir")
        plan.append(dict(layout=e.pop("layout", None) or rec["end"], content=e))
    return plan


def bridge_overlay(bridge: str, n: int, W: int, H: int, photos=None) -> str:
    """Elemento contínuo que atravessa as N páginas (px)."""
    total = n * W
    if bridge == "ribbon":
        txt = "   ★   ".join(["ARRASTE PARA O LADO"] * 12)
        return (f'<div style="position:absolute;left:-60px;top:{H * 0.945:.0f}px;width:{total + 120}px;height:{H * 0.045:.0f}px;transform:rotate(-1deg);transform-origin:0 50%;'
                f'background:var(--accent);color:var(--on-accent);display:flex;align-items:center;overflow:hidden;font:800 {W * 0.022:.0f}px var(--font-body),Inter;letter-spacing:.2em;white-space:nowrap">'
                f'<span style="padding-left:30px">{txt}{txt}{txt}</span></div>')
    if bridge == "wave-line":
        pts = []
        steps = n * 4
        for i in range(steps + 1):
            x = i * total / steps
            y = H * 0.9 + (math.sin(i * math.pi / 2) * H * 0.018)
            pts.append((x, y))
        d = f"M{pts[0][0]:.0f} {pts[0][1]:.0f} " + " ".join(f"T{x:.0f} {y:.0f}" for x, y in pts[1:])
        return (f'<svg style="position:absolute;left:0;top:0" width="{total}" height="{H}" viewBox="0 0 {total} {H}"><path d="{d}" fill="none" stroke="var(--accent)" stroke-width="{W * 0.012:.0f}" stroke-linecap="round"/>'
                f'<path d="{d}" fill="none" stroke="var(--accent2)" stroke-width="{W * 0.004:.0f}" stroke-linecap="round" transform="translate(0,{H * 0.022:.0f})"/></svg>')
    if bridge == "big-circle":
        out = []
        for i in range(1, n):
            r = W * (0.30 if i % 2 else 0.2)
            cy = H * (0.12 if i % 2 else 0.9)
            col = "var(--accent)" if i % 2 else "var(--accent2)"
            out.append(f'<div style="position:absolute;left:{i * W - r:.0f}px;top:{cy - r:.0f}px;width:{2 * r:.0f}px;height:{2 * r:.0f}px;border-radius:50%;background:{col};opacity:.9;mix-blend-mode:normal"></div>')
        return "".join(out)
    if bridge == "photo-strip":
        ph = photos or []
        cells = []
        sz = W * 0.28
        for i in range(n * 3 + 1):
            src = ph[i % len(ph)] if ph else None
            inner = f'<img src="{src}" style="width:100%;height:100%;object-fit:cover">' if src else '<div class="ph ph' + str(i % 4) + '" style="width:100%;height:100%"></div>'
            cells.append(f'<div class="photo" style="flex:none;width:{sz:.0f}px;height:{sz * 1.25:.0f}px;border-radius:14px;transform:rotate({(-3, 2.5, -1.5, 3)[i % 4]}deg)">{inner}</div>')
        return (f'<div style="position:absolute;left:-20px;top:{H * 0.74:.0f}px;display:flex;gap:{W * 0.03:.0f}px;width:{total + 40}px">{"".join(cells)}</div>')
    if bridge == "arrow-path":
        d = f"M{W * 0.55:.0f} {H * 0.88:.0f} C{W * 0.9:.0f} {H * 0.78:.0f} {W * 1.1:.0f} {H * 0.98:.0f} {W * 1.45:.0f} {H * 0.86:.0f}"
        return (f'<svg style="position:absolute;left:0;top:0" width="{total}" height="{H}" viewBox="0 0 {total} {H}"><path d="{d}" fill="none" stroke="var(--accent)" stroke-width="{W * 0.008:.0f}" stroke-dasharray="{W * 0.025:.0f} {W * 0.02:.0f}" stroke-linecap="round"/>'
                f'<path d="M{W * 1.40:.0f} {H * 0.835:.0f} L{W * 1.46:.0f} {H * 0.862:.0f} L{W * 1.395:.0f} {H * 0.89:.0f}" fill="none" stroke="var(--accent)" stroke-width="{W * 0.01:.0f}" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    if bridge == "dots-path":
        y = H * 0.93
        els = [f'<div style="position:absolute;left:{W * 0.075:.0f}px;top:{y:.0f}px;width:{total - W * 0.15:.0f}px;height:{max(3, W * 0.004):.0f}px;background:var(--line)"></div>']
        for i in range(n):
            els.append(f'<div style="position:absolute;left:{i * W + W * 0.5 - 14:.0f}px;top:{y - 12:.0f}px;width:28px;height:28px;border-radius:50%;background:var(--accent);border:5px solid var(--bg)"></div>')
        return "".join(els)
    return ""


def render_carousel(recipe_id, theme, fmt, content, outdir, *, brand=None, base_dir=None, bridge=None, scale=1.0,
                    sample=False, renderer=None, pager=True, prefix="slide"):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    if sample:
        content = {**REG.carousels[recipe_id].get("sample", {}), **content}
    plan = plan_carousel(recipe_id, content)
    n = len(plan)
    F = FORMATS[fmt]
    W, H = F["w"], F["h"]
    own = renderer is None
    r = renderer or Renderer(scale).__enter__()
    outs = []
    try:
        if not bridge or bridge == "none":
            for i, p in enumerate(plan):
                html = page_html(slide_canvas(p["layout"], theme, fmt, p["content"], brand, base_dir=base_dir, sample=sample, pager=(i, n) if pager else None))
                out = outdir / f"{prefix}_{i + 1:02d}.png"
                r.shoot(html, out, W, H)
                outs.append(out)
        else:
            cells = []
            for i, p in enumerate(plan):
                cv = slide_canvas(p["layout"], theme, fmt, p["content"], brand, base_dir=base_dir, sample=sample, pager=(i, n) if (pager and bridge != "ribbon") else None)
                cells.append(f'<div style="position:absolute;left:{i * W}px;top:0;width:{W}px;height:{H}px">{cv}</div>')
            photos = [resolve_media(x, base_dir) for x in (content.get("photos") or [])]
            ov = bridge_overlay(bridge, n, W, H, photos)
            t = resolve_theme(theme, brand)
            vars_ = theme_css_vars(t)
            wrap = (f'<div id="pano" style="position:relative;width:{n * W}px;height:{H}px;{vars_}">{"".join(cells)}'
                    f'<div style="position:absolute;inset:0;z-index:40;pointer-events:none">{ov}</div></div>')
            html = head_html(False) + f'</head><body>{wrap}{_lottie_lib(wrap)}<script>{PREP_JS}</script></body></html>'
            pg = r.load(html, n * W, H)
            for i in range(n):
                out = outdir / f"{prefix}_{i + 1:02d}.png"
                pg.screenshot(path=str(out), type="png", clip={"x": i * W, "y": 0, "width": W, "height": H})
                outs.append(out)
    finally:
        if own:
            r.__exit__()
    return outs


# --------------------------------------------------------------------------- API: reel
def _ffmpeg():
    p = shutil.which("ffmpeg")
    if not p:
        raise SystemExit("ffmpeg não encontrado. Instale: https://ffmpeg.org/download.html")
    return p


def capture_scene(r: Renderer, html: str, w: int, h: int, seconds: float, fps: int, out: Path, fast: bool = False, blur: int = 1):
    """blur>1: motion blur real — captura `blur` subquadros por quadro e o ffmpeg mistura (obturador de 360°). Só o que se move borra."""
    pg = r.load(html, w, h)
    n = max(1, int(round(seconds * fps)))
    k = max(1, min(6, int(blur or 1)))
    vf = []
    if k > 1:
        vf = ["-vf", f"tmix=frames={k}:weights='{' '.join(['1'] * k)}',select='eq(mod(n+1\\,{k})\\,0)',setpts=N/({fps}*TB)"]
    cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps * k), "-c:v", "mjpeg", "-i", "-", *vf,
           *ffsetup.vcodec(fast, 17), "-r", str(fps), str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(n * k):
            pg.evaluate("async t=>{await __seek(t);return new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))}", i * 1000.0 / (fps * k))
            proc.stdin.write(pg.screenshot(type="jpeg", quality=94, clip={"x": 0, "y": 0, "width": w, "height": h}))
    finally:
        proc.stdin.close()
        proc.wait()
    return out


def join_scenes(clips: list[Path], durs: list[float], transitions: list[str], td: float, fps: int, out: Path, audio: str | None = None, ass: tuple | None = None, fast: bool = False):
    total = sum(durs)
    cmd = [_ffmpeg(), "-y", "-loglevel", "error"]
    for c in clips:
        cmd += ["-i", str(c)]
    if audio:
        cmd += ["-i", str(audio)]
    if len(clips) == 1:
        fc = f"[0:v]fps={fps},format=yuv420p[vout]"
    else:
        parts = [f"[{i}:v]settb=AVTB,fps={fps},format=yuv420p[s{i}]" for i in range(len(clips))]
        prev, acc = "s0", 0.0
        for i in range(1, len(clips)):
            acc += durs[i - 1]
            tag = f"x{i}"
            parts.append(f"[{prev}][s{i}]xfade=transition={transitions[i - 1]}:duration={td}:offset={acc:.3f}[{tag}]")
            prev = tag
        parts.append(f"[{prev}]format=yuv420p[vout]")
        fc = ";".join(parts)
    vmap = "[vout]"
    if ass:
        fc += f";[vout]ass=filename={ass[0]}:fontsdir={ass[1]}[vsub]"
        vmap = "[vsub]"
    cmd += ["-filter_complex", fc, "-map", vmap]
    if audio:
        cmd += ["-map", f"{len(clips)}:a", "-c:a", "aac", "-b:a", "192k", "-af", f"afade=t=in:d=0.3,afade=t=out:st={max(0, total - 1):.2f}:d=1,loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.84:level=disabled"]
    cmd += [*ffsetup.vcodec(fast, 17), "-movflags", "+faststart", "-t", f"{total:.3f}", str(out)]
    subprocess.run(cmd, check=True)
    return out


def tidy_sfx(events: list, same_kind_gap: float = 0.12, window: float = 0.25, max_layers: int = 3) -> list:
    """Regras de mixagem dos efeitos: dois sons do mesmo tipo quase no mesmo instante embolam (fica o mais forte) e
    no máximo `max_layers` sons por janela de `window` s (ficam os mais fortes)."""
    ev = sorted(events, key=lambda e: e["t"])
    out = []
    for e in ev:
        twin = next((o for o in out if o.get("kind") == e.get("kind") and abs(o["t"] - e["t"]) < same_kind_gap), None)
        if twin:
            if e.get("vol", 1) > twin.get("vol", 1):
                out[out.index(twin)] = e
            continue
        out.append(e)
    keep = []
    for e in out:
        near = [o for o in keep if abs(o["t"] - e["t"]) < window]
        if len(near) >= max_layers:
            weakest = min(near, key=lambda o: o.get("vol", 1))
            if e.get("vol", 1) <= weakest.get("vol", 1):
                continue
            keep.remove(weakest)
        keep.append(e)
    return sorted(keep, key=lambda e: e["t"])


CAMERA_DEFAULT = {"site-hero": "push", "site-stats": "orbit", "site-list": "orbit", "site-cta": "dolly"}


def _cam_for(s: dict, camera):
    """Câmera da cena: valor da cena > --camera > padrão do layout. 'none' desliga."""
    c = s.get("camera") or camera or CAMERA_DEFAULT.get(s.get("layout"))
    return None if c in (None, "none", "off") else c


def snap_to_beat(d: float, bpm: float, beats: int = 4) -> float:
    unit = 60.0 / bpm * beats / 2  # meio compasso
    return max(unit, round(d / unit) * unit)



def render_storyboard(scenes: list, theme: str, out_dir: Path, *, brand: dict | None = None, base_dir: Path | None = None, title: str = "") -> Path:
    """Renderiza um thumbnail de cada cena e monta `storyboard.png` em grade (3 colunas).
    Serve para o Diretor de Arte aprovar o conjunto antes de pagar o render do reel."""
    from PIL import Image, ImageDraw, ImageFont
    out_dir = Path(out_dir)
    thumbs_dir = out_dir / ".storyboard-thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    thumbs = []
    with Renderer(0.5) as r:
        for i, sc in enumerate(scenes, 1):
            lay = sc["layout"]
            ct = {k: v for k, v in sc.items() if k not in ("dur", "theme", "photo_meta")}
            t = sc.get("theme") or theme
            try:
                p = thumbs_dir / f"{i:02d}-{lay}.png"
                render_static(lay, t, "reel", ct, p, brand=brand, base_dir=base_dir or out_dir, scale=0.5, renderer=r, kind="png")
                thumbs.append((i, lay, sc.get("title", ""), p))
            except Exception as e:  # noqa
                print(f"  ! storyboard: cena {i} ({lay}) não rasterizou ({type(e).__name__})")
    if not thumbs:
        return out_dir / "storyboard.png"
    cols = 3
    tw, th_ = 540, 960
    for _, _, _, p in thumbs:
        try:
            with Image.open(p) as im:
                th_ = max(th_, int(540 * im.height / im.width))
        except Exception:  # noqa
            pass
    pad, gap, lbl = 24, 24, 56
    rows = (len(thumbs) + cols - 1) // cols
    W = pad * 2 + cols * tw + (cols - 1) * gap
    hdr = 92 if title else 0
    H = pad * 2 + hdr + rows * (th_ + lbl) + (rows - 1) * gap
    sheet = Image.new("RGB", (W, H), (248, 248, 250))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(str((ROOT / "library" / "fonts" / "Inter-Bold.ttf")) if (ROOT / "library" / "fonts" / "Inter-Bold.ttf").exists() else "DejaVuSans-Bold.ttf", 34)
        small = ImageFont.truetype("DejaVuSans.ttf", 22)
    except Exception:  # noqa
        font = ImageFont.load_default()
        small = font
    if title:
        d.text((pad, pad), title, fill=(18, 18, 22), font=font)
        d.text((pad, pad + 44), f"{len(thumbs)} cena(s) · aprove antes de renderizar", fill=(130, 130, 140), font=small)
    for k, (num, lay, titulo, p) in enumerate(thumbs):
        col, row = k % cols, k // cols
        x = pad + col * (tw + gap)
        y = pad + hdr + row * (th_ + lbl + gap)
        try:
            with Image.open(p) as im:
                im = im.convert("RGB")
                w2 = tw
                h2 = int(im.height * w2 / im.width)
                im = im.resize((w2, h2), Image.LANCZOS)
                sheet.paste(im, (x, y))
        except Exception:  # noqa
            d.rectangle([x, y, x + tw, y + th_], outline=(200, 200, 210), width=2)
        tag = f"#{num} · {lay}"
        head = (titulo or "")[:48].replace("*", "")
        d.text((x, y + th_ + 6), tag, fill=(70, 70, 80), font=small)
        if head:
            d.text((x, y + th_ + 30), head, fill=(18, 18, 22), font=small)
    out_file = out_dir / "storyboard.png"
    sheet.save(out_file)
    return out_file

def render_reel(scenes: list[dict], theme: str, out, *, fmt="reel", motion="fade-up", transition="smooth", tdur=None, fps=30,
                bpm=None, audio=None, brand=None, base_dir=None, sample=False, renderer=None, pager=False, verbose=True,
                pace=None, speed=None, stagger_scale=None, intensity=None, ease=None, kenburns=None, count_up=False,
                sync=False, music=None, sfx=None, key="A", music_vol=0.75, voice=None, voice_vol=1.0, duck=0.6, voice_start=0.0,
                human=False, parallax=False, highlight=None, captions=None, stems=None, script=None, words_file=None, transcribe=False, exit=None, preview=False, fit_voice=False, cap_style=None, vocab=None, camera=None, blur=1):
    """scenes: [{layout, content, dur?}]
    music: estilo gerado localmente (lofi|house|pop|corporate|cinematic|hype|ambient) ou None (use `audio` p/ arquivo próprio)
    sfx: None | 'light' (whoosh nas transições) | 'full' (+ pops de entrada e brilho final)
    sync: alinha stagger/duração do movimento/transição ao BPM (exige bpm)."""
    from . import motion as _motion
    if human and not ease:
        ease = 'spring-soft'  # motion humanizado: entradas com física de mola por padrão
    F = FORMATS[fmt]
    W, H = F["w"], F["h"]
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if music and not bpm:
        from . import audio as _audio
        bpm = _audio.STYLES[music]["bpm"]
    if tdur is None:
        tdur = _motion.PACE.get(pace or "standard", _motion.PACE["standard"])["tdur"]
    if sync and bpm:
        tdur = 60.0 / float(bpm) / 2
    durs = []
    for s in scenes:
        d = float(s.get("dur", 3.0))
        if bpm:
            d = snap_to_beat(d, float(bpm))
        durs.append(d)
    if fit_voice:
        if not voice:
            raise SystemExit("--fit-voice precisa de --voice arquivo.wav")
        from . import voice as _vz
        vlen = _vz.duration(voice)
        def _w(s):  # peso = palavras faladas ("say") ou textos da cena
            c = s.get("content") or {}
            txt = c.get("say") or " ".join(str(c.get(k, "")) for k in ("kicker", "title", "subtitle", "body", "text"))
            txt += " " + " ".join(str(i.get("title", i) if isinstance(i, dict) else i) for i in (c.get("items") or []))
            return max(3, len(txt.replace("*", "").split()))
        ws = [_w(s) for s in scenes]
        avail = max(1.0, vlen + 0.8 - tdur * max(0, len(scenes) - 1) - voice_start)
        durs = [max(1.8, avail * w / sum(ws)) for w in ws]
        durs[0] += voice_start
        if bpm:
            durs = [snap_to_beat(d, float(bpm)) for d in durs]
        if verbose:
            print(f"  --fit-voice: voz {vlen:.1f}s -> cenas {[round(d, 1) for d in durs]}")
    tr_list = []
    for i in range(max(0, len(scenes) - 1)):
        if transition.startswith("set:"):
            pool = TRANSITION_SETS.get(transition[4:])
            if not pool:
                raise SystemExit(f"Conjunto de transições '{transition[4:]}' não existe: {', '.join(TRANSITION_SETS)}")
            tr_list.append(pool[(i + sum(map(ord, theme))) % len(pool)])
        elif transition in ("smooth", "random", "mix"):
            tr_list.append(TRANSITION_POOL[(i + sum(map(ord, theme))) % len(TRANSITION_POOL)])
        elif "," in transition:
            seq = transition.split(",")
            tr_list.append(seq[i % len(seq)])
        else:
            tr_list.append(transition)
    own = renderer is None
    if preview:
        fps = min(fps, 15)
    r = renderer or Renderer(0.4 if preview else 1.0).__enter__()
    tmpd = CACHE / f"reel_{uuid.uuid4().hex[:6]}"
    tmpd.mkdir()
    clips = []
    try:
        for i, s in enumerate(scenes):
            seconds = durs[i] + (tdur if i < len(scenes) - 1 else 0.0)
            html = page_html(slide_canvas(s["layout"], s.get("theme") or theme, fmt, s.get("content", {}), brand, base_dir=base_dir, sample=sample,
                                          reel=dict(motion=s.get("motion", motion), scene_dur=durs[i] + tdur, extra_delay=(tdur if i > 0 else 0.0),
                                                    pace=pace, speed=speed, stagger_scale=stagger_scale, intensity=intensity, ease=ease,
                                                    kenburns=kenburns, count_up=count_up, sync=sync, bpm=bpm,
                                                    human=human, parallax=parallax, highlight=highlight,
                                                    exit=(exit if i < len(scenes) - 1 else None), exit_at=durs[i], camera=_cam_for(s, camera)),
                                          pager=(i, len(scenes)) if pager else None), reel=True)
            clip = tmpd / f"s{i}.mp4"
            if verbose:
                print(f"  cena {i + 1}/{len(scenes)} · {s['layout']} · {seconds:.1f}s")
            capture_scene(r, html, W, H, seconds, fps, clip, fast=preview, blur=1 if preview else blur)
            clips.append(clip)
        total = sum(durs)
        starts = [sum(durs[:i]) for i in range(len(durs))]
        events = []
        if sfx:
            for i in range(1, len(scenes)):
                kind = TRANSITION_SFX.get(tr_list[i - 1], "whoosh")
                if kind:
                    events.append(dict(t=max(0, starts[i] - .08), kind=kind, vol=.9, vary=bool(human)))
                if kind == "riser" or (sfx == "full" and i == len(scenes) - 1):
                    events.append(dict(t=max(0, starts[i] - 1.1), kind="riser", vol=.5, vary=bool(human)))
            if sfx == "full":
                for i in range(len(scenes)):
                    events.append(dict(t=starts[i] + (tdur if i else 0) + .18, kind="pop", vol=.7, vary=bool(human)))
                events.append(dict(t=max(0, starts[-1] + tdur + .5), kind="shimmer", vol=.7))
        events = tidy_sfx(events)
        clip_wav = None
        clip_items = []
        for i, s_ in enumerate(scenes):
            for ph in ((s_.get("content") or {}).get("photos") or []):
                if isinstance(ph, dict) and float(ph.get("volume", 0)) > 0:
                    src_ = resolve_media(ph.get("src"), base_dir)
                    if src_:
                        clip_items.append(dict(src=src_.replace("file://", ""), t=starts[i], dur=durs[i] + (tdur if i < len(scenes) - 1 else 0),
                                               start=float(ph.get("start", 0)), speed=float(ph.get("speed", 1)), volume=float(ph["volume"]), loop=bool(ph.get("loop", True))))
        if clip_items:
            from . import audio as _audio
            clip_wav = tmpd / "clipes.wav"
            _audio.clips_track(clip_items, total, clip_wav)
        audio_src = audio
        if music or events or audio or voice or clip_wav:
            from . import audio as _audio
            wav = out.with_suffix(".mix.wav")
            _audio.build_track(total, music, bpm, events, wav, music_file=None if music else audio, music_vol=music_vol, key=key,
                               voice_file=voice, voice_vol=voice_vol, duck=duck, voice_start=voice_start, extra_voice=str(clip_wav) if clip_wav else None)
            audio = str(wav)
        ass_arg, cap_files = None, {}
        if captions:
            from . import captions as _cap
            if not (script or words_file or transcribe):
                raise SystemExit("--captions precisa de tempos: use --script \"texto\"|@roteiro.txt, --words arquivo.srt|json ou --transcribe")
            th = resolve_theme(theme, brand)
            cs = cap_style or {}
            if words_file:
                words = _cap.from_file(words_file, voice_start)
            elif transcribe:
                words = _cap.transcribe(voice or audio_src, "pt", "small", vocab=vocab)
            else:
                words = _cap.align(script, voice, total, voice_start)
            assp, fdir = _cap.build_ass(words, tmpd / "legendas.ass", style=captions, W=W, H=H, font_slug=th.get("font_display", "Space Grotesk").lower().replace(" ", "-"),
                                        accent=cs.get("accent") or th.get("accent2", th.get("accent", "#FFFFFF")), fg=cs.get("fg", "#FFFFFF"), pos_y=cs.get("pos_y", .64),
                                        upper=bool(cs.get("upper")), size=int(min(W, H) * cs["size_pct"] / 100) if cs.get("size_pct") else None,
                                        scrim=_cap.band_brightness(clips, starts, durs, cs.get("pos_y", .64)) > 150 if captions != "box" else False)
            ass_arg = (assp, fdir)
            cap_files = {"legendas.ass": assp, "legendas.srt": assp.with_suffix(".srt"), "palavras.json": assp.with_suffix(".words.json")}
        join_scenes(clips, durs, tr_list, tdur, fps, out, audio, ass_arg, fast=preview)
        if stems:
            from . import audio as _audio, export as _export
            stem_files = {}
            if music or events or audio or voice or clip_wav:
                for part in ("mix", "musica", "voz", "sfx"):
                    solo = {"mix": None, "musica": "music", "voz": "voice", "sfx": "sfx"}[part]
                    pth = tmpd / f"{part}.wav"
                    _audio.build_track(total, music, bpm, events, pth, music_file=None if music else audio_src, music_vol=music_vol, key=key,
                                       voice_file=voice, voice_vol=voice_vol, duck=duck, voice_start=voice_start, solo=solo, extra_voice=str(clip_wav) if clip_wav else None)
                    stem_files[part] = pth
            _tl = dict(total=round(total, 3), scenes=[dict(i=i, layout=s["layout"], start=round(starts[i], 3), dur=round(durs[i], 3)) for i, s in enumerate(scenes)],
                       transitions=[dict(at=round(starts[i], 3), dur=tdur, type=tr_list[i - 1]) for i in range(1, len(scenes))], sfx_events=events, fps=fps, bpm=bpm)
            _export.export_all(stems, clips=clips, durs=durs, starts=starts, tdur=tdur, fps=fps, timeline=_tl, audio_stems=stem_files, caption_files=cap_files,
                               spec=dict(theme=theme, motion=motion, transition=transition, human=human, parallax=parallax, highlight=highlight, captions=captions))
        if audio and str(audio).endswith(".mix.wav"):
            Path(audio).unlink(missing_ok=True)
        beat = 60.0 / float(bpm) if bpm else None
        from . import review as _review
        tl = dict(total=round(total, 3), fps=fps, format=fmt, theme=theme, motion=motion, pace=pace or "standard", ease=ease,
                  bpm=bpm, beat=round(beat, 4) if beat else None, music=music, sfx=sfx, sync=bool(sync), voice=bool(voice),
                  scenes=[dict(i=i, layout=s["layout"], start=round(starts[i], 3), dur=round(durs[i], 3), words=_review.count_words(s.get("content"))) for i, s in enumerate(scenes)],
                  transitions=[dict(at=round(starts[i], 3), dur=tdur, type=tr_list[i - 1]) for i in range(1, len(scenes))],
                  sfx_events=events,
                  beat_grid_first_bars=[round(b * beat, 3) for b in range(0, 33)] if beat else None)
        out.with_suffix(".timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")
    finally:
        if own:
            r.__exit__()
        shutil.rmtree(tmpd, ignore_errors=True)
    return out
