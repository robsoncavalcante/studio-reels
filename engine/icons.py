# Ícones Lucide (lucide.dev) — biblioteca aberta ISC, sem exigência de atribuição.
# Conjunto curado para peças de site; se faltar algum termo, cai no silhueta genérica (circle-dot).
# O stroke é preto para o filtro brightness(0) invert(1) nas bolhas gerar silhueta branca; a cor do traço
# pode ser alterada a qualquer momento sem reescrever o arquivo.
from __future__ import annotations

import re
from pathlib import Path


def _svg(d: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="#000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        f"{d}</svg>\n"
    )


LUCIDE: dict[str, str] = {
    "home": _svg('<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>'),
    "volume": _svg('<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>'),
    "music": _svg('<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>'),
    "mic": _svg('<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/>'),
    "headphones": _svg('<path d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H4a1 1 0 0 1-1-1v-6a9 9 0 0 1 18 0v6a1 1 0 0 1-1 1h-2a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3"/>'),
    "grid": _svg('<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/><path d="M9 3v18"/><path d="M15 3v18"/>'),
    "layout": _svg('<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><line x1="3" x2="21" y1="9" y2="9"/><line x1="9" x2="9" y1="21" y2="9"/>'),
    "shield": _svg('<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>'),
    "lock": _svg('<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>'),
    "key": _svg('<path d="m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4"/><path d="m21 2-9.6 9.6"/><circle cx="7.5" cy="15.5" r="5.5"/>'),
    "eye": _svg('<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>'),
    "users": _svg('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'),
    "user": _svg('<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>'),
    "settings": _svg('<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>'),
    "sparkles": _svg('<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>'),
    "zap": _svg('<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>'),
    "heart": _svg('<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>'),
    "star": _svg('<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>'),
    "check-circle": _svg('<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>'),
    "help-circle": _svg('<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>'),
    "info": _svg('<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>'),
    "message": _svg('<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>'),
    "bell": _svg('<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>'),
    "play": _svg('<polygon points="6 3 20 12 6 21 6 3"/>'),
    "film": _svg('<rect width="20" height="20" x="2" y="2" rx="2.18" ry="2.18"/><line x1="7" x2="7" y1="2" y2="22"/><line x1="17" x2="17" y1="2" y2="22"/><line x1="2" x2="22" y1="12" y2="12"/><line x1="2" x2="7" y1="7" y2="7"/><line x1="2" x2="7" y1="17" y2="17"/><line x1="17" x2="22" y1="17" y2="17"/><line x1="17" x2="22" y1="7" y2="7"/>'),
    "image": _svg('<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>'),
    "camera": _svg('<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>'),
    "calendar": _svg('<rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/>'),
    "clock": _svg('<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>'),
    "tv": _svg('<rect width="20" height="15" x="2" y="7" rx="2" ry="2"/><polyline points="17 2 12 7 7 2"/>'),
    "smartphone": _svg('<rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/>'),
    "laptop": _svg('<path d="M20 16V7a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v9m16 0H4m16 0 1.28 2.55a1 1 0 0 1-.9 1.45H3.62a1 1 0 0 1-.9-1.45L4 16"/>'),
    "wifi": _svg('<path d="M5 13a10 10 0 0 1 14 0"/><path d="M8.5 16.5a5 5 0 0 1 7 0"/><path d="M2 8.82a15 15 0 0 1 20 0"/><line x1="12" x2="12.01" y1="20" y2="20"/>'),
    "radio": _svg('<path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9"/><path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5"/><circle cx="12" cy="12" r="2"/><path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5"/><path d="M19.1 4.9C23 8.8 23 15.1 19.1 19"/>'),
    "shopping-cart": _svg('<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>'),
    "credit-card": _svg('<rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" x2="22" y1="10" y2="10"/>'),
    "gift": _svg('<polyline points="20 12 20 22 4 22 4 12"/><rect width="20" height="5" x="2" y="7"/><line x1="12" x2="12" y1="22" y2="7"/><path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"/><path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"/>'),
    "rocket": _svg('<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>'),
    "globe": _svg('<circle cx="12" cy="12" r="10"/><line x1="2" x2="22" y1="12" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'),
    "share": _svg('<path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" x2="12" y1="2" y2="15"/>'),
    "download": _svg('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>'),
    "box": _svg('<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" x2="12" y1="22.08" y2="12"/>'),
    "palette": _svg('<circle cx="13.5" cy="6.5" r=".5"/><circle cx="17.5" cy="10.5" r=".5"/><circle cx="8.5" cy="7.5" r=".5"/><circle cx="6.5" cy="12.5" r=".5"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/>'),
    "layers": _svg('<path d="m12 2 8 4-8 4-8-4 8-4z"/><polyline points="4 12 12 16 20 12"/><polyline points="4 18 12 22 20 18"/>'),
    "sliders": _svg('<line x1="4" x2="4" y1="21" y2="14"/><line x1="4" x2="4" y1="10" y2="3"/><line x1="12" x2="12" y1="21" y2="12"/><line x1="12" x2="12" y1="8" y2="3"/><line x1="20" x2="20" y1="21" y2="16"/><line x1="20" x2="20" y1="12" y2="3"/><line x1="2" x2="6" y1="14" y2="14"/><line x1="10" x2="14" y1="8" y2="8"/><line x1="18" x2="22" y1="16" y2="16"/>'),
    "flame": _svg('<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>'),
    "lightbulb": _svg('<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>'),
    "target": _svg('<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>'),
    "trending-up": _svg('<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>'),
    "award": _svg('<circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/>'),
    "circle-dot": _svg('<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3" fill="#000"/>'),
}


