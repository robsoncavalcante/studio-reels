"""
Bancos de imagem GRATUITOS (nenhuma imagem gerada por IA): Pexels, Unsplash, Pixabay, Openverse, Wikimedia Commons.

Chaves (grátis) em variáveis de ambiente:  PEXELS_API_KEY · UNSPLASH_ACCESS_KEY · PIXABAY_API_KEY
Openverse e Wikimedia funcionam sem chave (licença é por imagem: o filtro padrão aceita só CC0/PDM/CC BY).

Cada download grava o comprovante (fonte, autor, licença, data) em library/stock/credits.json —
"guarde a origem e a versão da licença no momento do download" é a recomendação para uso comercial.
Respeitamos as regras das APIs: Unsplash exige crédito e o ping de download; Pexels pede link de volta;
nada de montar um banco concorrente/redistribuir os arquivos soltos.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOCK_DIR = ROOT / "library" / "stock"
LEDGER = STOCK_DIR / "credits.json"
UA = "StudioReels/2.0 (+local tool)"

PROVIDERS = {
    "pexels": dict(key="PEXELS_API_KEY", license="Pexels License", attribution="recomendada (link de volta)",
                   rules="Uso comercial livre. Proibido: vender sem alteração, marca/logo, sugerir endosso por pessoas retratadas."),
    "unsplash": dict(key="UNSPLASH_ACCESS_KEY", license="Unsplash License", attribution="obrigatória pela API (fotógrafo + Unsplash)",
                     rules="Uso comercial livre. Via API é obrigatório creditar e acionar o endpoint de download. Proibido montar serviço concorrente."),
    "pixabay": dict(key="PIXABAY_API_KEY", license="Pixabay Content License", attribution="não exigida",
                    rules="Uso comercial livre. Proibido redistribuir arquivos soltos; atenção a marcas/pessoas reconhecíveis."),
    "openverse": dict(key=None, license="por imagem (CC0/PDM/CC BY…)", attribution="depende da licença",
                      rules="Confira a licença de CADA imagem; CC BY exige crédito; evite NC/ND em trabalho de cliente."),
    "wikimedia": dict(key=None, license="por imagem", attribution="depende da licença",
                      rules="Confira a licença de CADA imagem; BY-SA exige compartilhar igual; pode ter marcas e pessoas."),
}


def _http(url: str, headers: dict | None = None, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _json(url, headers=None):
    return json.loads(_http(url, headers).decode("utf-8"))


def _need(provider):
    k = PROVIDERS[provider]["key"]
    v = os.environ.get(k or "")
    if k and not v:
        raise SystemExit(f"Falta a chave grátis do {provider}: defina {k} (cadastro gratuito no site do {provider}).")
    return v


# ------------------------------------------------------------- normalizadores (testáveis sem rede)
def norm_pexels(j) -> list[dict]:
    return [dict(provider="pexels", id=str(p["id"]), w=p["width"], h=p["height"], thumb=p["src"].get("medium"),
                 url=p["src"].get("large2x") or p["src"].get("original"), author=p.get("photographer"),
                 author_url=p.get("photographer_url"), source_url=p.get("url"), license="Pexels License",
                 color=p.get("avg_color"), alt=p.get("alt", ""),
                 credit=f"Foto: {p.get('photographer')} / Pexels") for p in j.get("photos", [])]


def norm_unsplash(j) -> list[dict]:
    out = []
    for p in j.get("results", []):
        u = p["user"]
        out.append(dict(provider="unsplash", id=p["id"], w=p["width"], h=p["height"], thumb=p["urls"]["small"],
                        url=p["urls"]["regular"], author=u["name"], author_url=u["links"]["html"] + "?utm_source=studio_reels&utm_medium=referral",
                        source_url=p["links"]["html"], license="Unsplash License", color=p.get("color"), alt=p.get("alt_description") or "",
                        ping=p["links"].get("download_location"), credit=f"Foto: {u['name']} / Unsplash"))
    return out


def norm_pixabay(j) -> list[dict]:
    return [dict(provider="pixabay", id=str(p["id"]), w=p["imageWidth"], h=p["imageHeight"], thumb=p.get("webformatURL"),
                 url=p.get("largeImageURL") or p.get("webformatURL"), author=p.get("user"),
                 author_url=f"https://pixabay.com/users/{p.get('user')}-{p.get('user_id')}/", source_url=p.get("pageURL"),
                 license="Pixabay Content License", color=None, alt=p.get("tags", ""), credit=f"Imagem: {p.get('user')} / Pixabay")
            for p in j.get("hits", [])]


def _ov_license(p) -> str:
    lic = (p.get("license") or "").upper()
    ver = p.get("license_version") or ""
    if lic.startswith(("CC", "PDM")):
        return f"{lic} {ver}".strip()
    return f"CC {lic} {ver}".strip()


def norm_openverse(j) -> list[dict]:
    return [dict(provider="openverse", id=p["id"], w=p.get("width") or 0, h=p.get("height") or 0, thumb=p.get("thumbnail"),
                 url=p.get("url"), author=p.get("creator"), author_url=p.get("creator_url"), source_url=p.get("foreign_landing_url"),
                 license=_ov_license(p), color=None, alt=p.get("title", ""),
                 credit=p.get("attribution") or f"{p.get('title')} por {p.get('creator')} ({p.get('license')})") for p in j.get("results", [])]


def norm_wikimedia(j) -> list[dict]:
    out = []
    for pg in (j.get("query", {}).get("pages", {}) or {}).values():
        ii = (pg.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata", {})
        lic = (md.get("LicenseShortName") or {}).get("value", "")
        out.append(dict(provider="wikimedia", id=str(pg.get("pageid")), w=ii.get("width", 0), h=ii.get("height", 0), thumb=ii.get("thumburl"),
                        url=ii.get("url"), author=re.sub("<[^>]+>", "", (md.get("Artist") or {}).get("value", "")), author_url=None,
                        source_url=ii.get("descriptionurl"), license=lic, color=None, alt=pg.get("title", ""),
                        credit=f"{pg.get('title')} — {lic} — Wikimedia Commons"))
    return out


OPEN_LICENSES = ("CC0", "PDM", "CC BY ", "CC BY-", "PUBLIC DOMAIN")


def safe_license(lic: str) -> bool:
    L = (lic or "").upper()
    if "NC" in L.split() or "-NC" in L or "ND" in L.split() or "-ND" in L:
        return False
    return any(L.startswith(o) or o.strip() in L for o in OPEN_LICENSES) or "PEXELS" in L or "UNSPLASH" in L or "PIXABAY" in L


# ------------------------------------------------------------- busca / download
def search(query: str, provider: str = "pexels", orientation: str = "portrait", color: str | None = None,
           per_page: int = 12, page: int = 1, only_safe: bool = True) -> list[dict]:
    q = urllib.parse.quote(query)
    if provider == "pexels":
        url = f"https://api.pexels.com/v1/search?query={q}&per_page={per_page}&page={page}&orientation={orientation}"
        if color:
            url += f"&color={urllib.parse.quote(color)}"
        res = norm_pexels(_json(url, {"Authorization": _need("pexels")}))
    elif provider == "unsplash":
        o = {"portrait": "portrait", "landscape": "landscape", "square": "squarish"}.get(orientation, "portrait")
        url = f"https://api.unsplash.com/search/photos?query={q}&per_page={per_page}&page={page}&orientation={o}"
        if color:
            url += f"&color={urllib.parse.quote(color)}"
        res = norm_unsplash(_json(url, {"Authorization": f"Client-ID {_need('unsplash')}"}))
    elif provider == "pixabay":
        o = {"portrait": "vertical", "landscape": "horizontal"}.get(orientation, "all")
        url = f"https://pixabay.com/api/?key={_need('pixabay')}&q={q}&per_page={max(3, per_page)}&page={page}&orientation={o}&image_type=photo&safesearch=true"
        res = norm_pixabay(_json(url))
    elif provider == "openverse":
        asp = {"portrait": "tall", "landscape": "wide", "square": "square"}.get(orientation, "")
        url = f"https://api.openverse.org/v1/images/?q={q}&page_size={per_page}&page={page}&license_type=commercial,modification" + (f"&aspect_ratio={asp}" if asp else "")
        res = norm_openverse(_json(url))
    elif provider == "wikimedia":
        url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6"
               f"&gsrsearch={q}%20filetype:bitmap&gsrlimit={per_page}&prop=imageinfo&iiprop=url|size|extmetadata&iiurlwidth=600")
        res = norm_wikimedia(_json(url))
    else:
        raise SystemExit(f"Provedor desconhecido: {provider} ({', '.join(PROVIDERS)})")
    if only_safe:
        res = [r for r in res if safe_license(r["license"])]
    # tamanho mínimo para story 1080 de largura
    return [r for r in res if (r["w"] or 9999) >= 1000 or provider == "openverse"]


def download(item: dict, dest: Path | None = None) -> Path:
    dest = Path(dest) if dest else STOCK_DIR
    dest.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(urllib.parse.urlparse(item["url"]).path)[1].lower()
    ext = ext if ext in (".jpg", ".jpeg", ".png", ".webp") else ".jpg"
    path = dest / f"{item['provider']}-{item['id']}{ext}"
    if not path.exists():
        path.write_bytes(_http(item["url"]))
    if item["provider"] == "unsplash" and item.get("ping"):
        try:
            _http(item["ping"], {"Authorization": f"Client-ID {_need('unsplash')}"})  # exigido pela API
        except Exception:
            pass
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {"items": []}
    ledger["items"] = [i for i in ledger["items"] if i["file"] != path.name]
    ledger["items"].append(dict(file=path.name, provider=item["provider"], id=item["id"], source_url=item.get("source_url"),
                                author=item.get("author"), license=item["license"], credit=item.get("credit"),
                                rules=PROVIDERS[item["provider"]]["rules"], downloaded=dt.date.today().isoformat()))
    STOCK_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def credits_for(files: list[str]) -> list[str]:
    """Linhas de crédito prontas para a legenda, para os arquivos usados."""
    if not LEDGER.exists():
        return []
    names = {Path(f).name for f in files}
    return [i["credit"] for i in json.loads(LEDGER.read_text())["items"] if i["file"] in names and i.get("credit")]
