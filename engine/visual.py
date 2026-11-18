"""Linguagens visuais (v6): o reel de cada marca ganha um partido próprio, escolhido a partir do site.

- Marca igual → mesma linguagem (consistência: a memória fica em library/history.json).
- Marcas diferentes → linguagens diferentes (trava de repetição olha as últimas peças).
- Mesma marca, peças diferentes → `--variante N` troca o layout dentro da linguagem.
O Diretor de Arte registra o "partido visual" (1 linha) antes de montar; o portão confere (ver agents/PROTOCOL.md).
Nada aqui conhece empresa nenhuma: tudo vem dos sinais do site capturado."""
from __future__ import annotations

import json
import re
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
def _hist_path() -> Path:
    import os
    return Path(os.environ.get("STUDIO_HISTORY") or (ROOT / "library" / "history.json"))

# papéis de cena → layouts (alternativas rodam com --variante). Mídia de vídeo é sempre o cartão 3D do site.
LINGUAGENS = {
    "cards3d": dict(
        nome="Cartões 3D", desc="telas e mídia do site em cartões 3D com câmera; texto enxuto — para sites ricos em imagem/vídeo e produto",
        roles=dict(list=["site-list", "service-grid", "step-process"]), style={}, transition=None),
    "poster": dict(
        nome="Pôster tipográfico", desc="tipografia gigante, foto de sangria e poucos elementos — para marcas diretas, escuras ou de impacto",
        roles=dict(hero=["typographic"], cover=["full-bleed-bottom", "split-vertical"], showcase=["full-bleed-bottom", "split-vertical"],
                   duo=["collage-2"], list=["tips-list", "checklist"], stats=["big-number"], quote=["quote"], cta=["cta-follow"]),
        style=dict(dcase="uppercase", dw=800, card_radius="0cqw", ph_radius="0cqw"), transition="set:punch"),
    "editorial": dict(
        nome="Editorial", desc="capa de revista, molduras e respiro — para marcas com serifa, tom sóbrio ou de serviço premium",
        roles=dict(hero=["magazine-cover"], cover=["framed-photo", "arch-window"], showcase=["framed-photo", "arch-window"],
                   duo=["collage-2"], list=["service-grid", "checklist", "step-process", "tips-list"], stats=["big-number"], quote=["quote"], cta=["typographic", "cta-follow"]),
        style=dict(dw=500, card_radius="1.2cqw", ph_radius="0.6cqw"), transition="set:editorial"),
    "modular": dict(
        nome="Modular / grade", desc="blocos, grade e passos numerados — para marcas de serviço com muitas ofertas e identidade sóbria",
        roles=dict(hero=["split-vertical", "site-hero"], cover=["site-cover"], showcase=["site-showcase"], duo=["site-duo"],
                   list=["service-grid", "step-process"], stats=["site-stats"], quote=["testimonial"], cta=["site-cta"]),
        style=dict(card_radius="0.8cqw", ph_radius="0.8cqw"), transition="set:clean"),
}
ROLE_OF = {"site-hero": "hero", "site-cover": "cover", "site-showcase": "showcase", "site-duo": "duo", "site-list": "list",
           "site-icons": "list", "site-stats": "stats", "testimonial": "quote", "site-cta": "cta"}
SERIF = re.compile(r"serif|georgia|times|playfair|merriweather|garamond|didot|cormorant|lora|bodoni|abril|fraunces|dm serif|libre baskerville|spectral|crimson|prata", re.I)
SANS_HINT = re.compile(r"sans|grotesk|helvet|arial|inter\b|roboto|montserrat|poppins|proxima|open sans", re.I)


def _h(s: str) -> int:
    return zlib.crc32((s or "x").encode())


def load_history() -> list:
    try:
        return json.loads(_hist_path().read_text(encoding="utf-8"))
    except Exception:  # noqa
        return []


