"""
Motion: curvas de easing (Penner + Material + física via CSS linear()), ritmo (pace), sincronia com BPM.

Referências de timing (pesquisa): UI 200–500 ms; entradas de hero 500–800 ms; bounce/elastic 800–1200 ms;
nunca linear em movimento de objeto; ease-out para entrar, ease-in para sair; stagger curto (60–140 ms).
"""
from __future__ import annotations

import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- easings
BEZIER = {
    # Penner (easings.net)
    "in-sine": (.12, 0, .39, 0), "out-sine": (.61, 1, .88, 1), "inout-sine": (.37, 0, .63, 1),
    "in-quad": (.11, 0, .5, 0), "out-quad": (.5, 1, .89, 1), "inout-quad": (.45, 0, .55, 1),
    "in-cubic": (.32, 0, .67, 0), "out-cubic": (.33, 1, .68, 1), "inout-cubic": (.65, 0, .35, 1),
    "in-quart": (.5, 0, .75, 0), "out-quart": (.25, 1, .5, 1), "inout-quart": (.76, 0, .24, 1),
    "in-quint": (.64, 0, .78, 0), "out-quint": (.22, 1, .36, 1), "inout-quint": (.83, 0, .17, 1),
    "in-expo": (.7, 0, .84, 0), "out-expo": (.16, 1, .3, 1), "inout-expo": (.87, 0, .13, 1),
    "in-circ": (.55, 0, 1, .45), "out-circ": (0, .55, .45, 1), "inout-circ": (.85, 0, .15, 1),
    "in-back": (.36, 0, .66, -.56), "out-back": (.34, 1.56, .64, 1), "inout-back": (.68, -.6, .32, 1.6),
    # Material
    "standard": (.4, 0, .2, 1), "decelerate": (0, 0, .2, 1), "accelerate": (.4, 0, 1, 1),
    "emphasized": (.2, 0, 0, 1),
}
BEZIER_DESC = {
    "out-expo": "saída suave e longa — o padrão premium para entradas",
    "out-cubic": "entrada natural, versátil", "out-quart": "entrada elegante",
    "out-back": "passa um pouco do alvo e volta (energia)", "inout-cubic": "movimentos entre posições",
    "standard": "Material: uso geral", "decelerate": "Material: entrar na tela", "accelerate": "Material: sair da tela",
    "emphasized": "Material: ação importante",
}


def _spring(zeta: float, omega: float, n: int = 48) -> list[float]:
    wd = omega * math.sqrt(max(1e-6, 1 - zeta ** 2)) if zeta < 1 else omega
    # tempo até a envoltória < 0.002
    T = -math.log(0.002) / (zeta * omega) if zeta > 0 else 3
    pts = []
    for i in range(n + 1):
        t = T * i / n
        if zeta < 1:
            v = 1 - math.exp(-zeta * omega * t) * (math.cos(wd * t) + (zeta * omega / wd) * math.sin(wd * t))
        else:
            v = 1 - math.exp(-omega * t) * (1 + omega * t)
        pts.append(v)
    pts[-1] = 1.0
    return pts


def _bounce(n: int = 48) -> list[float]:
    def f(x):
        n1, d1 = 7.5625, 2.75
        if x < 1 / d1:
            return n1 * x * x
        if x < 2 / d1:
            x -= 1.5 / d1
            return n1 * x * x + .75
        if x < 2.5 / d1:
            x -= 2.25 / d1
            return n1 * x * x + .9375
        x -= 2.625 / d1
        return n1 * x * x + .984375
    return [f(i / n) for i in range(n + 1)]


def _elastic(n: int = 60) -> list[float]:
    c4 = 2 * math.pi / 3
    return [0 if i == 0 else 1 if i == n else 2 ** (-10 * i / n) * math.sin((i / n * 10 - .75) * c4) + 1 for i in range(n + 1)]


PHYSICS = {
    "spring-soft": (_spring(.75, 9), "mola suave: assenta sem balançar muito"),
    "spring-bouncy": (_spring(.32, 11), "mola saltitante: bem energética"),
    "spring-snappy": (_spring(.88, 17), "mola rápida e firme: UI moderna"),
    "bounce": (_bounce(), "quica como uma bola"),
    "elastic": (_elastic(), "elástico: balança no final"),
}


