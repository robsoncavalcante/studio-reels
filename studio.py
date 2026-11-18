#!/usr/bin/env python3
"""
STUDIO REELS — biblioteca local de modelos para Reels, Stories, Posts e Carrosséis.

  python studio.py doctor
  python studio.py list layouts|themes|carousels|reels|motions|bridges|transitions [--cat X] [-q texto]
  python studio.py render   --layout L --theme T [--format story|post|square|grid|all] [--content c.json] [--out f.png]
  python studio.py carousel --recipe R --theme T [--format post] [--content c.json] [--bridge ribbon|auto|none] [--out pasta]
  python studio.py reel     (--recipe R | --layout L) --theme T [--content c.json] [--motion M] [--transition T] [--bpm N] [--audio a.mp3] [--out f.mp4]
  python studio.py brand    --name "Cliente" --handle @cliente --accent "#ff3d00" ... (cria library/brands/<slug>.json)
  python studio.py fonts    install|list|pair|check|specimen   (kit open source + pareamento; --pair em render/carousel/reel)
  python studio.py gallery  [--workers 2]      (gera gallery/index.html com miniaturas de tudo)
  python studio.py catalog                      (gera catalog/catalog.json)
Sem --content, os modelos usam texto de exemplo (pré-visualização).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import ffsetup  # noqa: E402
ffsetup.prefer_ffmpeg_with_ass()
from engine import core  # noqa: E402
from engine import gate  # noqa: E402
from engine.core import REG, FORMATS, STATIC_FORMATS, Renderer  # noqa: E402

ROOT = core.ROOT


# ----------------------------------------------------------------------------- util
def load_json(p):
    if not p:
        return {}
    path = Path(p)
    return json.loads(path.read_text(encoding="utf-8"))


def load_brand(args, content):
    b = {}
    if getattr(args, "brand", None):
        bp = Path(args.brand)
        if not bp.exists():
            bp = ROOT / "library" / "brands" / f"{args.brand}.json"
        b = load_json(bp)
        b.setdefault("_dir", str(bp.parent))
    if isinstance(content, dict) and content.get("brand"):
        b = {**b, **content["brand"]}
    if getattr(args, "pair", None):
        b["font_pair"] = args.pair
    return b or None


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def pick_formats(arg):
    if arg == "all":
        return STATIC_FORMATS
    if arg not in FORMATS:
        raise SystemExit(f"Formato inválido: {arg}. Use {', '.join(FORMATS)} ou all")
    return [arg]


# ----------------------------------------------------------------------------- comandos
def cmd_doctor(a):
    ok = True
    print("• Python:", sys.version.split()[0])
    for mod in ("playwright", "jinja2", "markupsafe"):
        try:
            __import__(mod)
            print(f"• {mod}: ok")
        except ImportError:
            ok = False
            print(f"• {mod}: FALTA  → pip install -r requirements.txt")
    cp = core._chrome_path()
    print("• Chrome:", cp or "não achei Chrome/Chromium — rode: playwright install chromium")
    ff = shutil.which("ffmpeg")
    print("• ffmpeg:", ff or "FALTA (necessário só para reels/vídeo)")
    if ff:
        out = subprocess.run([ff, "-hide_banner", "-h", "filter=xfade"], capture_output=True, text=True).stdout
        print("• xfade (transições):", "ok" if "transition" in out else "versão do ffmpeg sem xfade — atualize (>=4.3)")
        ass_ok = ffsetup.has_filter("ass")
        print("• ass (legendas queimadas):", "ok" if ass_ok else "AUSENTE — rode: brew install ffmpeg-full (o ffmpeg padrão do Homebrew não tem legendas)")
    print(f"• Biblioteca: {len(REG.layouts)} layouts · {len(REG.themes)} temas · {len(REG.carousels)} receitas de carrossel · {len(REG.reels)} receitas de reel · {len(REG.motions)} movimentos")
    print("• Fontes embutidas:", len(json.loads((ROOT / 'fonts' / 'manifest.json').read_text())), "famílias open source")
    return 0 if ok else 1


def cmd_list(a):
    what = a.what
    q = (a.q or "").lower()
    cat = (a.cat or "").lower()

    def match(d):
        blob = json.dumps(d, ensure_ascii=False).lower()
        if q and q not in blob:
            return False
        cats = [c.lower() for c in (d.get("cats") or d.get("tags") or [])]
        return not cat or cat in cats or cat in blob

    if what == "layouts":
        for l in REG.layouts.values():
            if match(l):
                print(f"{l['id']:<22} fotos:{l['photos']:<2} [{l['kind']}]  {l['name']} — {l['desc']}")
    elif what == "themes":
        for t in REG.themes.values():
            if match(t):
                print(f"{t['id']:<20} {t['kind']:<5} {t['name']:<22} {', '.join(t['cats'])}")
    elif what == "carousels":
        for c in REG.carousels.values():
            if match(c):
                print(f"{c['id']:<16} {c['name']:<28} capa:{c['cover']} corpo:{'/'.join(c['body'])} fim:{c['end']}  ponte:{c['default_bridge']}")
    elif what == "reels":
        for r in REG.reels.values():
            if match(r):
                print(f"{r['id']:<16} {r['name']:<26} {len(r['scenes'])} cenas · motion:{r['motion']} · {r['desc']}")
    elif what == "motions":
        for m in REG.motions.values():
            if cat and cat != m.get("level", ""):
                continue
            if q and q not in json.dumps(m, ensure_ascii=False).lower():
                continue
            print(f"{m['id']:<14} {m.get('level', ''):<14} {m['dur']:.2f}s  {m['name']} — {m.get('desc', '')}")
    elif what == "bridges":
        for b in REG.bridges:
            print(f"{b['id']:<12} {b['name']} — {b['desc']}")
    elif what == "transitions":
        print(", ".join(core.TRANSITIONS))
    return 0


def cmd_render(a):
    content = load_json(a.content)
    base = Path(a.content).parent if a.content else Path.cwd()
    brand = load_brand(a, content)
    sample = not a.content or a.sample
    fmts = pick_formats(a.format)
    out = Path(a.out) if a.out else ROOT / "samples" / f"{a.layout}__{a.theme}.png"
    layouts = list(REG.layouts) if a.layout == "all" else [a.layout]
    themes = list(REG.themes) if a.theme == "all" else [a.theme]
    n = 0
    made = []
    with Renderer(a.scale) as r:
        for lay in layouts:
            for th in themes:
                for f in fmts:
                    if len(layouts) * len(themes) * len(fmts) == 1 and a.out:
                        o = out
                    else:
                        d = (Path(a.out) if a.out else ROOT / "samples") / f
                        d.mkdir(parents=True, exist_ok=True)
                        o = d / f"{lay}__{th}.png"
                    o.parent.mkdir(parents=True, exist_ok=True)
                    core.render_static(lay, th, f, content, o, brand=brand, base_dir=base, sample=sample, renderer=r)
                    n += 1
                    made.append((lay, th, f, o))
                    print("✓", o)
    if made and len(made) <= 6:
        pages = [dict(name=f"{lay} · {f}", fmt=f, content=content, theme=th,
                      html=core.page_html(core.slide_canvas(lay, th, f, content, brand, base_dir=base, sample=sample))) for lay, th, f, _ in made]
        gate.run("static", made[0][3] if len(made) == 1 else made[0][3].parent, pages, brand or {}, made[0][1], [m[3] for m in made])
    return 0


def cmd_carousel(a):
    content = load_json(a.content)
    base = Path(a.content).parent if a.content else Path.cwd()
    brand = load_brand(a, content)
    sample = not a.content or a.sample
    rec = REG.carousels[a.recipe]
    bridge = a.bridge
    if bridge == "auto":
        bridge = rec.get("default_bridge")
    out = Path(a.out) if a.out else ROOT / "samples" / f"carousel_{a.recipe}__{a.theme}"
    with Renderer(a.scale) as r:
        files = core.render_carousel(a.recipe, a.theme, a.format, content, out, brand=brand, base_dir=base, bridge=bridge,
                                     sample=sample, renderer=r, pager=not a.no_pager)
    for f in files:
        print("✓", f)
    cont = {**REG.carousels[a.recipe].get("sample", {}), **content} if sample else content
    plan = core.plan_carousel(a.recipe, cont)
    pages = [dict(name=f"slide {i + 1} · {p['layout']}", fmt=a.format, content=p["content"], theme=a.theme,
                  html=core.page_html(core.slide_canvas(p["layout"], a.theme, a.format, p["content"], brand, base_dir=base, sample=sample, pager=(i, len(plan)))))
             for i, p in enumerate(plan)]
    gate.run("carousel", out, pages, brand or {}, a.theme, [f for f in files if str(f).lower().endswith((".png", ".jpg", ".jpeg"))])
    return 0


def cmd_reel(a):
    content = load_json(a.content)
    base = Path(a.content).parent if a.content else Path.cwd()
    brand = load_brand(a, content)
    sample = not a.content or a.sample
    scenes = []
    if a.recipe:
        rec = REG.reels[a.recipe]
        cs = content.get("scenes") or []
        for i, s in enumerate(rec["scenes"]):
            c = dict(cs[i]) if i < len(cs) else {}
            if i == 0:
                for k in ("kicker", "title", "subtitle", "photos", "badge", "cta"):
                    if content.get(k) is not None and k not in c:
                        c[k] = content[k]
            d = c.pop("dur", s["dur"])
            scenes.append(dict(layout=c.pop("layout", s["layout"]), content=c, dur=d))
        motion = a.motion or rec["motion"]
        transition = a.transition or rec["transition"]
        name = a.recipe
    elif not a.layout and content.get("scenes") and all("layout" in x for x in content["scenes"]):
        # roteiro direto: scenes[{layout, dur?, ...conteúdo}] sem receita (aceita photos com clipes de vídeo)
        for x in content["scenes"]:
            c = dict(x); d = c.pop("dur", 3.0); th = c.pop("theme", None)
            scenes.append(dict(layout=c.pop("layout"), content=c, dur=d, **({"theme": th} if th else {})))
        motion, transition, name = a.motion or "fade-up", a.transition or "smooth", "roteiro"
    elif a.layout:
        scenes = [dict(layout=a.layout, content=content, dur=a.dur)]
        motion, transition, name = a.motion or "fade-up", a.transition or "fade", a.layout
    else:
        raise SystemExit("Use --recipe R ou --layout L")
    out = Path(a.out) if a.out else ROOT / "samples" / f"reel_{name}__{a.theme}{'_previa' if a.preview else ''}.mp4"
    print(f"Renderizando reel '{name}' · tema {a.theme} · movimento {motion} · transição {transition}")
    core.render_reel(scenes, a.theme, out, fmt=a.format, motion=motion, transition=transition, tdur=a.tdur, fps=a.fps,
                     bpm=a.bpm, audio=a.audio, brand=brand, base_dir=base, sample=sample,
                     pace=a.pace, speed=a.speed, stagger_scale=a.stagger_scale, intensity=a.intensity, ease=a.ease,
                     kenburns=a.kenburns, camera=getattr(a,"camera",None), blur=getattr(a, "blur", 1) or 1, count_up=a.count_up, sync=a.sync, music=a.music, sfx=a.sfx, key=a.key, music_vol=a.music_vol,
                     voice=a.voice, voice_vol=a.voice_vol, duck=a.duck, fit_voice=a.fit_voice,
                     human=a.human, parallax=a.parallax, highlight=a.highlight, captions=a.captions, stems=a.stems,
                     words_file=a.words, transcribe=a.transcribe, exit=a.exit, preview=a.preview,
                     cap_style=dict(accent=a.cap_cor, fg=a.cap_texto, pos_y=a.cap_pos, size_pct=a.cap_tamanho, upper=a.cap_maiusculas), vocab=a.vocab,
                     script=(Path(a.script[1:]).read_text(encoding='utf-8') if a.script and a.script.startswith('@') else a.script))
    print("✓", out)
    def _cont(sc):
        c = dict(sc.get("content", {}))
        if sample:
            c = {**(REG.layouts.get(sc["layout"], {}).get("sample") or {}), **c}
        return c
    pages = [dict(name=f"cena {i + 1} · {sc['layout']}", fmt="reel", content=_cont(sc), theme=sc.get("theme") or a.theme,
                  html=core.page_html(core.slide_canvas(sc["layout"], sc.get("theme") or a.theme, "reel", _cont(sc), brand, base_dir=base, sample=sample)))
             for i, sc in enumerate(scenes)]
    gate.run("reel", out, pages, brand or {}, a.theme, [out], timeline=str(Path(out).with_suffix(".timeline.json")))
    return 0


def cmd_brand(a):
    colors = {k: v for k, v in dict(bg=a.bg, bg2=a.bg2, fg=a.fg, accent=a.accent, accent2=a.accent2).items() if v}
    b = dict(name=a.name, handle=a.handle, logo=a.logo, colors=colors, font_display=a.font_display, font_body=a.font_body)
    b = {k: v for k, v in b.items() if v}
    d = ROOT / "library" / "brands"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{slug(a.name)}.json"
    p.write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
    print("✓ marca salva em", p, "→ use: --brand", slug(a.name), "--theme brand-dark|brand-light|brand-vivid")
    return 0


def cmd_agentes(a):
    """Valida o parecer dos especialistas. Só libera a entrega (entregar) quando tudo estiver aprovado."""
    res = gate.validate(a.saida)
    if res.get("gate"):
        g = res["gate"]
        print(f"Portão: {g['blockers']} bloqueio(s) · {g['warnings']} aviso(s) · nota {g['score']}/100 · especialistas exigidos: {len(g['roles'])}")
    if res["ok"]:
        print("✓ APROVADO pelos agentes — liberado para: python studio.py entregar", a.saida)
        return 0
    print("✗ PENDENTE:")
    for x in res["pend"]:
        print("  -", x)
    if res.get("dir"):
        print("Checklist:", res["dir"] / "CHECKLIST.md")
    return 2


def cmd_entregar(a):
    """Entrega final: copia a peça + parecer para a pasta de entrega, só se aprovada pelos agentes e inalterada."""
    src = Path(a.saida)
    if not gate.approved(src):
        print("✗ ENTREGA BLOQUEADA: peça sem aprovação dos agentes (ou alterada depois do parecer).")
        return cmd_agentes(a) or 2
    dst = Path(a.para or ROOT / "entregas" / slug(src.stem))
    dst.mkdir(parents=True, exist_ok=True)
    ad = gate.agentes_dir(src)
    g = json.loads((ad / "gate.json").read_text(encoding="utf-8"))
    for name in g["files"]:
        f = (src / name) if src.is_dir() else src.parent / name
        (dst / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst / name)
    shutil.copy2(ad / "parecer.json", dst / "parecer.json")
    print("✓ entregue em", dst)
    return 0


def _cta_bg(data, b):
    """Se o rodapé/CTA do próprio site tem fundo de cor forte (ex.: amarelo do Mercado Livre), o CTA do reel usa essa cor."""
    from engine import site as _s
    last = [x for x in data.get("sections", []) if x.get("bg")]
    for x in reversed(last[-2:]):
        if _s._saturated(x["bg"]):
            b["colors"]["cta_bg"] = x["bg"]
            return x["bg"]
    return None


def cmd_site(a):
    from engine import site, logo as _logo
    from urllib.parse import urlparse
    host = (urlparse(a.url if "://" in a.url else "https://" + a.url).hostname or "site").replace("www.", "")
    out = Path(a.out or ROOT / "samples" / f"site-{slug(host)}")
    print(f"Abrindo {a.url} … (rola a página, extrai textos, cores, fontes e tira as telas do celular)")
    try:
        res = site.capture(a.url, out, shots=a.telas)
    except RuntimeError as e:
        print(f"\n✗ {e}")
        sys.exit(3)
    data = res["data"]
    cat = json.loads((ROOT / "fonts" / "manifest.json").read_text())
    b = site.pick_brand(data, cat, res.get("font_files"))
    name = a.name or data.get("siteName") or (data.get("title") or host).split("|")[0].split(" - ")[0].strip() or host
    handle = a.handle or ""
    if handle and not handle.startswith("@"):
        handle = "@" + handle
    if not handle and not site.is_local(host.split(":")[0]):
        handle = ""  # nunca inventa @: sem --handle a assinatura mostra só o nome
    if a.brand:  # identidade já cadastrada (design system da marca): ela manda, o site só fornece textos e logo
        bp = Path(a.brand) if Path(a.brand).exists() else ROOT / "library" / "brands" / f"{a.brand}.json"
        brand = json.loads(bp.read_text(encoding="utf-8"))
        brand.setdefault("name", name)
        handle = handle or brand.get("handle", "")
        if not brand.get("logo") and res.get("logo"):
            brand["logo"] = str(out / res["logo"])
    else:
        brand = dict(name=name, handle=handle, colors=b["colors"], style=b.get("style", {}), font_display=b["font_display"], font_body=b["font_body"], source=res["url"])
        if b.get("font_files"):
            brand["font_files"] = b["font_files"]
        if res.get("logo"):
            brand["logo"] = res["logo"]
    cb = _cta_bg(data, b)
    if cb:
        brand.setdefault("colors", {})["cta_bg"] = cb
    theme = a.theme or ("brand-dark" if b["dark"] else "brand-light")
    alt = None
    if theme in REG.themes:
        for x, y in (("light", "dark"), ("dark", "light")):
            if theme.endswith(x) and theme[: -len(x)] + y in REG.themes:
                alt = theme[: -len(x)] + y
                break
    if a.brand and alt is None:
        alt = None
    tcol = (core.resolve_theme(theme, brand).get("bg") or b["colors"]["bg"])
    if res.get("logo"):
        try:
            _logo.avatar(out / res["logo"], out / "logo-avatar.png", tcol, ink=b["colors"]["fg"])
        except Exception as e:  # noqa
            print(f"  ! avatar da logo não gerado ({type(e).__name__})")
    (out / "brand.json").write_text(json.dumps(brand, ensure_ascii=False, indent=2), encoding="utf-8")
    scenes = site.build_scenes(data, res["shots"], res.get("logo"), res["url"], max_scenes=max(a.cenas, 9) if data.get("media") else a.cenas, handle_at=handle, alt_theme=alt, name=name, media=data.get("media"), cta_bg=cb)
    from engine import visual
    bkey = slug(a.brand or site._host(res["url"]) or host)
    pv = visual.choose(bkey, brand, data, data.get("media"), forced=getattr(a, "linguagem", None))
    scenes = visual.apply(scenes, pv["linguagem"], getattr(a, "variante", 0) or 0, name=name)
    if not a.brand:  # identidade cadastrada manda; sem ela, a pele da linguagem completa o que o site não definiu
        brand["style"] = visual.skin(brand, pv["linguagem"])
    pv.update(variante=getattr(a, "variante", 0) or 0, layouts=[x["layout"] for x in scenes], marca=bkey)
    pv["repeticao"] = visual.repetition(pv["layouts"], bkey, pv["linguagem"])
    (out / "partido.json").write_text(json.dumps(pv, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "partido.md").write_text(visual.partido_md(pv), encoding="utf-8")
    visual.record(bkey, pv["linguagem"], pv["variante"], pv["layouts"])
    (out / "brand.json").write_text(json.dumps(brand, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "content.json").write_text(json.dumps(dict(scenes=scenes), ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "site.json").write_text(json.dumps(dict(url=res["url"], title=data.get("title"), h1=data.get("h1"), brand=b, sections=data["sections"], buttons=data["buttons"], description=data.get("description"), warnings=res.get("warnings", []), media=[{k: v for k, v in m.items() if k in ("kind", "file", "head", "top", "w", "h")} for m in data.get("media", [])]),
                                              ensure_ascii=False, indent=1), encoding="utf-8")
    sb = ["# Storyboard da captura (a fonte da verdade do reel)", "", f"Site: {res['url']}", "", "## Telas capturadas (celular)"]
    sb += [f"- `{n}`" for n in res["shots"]]
    sb += ["", "## Cenas do reel ↔ origem no site", "| # | layout | título | mídia real usada |", "|---|---|---|---|"]
    for i, sc in enumerate(scenes, 1):
        sb.append(f"| {i} | {sc['layout']} | {str(sc.get('title', '')).replace('|', '/')[:70]} | {', '.join([x if isinstance(x, str) else x.get('src', '') for x in (sc.get('photos') or [])] or [i.get('icon') for i in sc.get('items', []) if isinstance(i, dict) and i.get('icon')]) or '—'} |")
    sb += ["", "## Avisos da captura"] + ([f"- {w}" for w in res.get("warnings", [])] or ["- nenhum"])
    sb += ["", "Regra dos agentes: cada cena precisa corresponder a uma tela/seção acima; cor, fonte e mídia vêm do site. Se não, refazer."]
    (out / "storyboard.md").write_text("\n".join(sb), encoding="utf-8")
    c = b["colors"]
    print(f"\n✓ marca «{name}»  fundo {c['bg']} · título {c['fg']} · acento {c['accent']} · acento 2 {c['accent2']}  (tema {theme}{' + ' + alt if alt else ''})")
    print(f"  fontes do site: título {b['fonts_site']['display'] or '—'} · texto {b['fonts_site']['body'] or '—'}  →  usadas: {b['font_display']} / {b['font_body']}")
    if a.brand:
        print(f"  identidade: biblioteca «{a.brand}» (cores/fontes do design system, não as extraídas)")
    for k, v in b["fonts_substituted"].items():
        print(f"  ! «{k}» não está no catálogo: usei {v} (instale a fonte da marca para trocar)")
    if site.glued(data.get("description") or ""):
        print("  ! a descrição (meta description) do site tem palavras coladas; usei o subtítulo do hero. Vale corrigir no WordPress/SEO.")
    for w in res.get("warnings", []):
        print(f"  ⚠ {w}")
    print(f"  logo: {res.get('logo') or 'não achei'} · {len(scenes)} cenas: " + " → ".join(x["layout"] for x in scenes))
    if not handle:
        print("  ! sem @ do Instagram: passe --handle @usuario para assinar o final")
    print(f"  pasta: {out}")
    if a.salvar_marca and not a.brand:
        d = ROOT / "library" / "brands"
        d.mkdir(parents=True, exist_ok=True)
        assets = d / "assets"
        assets.mkdir(exist_ok=True)
        bb = dict(brand)
        if res.get("logo"):
            import shutil as _sh
            _sh.copy(out / res["logo"], assets / f"{slug(name)}-logo.png")
            bb["logo"] = f"library/brands/assets/{slug(name)}-logo.png"
        (d / f"{slug(name)}.json").write_text(json.dumps(bb, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  marca salva: --brand {slug(name)}")
    cmd = [sys.executable, str(ROOT / "studio.py"), "reel", "--content", str(out / "content.json"), "--brand", str(out / "brand.json"),
           "--theme", theme, "--format", "reel", "--out", str(out / "reel.mp4")]
    cmd += ["--preview"] if a.rascunho else []
    cl = site.pick_clima(b, data.get("media"), res["url"])
    if visual.LINGUAGENS[pv["linguagem"]]["transition"] and not a.clima:
        cl["transition"] = visual.LINGUAGENS[pv["linguagem"]]["transition"]
    print(f"  partido visual: {visual.LINGUAGENS[pv['linguagem']]['nome']} (variante {pv['variante']}) — {'; '.join(pv['motivos'][:2])}")
    for w in pv["repeticao"]:
        print(f"  ⚠ repetição: {w}")
    if a.clima:
        cl = {**cl, **dict(zip(("music", "transition", "pace", "sfx"), site.CLIMAS[a.clima])), "clima": a.clima}
    print(f"  clima (Diretor de Movimento): {cl['clima']} · trilha {a.music or cl['music']} em {cl['key']} · transições {cl['transition']} · ritmo {cl['pace']}")
    cmd += ["--music", a.music or cl["music"], "--key", cl["key"], "--sfx", cl["sfx"], "--transition", cl["transition"], "--pace", cl["pace"],
            "--kenburns", "drift", "--count-up"]
    if a.render:
        r = subprocess.run(cmd)
        print(("✓ reel: " + str(out / "reel.mp4")) if r.returncode == 0 else "✗ o render falhou (veja acima)")
        return r.returncode
    print("  próximo passo: " + " ".join(cmd[1:]).replace(sys.executable, "python"))
    return 0


# ----------------------------------------------------------------------------- catálogo + galeria
def build_catalog():
    L, T = REG.layouts, REG.themes
    static = len(L) * len(T)
    cat = dict(
        stats=dict(
            layouts=len(L), themes=len(T), fonts=len(json.loads((ROOT / "fonts" / "manifest.json").read_text())),
            decor=len({d for t in T.values() for d in t.get("decor", [])}),
            formats=len(STATIC_FORMATS), motions=len(REG.motions), transitions=len(core.TRANSITIONS),
            carousel_recipes=len(REG.carousels), reel_recipes=len(REG.reels), bridges=len(REG.bridges),
            static_designs=static * len(STATIC_FORMATS),
            single_layout_reels=static * len(REG.motions),
            reel_recipe_combos=len(REG.reels) * len(T) * len(REG.motions),
            carousel_sets=len(REG.carousels) * len(T),
            carousel_variants=len(REG.carousels) * len(T) * (len(REG.bridges) + 1) * 2,
        ),
        layouts=list(L.values()), themes=list(T.values()), carousels=list(REG.carousels.values()),
        reels=list(REG.reels.values()), motions=list(REG.motions.values()), bridges=REG.bridges, transitions=core.TRANSITIONS,
    )
    out = ROOT / "catalog" / "catalog.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
    return cat


def cmd_catalog(a):
    cat = build_catalog()
    for k, v in cat["stats"].items():
        print(f"{k:>24}: {v:,}".replace(",", "."))
    return 0


def _thumb_job(job):
    kind, lay, th, path, scale = job
    global _R
    try:
        _R
    except NameError:
        _R = Renderer(scale).__enter__()
    try:
        if Path(path).exists():
            return path
        if kind == "static":
            html = core.page_html(core.slide_canvas(lay, th, "story", {}, None, sample=True))
            _R.shoot(html, path, 1080, 1920, kind="jpeg", quality=72)
        else:
            rec = REG.carousels[lay]
            plan = core.plan_carousel(lay, {**rec.get("sample", {})})
            p = plan[0]
            html = core.page_html(core.slide_canvas(p["layout"], th, "post", p["content"], None, sample=True, pager=(0, len(plan))))
            _R.shoot(html, path, 1080, 1350, kind="jpeg", quality=72)
    except Exception as e:  # noqa
        return f"ERRO {lay}/{th}: {e}"
    return path


def cmd_gallery(a):
    from concurrent.futures import ProcessPoolExecutor
    cat = build_catalog()
    tdir = ROOT / "gallery" / "thumbs"
    tdir.mkdir(parents=True, exist_ok=True)
    scale = 300 / 1080
    jobs = []
    for l in REG.layouts:
        for t in REG.themes:
            jobs.append(("static", l, t, str(tdir / f"s__{l}__{t}.jpg"), scale))
    for c in REG.carousels:
        for t in REG.themes:
            jobs.append(("carousel", c, t, str(tdir / f"c__{c}__{t}.jpg"), scale))
    if a.limit:
        jobs = jobs[: a.limit]
    todo = [j for j in jobs if not Path(j[3]).exists()]
    print(f"{len(jobs)} miniaturas · {len(jobs) - len(todo)} já prontas · {len(todo)} a gerar com {a.workers} processo(s)")
    errs = 0
    if todo:
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            for i, res in enumerate(ex.map(_thumb_job, todo, chunksize=8), 1):
                if str(res).startswith("ERRO"):
                    errs += 1
                    print(res)
                if i % 100 == 0:
                    print(f"  {i}/{len(todo)}")
    write_gallery_html(cat)
    print(f"✓ gallery/index.html ({errs} erros)")
    return 0


def write_gallery_html(cat):
    data = dict(
        layouts=[dict(id=l["id"], name=l["name"], kind=l["kind"], photos=l["photos"]) for l in cat["layouts"]],
        themes=[dict(id=t["id"], name=t["name"], kind=t["kind"], cats=t["cats"]) for t in cat["themes"]],
        carousels=[dict(id=c["id"], name=c["name"], bridge=c["default_bridge"]) for c in cat["carousels"]],
        stats=cat["stats"],
    )
    tpl = (ROOT / "engine" / "gallery.html").read_text(encoding="utf-8")
    (ROOT / "gallery" / "index.html").write_text(tpl.replace("/*__DATA__*/", "const DATA=" + json.dumps(data, ensure_ascii=False) + ";"), encoding="utf-8")


def cmd_fonts(a):
    from engine import fonts
    act = a.action
    if not a.spec and a.names and act in ("check", "specimen"):
        a.spec = " ".join(a.names)
    if act == "install":
        names = list(fonts.F) if a.all else [fonts.slugify(n) for n in a.names]
        if not names:
            raise SystemExit("Informe nomes (ex.: 'Outfit' 'Lora') ou --all")
        r = fonts.install(names)
        print(f"✓ instaladas: {len(r['ok'])}", ("· não encontradas: " + ", ".join(r["fail"])) if r["fail"] else "")
        print("  (qualquer fonte do Google Fonts/Fontsource funciona: o slug é o nome em minúsculas com hífen)")
        return 0
    if act == "sync":
        c = fonts.rebuild()
        print("✓ catálogo reconstruído:", len(c), "famílias")
        return 0
    cat = fonts.catalog()
    if act == "list":
        q = (a.q or "").lower()
        n = 0
        for c in sorted(cat.values(), key=lambda c: (c["cls"], c["name"])):
            if a.cls and c["cls"] != a.cls:
                continue
            if a.mood and a.mood not in c["moods"]:
                continue
            if q and q not in c["name"].lower():
                continue
            m = c["metrics"]
            print(f"{c['name']:<24} {c['cls']:<14} {c['role']:<8} x={m.get('x')}  pesos={','.join(map(str, c['weights']))}  {' '.join(c['moods'])}")
            n += 1
        print(f"— {n} fontes")
        return 0
    if act == "pair":
        res = fonts.suggest(a.mood, a.display, a.limit)
        if not res:
            print("Nenhum par. Humores: elegante luxo editorial moderno minimalista impacto promocao esportivo tech retro neon handmade casamento saude corporativo imobiliario jornal urbano")
        for r in res:
            adj = f"  ajuste={r['adjust']}" if r["adjust"] else ""
            print(f"[{r['score']:>3}] {r['id']:<22} {r['display']} + {r['body']}{adj}\n      {r['why']}")
        return 0
    if act == "check":
        if "+" not in a.spec:
            raise SystemExit("Use: fonts check 'Display+Corpo'")
        d, b = [x.strip() for x in a.spec.split("+", 1)]
        r = fonts.score_pair(d, b)
        print(f"{d} + {b}: nota {r['score']}/100")
        for n in r["notes"]:
            print("  •", n)
        if r.get("adjust"):
            print(f"  → ajuste óptico do corpo: font-size-adjust {r['adjust']}")
        return 0
    if act == "specimen":
        pr = fonts.resolve_pair(a.spec)
        if not pr:
            raise SystemExit("Par inválido")
        out = Path(a.out) if a.out else ROOT / "samples" / f"fonts__{slug(a.spec)}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        content = {"kicker": pr["body"], "title": f"{pr['display']} *Aa*", "subtitle": "Título em destaque e texto corrido legível",
                   "body": "Pack de 3 serviços para quem quer vender mais com design consistente, ritmo e clareza."}
        with Renderer(1.0) as r:
            core.render_static("typographic", a.theme, "post", content, out, brand={"font_pair": a.spec}, base_dir=Path.cwd(), sample=True, renderer=r)
        print("✓", out)
        return 0
    return 1


def cmd_autocut(a):
    from engine import autocut
    if not Path(a.video).expanduser().exists():
        raise SystemExit(f"Arquivo não encontrado: {a.video}\nDica: arraste o vídeo para o Terminal para colar o caminho certo, ou rode: find ~ -name \"{Path(a.video).name}\" -not -path \"*/Library/*\"")
    out = a.out or str(Path(a.video).with_suffix("")) + "_autocut.mp4"
    words = None
    if a.words:
        from engine import captions
        words = captions.from_file(a.words)
    elif a.transcribe:
        from engine import captions
        words = captions.transcribe(a.video, a.lang, a.model, vocab=a.vocab)
    k = autocut.run(a.video, out, a.ritmo, a.jcut, words, camera=a.camera, zoom=a.zoom, push=a.push / 100, fast=a.rapido, min_len=a.min_trecho)
    print(f"✓ {out}  ({len(k)} trechos mantidos)")
    if words:
        from engine import captions
        nw = autocut.remap_words(words, k)
        base = Path(out).with_suffix("")
        (Path(str(base) + ".palavras.json")).write_text(json.dumps(nw, ensure_ascii=False, indent=1), encoding="utf-8")
        W, H = autocut.size(out)
        assp, fdir = captions.build_ass(nw, Path(str(base) + ".ass"), style=a.captions or "karaoke", W=W, H=H, font_slug=a.fonte,
                                        accent=a.cor, fg=a.texto, upper=a.maiusculas,
                                        pos_y=a.posicao if a.posicao is not None else (.64 if H > W else .84), size=int(min(W, H) * a.tamanho / 100))
        print(f"✓ legenda (SRT): {assp.with_suffix('.srt')}")
        if a.captions:
            outc = Path(str(base) + "_legendado.mp4")
            autocut.burn(out, assp, fdir, outc, fast=a.rapido)
            print(f"✓ com legenda: {outc}")
    elif a.captions:
        print("! --captions precisa de --words ou --transcribe")
    return 0


def cmd_motion(a):
    from engine import motion
    if a.action == "easings":
        for k, v in motion.easings().items():
            print(f"{k:<14} {v['kind']:<8} {v['dur'][0]:.1f}–{v['dur'][1]:.1f}s  {v['desc']}")
        return 0
    if a.action == "pace":
        for k, v in motion.PACE.items():
            print(f"{k:<9} velocidade×{v['speed']}  stagger×{v['stagger']}  intensidade×{v['k']}  transição {v['tdur']}s — {v['desc']}")
        return 0
    if a.action == "build":
        print("✓", motion.build_css())
        return 0
    if a.action == "preview":
        # tira de 6 quadros de um movimento: mostra a curva no tempo
        from PIL import Image
        mid = a.name
        if mid not in REG.motions:
            raise SystemExit("Movimento inexistente: studio.py list motions")
        out = Path(a.out) if a.out else ROOT / "samples" / f"motion__{mid}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        content = {"kicker": "MOTION", "title": "Título *em movimento*", "subtitle": "Prévia da curva", "cta": "Saiba mais"}
        import io
        frames = []
        Wd, Hd = core.FORMATS["reel"]["w"], core.FORMATS["reel"]["h"]
        with Renderer(0.4) as r:
            html = core.page_html(core.slide_canvas("announcement", a.theme, "reel", content, None, base_dir=Path.cwd(), sample=True,
                                                    reel=dict(motion=mid, scene_dur=3.0, ease=a.ease, pace=a.pace, speed=a.speed)), reel=True)
            pg = r.load(html, Wd, Hd)
            for t in (0.1, 0.3, 0.5, 0.7, 0.95, 1.8):
                pg.evaluate("t=>{__seek(t);return new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))}", t * 1000.0)
                frames.append(Image.open(io.BytesIO(pg.screenshot(type="png", clip={"x": 0, "y": 0, "width": Wd, "height": Hd}))).convert("RGB"))
        w, h = frames[0].size
        sheet = Image.new("RGB", (w * len(frames) + 8 * (len(frames) - 1), h), "white")
        for i, f in enumerate(frames):
            sheet.paste(f, (i * (w + 8), 0))
        sheet.save(out)
        print("✓", out)
        return 0
    return 1


def cmd_audio(a):
    from engine import voice
    try:
        return _cmd_audio(a)
    except voice.ProviderError as e:
        print(f"✗ {e}")
        return 1


def _cmd_audio(a):
    from engine import audio, voice
    if a.action in ("tts", "music", "sfxgen", "fetch", "import") and not a.text:
        a.text = a.name  # o 1º argumento posicional é o texto/prompt/busca/arquivo
    if a.action == "clean":
        src = a.text or a.name
        out = a.out if getattr(a, "out", None) else str(Path(src).with_suffix("")) + "_limpo.wav"
        print(audio.clean_voice(src, out), "->", out)
        return 0
    if a.action == "levels":
        print(audio.levels(a.text or a.name))
        return 0
    if a.action == "styles":
        for k, v in audio.STYLES.items():
            print(f"{k:<10} {v['bpm']:>3} bpm  {v['desc']}  [{v['mood']}]")
        print("SFX:", ", ".join(audio.SFX_KINDS))
        return 0
    if a.action == "sources":
        for s_ in audio.sources():
            print(f"• {s_['nome']}  [{s_['licenca']}]  crédito: {s_['atribuicao']}  comercial: {s_['uso_comercial']}\n    {s_['url']}  {s_['obs']}")
        return 0
    if a.action == "providers":
        for p_ in voice.status():
            print(f"{'✓' if p_['ok'] else '·'} {p_['id']:<11} {p_['kind']:<14} {p_['note']}")
        return 0
    if a.action == "brief":
        import json as _j
        d = _j.loads((ROOT / "library" / "audio_prompts.json").read_text(encoding="utf-8"))
        st = a.name if a.name in d["music"] else "corporate"
        print(f"== Trilha ({st}) — cole no Magnific (audio_music_generate: google-lyria-3-pro p/ 30-180s) ou ElevenLabs Music:\n{d['music'][st]}\n")
        print("== SFX — audio_sfx_generate (1-2 s cada):")
        for k, v in d["sfx"].items():
            print(f"  {k:<8} {v}")
        print("\n== Vozes pt-BR (Magnific audio_tts, ids do catálogo):")
        for v in d["voices_pt_br"]:
            print(f"  {v['id']:>5}  {v['name']:<22} {v['perfil']}")
        print("\n" + d["workflow"])
        return 0
    if a.action == "tts":
        out = Path(a.out) if a.out else ROOT / "samples" / "voz.wav"
        text = Path(a.text[1:]).read_text(encoding="utf-8") if a.text.startswith("@") else a.text
        f, p_ = voice.tts(text, out, provider=a.provider, voice=a.voice, speed=a.speed)
        print(f"✓ {f}  ({voice.duration(f):.1f}s · provedor {p_})")
        return 0
    if a.action == "music":
        out = Path(a.out) if a.out else ROOT / "samples" / "trilha.wav"
        f, p_ = voice.gen_music(a.text, out, a.dur, a.provider)
        print(f"✓ {f}  (provedor {p_})")
        return 0
    if a.action == "sfxgen":
        out = Path(a.out) if a.out else ROOT / "samples" / "sfx.wav"
        f, p_ = voice.gen_sfx(a.text, out, min(a.dur, 10), a.provider)
        print(f"✓ {f}  (provedor {p_})")
        return 0
    if a.action == "fetch":
        out = Path(a.out) if a.out else ROOT / "samples" / "fetch.mp3"
        f, meta = voice.fetch(a.kind, a.text, out, provider=a.provider)
        print(f"✓ {f}\n  {meta.get('title')} — {meta.get('author')} · {meta.get('license')} · {meta.get('url')}")
        if meta.get("warn"):
            print("  !", meta["warn"])
        return 0
    if a.action == "import":
        f = voice.import_file(a.text, a.kind, a.out, name=a.as_name)
        print(f"✓ {f}  ({voice.duration(f):.1f}s)")
        return 0
    if a.action == "mix":
        if not a.video:
            raise SystemExit("Use --video arquivo.mp4 (o áudio dele será substituído)")
        out = Path(a.out) if a.out else Path(a.video).with_name(Path(a.video).stem + "_audio.mp4")
        audio.remix_video(a.video, out, music_file=a.music_file, voice_file=a.voice_file, style=a.style, bpm=a.bpm,
                          music_vol=a.music_vol, voice_vol=a.voice_vol, duck=a.duck)
        print("✓", out)
        return 0
    out = Path(a.out) if a.out else ROOT / "samples" / f"audio_{a.name}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    if a.action == "gen":
        audio.write_wav(out, audio.music(a.name, a.dur, a.bpm, a.key))
    elif a.action == "sfx":
        audio.write_wav(out, audio.sfx(a.name))
    print("✓", out)
    return 0


def cmd_stock(a):
    from engine import stock
    last = stock.STOCK_DIR / ".last.json"
    if a.action == "providers":
        for k, v in stock.PROVIDERS.items():
            print(f"{k:<10} chave:{v['key'] or 'não precisa':<20} {v['license']} · crédito: {v['attribution']}\n    {v['rules']}")
        return 0
    if a.action == "search":
        if not a.query:
            raise SystemExit("Use: stock search 'consultório moderno' --provider pexels --orientation portrait")
        res = stock.search(a.query, a.provider, a.orientation, a.color, a.limit)
        stock.STOCK_DIR.mkdir(parents=True, exist_ok=True)
        last.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        for i, r in enumerate(res):
            print(f"[{i}] {r['w']}x{r['h']}  {r['license']}  {r['author']}  {r['source_url']}")
        print(f"— {len(res)} resultados (só licenças seguras para uso comercial). Baixe com: stock get N")
        return 0
    if a.action == "get":
        res = json.loads(last.read_text())
        idx = [int(x) for x in a.query.split(",")]
        for i in idx:
            p = stock.download(res[i], Path(a.out) if a.out else None)
            print("✓", p, "|", res[i]["credit"])
        return 0
    if a.action == "credits":
        files = a.query.split(",") if a.query else []
        for c in stock.credits_for(files):
            print(c)
        return 0
    return 1


def cmd_color(a):
    from engine import color
    if a.action == "contrast":
        c = color.contrast(a.a, a.b)
        print(f"{a.a} × {a.b}: {c:.2f}:1  corpo(4.5) {'✓' if c >= 4.5 else '✗'}  texto grande(3) {'✓' if c >= 3 else '✗'}")
        return 0
    if a.action == "harmony":
        for sch in ([a.scheme] if a.scheme else color.SCHEMES):
            print(f"{sch:<14}", " ".join(color.harmony(a.a, sch)))
        return 0
    if a.action == "from-image":
        pal = color.palette_from_image(a.a, 6)
        for p in pal:
            print(f"{p['hex']}  {p['share'] * 100:>4.0f}%  sat {p['sat']}  luz {p['light']}")
        th = color.theme_from_palette(pal)
        print("→ tema sugerido:", json.dumps(th))
        for m in color.report(th):
            print("  •", m)
        if a.name:
            colors = {k: th[k] for k in ("bg", "bg2", "fg", "accent", "accent2")}
            d = ROOT / "library" / "brands"
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"{slug(a.name)}.json"
            old = json.loads(p.read_text()) if p.exists() else {}
            p.write_text(json.dumps({**old, "name": a.name, "colors": colors}, ensure_ascii=False, indent=2), encoding="utf-8")
            print("✓ cores gravadas na marca:", p)
        return 0
    return 1


def _spec_brand(spec):
    b = dict(spec.get("brand") or {})
    if spec.get("brand_file"):
        bp = Path(spec["brand_file"])
        if not bp.exists():
            bp = ROOT / "library" / "brands" / f"{spec['brand_file']}.json"
        b = {**load_json(bp), **b}
    if spec.get("pair"):
        b["font_pair"] = spec["pair"]
    return b or None


def qa_spec(spec, outdir: Path, base: Path):
    """Roda o QA de uma especificação (static | carousel | reel já renderizado) e devolve lista de relatórios."""
    from engine import qa
    kind = spec.get("kind", "static")
    fmt = spec.get("format", "post")
    brand = _spec_brand(spec)
    theme = spec["theme"]
    reps = []
    outdir.mkdir(parents=True, exist_ok=True)
    with Renderer(1.0) as r:
        if kind == "static":
            html = core.page_html(core.slide_canvas(spec["layout"], theme, fmt, spec.get("content", {}), brand, base_dir=base, sample=bool(spec.get("sample"))))
            reps.append(qa.check_static(html, fmt, r, spec["layout"], annotate=outdir / f"qa_{spec['layout']}.png"))
        elif kind == "carousel":
            content = spec.get("content", {})
            if spec.get("sample"):
                content = {**REG.carousels[spec["recipe"]].get("sample", {}), **content}
            plan = core.plan_carousel(spec["recipe"], content)
            for i, p in enumerate(plan):
                html = core.page_html(core.slide_canvas(p["layout"], theme, fmt, p["content"], brand, base_dir=base, sample=bool(spec.get("sample")),
                                                        pager=(i, len(plan))))
                reps.append(qa.check_static(html, fmt, r, f"slide {i + 1} · {p['layout']}", annotate=outdir / f"qa_slide{i + 1:02d}.png"))
            if len(plan) > 10:
                reps.append(dict(name="carrossel", score=0, blockers=1, warnings=0, issues=[dict(level="blocker", code="slides", msg=f"{len(plan)} slides: limite do Instagram é 10", fix="reduzir", box=None, text=None)]))
        elif kind == "reel":
            for sc in spec.get("scenes", []):
                html = core.page_html(core.slide_canvas(sc["layout"], theme, "reel", sc.get("content", {}), brand, base_dir=base, sample=bool(spec.get("sample"))))
                reps.append(qa.check_static(html, "reel", r, f"cena · {sc['layout']}", annotate=outdir / f"qa_cena_{sc['layout']}.png"))
    return reps


def cmd_qa(a):
    from engine import qa
    reps = []
    if a.action == "review":
        from engine import review
        if not a.target or not a.video:
            raise SystemExit("uso: studio.py qa review reel.timeline.json --video reel.mp4 [--out pasta]")
        tl = json.loads(Path(a.target).read_text(encoding="utf-8"))
        out = Path(a.out or Path(a.video).parent / "revisao")
        sh = review.sheets(a.video, tl, out)
        rep = qa.check_reel(a.target, a.video)
        print(qa.format_report(rep))
        p_ = review.write_review(rep, out, sh)
        print(f"\nRevisão: {p_}\nFolhas: " + ", ".join(Path(v).name for v in sh.values()))
        return 2 if rep["blockers"] else 0
    if a.action == "reel":
        reps.append(qa.check_reel(a.target, a.video))
    else:
        spec = {"kind": a.action, "format": a.format, "theme": a.theme, "layout": a.layout, "recipe": a.recipe, "pair": a.pair,
                "content": load_json(a.content), "sample": (not a.content) or a.sample, "brand_file": a.brand}
        if a.action == "static" and not a.layout:
            raise SystemExit("--layout é obrigatório")
        base = Path(a.content).parent if a.content else Path.cwd()
        reps = qa_spec(spec, Path(a.out or ROOT / "samples" / "qa"), base)
    worst = 0
    for rep in reps:
        print(qa.format_report(rep))
        worst = max(worst, rep["blockers"])
    return 2 if worst else 0


def _gate_spec(kind, spec, out, brand, theme, fmt, content, base, sample):
    if kind == "static":
        pages = [dict(name=spec["layout"], fmt=fmt, content=content, theme=theme,
                      html=core.page_html(core.slide_canvas(spec["layout"], theme, fmt, content, brand, base_dir=base, sample=sample)))]
        gate.run("static", out, pages, brand or {}, theme, [out / "peca.png"])
    elif kind == "carousel":
        cont = {**REG.carousels[spec["recipe"]].get("sample", {}), **content} if sample else content
        plan = core.plan_carousel(spec["recipe"], cont)
        pages = [dict(name=f"slide {i + 1} · {p['layout']}", fmt=fmt, content=p["content"], theme=theme,
                      html=core.page_html(core.slide_canvas(p["layout"], theme, fmt, p["content"], brand, base_dir=base, sample=sample, pager=(i, len(plan)))))
                 for i, p in enumerate(plan)]
        gate.run("carousel", out, pages, brand or {}, theme, sorted((out / "slides").glob("*.png")))
    elif kind == "reel":
        pages = [dict(name=f"cena {i + 1} · {sc['layout']}", fmt="reel", content=sc.get("content", {}), theme=theme,
                      html=core.page_html(core.slide_canvas(sc["layout"], theme, "reel", sc.get("content", {}), brand, base_dir=base, sample=sample)))
                 for i, sc in enumerate(spec["scenes"])]
        gate.run("reel", out, pages, brand or {}, theme, [out / "reel.mp4"], timeline=str(out / "reel.timeline.json"))


COUNCIL_ROLES = ["project-planner", "brand-strategist", "social-media", "copywriter", "art-director", "graphic-designer", "color-specialist", "typographer",
                 "composition", "image-curator", "motion-designer", "sound-designer", "video-editor", "accessibility", "creative-director"]


def cmd_council(a):
    """Mesa de especialistas: init (cria a pasta de trabalho) · build (renderiza + QA, versionado) · status."""
    d = Path(a.dir)
    if a.action == "init":
        d.mkdir(parents=True, exist_ok=True)
        (d / "brief.json").write_text(json.dumps({
            "cliente": a.name or "", "objetivo": a.brief or "", "publico": "", "tom": "", "canal": "instagram",
            "tipo": a.kind, "formato": "story" if a.kind == "reel" else "post", "cta": "", "restricoes": [], "referencias": [],
            "marca": {"cores": {}, "fontes": {}, "logo": ""}, "prazo": ""}, ensure_ascii=False, indent=1), encoding="utf-8")
        spec0 = {"kind": a.kind if a.kind != "story" else "static", "format": "story" if a.kind in ("reel", "story") else "post",
                 "theme": "clean-white", "pair": "", "layout": "full-bleed-bottom", "recipe": "dicas", "content": {}, "brand_file": ""}
        (d / "spec.json").write_text(json.dumps(spec0, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "thread.md").write_text(f"# Mesa de criação — {a.name or d.name}\n\nRegistro das conversas entre especialistas (cada rodada abre com `## Rodada N`).\n", encoding="utf-8")
        (d / "scorecard.json").write_text(json.dumps({"rodada": 0, "notas": {k: None for k in (
            "estrategia_e_gancho", "copy", "hierarquia_e_composicao", "cor_e_contraste", "tipografia", "consistencia_de_marca", "motion_e_ritmo",
            "som", "acessibilidade_e_legibilidade", "acabamento")}, "qa_automatico": None, "veredito": "pendente", "retrabalho": []}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"✓ mesa criada em {d}\n  1) preencha brief.json  2) siga agents/PROTOCOL.md  3) python studio.py council build {d}")
        return 0
    spec = load_json(d / "spec.json")
    if a.action == "build":
        from engine import qa
        ver = 1 + len([p for p in d.glob("v*") if p.is_dir()])
        out = d / f"v{ver}"
        out.mkdir()
        base = d
        brand = _spec_brand(spec)
        kind, fmt, theme = spec.get("kind", "static"), spec.get("format", "post"), spec["theme"]
        content = spec.get("content", {})
        sample = bool(spec.get("sample"))
        with Renderer(1.0) as r:
            if kind == "static":
                core.render_static(spec["layout"], theme, fmt, content, out / "peca.png", brand=brand, base_dir=base, sample=sample, renderer=r)
            elif kind == "carousel":
                rec = REG.carousels[spec["recipe"]]
                core.render_carousel(spec["recipe"], theme, fmt, content, out / "slides", brand=brand, base_dir=base, bridge=spec.get("bridge", rec.get("default_bridge")),
                                     sample=sample, renderer=r, pager=True)
            elif kind == "reel":
                m = spec.get("motion", {})
                aud = spec.get("audio", {})
                scenes = [dict(layout=s["layout"], content=s.get("content", {}), dur=s.get("dur", 3.0)) for s in spec["scenes"]]
                core.render_reel(scenes, theme, out / "reel.mp4", fmt="reel", motion=m.get("preset", "fade-up"), transition=m.get("transition", "smooth"),
                                 tdur=m.get("tdur"), bpm=aud.get("bpm"), audio=aud.get("file"), brand=brand, base_dir=base, sample=sample, renderer=r,
                                 pace=m.get("pace"), speed=m.get("speed"), stagger_scale=m.get("stagger_scale"), intensity=m.get("intensity"),
                                 ease=m.get("ease"), kenburns=m.get("kenburns"), count_up=m.get("count_up", False), sync=m.get("sync", False),
                                 music=aud.get("music"), sfx=aud.get("sfx"), key=aud.get("key", "A"), music_vol=aud.get("vol", .75),
                                 voice=aud.get("voice"), voice_vol=aud.get("voice_vol", 1.0), duck=aud.get("duck", .6))
        reps = qa_spec(spec, out, base)
        if kind == "reel":
            reps.append(qa.check_reel(str(out / "reel.timeline.json"), str(out / "reel.mp4")))
        (out / "qa.json").write_text(json.dumps(reps, ensure_ascii=False, indent=1), encoding="utf-8")
        _gate_spec(kind, spec, out, brand, theme, fmt, content, base, sample)
        blockers = sum(r_["blockers"] for r_ in reps)
        warns = sum(r_["warnings"] for r_ in reps)
        score = round(sum(r_["score"] for r_ in reps) / max(1, len(reps)))
        for r_ in reps:
            print(qa.format_report(r_))
        print(f"\n=== v{ver}: QA médio {score}/100 · {blockers} bloqueio(s) · {warns} aviso(s) → {out}")
        print("APROVADO pelo QA automático (falta o parecer do Diretor de Criação)" if not blockers else "REPROVADO: corrigir bloqueios e rodar build de novo")
        return 2 if blockers else 0
    if a.action == "status":
        for v in sorted(d.glob("v*")):
            q = v / "qa.json"
            if q.exists():
                reps = json.loads(q.read_text())
                print(v.name, "QA", round(sum(x["score"] for x in reps) / max(1, len(reps))), "· bloqueios", sum(x["blockers"] for x in reps))
        print("scorecard:", (d / "scorecard.json").read_text()[:400])
        return 0
    return 1


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(prog="studio", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    p = sub.add_parser("list")
    p.add_argument("what", choices=["layouts", "themes", "carousels", "reels", "motions", "bridges", "transitions"])
    p.add_argument("--cat")
    p.add_argument("-q")
    p.set_defaults(fn=cmd_list)

    def common(p):
        p.add_argument("--theme", required=True, help="id do tema (ou 'all' no render)")
        p.add_argument("--content", help="JSON com textos/fotos")
        p.add_argument("--brand", help="arquivo .json ou nome em library/brands")
        p.add_argument("--pair", help="par de fontes: id (studio.py fonts pair) ou 'Display+Corpo'")
        p.add_argument("--sample", action="store_true", help="completa campos faltantes com texto de exemplo")
        p.add_argument("--out")
        p.add_argument("--scale", type=float, default=1.0)

    p = sub.add_parser("render")
    p.add_argument("--layout", required=True, help="id do layout (ou 'all')")
    p.add_argument("--format", default="story")
    common(p)
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("carousel")
    p.add_argument("--recipe", required=True)
    p.add_argument("--format", default="post", choices=["post", "square", "grid", "story"])
    p.add_argument("--bridge", default="auto", help="auto | none | ribbon | wave-line | big-circle | photo-strip | arrow-path | dots-path")
    p.add_argument("--no-pager", action="store_true")
    common(p)
    p.set_defaults(fn=cmd_carousel)

    p = sub.add_parser("reel")
    p.add_argument("--recipe")
    p.add_argument("--layout")
    p.add_argument("--format", default="reel", choices=["reel", "post", "square"])
    p.add_argument("--motion")
    p.add_argument("--transition", help="nome do xfade, lista separada por vírgula, ou 'smooth'")
    p.add_argument("--tdur", type=float, default=None, help="duração da transição (padrão: do --pace)")
    p.add_argument("--pace", choices=["calm", "standard", "snappy", "hype"], help="ritmo geral (velocidade, stagger, intensidade)")
    p.add_argument("--speed", type=float, help="multiplicador de velocidade (1 = normal; 2 = dobro)")
    p.add_argument("--stagger-scale", type=float, dest="stagger_scale", help="multiplica o intervalo entre elementos")
    p.add_argument("--intensity", type=float, help="distância/força do movimento (1 = normal)")
    p.add_argument("--ease", help="easing (studio.py motion easings) ou cubic-bezier(...)")
    p.add_argument("--kenburns", choices=["none", "zoom-in", "zoom-out", "pan-left", "pan-right", "pan-up", "pan-down", "drift"])
    p.add_argument("--count-up", action="store_true", dest="count_up", help="números contam de 0 até o valor")
    p.add_argument("--camera", choices=["none", "push", "orbit", "drift", "dolly"], help="câmera 3D por cena (padrão: por layout nas cenas do site; 'none' desliga)")
    p.add_argument("--blur", type=int, default=1, help="motion blur real: subquadros por quadro (1 = desligado, 3 = recomendado; renderiza mais devagar)")
    p.add_argument("--sync", action="store_true", help="alinha movimento e transição ao --bpm")
    p.add_argument("--music", choices=["lofi", "house", "pop", "corporate", "cinematic", "hype", "ambient"], help="trilha original gerada localmente")
    p.add_argument("--sfx", choices=["light", "full"], help="efeitos sonoros: whoosh nas transições (+ pops e brilho no full)")
    p.add_argument("--key", default="A", help="tonalidade da trilha gerada (C, D#, A…)")
    p.add_argument("--music-vol", type=float, default=0.75, dest="music_vol")
    p.add_argument("--voice", help="locução (wav/mp3) a mixar com ducking da trilha; gere com `studio.py audio tts`")
    p.add_argument("--voice-vol", type=float, default=1.0, dest="voice_vol")
    p.add_argument("--fit-voice", action="store_true", dest="fit_voice", help="ajusta a duração das cenas à duração da locução (peso = palavras da cena ou campo content.say)")
    p.add_argument("--duck", type=float, default=0.6, help="quanto a trilha abaixa enquanto a voz fala (0..1)")
    p.add_argument("--human", action="store_true", help="motion humanizado: tempos irregulares, câmera de mão, SFX com variação")
    p.add_argument("--parallax", action="store_true", help="profundidade: fundo, foto e texto em velocidades diferentes")
    p.add_argument("--highlight", choices=["box", "marker", "underline"], help="anima o *destaque* do título como caixa, marca-texto ou sublinhado")
    p.add_argument("--captions", help="legendas por palavra: estilo (karaoke|pop|box|clean|curta) usando o texto da locução; veja `studio.py captions`")
    p.add_argument("--cap-cor", help="cor da palavra falada na legenda (padrão: cor de destaque do tema), ex.: #FFD400")
    p.add_argument("--cap-texto", default="#FFFFFF", help="cor do texto da legenda")
    p.add_argument("--cap-pos", type=float, default=.64, help="altura da legenda de 0 (topo) a 1 (base)")
    p.add_argument("--cap-tamanho", type=float, help="tamanho da letra em %% da largura (padrão 7.8)")
    p.add_argument("--cap-maiusculas", action="store_true", help="legenda em MAIÚSCULAS")
    p.add_argument("--vocab", help='nomes/termos para o Whisper acertar com --transcribe, ex.: "Construvale, Petra"')
    p.add_argument("--script", help="texto da locução para as legendas (ou @roteiro.txt)")
    p.add_argument("--words", help="palavras com tempo reais (SRT ou JSON) para as legendas, em vez de estimar pelo roteiro")
    p.add_argument("--exit", choices=["pop", "fade", "slide", "drop", "blur"], help="saída em cascata dos elementos antes da transição (consistente em todas as cenas)")
    p.add_argument("--preview", action="store_true", help="prévia rápida: 40%% da resolução e até 15 fps, para aprovar antes do render final")
    p.add_argument("--transcribe", action="store_true", help="transcreve a voz com faster-whisper (exige internet no 1º uso)")
    p.add_argument("--stems", help="pasta para exportar cenas, trilha, voz, SFX, legendas (.srt/.ass) e EDL para o Premiere/After Effects")
    p.add_argument("--dur", type=float, default=5.0, help="duração (modo --layout)")
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--bpm", type=float)
    p.add_argument("--audio")
    common(p)
    p.set_defaults(fn=cmd_reel)

    p = sub.add_parser("brand")
    p.add_argument("--name", required=True)
    p.add_argument("--handle")
    p.add_argument("--logo")
    for k in ("bg", "bg2", "fg", "accent", "accent2", "font-display", "font-body"):
        p.add_argument("--" + k)
    p.set_defaults(fn=cmd_brand)

    p = sub.add_parser("fonts", help="kit de fontes open source + pareamento")
    p.add_argument("action", choices=["install", "sync", "list", "pair", "check", "specimen"])
    p.add_argument("names", nargs="*")
    p.add_argument("--all", action="store_true")
    p.add_argument("--cls")
    p.add_argument("--mood")
    p.add_argument("--display")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("-q")
    p.add_argument("--spec", help="'Display+Corpo' ou id do par")
    p.add_argument("--theme", default="clean-white")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_fonts)

    p = sub.add_parser("motion", help="easings, ritmos e prévia de movimentos")
    p.add_argument("action", choices=["easings", "pace", "build", "preview"])
    p.add_argument("name", nargs="?")
    p.add_argument("--theme", default="neon-night")
    p.add_argument("--ease")
    p.add_argument("--pace")
    p.add_argument("--speed", type=float)
    p.add_argument("--out")
    p.set_defaults(fn=cmd_motion)

    p = sub.add_parser("autocut", help="corta silêncios de vídeo falado (ritmo suave|ritmo|dinamico, J-cut opcional)")
    p.add_argument("video"); p.add_argument("-o", "--out", default=None)
    p.add_argument("--ritmo", choices=["suave", "ritmo", "dinamico"], default="ritmo")
    p.add_argument("--jcut", type=float, default=0.0, help="segundos que o áudio antecipa a imagem")
    p.add_argument("--words", help="palavras com tempo (SRT/JSON) para cortar vícios de fala e repetições")
    p.add_argument("--transcribe", action="store_true", help="transcreve com faster-whisper (exige internet no 1º uso)")
    p.add_argument("--lang", default="pt"); p.add_argument("--model", default="small")
    p.add_argument("--cor", default="#FB2C36", help="cor do destaque (palavra falada), ex.: #FFD400")
    p.add_argument("--texto", default="#FFFFFF", help="cor do texto, ex.: #FFFFFF")
    p.add_argument("--posicao", type=float, help="altura da legenda de 0 (topo) a 1 (base); padrão 0.64 no vertical")
    p.add_argument("--tamanho", type=float, default=7.8, help="tamanho da letra em %% da largura (padrão 7.8)")
    p.add_argument("--fonte", default="space-grotesk", help="fonte da biblioteca (ver `studio.py fonts`), ex.: inter, poppins")
    p.add_argument("--maiusculas", action="store_true", help="legenda em MAIÚSCULAS")
    p.add_argument("--vocab", help='nomes/termos para o Whisper acertar, ex.: "Construvale, Petra Condomínios"')
    p.add_argument("--captions", choices=["karaoke", "pop", "box", "clean", "curta"], help="queima legendas por palavra no vídeo cortado (precisa de --words ou --transcribe); curta = até 3 palavras, 1 linha")
    p.add_argument("--min-trecho", type=float, default=0.0, help="descarta trechos mantidos mais curtos que N segundos (ex.: 0.5 tira fiapos de palavra solta)")
    p.add_argument("--camera", action="store_true", help="câmera virtual: alterna plano aberto/fechado a cada corte e aproxima devagar (disfarça o jump cut)")
    p.add_argument("--zoom", type=float, default=1.25, help="escala do plano fechado com --camera (padrão 1.25)")
    p.add_argument("--push", type=float, default=4.0, help="aproximação lenta dentro de cada trecho, em %% (padrão 4)")
    p.add_argument("--rapido", action="store_true", help="rascunho: usa o codificador de hardware (VideoToolbox no Mac) se disponível; o final sai em libx264")
    p.set_defaults(fn=cmd_autocut)

    p = sub.add_parser("audio", help="trilhas, voz (TTS), SFX, bancos livres, importação e remix de vídeo")
    p.add_argument("action", choices=["styles", "gen", "sfx", "sources", "providers", "brief", "tts", "music", "sfxgen", "fetch", "import", "mix", "clean", "levels"])
    p.add_argument("name", nargs="?", default="pop", help="estilo (gen/sfx/brief) ou nome do arquivo (import)")
    p.add_argument("text", nargs="?", default="", help="texto da locução (ou @arquivo.txt), prompt da trilha/SFX, busca (fetch) ou arquivo (import)")
    p.add_argument("--dur", type=float, default=20)
    p.add_argument("--bpm", type=float)
    p.add_argument("--key", default="A")
    p.add_argument("--provider", default="auto", help="auto|kokoro|edge|elevenlabs|freesound|jamendo|openverse")
    p.add_argument("--voice", help="id da voz (kokoro: pf_dora|pm_alex|pm_santa; edge: pt-BR-FranciscaNeural; elevenlabs: voice_id)")
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--kind", default="music", help="music|voice|sfx (fetch/import)")
    p.add_argument("--as", dest="as_name", help="import: nome do arquivo na biblioteca")
    p.add_argument("--video", help="mix: vídeo cujo áudio será refeito")
    p.add_argument("--music-file", dest="music_file")
    p.add_argument("--voice-file", dest="voice_file")
    p.add_argument("--style", help="mix: trilha local (lofi|house|pop|corporate|cinematic|hype|ambient) se não houver arquivo")
    p.add_argument("--music-vol", type=float, default=0.75, dest="music_vol")
    p.add_argument("--voice-vol", type=float, default=1.0, dest="voice_vol")
    p.add_argument("--duck", type=float, default=0.6)
    p.add_argument("--out")
    p.set_defaults(fn=cmd_audio)

    p = sub.add_parser("stock", help="bancos de imagem gratuitos (sem IA) + comprovante de licença")
    p.add_argument("action", choices=["providers", "search", "get", "credits"])
    p.add_argument("query", nargs="?")
    p.add_argument("--provider", default="pexels", choices=["pexels", "unsplash", "pixabay", "openverse", "wikimedia"])
    p.add_argument("--orientation", default="portrait", choices=["portrait", "landscape", "square"])
    p.add_argument("--color")
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--out")
    p.set_defaults(fn=cmd_stock)

    p = sub.add_parser("color", help="estudo de cor: contraste, harmonias, paleta de foto")
    p.add_argument("action", choices=["contrast", "harmony", "from-image"])
    p.add_argument("a")
    p.add_argument("b", nargs="?")
    p.add_argument("--scheme")
    p.add_argument("--name", help="(from-image) grava as cores na marca <name>")
    p.set_defaults(fn=cmd_color)

    p = sub.add_parser("qa", help="verificação automática de qualidade (contraste, cortes, zonas seguras, hierarquia, reels)")
    p.add_argument("action", choices=["static", "carousel", "reel", "review"])
    p.add_argument("target", nargs="?", help="(reel|review) caminho do .timeline.json")
    p.add_argument("--video")
    p.add_argument("--layout")
    p.add_argument("--recipe")
    p.add_argument("--theme", default="clean-white")
    p.add_argument("--format", default="post")
    p.add_argument("--content")
    p.add_argument("--brand")
    p.add_argument("--pair")
    p.add_argument("--sample", action="store_true")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_qa)

    p = sub.add_parser("site", help="site → marca (cores, fontes, logo) + telas do celular + reel pronto")
    p.add_argument("url")
    p.add_argument("--name", help="nome da marca (padrão: nome do site)")
    p.add_argument("--out", help="pasta de saída (padrão samples/site-<domínio>)")
    p.add_argument("--telas", type=int, default=6, help="quantas telas do celular capturar")
    p.add_argument("--cenas", type=int, default=7, help="máximo de cenas do reel")
    p.add_argument("--linguagem", choices=["cards3d", "poster", "editorial", "modular"], help="força a linguagem visual (padrão: o motor escolhe pelo site; a marca repete a mesma)")
    p.add_argument("--variante", type=int, default=0, help="peça diferente da mesma marca: troca os layouts dentro da linguagem (0, 1, 2…)")
    p.add_argument("--clima", choices=["clean", "energetic", "punch", "cinematic", "editorial"], help="força o clima (trilha/transições/ritmo); padrão: decidido pela marca e pelo material")
    p.add_argument("--theme", help="brand-dark|brand-light|brand-vivid (padrão: pelo fundo do site) ou o tema do design system da marca")
    p.add_argument("--brand", help="usa a identidade cadastrada em library/brands (ex.: criative) em vez das cores extraídas")
    p.add_argument("--handle", help="@ do Instagram da marca para a assinatura final")
    p.add_argument("--salvar-marca", action="store_true", help="grava a marca em library/brands para usar com --brand")
    p.add_argument("--render", action="store_true", help="já renderiza o reel.mp4")
    p.add_argument("--rascunho", action="store_true", help="(com --render) render rápido de prévia")
    p.add_argument("--music", help="(com --render) estilo de trilha: lofi|house|pop|corporate|cinematic|hype|ambient")
    p.set_defaults(fn=cmd_site)

    p = sub.add_parser("agentes", help="valida o parecer dos especialistas de uma peça (portão obrigatório)")
    p.add_argument("saida", help="arquivo (png/mp4) ou pasta gerada")
    p.set_defaults(fn=cmd_agentes)
    p = sub.add_parser("entregar", help="entrega final: só libera peça aprovada pelos agentes")
    p.add_argument("saida")
    p.add_argument("--para")
    p.set_defaults(fn=cmd_entregar)

    p = sub.add_parser("council", help="mesa de especialistas + diretor de criação (pasta de trabalho, build versionado, QA)")
    p.add_argument("action", choices=["init", "build", "status"])
    p.add_argument("dir")
    p.add_argument("--name")
    p.add_argument("--brief")
    p.add_argument("--kind", default="carousel", choices=["static", "story", "carousel", "reel"])
    p.set_defaults(fn=cmd_council)

    p = sub.add_parser("gallery")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--limit", type=int)
    p.set_defaults(fn=cmd_gallery)
    sub.add_parser("catalog").set_defaults(fn=cmd_catalog)

    args = ap.parse_args()
    if hasattr(args, "font_display"):
        pass
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