def save_history(h: list) -> None:
    try:
        _hist_path().parent.mkdir(parents=True, exist_ok=True)
        _hist_path().write_text(json.dumps(h[-60:], ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:  # noqa
        pass


def signals(brand: dict, data: dict, media: list | None, scenes: list | None = None) -> dict:
    """Sinais objetivos do site que decidem a linguagem (todos entram no partido.json para auditoria)."""
    from .site import _lum, _saturated, _hls
    c = brand.get("colors", {})
    st = brand.get("style", {}) or {}
    fonts = " ".join(str(v) for v in ((data or {}).get("fonts") or {}).values())
    media = media or []
    n_img = sum(1 for m in media if m.get("kind") == "image")
    n_vid = sum(1 for m in media if m.get("kind") == "video")
    secs = [s for s in (data or {}).get("sections", []) if s.get("heading") or s.get("items")]
    try:
        _h_, _l_, _s_ = _hls(c.get("accent", "#888888"))
        warm = bool(_saturated(c.get("accent", "#888888"))) and (_h_ < 68 or _h_ > 300)  # vermelho/laranja/amarelo/rosa; azul e verde frios não são "divertidos"
    except Exception:  # noqa
        warm = False
    return dict(
        warm=warm,
        dark=_lum(c.get("bg", "#FFFFFF")) < 0.3,
        sat=bool(_saturated(c.get("accent", "#888888"))),
        serif=bool(SERIF.search(re.sub(r"sans-serif|-apple-system|system-ui", " ", fonts, flags=re.I))) and not SANS_HINT.search((data or {}).get("fonts", {}).get("h1", "") or ""),
        upper=st.get("dcase") == "uppercase",
        heavy=(st.get("dw") or 0) >= 700,
        round_btn=st.get("btn_radius") == "999px",
        square_btn=str(st.get("btn_radius", "")).startswith("0") or (st.get("btn_radius") is None and False),
        media=n_img + n_vid * 2, videos=n_vid,
        offers=sum(1 for s in secs if len(s.get("items", [])) >= 3),
    )


def score(sig: dict) -> dict:
    s = dict(cards3d=0.0, poster=0.0, editorial=0.0, modular=0.0)
    s["cards3d"] += 2.5 if sig["media"] >= 5 else (1 if sig["media"] >= 3 else -1.5)
    s["cards3d"] += 1.5 if sig["round_btn"] else 0
    s["cards3d"] += 1 if sig["sat"] else 0
    s["cards3d"] += 1 if sig["videos"] else 0
    s["poster"] += 2.5 if (sig["upper"] or sig["heavy"]) else 0
    s["poster"] += 1.5 if sig["dark"] else 0
    s["poster"] += 1.5 if sig["media"] <= 2 else 0
    s["poster"] += 1 if sig["square_btn"] else 0
    s["editorial"] += 3.5 if sig["serif"] else 0
    s["editorial"] += 1.5 if (not sig["dark"] and not sig["sat"]) else 0
    s["editorial"] += 1 if not sig["heavy"] else 0
    s["modular"] += 2 if sig["offers"] >= 3 else 0.5 * sig["offers"]
    s["modular"] += 1.5 if (not sig["dark"] and not sig["serif"]) else 0
    s["modular"] += 1 if sig["media"] <= 4 else 0
    s["modular"] += 1 if sig["square_btn"] else 0
    return s


def choose(brand_key: str, brand: dict, data: dict, media: list | None, forced: str | None = None, history: list | None = None) -> dict:
    """Escolhe a linguagem: pedida > memória da marca > pontuação do site com trava de repetição entre marcas."""
    history = load_history() if history is None else history
    sig = signals(brand, data, media)
    sc = score(sig)
    tb = {k: ((_h(brand_key + k) % 100) / 1000) for k in sc}  # desempate estável por marca
    ranked = sorted(sc, key=lambda k: -(sc[k] + tb[k]))
    mem = next((h for h in reversed(history) if h.get("marca") == brand_key and h.get("linguagem") in LINGUAGENS), None)
    why = []
    if forced:
        pick = forced
        why.append(f"linguagem pedida ({forced})")
    elif mem:
        pick = mem["linguagem"]
        why.append(f"memória da marca: usa de novo «{pick}» (consistência entre peças)")
    else:
        pick = ranked[0]
        recent = [h["linguagem"] for h in history[-2:] if h.get("marca") != brand_key]
        if len(recent) == 2 and recent[0] == recent[1] == pick:
            alt = next((k for k in ranked[1:] if sc[k] >= sc[pick] - 2.5 and k not in recent), None)
            if alt:
                why.append(f"trava de repetição: as 2 últimas peças (outras marcas) foram «{pick}» → «{alt}» (pontuação {sc[alt]:.1f} vs {sc[pick]:.1f})")
                pick = alt
        why.append("sinais do site: " + ", ".join(k for k, v in sig.items() if v is True) + f" · mídia {sig['media']} · ofertas {sig['offers']}")
    return dict(linguagem=pick, pontuacao={k: round(v, 1) for k, v in sc.items()}, sinais=sig, motivos=why)


def apply(scenes: list, lang: str, variante: int = 0, name: str = "") -> list:
    """Reescreve o layout das cenas conforme a linguagem. Vídeo do site e cenas sem equivalente ficam como estão."""
    L = LINGUAGENS[lang]["roles"]
    out, seen = [], {}
    for sc in scenes:
        sc = dict(sc)
        role = ROLE_OF.get(sc["layout"])
        alts = L.get(role) if role else None
        if alts:
            i = seen.get(role, 0)
            seen[role] = i + 1
            new = alts[(variante + i) % len(alts)]
            sc = _adapt(sc, new, name)
        out.append(sc)
    return _no_repeat(out, L)


# ------------------------------------------------------------------ arquétipo de movimento (v6.2, inspirado em motion-personality)
ARQUETIPOS = {
    "premium": dict(nome="Premium", desc="lento, elegante, sem quique: poucos elementos, respiro longo",
                    pace="calm", ease="out-expo", intensity=0.8, motion="drift", kenburns="drift", stagger=1.4, entrada="deslize curto 12–20px, escala inicial 96–98%, blur leve",
                    ambiente="respiração 1.00→1.02 em 6–8s; parallax 0.3/0.6/1.0", transicao="fade/dissolve longo"),
    "playful": dict(nome="Divertido", desc="saltitante e caloroso: overshoot controlado, stagger curto",
                    pace="snappy", ease="out-back", intensity=1.15, motion="overshoot", kenburns="drift", stagger=0.8, entrada="sobe 30–50px com overshoot, escala inicial 80–90%",
                    ambiente="flutuação em camadas 3–6px, 3–5s", transicao="wipe/pop"),
    "corporate": dict(nome="Corporativo", desc="firme e previsível: linear-clean, sem exagero",
                      pace="standard", ease="out-cubic", intensity=0.9, motion="fade-up", kenburns="drift", stagger=1.0, entrada="sobe 20–30px, escala inicial 95%",
                      ambiente="brilho/shimmer discreto na linha de destaque", transicao="clean/slide"),
    "energetic": dict(nome="Enérgico", desc="rápido e marcado: entradas fortes, cortes no beat",
                      pace="hype", ease="out-quint", intensity=1.2, motion="stamp", kenburns="push", stagger=0.6, entrada="whip/stamp, 60–100px, escala inicial 60–80%",
                      ambiente="pulso de escala 1.00→1.04 no beat", transicao="punch/whip"),
}


def arquetipo(sig: dict, brand_key: str = "", forced: str | None = None, history: list | None = None) -> dict:
    """Personalidade de movimento: Premium / Divertido / Corporativo / Enérgico (decidida pelos sinais do site)."""
    history = load_history() if history is None else history
    s = dict(premium=0.0, playful=0.0, corporate=0.0, energetic=0.0)
    s["premium"] += 2 if (sig["dark"] and not sig["sat"]) else 0
    s["premium"] += 2 if sig["serif"] else 0
    s["premium"] += 1.5 if (not sig["sat"] and not sig["heavy"] and not sig["upper"]) else 0
    s["premium"] += 1 if sig["media"] >= 5 else 0
    s["playful"] += 2.5 if (sig.get("warm") and sig["round_btn"] and not sig["dark"]) else 0
    s["playful"] += 1 if (sig["round_btn"] and sig.get("warm")) else 0
    s["premium"] += 2.5 if (sig["media"] >= 5 and not sig.get("warm") and not sig["upper"] and not sig["heavy"]) else 0
    s["energetic"] += 2 if (sig["upper"] or sig["heavy"]) else 0
    s["energetic"] += 1.5 if (sig["sat"] and sig["dark"]) else 0
    s["energetic"] += 1 if sig["videos"] >= 2 else 0
    s["corporate"] += 2 if sig["square_btn"] else 0
    s["corporate"] += 1.5 if sig["offers"] >= 3 else 0
    s["corporate"] += 1 if (not sig["sat"] and not sig["serif"]) else 0
    mem = next((h for h in reversed(history) if h.get("marca") == brand_key and h.get("arquetipo") in ARQUETIPOS), None)
    ranked = sorted(s, key=lambda k: -(s[k] + (_h(brand_key + k) % 100) / 1000))
    if forced:
        pick, why = forced, f"arquétipo pedido ({forced})"
    elif mem:
        pick, why = mem["arquetipo"], "memória da marca (identidade de movimento constante entre peças)"
    else:
        pick, why = ranked[0], "sinais: " + ", ".join(f"{k} {v:.1f}" for k, v in sorted(s.items(), key=lambda kv: -kv[1]))
    return dict(id=pick, motivo=why, pontuacao={k: round(v, 1) for k, v in s.items()}, **ARQUETIPOS[pick])


def _no_repeat(scenes: list, L: dict) -> list:
    """Nunca dois layouts iguais em sequência nas cenas de texto: troca o repetido por outra alternativa do papel."""
    alt_pool = {"list": ["site-list", "service-grid", "step-process", "tips-list", "checklist"]}
    for i in range(1, len(scenes)):
        a, b = scenes[i - 1]["layout"], scenes[i]["layout"]
        if a == b and ROLE_OF.get(b, "") == "list" or (a == b and b in alt_pool["list"]):
            for cand in alt_pool["list"]:
                if cand != a and (i + 1 >= len(scenes) or cand != scenes[i + 1]["layout"]):
                    scenes[i] = _adapt(dict(scenes[i], layout=b), cand, "")
                    break
    return scenes


def _adapt(sc: dict, new: str, name: str) -> dict:
    old = sc["layout"]
    if new == old:
        return sc
    base = {k: sc[k] for k in ("kicker", "title", "subtitle", "dur", "theme") if k in sc}
    ph = {k: sc[k] for k in ("photos", "photo_meta") if k in sc}
    its = [i for i in (sc.get("items") or [])]
    if new == "typographic":
        return dict(layout=new, **base)
    if new == "magazine-cover":
        return dict(layout=new, masthead=(name or "").upper()[:18], kicker=sc.get("kicker", ""), title=sc["title"], subtitle=sc.get("subtitle", ""),
                    items=[dict(title=i["title"]) for i in its[:3]], **{k: sc[k] for k in ("dur", "theme") if k in sc})
    if new in ("full-bleed-bottom", "split-vertical", "framed-photo", "arch-window"):
        d = dict(layout=new, **base, **ph)
        if sc.get("cta") and new == "full-bleed-bottom":
            d["cta"] = sc["cta"]
        return d
    if new == "collage-2":
        return dict(layout=new, **base, **ph)
    if new in ("tips-list", "checklist", "service-grid", "step-process"):
        rows = [dict(title=i.get("title", ""), text=i.get("text", "")) for i in its[:5 if new != "service-grid" else 4]]
        if new == "checklist":
            rows = [dict(title=r["title"]) for r in rows]
        return dict(layout=new, **base, items=rows)
    if new == "big-number":
        first = its[0] if its else {}
        rest = " · ".join(f"{i.get('number', '')} {i.get('title', '')}".strip() for i in its[1:3])
        return dict(layout=new, kicker=sc.get("kicker", ""), number=first.get("number", ""), label=first.get("title") or first.get("text", ""),
                    title=sc.get("title", ""), subtitle=rest, **{k: sc[k] for k in ("dur", "theme") if k in sc})
    if new == "quote":
        return dict(layout=new, quote=sc.get("quote", ""), author=sc.get("author", ""), role=sc.get("role", ""), **{k: sc[k] for k in ("dur", "theme") if k in sc})
    if new == "cta-follow":
        return dict(layout=new, title=sc["title"], subtitle=sc.get("subtitle", ""), cta=sc.get("cta", "Saiba mais"), handle=sc.get("handle", ""), **{k: sc[k] for k in ("dur", "theme") if k in sc})
    if new in ("site-hero", "site-cover", "site-showcase", "site-duo", "site-stats", "testimonial", "site-cta"):
        return dict(sc, layout=new)
    return sc


def skin(brand: dict, lang: str) -> dict:
    """Pele da linguagem: preenche só o que o site não definiu (o que o site tem sempre vence)."""
    st = dict(brand.get("style") or {})
    for k, v in LINGUAGENS[lang]["style"].items():
        st.setdefault(k, v)
    return st


def repetition(layouts: list, brand_key: str, lang: str, history: list | None = None) -> list:
    """Avisos de repetição: mesma sequência de layouts de outra marca, ou da mesma marca sem mudar de variante."""
    history = load_history() if history is None else history
    out = []
    for h in history[-12:]:
        if h.get("layouts") == layouts:
            who = "da mesma marca (troque --variante)" if h.get("marca") == brand_key else f"de «{h.get('marca')}»"
            out.append(f"sequência de layouts idêntica à última peça {who}")
        elif h.get("marca") != brand_key and h.get("linguagem") == lang:
            a, b = set(layouts), set(h.get("layouts") or [])
            if a and b and len(a & b) / len(a | b) >= 0.85:
                out.append(f"mesma linguagem e quase os mesmos layouts de «{h.get('marca')}» ({int(100 * len(a & b) / len(a | b))}% iguais)")
    return out


def record(brand_key: str, lang: str, variante: int, layouts: list, history: list | None = None, arq: str | None = None) -> None:
    history = load_history() if history is None else history
    history.append(dict(marca=brand_key, linguagem=lang, variante=variante, arquetipo=arq, layouts=layouts, quando=time.strftime("%Y-%m-%d %H:%M")))
    save_history(history)


def partido_md(p: dict) -> str:
    L = LINGUAGENS[p["linguagem"]]
    return "\n".join([
        "# Partido visual (decidido pelo motor; o Diretor de Arte confirma ou troca antes de montar)", "",
        f"**Linguagem:** {L['nome']} — {L['desc']}", f"**Variante:** {p['variante']}",
        f"**Pontuação:** " + " · ".join(f"{k} {v}" for k, v in p["pontuacao"].items()),
        "", "## Por quê"] + [f"- {m}" for m in p["motivos"]] + [
        "", "## Sequência", " → ".join(p["layouts"]),
        "", "## Repetição"] + ([f"- ⚠ {w}" for w in p["repeticao"]] or ["- nenhuma detectada nas últimas peças"]) + [
        "", "O Diretor de Arte escreve no parecer.json o campo `partido_visual` (1 linha: linguagem + por que serve a esta marca + o que a diferencia das outras).", ""])