def _linear(pts):
    return "linear(" + ", ".join(f"{p:.4f}".rstrip("0").rstrip(".") or "0" for p in pts) + ")"


def easings() -> dict[str, dict]:
    out = {}
    for k, v in BEZIER.items():
        out[k] = dict(css="cubic-bezier(%s)" % ",".join(str(x) for x in v), kind="bezier", dur=(.2, .8), desc=BEZIER_DESC.get(k, ""))
    for k, (pts, d) in PHYSICS.items():
        out[k] = dict(css=_linear(pts), kind="physics", dur=(.8, 1.2) if k in ("elastic", "spring-bouncy", "bounce") else (.5, 1.0), desc=d)
    out["linear"] = dict(css="linear", kind="linear", dur=(0, 99), desc="velocidade constante: só para rotação contínua/marquee")
    return out


def build_css() -> Path:
    css = ":root{" + ";".join(f"--ez-{k}:{v['css']}" for k, v in easings().items()) + "}\n"
    p = ROOT / "engine" / "easings.css"
    p.write_text(css)
    return p


def ease_css(name: str | None) -> str | None:
    if not name:
        return None
    e = easings()
    if name in e:
        return e[name]["css"]
    if name.startswith("cubic-bezier") or name.startswith("linear("):
        return name
    raise SystemExit(f"Easing '{name}' não existe. Use: studio.py motion easings")


# ---------------------------------------------------------------- ritmo
PACE = {
    "calm": dict(speed=.8, stagger=1.3, k=.85, tdur=.7, desc="lento e elegante (marcas premium, institucional)"),
    "standard": dict(speed=1.0, stagger=1.0, k=1.0, tdur=.5, desc="equilibrado (padrão)"),
    "snappy": dict(speed=1.3, stagger=.8, k=1.0, tdur=.4, desc="ágil e limpo (negócios, tech)"),
    "hype": dict(speed=1.7, stagger=.6, k=1.2, tdur=.3, desc="rápido e enérgico (promoção, esporte, trend)"),
}


def style_for(m: dict, reel: dict) -> tuple[list[str], str]:
    """Classes e variáveis CSS (inline) para o movimento `m` + ajustes do reel."""
    pace = PACE.get(reel.get("pace") or "standard", PACE["standard"])
    speed = float(reel.get("speed") or pace["speed"])
    stg_scale = float(reel.get("stagger_scale") or pace["stagger"])
    k = float(reel.get("intensity") or pace["k"])
    md, stg, bd = m.get("dur", .7), m.get("stagger", .14), m.get("delay", .15)
    bpm = reel.get("bpm")
    if reel.get("sync") and bpm:
        beat = 60.0 / float(bpm)
        stg = beat / 2 if not m.get("chars") else beat / 8
        md = min(max(beat, .45), 1.1)
        bd = beat / 4
        speed, stg_scale = 1.0, 1.0
    md, stg, bd = md / speed, stg * stg_scale / speed, bd / speed
    classes = []
    style = f";--md:{md:.3f}s;--stg:{stg:.3f}s;--bd:{bd + reel.get('extra_delay', 0):.3f}s;--sd:{reel.get('scene_dur', 3.2)}s;--k:{k}"
    e = ease_css(reel.get("ease"))
    if e:
        classes.append("ease-o")
        style += f";--ease-o:{e}"
    kb = reel.get("kenburns")
    if kb:
        classes.append(f"kb-{kb}")
    if reel.get("count_up"):
        classes.append("cu")
    if reel.get("human"):
        classes.append("hm")
    if reel.get("parallax"):
        classes.append("px")
    if reel.get("highlight") in ("box", "marker", "underline"):
        classes.append(f"hl-{reel['highlight']}")
    return classes, style


def ease_check(ease_name: str, dur_s: float) -> str | None:
    e = easings().get(ease_name)
    if not e:
        return None
    lo, hi = e["dur"]
    if dur_s < lo * .8 or dur_s > hi * 1.25:
        return f"easing '{ease_name}' funciona melhor entre {lo:.1f}s e {hi:.1f}s (atual {dur_s:.2f}s)"
    return None
