"""
Fontes open source (Fontsource = Google Fonts + outras, licença OFL/Apache) e pareamento tipográfico.

 - instala famílias via `npm pack @fontsource/<slug>` (só woff2 latin, cobre português)
 - mede x-height / cap-height reais de cada fonte (fontTools) -> library/fonts_catalog.json
 - pontua pares (contraste de classe, x-height, peso, legibilidade) e sugere ajuste óptico
Regras de pareamento (pesquisadas): contraste com harmonia; x-height igual OU bem diferente (nunca
"meio-termo"); no máximo 2 famílias; corpo nunca script/decorativa; display com peso alto, corpo leve.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "fonts"
CATALOG_JSON = ROOT / "library" / "fonts_catalog.json"
PAIRS_JSON = ROOT / "library" / "font_pairs.json"

# slug: (Nome, classe, papel, [humores])
# classes: sans-geo, sans-hum, sans-grot, condensed, serif-display, serif-text, slab, script, hand, deco, mono
# papel: display | body | both
F = {}


def _f(slug, name, cls, role, moods):
    F[slug] = dict(name=name, cls=cls, role=role, moods=moods.split())


# --- sans geométricas
_f("poppins", "Poppins", "sans-geo", "both", "moderno amigavel corporativo")
_f("montserrat", "Montserrat", "sans-geo", "both", "moderno corporativo imobiliario")
_f("outfit", "Outfit", "sans-geo", "both", "moderno minimalista tech")
_f("urbanist", "Urbanist", "sans-geo", "both", "moderno minimalista")
_f("sora", "Sora", "sans-geo", "both", "tech moderno")
_f("lexend", "Lexend", "sans-geo", "body", "saude acessivel educacao")
_f("plus-jakarta-sans", "Plus Jakarta Sans", "sans-geo", "both", "moderno corporativo saude")
_f("manrope", "Manrope", "sans-geo", "both", "moderno tech corporativo")
_f("figtree", "Figtree", "sans-geo", "body", "amigavel moderno")
_f("red-hat-display", "Red Hat Display", "sans-geo", "both", "corporativo moderno")
_f("jost", "Jost", "sans-geo", "both", "elegante minimalista luxo")
_f("league-spartan", "League Spartan", "sans-geo", "display", "impacto moderno")
_f("quicksand", "Quicksand", "sans-geo", "both", "amigavel divertido saude")
_f("nunito", "Nunito", "sans-geo", "body", "amigavel saude educacao")
_f("raleway", "Raleway", "sans-geo", "both", "elegante luxo moderno")
# --- sans humanistas / neutras
_f("dm-sans", "DM Sans", "sans-hum", "both", "moderno minimalista corporativo")
_f("inter", "Inter", "sans-hum", "body", "tech minimalista corporativo")
_f("work-sans", "Work Sans", "sans-hum", "body", "corporativo minimalista")
_f("source-sans-3", "Source Sans 3", "sans-hum", "body", "corporativo educacao")
_f("open-sans", "Open Sans", "sans-hum", "body", "corporativo neutro")
_f("lato", "Lato", "sans-hum", "body", "corporativo elegante neutro")
_f("ibm-plex-sans", "IBM Plex Sans", "sans-hum", "body", "tech corporativo")
_f("karla", "Karla", "sans-hum", "body", "editorial moderno")
_f("rubik", "Rubik", "sans-hum", "both", "amigavel moderno divertido")
_f("barlow", "Barlow", "sans-hum", "both", "esportivo corporativo")
_f("public-sans", "Public Sans", "sans-hum", "body", "neutro corporativo")
_f("albert-sans", "Albert Sans", "sans-hum", "both", "moderno editorial")
_f("be-vietnam-pro", "Be Vietnam Pro", "sans-hum", "both", "moderno tech")
_f("mulish", "Mulish", "sans-hum", "body", "minimalista saude")
_f("hanken-grotesk", "Hanken Grotesk", "sans-hum", "both", "moderno editorial")
_f("instrument-sans", "Instrument Sans", "sans-hum", "both", "editorial moderno")
# --- grotescas / display sans
_f("space-grotesk", "Space Grotesk", "sans-grot", "both", "tech moderno retro")
_f("bricolage-grotesque", "Bricolage Grotesque", "sans-grot", "both", "editorial moderno divertido")
_f("syne", "Syne", "sans-grot", "display", "arte moderno ousado")
_f("unbounded", "Unbounded", "sans-grot", "display", "tech ousado moderno")
_f("archivo", "Archivo", "sans-grot", "both", "corporativo editorial esportivo")
_f("familjen-grotesk", "Familjen Grotesk", "sans-grot", "both", "editorial moderno")
_f("schibsted-grotesk", "Schibsted Grotesk", "sans-grot", "both", "editorial jornal")
_f("epilogue", "Epilogue", "sans-grot", "both", "editorial moderno")
_f("onest", "Onest", "sans-grot", "both", "moderno tech")
_f("chivo", "Chivo", "sans-grot", "both", "editorial corporativo")
_f("big-shoulders-display", "Big Shoulders Display", "condensed", "display", "impacto esportivo industrial")
# --- condensadas / impacto
_f("bebas-neue", "Bebas Neue", "condensed", "display", "impacto esportivo promocao")
_f("doto", "Doto", "deco", "display", "tecnologia pixel dot-matrix")
_f("google-sans-flex", "Google Sans Flex", "sans-hum", "both", "moderno tecnologia limpo")
_f("geist", "Geist", "sans-grot", "both", "moderno tecnologia limpo")
_f("geist-mono", "Geist Mono", "mono", "body", "tecnologia rotulo")
_f("anton", "Anton", "condensed", "display", "impacto promocao")
_f("oswald", "Oswald", "condensed", "display", "impacto esportivo")
_f("archivo-black", "Archivo Black", "sans-grot", "display", "impacto promocao ousado")
_f("barlow-condensed", "Barlow Condensed", "condensed", "both", "esportivo industrial")
_f("fjalla-one", "Fjalla One", "condensed", "display", "impacto jornal")
_f("league-gothic", "League Gothic", "condensed", "display", "impacto editorial")
_f("saira-condensed", "Saira Condensed", "condensed", "both", "tech esportivo")
# --- serifas display
_f("playfair-display", "Playfair Display", "serif-display", "display", "elegante editorial luxo")
_f("dm-serif-display", "DM Serif Display", "serif-display", "display", "elegante editorial")
_f("fraunces", "Fraunces", "serif-display", "both", "editorial divertido retro")
_f("instrument-serif", "Instrument Serif", "serif-display", "display", "editorial minimalista elegante")
_f("cormorant-garamond", "Cormorant Garamond", "serif-display", "display", "luxo elegante casamento")
_f("bodoni-moda", "Bodoni Moda", "serif-display", "display", "luxo moda editorial")
_f("abril-fatface", "Abril Fatface", "serif-display", "display", "impacto moda editorial")
_f("young-serif", "Young Serif", "serif-display", "display", "editorial amigavel retro")
_f("gloock", "Gloock", "serif-display", "display", "editorial impacto elegante")
_f("prata", "Prata", "serif-display", "display", "luxo elegante")
_f("italiana", "Italiana", "serif-display", "display", "luxo minimalista moda")
_f("cinzel", "Cinzel", "serif-display", "display", "luxo classico")
_f("libre-caslon-display", "Libre Caslon Display", "serif-display", "display", "editorial classico")
# --- serifas de texto
_f("lora", "Lora", "serif-text", "both", "editorial elegante")
_f("merriweather", "Merriweather", "serif-text", "body", "editorial jornal")
_f("source-serif-4", "Source Serif 4", "serif-text", "body", "editorial corporativo")
_f("libre-baskerville", "Libre Baskerville", "serif-text", "body", "classico editorial")
_f("crimson-pro", "Crimson Pro", "serif-text", "body", "editorial classico")
_f("eb-garamond", "EB Garamond", "serif-text", "body", "classico luxo")
_f("pt-serif", "PT Serif", "serif-text", "body", "editorial jornal")
_f("newsreader", "Newsreader", "serif-text", "both", "editorial jornal")
_f("literata", "Literata", "serif-text", "body", "editorial")
_f("spectral", "Spectral", "serif-text", "both", "editorial elegante")
# --- slab
_f("roboto-slab", "Roboto Slab", "slab", "both", "corporativo industrial")
_f("zilla-slab", "Zilla Slab", "slab", "both", "editorial retro")
_f("bitter", "Bitter", "slab", "both", "editorial jornal")
_f("arvo", "Arvo", "slab", "both", "retro industrial")
_f("alfa-slab-one", "Alfa Slab One", "slab", "display", "impacto retro")
# --- manuscritas / script
_f("caveat", "Caveat", "hand", "display", "handmade amigavel")
_f("pacifico", "Pacifico", "script", "display", "divertido retro")
_f("permanent-marker", "Permanent Marker", "hand", "display", "handmade impacto divertido")
_f("dancing-script", "Dancing Script", "script", "display", "elegante casamento")
_f("great-vibes", "Great Vibes", "script", "display", "luxo casamento")
_f("sacramento", "Sacramento", "script", "display", "elegante casamento")
_f("satisfy", "Satisfy", "script", "display", "handmade retro")
_f("kalam", "Kalam", "hand", "both", "handmade amigavel")
_f("amatic-sc", "Amatic SC", "hand", "display", "handmade organico")
_f("yellowtail", "Yellowtail", "script", "display", "retro divertido")
# --- decorativas / tendência
_f("monoton", "Monoton", "deco", "display", "retro neon")
_f("righteous", "Righteous", "deco", "display", "retro divertido")
_f("bungee", "Bungee", "deco", "display", "urbano impacto")
_f("lobster", "Lobster", "script", "display", "divertido retro")
_f("rubik-mono-one", "Rubik Mono One", "deco", "display", "ousado urbano")
_f("press-start-2p", "Press Start 2P", "deco", "display", "retro games")
_f("special-elite", "Special Elite", "deco", "display", "retro vintage")
# --- mono
_f("jetbrains-mono", "JetBrains Mono", "mono", "both", "tech")
_f("ibm-plex-mono", "IBM Plex Mono", "mono", "both", "tech editorial")
_f("space-mono", "Space Mono", "mono", "both", "tech retro")
_f("dm-mono", "DM Mono", "mono", "both", "tech minimalista")

SERIF = {"serif-display", "serif-text", "slab"}
SANS = {"sans-geo", "sans-hum", "sans-grot", "condensed"}
LOUD = {"script", "hand", "deco"}
WEIGHTS_OK = (300, 400, 500, 600, 700, 800, 900)


# ------------------------------------------------------------------ instalação
def _pack(slug: str, tmp: Path) -> Path | None:
    out = tmp / slug
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["npm", "pack", f"@fontsource/{slug}", "--silent"], cwd=out, capture_output=True, text=True)
    tgz = next(out.glob("*.tgz"), None)
    return tgz if r.returncode == 0 and tgz else None


def _extract(slug: str, tgz: Path) -> list[str]:
    meta = F.get(slug, {})
    italic_ok = meta.get("cls") in SERIF or meta.get("role") in ("body", "both")
    got = []
    with tarfile.open(tgz) as t:
        for m in t.getmembers():
            mm = re.fullmatch(rf"package/files/{re.escape(slug)}-latin-(\d+)-(normal|italic)\.woff2", m.name)
            if not mm:
                continue
            w, style = int(mm.group(1)), mm.group(2)
            if w not in WEIGHTS_OK or (style == "italic" and (not italic_ok or w not in (400, 700))):
                continue
            dest = FONTS / f"{slug}-latin-{w}-{style}.woff2"
            if not dest.exists():
                dest.write_bytes(t.extractfile(m).read())
            got.append(dest.name)
    return got


def install(slugs: list[str], workers: int = 8) -> dict:
    FONTS.mkdir(exist_ok=True)
    res = {"ok": [], "fail": []}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        def one(slug):
            tgz = _pack(slug, tmp)
            if not tgz:
                return slug, None
            return slug, _extract(slug, tgz)

        with ThreadPoolExecutor(workers) as ex:
            for slug, files in ex.map(one, slugs):
                (res["ok"] if files else res["fail"]).append(slug)
    rebuild()
    return res


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def installed_slugs() -> set[str]:
    return {re.match(r"(.+)-latin-\d+-(?:normal|italic)\.woff2", p.name).group(1) for p in FONTS.glob("*.woff2")}


# ------------------------------------------------------------------ metadados e CSS
def _metrics(path: Path) -> dict:
    try:
        from fontTools.ttLib import TTFont
        f = TTFont(str(path))
        upm = f["head"].unitsPerEm
        os2 = f["OS/2"]
        x = getattr(os2, "sxHeight", 0) or 0
        c = getattr(os2, "sCapHeight", 0) or 0
        if not x:  # fallback: medir o glifo x
            gs = f.getGlyphSet()
            from fontTools.pens.boundsPen import BoundsPen
            bp = BoundsPen(gs)
            gs[f.getBestCmap()[ord("x")]].draw(bp)
            x = bp.bounds[3] if bp.bounds else 0
        return dict(x=round(x / upm, 4), cap=round(c / upm, 4) if c else None, avg=round(os2.xAvgCharWidth / upm, 4))
    except Exception:
        return {}


def rebuild() -> dict:
    """Regenera fonts.css, manifest.json e library/fonts_catalog.json a partir dos woff2 presentes."""
    by: dict[str, dict] = {}
    for p in sorted(FONTS.glob("*.woff2")):
        m = re.fullmatch(r"(.+)-latin-(\d+)-(normal|italic)\.woff2", p.name)
        if not m:
            continue
        slug, w, st = m.group(1), int(m.group(2)), m.group(3)
        by.setdefault(slug, {"normal": [], "italic": []})[st].append(w)
    css, manifest, catalog = [], {}, {}
    old = {}
    if CATALOG_JSON.exists():
        old = {c["slug"]: c for c in json.loads(CATALOG_JSON.read_text())["fonts"]}
    for slug, ws in by.items():
        meta = F.get(slug, dict(name=slug.replace("-", " ").title(), cls="sans-hum", role="both", moods=[]))
        name = meta["name"]
        manifest[name] = sorted(ws["normal"])
        for st in ("normal", "italic"):
            for w in sorted(ws[st]):
                css.append(f"@font-face{{font-family:'{name}';font-style:{st};font-weight:{w};font-display:block;"
                           f"src:url('{slug}-latin-{w}-{st}.woff2') format('woff2')}}")
        ref = 400 if 400 in ws["normal"] else sorted(ws["normal"])[0]
        met = old.get(slug, {}).get("metrics") or _metrics(FONTS / f"{slug}-latin-{ref}-normal.woff2")
        catalog[slug] = dict(slug=slug, name=name, cls=meta["cls"], role=meta["role"], moods=meta["moods"],
                             weights=sorted(ws["normal"]), italic=bool(ws["italic"]), metrics=met)
    (FONTS / "fonts.css").write_text("\n".join(css) + "\n")
    (FONTS / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    CATALOG_JSON.write_text(json.dumps({"fonts": sorted(catalog.values(), key=lambda c: c["name"])},
                                       indent=1, ensure_ascii=False))
    return catalog


_cat_cache: dict | None = None


def catalog() -> dict[str, dict]:
    global _cat_cache
    if _cat_cache is None:
        _cat_cache = {c["name"]: c for c in json.loads(CATALOG_JSON.read_text())["fonts"]} if CATALOG_JSON.exists() else {}
    return _cat_cache


# ------------------------------------------------------------------ pareamento
def _group(cls):
    return "serif" if cls in SERIF else "loud" if cls in LOUD else "mono" if cls == "mono" else "sans"


def score_pair(display: str, body: str) -> dict:
    """Pontua (0-100) o par display+corpo. Retorna notas e ajuste óptico sugerido para o corpo."""
    cat = catalog()
    d, b = cat.get(display), cat.get(body)
    if not d or not b:
        return dict(score=None, notes=[f"fonte não instalada: {n}" for n, c in ((display, d), (body, b)) if not c], adjust=None)
    notes, s = [], 50
    gd, gb = _group(d["cls"]), _group(b["cls"])
    if b["cls"] in LOUD or b["role"] == "display":
        s -= 35
        notes.append("corpo com fonte de display/script: legibilidade ruim em texto corrido")
    if display == body:
        s += 5
        notes.append("mesma família: hierarquia só por peso/tamanho (seguro, mas pouco contraste)")
    elif gd != gb:
        s += 25
        notes.append(f"contraste de classe ({d['cls']} × {b['cls']}): bom")
    elif d["cls"] != b["cls"]:
        s += 10
        notes.append(f"classes parecidas ({d['cls']} × {b['cls']}): contraste moderado")
    else:
        s -= 20
        notes.append(f"mesma classe ({d['cls']}): conflito, as duas competem")
    xd, xb = d["metrics"].get("x"), b["metrics"].get("x")
    adjust = None
    if xd and xb:
        diff = abs(xd - xb) / max(xd, xb)
        if diff <= 0.07:
            s += 25
            notes.append(f"x-height muito próximo ({xd:.2f}/{xb:.2f}): harmônico")
        elif diff >= 0.22:
            s += 10
            notes.append(f"x-height bem diferente ({xd:.2f}/{xb:.2f}): contraste deliberado")
        else:
            s += 2
            notes.append(f"x-height em zona intermediária ({xd:.2f}/{xb:.2f}): ajuste óptico aplicado")
        adjust = round(min(max(xd, xb * 0.9), xb * 1.1), 3) if diff <= 0.22 else None
    wd, wb = max(d["weights"]), min(b["weights"], key=lambda w: abs(w - 400))
    if wd >= 600 and wb <= 500:
        s += 8
        notes.append("peso: display forte + corpo leve")
    if d["cls"] in LOUD and b["cls"] in LOUD:
        s -= 30
        notes.append("duas fontes decorativas: evitar")
    return dict(score=max(0, min(100, s)), notes=notes, adjust=adjust,
                display=display, body=body, x_display=xd, x_body=xb)


def load_pairs() -> list[dict]:
    return json.loads(PAIRS_JSON.read_text())["pairs"] if PAIRS_JSON.exists() else []


def suggest(mood: str | None = None, display: str | None = None, limit: int = 8) -> list[dict]:
    """Pares curados (filtrados por humor) + pares gerados automaticamente, ordenados pela pontuação."""
    mood = (mood or "").lower() or None
    out, seen = [], set()
    for p in load_pairs():
        if mood and mood not in p["moods"]:
            continue
        if display and p["display"] != display:
            continue
        r = score_pair(p["display"], p["body"])
        if r["score"] is None:
            continue
        out.append(dict(r, id=p["id"], moods=p["moods"], why=p.get("why", ""), curated=True))
        seen.add((p["display"], p["body"]))
    cat = catalog()
    if mood:
        disp = [c for c in cat.values() if c["role"] in ("display", "both") and (mood in c["moods"]) and (not display or c["name"] == display)]
        bodies = [c for c in cat.values() if c["role"] in ("body", "both") and c["cls"] not in LOUD]
        for d in disp:
            for b in bodies:
                if (d["name"], b["name"]) in seen or d["name"] == b["name"]:
                    continue
                r = score_pair(d["name"], b["name"])
                if r["score"] and r["score"] >= 80:
                    out.append(dict(r, id=f"auto-{d['slug']}+{b['slug']}", moods=[mood], why="gerado pelo pontuador", curated=False))
                    seen.add((d["name"], b["name"]))
    out.sort(key=lambda r: (-r["curated"], -r["score"]))
    return out[:limit]


def resolve_pair(spec: str) -> dict | None:
    """'id-do-par' ou 'Display+Body' -> dict(display, body, adjust)."""
    for p in load_pairs():
        if p["id"] == spec:
            r = score_pair(p["display"], p["body"])
            return dict(display=p["display"], body=p["body"], adjust=r.get("adjust"))
    if "+" in spec:
        d, b = [x.strip() for x in spec.split("+", 1)]
        r = score_pair(d, b)
        return dict(display=d, body=b, adjust=r.get("adjust"))
    return None
