"""
Portão dos agentes — nenhuma peça sai do Studio Reels sem passar por aqui.

Todo comando que produz arquivo (render, carousel, reel, site, council build) chama `run()` ao terminar. O portão:
  1. confere a peça contra a marca (logo visível, cores e fontes da marca, texto cortado, texto declarado × texto que aparece,
     prints de site usados como foto, texto duplicado/truncado) — medido no HTML renderizado, não adivinhado;
  2. gera as folhas que os agentes precisam LER (peças, cenas, celular 360 px) e o CHECKLIST.md por especialista;
  3. grava gate.json com a impressão digital (sha256) dos arquivos.
A entrega (`studio.py entregar`) só libera com `parecer.json` completo: todos os especialistas exigidos, cada um com o que viu,
sem P0 aberto, decisão do Diretor = aprovar, e a mesma impressão digital da peça. Mudou o arquivo depois do parecer → volta a pendente.

Os agentes são papéis executados por Claude: o código mede e bloqueia; o julgamento visual é registrado no parecer.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import time
from pathlib import Path

import numpy as np
from PIL import Image

from . import core, qa

ROLES_BASE = ["creative-director", "art-director", "brand-strategist", "typographer", "color-specialist", "composition", "accessibility", "copywriter"]
ROLES_EXTRA = {"static": ["social-media"], "carousel": ["social-media"], "reel": ["social-media", "motion-designer", "sound-designer", "video-editor"]}

QUESTIONS = {
    "creative-director": "A peça cumpre o brief e parece feita para ESTA marca (não um template)? Storyboard × resultado: cada cena mostra o que o título diz?",
    "art-director": "Linguagem visual do design system respeitada (layouts, cartões, rótulos, grades)? A imagem de cada cena tem a ver com o texto dela?",
    "brand-strategist": "Tom, promessa e vocabulário são da marca? Algum dado do site/briefing foi inventado, cortado ou sem sentido?",
    "typographer": "Fontes e pesos da marca, caixa alta/baixa do design system, nenhuma linha cortada, nenhuma palavra quebrada, tamanhos legíveis no celular (folha 360 px).",
    "color-specialist": "Só cores da paleta? Título na cor de título (tinta), texto de apoio na cor de apoio, acento usado com parcimônia, contraste ok.",
    "composition": "Hierarquia clara, respiro, nada colado na borda, nada cortado, zonas seguras do Instagram, cartões sem áreas vazias.",
    "accessibility": "Contraste ≥ 4.5:1 (3:1 grande), fonte ≥ 32 px em 1080, tempo de leitura suficiente (reel), legenda quando há fala.",
    "copywriter": "Texto sem reticências de corte, sem repetição entre título e subtítulo, sem palavras coladas, 1 ideia por cena, CTA claro.",
    "social-media": "Gancho nos primeiros 2 s (reel) ou na capa (carrossel), formato certo, texto cabe na interface do Instagram.",
    "motion-designer": "Movimento com causa (entra/sai de um jeito coerente), saída mais curta que entrada, sem trecho parado >3 s, transições não aleatórias.",
    "sound-designer": "Há trilha e efeitos? Volume (~-14 LUFS), sem corte seco, efeitos nas transições certas.",
    "video-editor": "Ritmo e duração por cena, primeiro e último quadro, nada preto, tempo de leitura por cena.",
}

PHOTO_BAD = re.compile(r"(^|/)(tela|print|screenshot|screen|site-desktop|captura)[-_.\d]", re.I)

BRAND_JS = r"""
() => {
  const cv = document.querySelector('.canvas'); const cr = cv.getBoundingClientRect();
  const logos = Array.from(cv.querySelectorAll('.brandbar img')).map((i, k) => { i.setAttribute('data-gate-logo', k); const r = i.getBoundingClientRect();
    return {k, l: r.left - cr.left, t: r.top - cr.top, w: r.width, h: r.height, src: i.currentSrc || i.src}; });
  const imgs = Array.from(cv.querySelectorAll('img')).filter(i => !i.closest('.brandbar')).map(i => i.currentSrc || i.src);
  return {logos, imgs};
}
"""


# ------------------------------------------------------------------ utilidades
def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _norm(s: str) -> str:
    s = re.sub(r"\*", "", s or "")
    return re.sub(r"[^\w]+", " ", s.lower(), flags=re.U).strip()


def _declared(content: dict) -> list[str]:
    """Textos que o roteiro promete mostrar na cena."""
    out = []
    for k in ("kicker", "title", "subtitle", "body", "label", "quote", "cta", "number"):
        v = content.get(k)
        if isinstance(v, str) and v.strip():
            out.append(v)
    for it in content.get("items") or []:
        if isinstance(it, dict):
            out += [x for x in (it.get("title"), it.get("text")) if isinstance(x, str) and x.strip()]
        elif isinstance(it, str):
            out.append(it)
    return out


def _palette(brand: dict, theme: dict) -> list[np.ndarray]:
    cols = []
    for src in (brand.get("colors") or {}, theme):
        for k in ("bg", "bg2", "fg", "muted", "accent", "accent2", "surface", "line"):
            v = src.get(k)
            if isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v):
                cols.append(np.array([int(v[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float32))
    cols += [np.array([255, 255, 255], np.float32), np.array([0, 0, 0], np.float32)]
    return cols


def _issue(level, code, msg, fix=None, text=None, box=None):
    return dict(level=level, code=code, msg=msg, fix=fix, text=text, box=box)


# ------------------------------------------------------------------ checagens de marca por página
def brand_check(renderer, html: str, fmt: str, brand: dict, theme_id: str, content: dict | None = None) -> list[dict]:
    F = core.FORMATS[fmt]
    W, H = F["w"], F["h"]
    th = core.resolve_theme(theme_id, brand)
    issues: list[dict] = []
    pg = renderer.load(html, W, H)
    info = pg.evaluate(BRAND_JS)
    data = pg.evaluate(qa.INSPECT_JS)
    # ---- logo precisa ser visível
    for lg in info["logos"]:
        if lg["w"] < 4 or lg["h"] < 4:
            issues.append(_issue("blocker", "logo-invisivel", "logo com tamanho zero", "corrigir o caminho/tamanho da logo da marca"))
            continue
        clip = {"x": max(0, lg["l"]), "y": max(0, lg["t"]), "width": min(lg["w"], W), "height": min(lg["h"], H)}
        a = np.asarray(Image.open(io.BytesIO(pg.screenshot(type="png", clip=clip))).convert("RGB")).astype(np.int16)
        pg.evaluate(f"document.querySelector('[data-gate-logo=\"{lg['k']}\"]').style.visibility='hidden'")
        b = np.asarray(Image.open(io.BytesIO(pg.screenshot(type="png", clip=clip))).convert("RGB")).astype(np.int16)
        pg.evaluate(f"document.querySelector('[data-gate-logo=\"{lg['k']}\"]').style.visibility='visible'")
        changed = float((np.abs(a - b).max(axis=-1) > 28).mean())
        cov = 0.0
        try:
            from urllib.parse import unquote
            p = unquote(lg["src"].replace("file://", ""))
            im = Image.open(p).convert("RGBA")
            cov = float((np.asarray(im)[..., 3] > 128).mean())
        except Exception:
            cov = 0.2
        if cov > 0.02 and changed < cov * 0.45:
            issues.append(_issue("blocker", "logo-invisivel", f"a logo não aparece no fundo ({changed:.0%} visível de {cov:.0%} esperado): nome branco sobre fundo claro?",
                                 "usar a versão da logo para este fundo (studio.py logo) ou o símbolo sozinho"))
    # ---- print de site usado como foto
    for src in info["imgs"]:
        if PHOTO_BAD.search(src or ""):
            issues.append(_issue("blocker", "print-como-foto", f"print de site usado como foto ({Path(src).name}): mostra texto de terceiros cortado e repete o conteúdo",
                                 "usar foto real da marca ou layout de texto; nunca print de tela"))
    # ---- paleta e fontes
    pal = _palette(brand, th)
    allowed_fonts = {f.lower() for f in (brand.get("font_display"), brand.get("font_body"), th.get("font_display"), th.get("font_body"), "geist mono", "inter") if f}
    bad_col, bad_font = set(), set()
    for it in data["items"]:
        c = qa._rgba(it["fill"]) or qa._rgba(it["color"])
        if c and c[3] > .95 and it["opacity"] > .95:
            d = min(float(np.linalg.norm(np.array(c[:3]) - p)) for p in pal)
            if d > 80 and not re.search(r"pager|brand|handle", it["cls"] or ""):
                bad_col.add("#%02X%02X%02X" % tuple(int(v) for v in c[:3]))
        fam = (it["family"] or "").lower()
        if fam and fam not in allowed_fonts and not re.search(r"pager|brand|handle", it["cls"] or ""):
            bad_font.add(it["family"])
    if bad_col:
        issues.append(_issue("warn", "cor-fora-da-paleta", f"cor(es) de texto fora da paleta da marca: {', '.join(sorted(bad_col))}", "usar só as cores do design system"))
    if bad_font:
        issues.append(_issue("blocker", "fonte-fora-da-marca", f"fonte(s) fora da marca: {', '.join(sorted(bad_font))} (marca: {brand.get('font_display')}/{brand.get('font_body')})",
                             "usar a fonte de título e a de texto da marca"))
    # ---- texto: reticências de corte, repetição, palavras coladas, declarado × aparece
    texts = [it["text"] for it in data["items"]]
    joined = _norm(" ".join(it["text"] for it in data["items"]))
    full = _norm(pg.evaluate("document.querySelector('.canvas').innerText"))
    for t in texts:
        if t.rstrip().endswith("…") or t.rstrip().endswith("..."):
            issues.append(_issue("warn", "texto-truncado", f"texto terminando em reticências (parece cortado): «{t[:60]}»", "escrever a frase completa e curta, não cortar", text=t))
        for w in re.findall(r"[A-Za-zÀ-ÿ]{17,}", t):
            if not w.islower() or w.isupper():
                issues.append(_issue("warn", "palavras-coladas", f"palavra suspeita (espaços perdidos?): «{w}»", "revisar o texto de origem", text=t))
    norm_texts = [_norm(t) for t in texts if len(_norm(t)) > 3]
    dup = {x for x in norm_texts if norm_texts.count(x) > 1}
    for d in dup:
        issues.append(_issue("blocker", "texto-duplicado", f"o mesmo texto aparece duas vezes na cena: «{d[:50]}»", "tirar um dos dois ou trocar o subtítulo"))
    for decl in _declared(content or {}):
        n = _norm(decl)
        if len(n) > 3 and n not in full and n[:min(len(n), 24)] not in full:
            issues.append(_issue("warn", "texto-nao-apareceu", f"texto do roteiro não apareceu na peça: «{decl[:50]}»", "o layout não comporta esse texto: usar outro layout ou encurtar", text=decl))
    return issues


# ------------------------------------------------------------------ folhas de contato
def _sheet_images(files: list[Path], out: Path, cols=4, w=360, label=True) -> Path:
    from PIL import ImageDraw
    ims = []
    for f in files[:16]:
        im = Image.open(f).convert("RGB")
        r = w / im.width
        ims.append((f.name, im.resize((w, int(im.height * r)), Image.LANCZOS)))
    if not ims:
        return out
    h = max(i.height for _, i in ims)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (w + 8) + 8, rows * (h + 30) + 8), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    for k, (name, im) in enumerate(ims):
        x, y = 8 + (k % cols) * (w + 8), 8 + (k // cols) * (h + 30)
        d.text((x, y + 2), f"{k + 1} · {name}"[:52], fill=(190, 190, 200))
        sheet.paste(im, (x, y + 18))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


# ------------------------------------------------------------------ execução
def _key(output, f) -> str:
    output, f = Path(output), Path(f)
    try:
        if output.is_dir():
            return str(f.relative_to(output))
    except ValueError:
        pass
    return f.name


def agentes_dir(output: Path) -> Path:
    output = Path(output)
    return output / "agentes" if output.is_dir() else output.with_name(output.stem + ".agentes")


def enabled() -> bool:
    return os.environ.get("STUDIO_PORTAO", "on").lower() not in ("off", "0", "no")


def run(kind: str, output, pages: list[dict], brand: dict, theme: str, files: list, timeline: str | None = None, extra: dict | None = None, verbose=True) -> dict | None:
    """kind: static|carousel|reel. pages: [{name, html, fmt, content}] (o que foi renderizado). files: arquivos de saída (png/mp4)."""
    if not enabled():
        return None
    output = Path(output)
    ad = agentes_dir(output)
    ad.mkdir(parents=True, exist_ok=True)
    brand = brand or {}
    reps, brand_issues = [], []
    with core.Renderer(1.0) as r:
        for p in pages:
            rep = qa.check_static(p["html"], p["fmt"], r, p["name"])
            bi = brand_check(r, p["html"], p["fmt"], brand, theme, p.get("content"))
            for i in bi:
                i["page"] = p["name"]
            rep["issues"] += bi
            rep["blockers"] = sum(i["level"] == "blocker" for i in rep["issues"])
            rep["warnings"] = sum(i["level"] == "warn" for i in rep["issues"])
            rep["score"] = max(0, 100 - 18 * rep["blockers"] - 5 * rep["warnings"])
            reps.append(rep)
            brand_issues += bi
    sheets = {}
    fl = [Path(f) for f in files]
    if kind == "reel" and timeline and Path(timeline).exists() and fl:
        from . import review
        tl = json.loads(Path(timeline).read_text(encoding="utf-8"))
        sheets = {k: str(v) for k, v in review.sheets(str(fl[0]), tl, ad).items()}
        try:
            rv = qa.check_reel(timeline, str(fl[0]))
            rv["name"] = "reel"
            reps.append(rv)
        except Exception as e:  # noqa
            reps.append(dict(name="reel", score=0, blockers=0, warnings=1, issues=[_issue("warn", "qa-reel", f"QA do reel falhou: {e}")]))
    else:
        imgs = [f for f in fl if f.suffix.lower() in (".png", ".jpg", ".jpeg")]
        if imgs:
            sheets["pecas"] = str(_sheet_images(imgs, ad / "sheet_pecas.png", cols=4 if len(imgs) > 1 else 1, w=360 if len(imgs) > 1 else 540))
    if kind == "reel":
        fi = site_fidelity(Path(output) if Path(output).is_dir() else Path(output).parent, pages, ad)
        if fi["issues"]:
            reps.append(dict(name="fidelidade-ao-site", score=max(0, 100 - 25 * sum(i["level"] == "blocker" for i in fi["issues"])),
                             blockers=sum(i["level"] == "blocker" for i in fi["issues"]), warnings=sum(i["level"] == "warn" for i in fi["issues"]), issues=fi["issues"]))
        sheets.update(fi["sheets"])
    blockers = sum(x["blockers"] for x in reps)
    warns = sum(x["warnings"] for x in reps)
    roles = ROLES_BASE + ROLES_EXTRA.get(kind, [])
    gate = dict(kind=kind, theme=theme, when=time.strftime("%Y-%m-%d %H:%M:%S"), blockers=blockers, warnings=warns,
                score=round(sum(x["score"] for x in reps) / max(1, len(reps))), roles=roles,
                files={_key(output, f): sha256(f) for f in fl if Path(f).exists()}, sheets={k: Path(v).name for k, v in sheets.items()},
                brand=dict(name=brand.get("name"), logo=brand.get("logo"), colors=brand.get("colors"), fonts=[brand.get("font_display"), brand.get("font_body")]),
                reports=reps, extra=extra or {})
    (ad / "gate.json").write_text(json.dumps(gate, ensure_ascii=False, indent=1), encoding="utf-8")
    (ad / "CHECKLIST.md").write_text(_checklist(gate, pages), encoding="utf-8")
    tpl = ad / "parecer.modelo.json"
    tpl.write_text(json.dumps(dict(rodada=1, roles={r_: dict(veredito="", visto=[], notas=[]) for r_ in roles}, diretor=dict(nota=None, decisao="")), ensure_ascii=False, indent=1), encoding="utf-8")
    if verbose:
        print(banner(gate, ad, output))
    return gate


def site_fidelity(folder: Path, pages: list[dict], ad: Path) -> dict:
    """Reel feito a partir de um site (existe site.json ao lado): confere se o vídeo segue o que foi capturado.
    Bloqueia captura vazia/erro, ausência de mídia real e reel que ignorou as telas; gera a folha das telas para os agentes compararem."""
    res = dict(issues=[], sheets={})
    sj = Path(folder) / "site.json"
    if not sj.exists():
        return res
    try:
        d = json.loads(sj.read_text(encoding="utf-8"))
    except Exception:  # noqa
        return res
    iss = res["issues"]
    if not (d.get("h1") or d.get("title")):
        iss.append(_issue("blocker", "captura-sem-titulo", "a captura não trouxe título nem h1 (página de erro ou bloqueio)", "refazer `studio.py site` (outra rede/Chrome) antes de produzir"))
    for w in d.get("warnings", []):
        lvl = "warn" if "desktop bloqueado" in w else "blocker"
        if "nenhuma foto" in w:
            lvl = "blocker"
        iss.append(_issue(lvl, "captura-aviso", w, "cores, fontes e mídia precisam vir do site real; refazer a captura ou fornecer a mídia" if lvl == "blocker" else "conferir cores/fontes: vieram da versão celular"))
    used = [str(p_ if isinstance(p_, str) else p_.get('src', '')) for pg_ in pages for p_ in ((pg_.get("content") or {}).get("photos") or [])]
    icons = [i for pg_ in pages for i in ((pg_.get("content") or {}).get("items") or []) if isinstance(i, dict) and i.get("icon")]
    if d.get("media") and not used and not icons:
        iss.append(_issue("blocker", "reel-ignorou-midia", f"o site tem {len(d['media'])} mídia(s) colhida(s) e nenhuma entrou no reel", "usar foto/vídeo/ícones do site nas cenas (layouts site-cover/video/showcase/icons)"))
    lays = [(pg_.get("content") or {}).get("layout") or pg_.get("name") for pg_ in pages]
    if len(lays) >= 3 and set(lays) <= {"site-hero", "site-list", "site-cta", "site-stats"} and d.get("media"):
        iss.append(_issue("warn", "reel-generico", "só layouts de texto (hero/lista/cta) apesar de o site ter mídia: o reel fica igual a qualquer outro", "trazer a mídia real e variar o layout por seção"))
    tel = sorted(Path(folder).glob("tela-*.png"))
    if tel:
        try:
            res["sheets"]["telas_do_site"] = str(_sheet_images(tel[:8], ad / "sheet_telas_do_site.png", cols=4, w=300))
        except Exception:  # noqa
            pass
    return res


def _checklist(g: dict, pages: list[dict]) -> str:
    L = [f"# Portão dos agentes — {g['kind']} · tema {g['theme']}", "",
         f"Medido automaticamente: **{g['blockers']} bloqueio(s)**, {g['warnings']} aviso(s), nota {g['score']}/100.",
         "", "## O que precisa ser LIDO antes do parecer",
         "Abra cada folha abaixo com a ferramenta de leitura de imagem e descreva o que viu. Não aprovar sem olhar.", ""]
    for k, v in g["sheets"].items():
        L.append(f"- `{v}`")
    b = g["brand"]
    L += ["", "## Marca a conferir", f"- nome: {b.get('name')} · logo: `{b.get('logo')}` · fontes: {', '.join(x for x in b.get('fonts', []) if x)}",
          f"- cores: {json.dumps(b.get('colors'), ensure_ascii=False)}", "", "## Storyboard × resultado (por cena/peça)", ""]
    for i, p in enumerate(pages, 1):
        c = p.get("content") or {}
        L.append(f"{i}. **{p['name']}** — título: «{c.get('title', '')}» · texto: «{(c.get('subtitle') or c.get('body') or c.get('label') or '')[:80]}» · fotos: {', '.join(str(x if isinstance(x, str) else x.get('src', '')) for x in (c.get('photos') or [])) or '—'}")
    L += ["", "## Problemas medidos", ""]
    n = 0
    for rep in g["reports"]:
        for it in rep["issues"]:
            if it["level"] in ("blocker", "warn"):
                n += 1
                L.append(f"- [{it['level']}] {rep.get('name')} · {it['code']}: {it['msg']}" + (f" → {it['fix']}" if it.get("fix") else ""))
    if not n:
        L.append("- nenhum")
    if "telas_do_site" in g["sheets"]:
        L += ["", "## FIDELIDADE AO SITE (obrigatório)", "Abra `sheet_telas_do_site.png` (o site real) e compare com as folhas do reel: mesma identidade (cores, fontes, fotos, vídeo, ícones), mesma ordem das seções.",
              "Se o reel parecer outro template com as cores trocadas, o veredito é `refazer`. Cada cena deve citar a tela/seção de origem no parecer.", ""]
    L += ["", "## Perguntas por especialista (o parecer responde cada uma)", ""]
    for r_ in g["roles"]:
        L.append(f"- **{r_}** — {QUESTIONS.get(r_, '')}")
    L += ["", "## Como fechar", "1. Corrigir tudo o que for bloqueio ou P0 e renderizar de novo (máx. 3 rodadas).",
          "2. Preencher `parecer.json` (modelo em `parecer.modelo.json`): para cada especialista `veredito` ok|refazer, `visto` (as folhas que abriu) e `notas` no formato `P0|P1|P2 · onde · problema → mudança`.",
          "3. `python studio.py agentes <saída>` valida; `python studio.py entregar <saída>` só libera depois de aprovado.", ""]
    return "\n".join(L)


def banner(g: dict, ad: Path, output) -> str:
    out_hint = str(output)
    st = "COM BLOQUEIOS" if g["blockers"] else "sem bloqueios medidos"
    return (f"\n━━ PORTÃO DOS AGENTES ━━ {st} · {g['warnings']} aviso(s)\n"
            f"   ENTREGA BLOQUEADA até o parecer dos especialistas (leitura das folhas + parecer.json).\n"
            f"   Leia: {ad / 'CHECKLIST.md'}\n   Depois: python studio.py agentes {out_hint}")


# ------------------------------------------------------------------ validação do parecer
def validate(output) -> dict:
    ad = agentes_dir(Path(output))
    gp = ad / "gate.json"
    if not gp.exists():
        return dict(ok=False, pend=["sem gate.json: rode o comando que gera a peça (o portão roda sozinho) ou STUDIO_PORTAO=on"])
    g = json.loads(gp.read_text(encoding="utf-8"))
    pend = []
    out = Path(output)
    base = out if out.is_dir() else out.parent
    for name, h in g["files"].items():
        f = (out / name) if out.is_dir() else out.parent / name
        if not f.exists():
            pend.append(f"arquivo {name} não existe mais")
        elif sha256(f) != h:
            pend.append(f"{name} mudou depois do portão: rodar de novo (a peça precisa de novo parecer)")
    if g["blockers"]:
        pend.append(f"{g['blockers']} bloqueio(s) medido(s) pelo portão: corrigir e renderizar de novo")
    pp = ad / "parecer.json"
    if not pp.exists():
        pend.append("falta parecer.json (modelo em parecer.modelo.json)")
        return dict(ok=False, pend=pend, gate=g, dir=ad)
    try:
        par = json.loads(pp.read_text(encoding="utf-8"))
    except Exception as e:  # noqa
        return dict(ok=False, pend=pend + [f"parecer.json inválido: {e}"], gate=g, dir=ad)
    if int(par.get("rodada", 1)) > 3:
        pend.append("mais de 3 rodadas: entregar a melhor versão com as pendências listadas pelo Diretor")
    roles = par.get("roles", {})
    for r_ in g["roles"]:
        e = roles.get(r_)
        if not e:
            pend.append(f"{r_}: sem parecer")
            continue
        if e.get("veredito") != "ok":
            pend.append(f"{r_}: veredito '{e.get('veredito') or 'vazio'}' (precisa ser ok)")
        vis = e.get("visto") or []
        if not vis:
            pend.append(f"{r_}: não registrou o que viu (lista 'visto' vazia)")
        for v in vis:
            if not (ad / v).exists() and not (base / v).exists():
                pend.append(f"{r_}: 'visto' cita arquivo que não existe ({v})")
        for n in e.get("notas", []) or []:
            if str(n).strip().upper().startswith("P0"):
                pend.append(f"{r_}: P0 aberto → {str(n)[:90]}")
    d = par.get("diretor", {})
    if d.get("decisao") != "aprovar":
        pend.append("Diretor de Criação: decisão diferente de 'aprovar'")
    if d.get("nota") is None or float(d.get("nota") or 0) < 8.0:
        pend.append("Diretor de Criação: nota < 8,0")
    ok = not pend
    if ok:
        (ad / "APROVADO.json").write_text(json.dumps(dict(files=g["files"], when=time.strftime("%Y-%m-%d %H:%M:%S"), nota=d.get("nota")), ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        (ad / "APROVADO.json").unlink(missing_ok=True)
    return dict(ok=ok, pend=pend, gate=g, dir=ad)


def approved(output) -> bool:
    ad = agentes_dir(Path(output))
    ap = ad / "APROVADO.json"
    if not ap.exists():
        return False
    return validate(output)["ok"]