# Mapeamento palavra→ícone. Ordem importa: a primeira regex que bate ganha.
_KW = [
    (r"\b(áudio|audio|som|sound|music|música|speaker|headphone|fone|hi.?fi|spatial|stereo)\b", "music"),
    (r"\b(voz|voice|siri|mic|microfon|chamada|call|phone)\b", "mic"),
    (r"\b(home|casa|lar|roof|teto|room|cômodo|sala|household)\b", "home"),
    (r"\b(app|aplicativ|appstore)\b", "grid"),
    (r"\b(data|dados|privacidade|privacy|privado|private|secure|seguro|segur|exclave|enclave)\b", "shield"),
    (r"\b(lock|senha|password|unlock|bloque|desbloq)\b", "lock"),
    (r"\b(key|chave|credencial|auth)\b", "key"),
    (r"\b(user|usuári|conta|pessoa|household|family|famíl|multi|group|grupo|people|everyone)\b", "users"),
    (r"\b(perfil|profile|account|me\b|minha)\b", "user"),
    (r"\b(setting|ajuste|config|preferências|opção|preferences)\b", "settings"),
    (r"\b(delight|encant|joy|alegria|wow|magic|magia|special|especial|destaque|highlight|star|stunning|incrível|incrivel)\b", "sparkles"),
    (r"\b(fast|rápid|rapid|veloz|speed|velocidade|powerful|poderos|perform|energy|energia|boost)\b", "zap"),
    (r"\b(love|am[eo]r|favorit|querid|loved)\b", "heart"),
    (r"\b(premiad|top|melhor|best|award|prêmio|premium|ranking)\b", "star"),
    (r"\b(confirm|check|feito|done|pronto|complete|ready)\b", "check-circle"),
    (r"\b(pergunta|dúvida|duvid|question|help|ajuda|answer|resposta|faq|support|suporte)\b", "help-circle"),
    (r"\b(info|sobre|about|detalhe|detail|saiba|learn)\b", "info"),
    (r"\b(mensagem|message|chat|conversa|comentário|comment)\b", "message"),
    (r"\b(notif|aviso|alerta|alert|bell|sino|reminder|lembrete|update|atualiz)\b", "bell"),
    (r"\b(play|iniciar|start|begin|watch|assist)\b", "play"),
    (r"\b(film|movie|vídeo|video|cinema|clip|streaming)\b", "film"),
    (r"\b(foto|photo|image|imagem|galeria|gallery|picture)\b", "image"),
    (r"\b(câmera|camera|lente|lens|capture|captur)\b", "camera"),
    (r"\b(calend|agenda|evento|event|data\b|date|birthday|aniversári|appointment|compromisso)\b", "calendar"),
    (r"\b(hora|time|relógio|clock|timer|cronômetro|minuto|second)\b", "clock"),
    (r"\b(tv\b|televis|monitor|display|tela|screen)\b", "tv"),
    (r"\b(iphone|ipad|celular|phone\b|smartphone|mobile|móvel|device|dispositivo|ios)\b", "smartphone"),
    (r"\b(laptop|notebook|macbook|computador|computer)\b", "laptop"),
    (r"\b(wi.?fi|internet|rede|network|online|conect|connected|conex)\b", "wifi"),
    (r"\b(airplay|mirror|cast|stream|broadcast)\b", "radio"),
    (r"\b(shop|loja|cart|carrinho|compra|buy|comprar|purchase|checkout)\b", "shopping-cart"),
    (r"\b(pay|paga|pagament|card|cartão|cartao|wallet|carteira|cash|dinheiro|price|preço|apple ?card)\b", "credit-card"),
    (r"\b(gift|presente|brinde|bonus|bônus|promo|desconto|discount)\b", "gift"),
    (r"\b(setup|configuração|personal|instala|instal|start|começ|comec|getting started|onboarding|guided|guiada)\b", "rocket"),
    (r"\b(global|mundo|world|language|idioma|location|localiz|regi(ão|on|aõ))\b", "globe"),
    (r"\b(compartilh|share|enviar|send|export|airdrop)\b", "share"),
    (r"\b(baixar|download|save|salv|archive|arquiv)\b", "download"),
    (r"\b(produto|product|item|box|caixa|accessory|acessório|accessories)\b", "box"),
    (r"\b(cor|color|theme|tema|paleta|palette|style|estilo|face|aesthetic|design)\b", "palette"),
    (r"\b(layer|camada|stack|pilha|multiroom|multi.?room|multi)\b", "layers"),
    (r"\b(control|ajust|tune|slider|equalizer|mixer|misturar|balance)\b", "sliders"),
    (r"\b(quente|hot|calor|trending|popular|top|viral|hit)\b", "flame"),
    (r"\b(ideia|idea|inspiration|inspiração|smart|inteligente|ai\b|intellig)\b", "lightbulb"),
    (r"\b(meta|goal|objetivo|focus|foco|target|alvo|precisão)\b", "target"),
    (r"\b(crescimento|growth|insight|analytics|stat|dados|chart|gráfico|report|progress|progresso)\b", "trending-up"),
    (r"\b(prêmio|conquista|achievement|badge|medalha|medal|trofeu|trophy)\b", "award"),
    (r"\b(watch|vê|veja|ver|look|see|view|visualiz)\b", "eye"),
    (r"\b(notif|peace|tranquil|calm|zen|mindful)\b", "bell"),
    (r"\b(fones|headphone|ouvido|ear|earbud)\b", "headphones"),
    (r"\b(layout|layout|section|seção|interface|ui\b|menu)\b", "layout"),
]


def pick(title: str) -> tuple[str | None, str | None]:
    """Devolve (nome, conteúdo SVG) do ícone que casa com o título; se nada bater, retorna o ponto genérico."""
    t = (title or "").strip()
    if not t:
        return "circle-dot", LUCIDE["circle-dot"]
    for pat, name in _KW:
        if re.search(pat, t, re.I):
            return name, LUCIDE[name]
    return "circle-dot", LUCIDE["circle-dot"]


def write_to(midia_dir: Path, name: str) -> str:
    """Escreve o SVG do ícone em midia/lucide-<name>.svg (idempotente) e devolve o caminho relativo."""
    svg = LUCIDE.get(name) or LUCIDE["circle-dot"]
    midia_dir.mkdir(parents=True, exist_ok=True)
    f = midia_dir / f"lucide-{name}.svg"
    if not f.exists():
        f.write_text(svg, encoding="utf-8")
    return f"midia/{f.name}"
