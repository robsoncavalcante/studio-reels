"""
Provedores de VOZ, TRILHA e SFX (além do sintetizador local de audio.py).

Cadeia automática (`--provider auto`), da melhor para a mais simples:
  voz   : elevenlabs (chave) -> kokoro (offline, grátis, Apache-2.0) -> edge (grátis, online)
  trilha: elevenlabs (chave) -> arquivo importado (Magnific/Lyria/Suno etc.) -> jamendo/openverse -> sintetizador local
  sfx   : elevenlabs (chave) -> freesound (chave, CC0) -> pacote em library/audio/sfx -> sintetizador local

Chaves por variável de ambiente (nunca grave chaves em arquivos):
  ELEVENLABS_API_KEY  (opcional ELEVENLABS_VOICE_ID)   FREESOUND_API_KEY   JAMENDO_CLIENT_ID
Sem rede/chaves o motor continua funcionando: Kokoro roda 100% offline e o resto cai para o sintetizador local.

Licenças (resumo; confira sempre no momento do uso):
  ElevenLabs plano grátis = 10 mil créditos/mês e SEM licença comercial (serve para teste; trabalho de cliente exige plano pago).
  Kokoro = Apache-2.0 (uso comercial livre). Edge TTS = serviço online gratuito não oficial, sem garantia de licença.
  Freesound = filtrado para CC0 aqui. Openverse = filtrado para uso comercial. Jamendo = verifique a licença de cada faixa.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = Path(os.environ.get("STUDIO_REELS_MODELS", Path.home() / ".cache" / "studio-reels" / "models"))
CREDITS = ROOT / "library" / "audio" / "credits.json"
KOKORO_URLS = {
    "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}
KOKORO_VOICES_PT = {"pf_dora": "feminina", "pm_alex": "masculina", "pm_santa": "masculina (grave)"}
EDGE_VOICES_PT = {"pt-BR-FranciscaNeural": "feminina", "pt-BR-AntonioNeural": "masculina", "pt-BR-ThalitaMultilingualNeural": "feminina (jovem)"}
EL_DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # voz pré-definida da biblioteca ElevenLabs; troque por ELEVENLABS_VOICE_ID


class ProviderError(RuntimeError):
    pass


# ------------------------------------------------------------------ util
def _have(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def _http(method, url, *, headers=None, json_body=None, params=None, timeout=120, stream_to=None):
    try:
        import requests
    except Exception as e:  # pragma: no cover
        raise ProviderError("instale 'requests' (pip install requests)") from e
    try:
        r = requests.request(method, url, headers=headers, json=json_body, params=params, timeout=timeout)
    except Exception as e:
        raise ProviderError(f"sem acesso a {url.split('/')[2]}: {type(e).__name__}") from e
    if r.status_code >= 400:
        raise ProviderError(f"{url.split('/')[2]} respondeu {r.status_code}: {r.text[:200]}")
    if stream_to:
        Path(stream_to).write_bytes(r.content)
        return Path(stream_to)
    return r


def _to_wav(src, dst, sr=44100):
    dst = Path(dst)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ar", str(sr), "-ac", "2", str(dst)], check=True)
    return dst


def log_credit(entry: dict):
    CREDITS.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(CREDITS.read_text(encoding="utf-8")) if CREDITS.exists() else []
    entry["date"] = time.strftime("%Y-%m-%d")
    data.append(entry)
    CREDITS.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def status() -> list[dict]:
    """Lista o que está disponível AGORA neste ambiente."""
    k_ok = all((MODELS / f).exists() for f in KOKORO_URLS)
    return [
        dict(id="kokoro", kind="voz", ok=_have("kokoro_onnx"), note=("modelo baixado" if k_ok else "modelo (350 MB) baixa sozinho do GitHub no 1º uso") + " · offline · Apache-2.0 · pt-BR: " + ", ".join(KOKORO_VOICES_PT)),
        dict(id="edge", kind="voz", ok=_have("edge_tts"), note="Microsoft Edge TTS, grátis, precisa de internet · " + ", ".join(EDGE_VOICES_PT)),
        dict(id="elevenlabs", kind="voz/trilha/sfx", ok=bool(os.environ.get("ELEVENLABS_API_KEY")), note="defina ELEVENLABS_API_KEY · plano grátis sem licença comercial"),
        dict(id="freesound", kind="sfx", ok=bool(os.environ.get("FREESOUND_API_KEY")), note="defina FREESOUND_API_KEY (grátis) · só CC0"),
        dict(id="jamendo", kind="trilha", ok=bool(os.environ.get("JAMENDO_CLIENT_ID")), note="defina JAMENDO_CLIENT_ID (grátis) · confira a licença de cada faixa"),
        dict(id="openverse", kind="trilha/sfx", ok=True, note="sem chave · Creative Commons de uso comercial · precisa de internet"),
        dict(id="magnific", kind="voz/trilha/sfx", ok=False, note="via conector do Claude (audio_tts, audio_music_generate, audio_sfx_generate): gere lá, baixe o arquivo e use `audio import`"),
        dict(id="local", kind="trilha/sfx", ok=True, note="sintetizador do motor (audio.py): sempre disponível, qualidade de demonstração"),
    ]


# ------------------------------------------------------------------ VOZ
def _kokoro_models():
    MODELS.mkdir(parents=True, exist_ok=True)
    for name, url in KOKORO_URLS.items():
        p = MODELS / name
        if p.exists() and p.stat().st_size > 1_000_000:
            continue
        print(f"  baixando {name} (uma vez só) …")
        r = _http("GET", url, timeout=600)
        p.write_bytes(r.content)
    return MODELS / "kokoro-v1.0.onnx", MODELS / "voices-v1.0.bin"


def tts_kokoro(text, out, voice="pf_dora", speed=1.0, lang="pt-br"):
    if not _have("kokoro_onnx"):
        raise ProviderError("pip install kokoro-onnx soundfile")
    import soundfile as sf
    from kokoro_onnx import Kokoro
    model, voices = _kokoro_models()
    k = Kokoro(str(model), str(voices))
    samples, sr = k.create(text, voice=voice, speed=speed, lang=lang)
    sf.write(str(out), samples, sr)
    return Path(out)


def tts_edge(text, out, voice="pt-BR-FranciscaNeural", speed=1.0, **_):
    if not _have("edge_tts"):
        raise ProviderError("pip install edge-tts")
    import edge_tts
    rate = f"{int(round((speed - 1) * 100)):+d}%"

    async def run():
        await edge_tts.Communicate(text, voice, rate=rate).save(str(out))
    try:
        asyncio.run(run())
    except Exception as e:
        raise ProviderError(f"Edge TTS indisponível: {type(e).__name__}") from e
    return Path(out)


def tts_elevenlabs(text, out, voice=None, speed=1.0, stability=0.5, similarity=0.75, model="eleven_multilingual_v2", **_):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise ProviderError("defina ELEVENLABS_API_KEY")
    vid = voice or os.environ.get("ELEVENLABS_VOICE_ID") or EL_DEFAULT_VOICE
    r = _http("POST", f"https://api.elevenlabs.io/v1/text-to-speech/{vid}", params={"output_format": "mp3_44100_128"},
              headers={"xi-api-key": key}, json_body=dict(text=text, model_id=model, voice_settings=dict(stability=stability, similarity_boost=similarity, speed=speed)))
    Path(out).write_bytes(r.content)
    return Path(out)


def tts(text: str, out, provider="auto", voice=None, speed=1.0, lang="pt-br") -> tuple[Path, str]:
    """Gera a locução. Retorna (arquivo, provedor usado). Em `auto` tenta a cadeia até um funcionar."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    chain = ["elevenlabs", "kokoro", "edge"] if provider == "auto" else [provider]
    errs = []
    for p in chain:
        try:
            if p == "elevenlabs":
                f = tts_elevenlabs(text, out.with_suffix(".mp3"), voice=voice, speed=speed)
            elif p == "kokoro":
                f = tts_kokoro(text, out.with_suffix(".k.wav"), voice=voice or "pf_dora", speed=speed, lang=lang)
            elif p == "edge":
                f = tts_edge(text, out.with_suffix(".mp3"), voice=voice or "pt-BR-FranciscaNeural", speed=speed)
            else:
                raise ProviderError(f"provedor de voz desconhecido: {p}")
            wav = _to_wav(f, out.with_suffix(".wav"))
            if f != wav:
                f.unlink(missing_ok=True)
            log_credit(dict(kind="voz", provider=p, voice=voice, chars=len(text), file=str(wav)))
            return wav, p
        except ProviderError as e:
            errs.append(f"{p}: {e}")
            if provider != "auto":
                raise
    raise ProviderError("nenhum provedor de voz funcionou:\n  " + "\n  ".join(errs) + "\nAlternativa: gere a voz no Magnific/ElevenLabs e use `audio import --kind voice`.")


# ------------------------------------------------------------------ TRILHA / SFX por IA
def music_elevenlabs(prompt, out, dur=30, instrumental=True):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise ProviderError("defina ELEVENLABS_API_KEY")
    body = dict(prompt=prompt + (" Instrumental, sem vocais." if instrumental else ""), music_length_ms=int(dur * 1000))
    r = _http("POST", "https://api.elevenlabs.io/v1/music", params={"output_format": "mp3_44100_128"}, headers={"xi-api-key": key}, json_body=body, timeout=300)
    Path(out).write_bytes(r.content)
    return Path(out)


def sfx_elevenlabs(prompt, out, dur=2.0, influence=0.3):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise ProviderError("defina ELEVENLABS_API_KEY")
    r = _http("POST", "https://api.elevenlabs.io/v1/sound-generation", params={"output_format": "mp3_44100_128"}, headers={"xi-api-key": key},
              json_body=dict(text=prompt, duration_seconds=dur, prompt_influence=influence))
    Path(out).write_bytes(r.content)
    return Path(out)


def gen_music(prompt, out, dur=30, provider="auto"):
    """Trilha por IA (ElevenLabs). Magnific/Lyria roda pelo conector do Claude (veja `audio brief`)."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if provider not in ("auto", "elevenlabs"):
        raise ProviderError("trilha por IA direta no motor: elevenlabs. Para Magnific/Lyria use o conector e `audio import`.")
    f = music_elevenlabs(prompt, out.with_suffix(".mp3"), dur)
    wav = _to_wav(f, out.with_suffix(".wav"))
    log_credit(dict(kind="trilha", provider="elevenlabs", prompt=prompt, file=str(wav)))
    return wav, "elevenlabs"


def gen_sfx(prompt, out, dur=2.0, provider="auto"):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    chain = ["elevenlabs", "freesound"] if provider == "auto" else [provider]
    errs = []
    for p in chain:
        try:
            if p == "elevenlabs":
                f = sfx_elevenlabs(prompt, out.with_suffix(".mp3"), dur)
            else:
                f = fetch("sfx", prompt, out.with_suffix(".mp3"), provider="freesound")[0]
            wav = _to_wav(f, out.with_suffix(".wav"))
            log_credit(dict(kind="sfx", provider=p, prompt=prompt, file=str(wav)))
            return wav, p
        except ProviderError as e:
            errs.append(f"{p}: {e}")
    raise ProviderError("nenhum provedor de SFX funcionou:\n  " + "\n  ".join(errs))


# ------------------------------------------------------------------ bancos livres (busca + download)
def fetch(kind: str, query: str, out, provider="auto", n=1) -> tuple[Path, dict]:
    """Busca e baixa 1 faixa/efeito livre. Registra licença/autor em library/audio/credits.json."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    chain = {"music": ["jamendo", "openverse"], "sfx": ["freesound", "openverse"]}[kind] if provider == "auto" else [provider]
    errs = []
    for p in chain:
        try:
            if p == "freesound":
                key = os.environ.get("FREESOUND_API_KEY")
                if not key:
                    raise ProviderError("defina FREESOUND_API_KEY")
                r = _http("GET", "https://freesound.org/apiv2/search/text/", params=dict(
                    query=query, token=key, page_size=n, fields="id,name,username,license,previews,duration",
                    filter='license:"Creative Commons 0" duration:[0.2 TO 8]')).json()
                if not r.get("results"):
                    raise ProviderError("nada encontrado")
                it = r["results"][0]
                _http("GET", it["previews"]["preview-hq-mp3"], stream_to=out)
                meta = dict(provider=p, title=it["name"], author=it["username"], license="CC0", url=f"https://freesound.org/s/{it['id']}/")
            elif p == "jamendo":
                cid = os.environ.get("JAMENDO_CLIENT_ID")
                if not cid:
                    raise ProviderError("defina JAMENDO_CLIENT_ID")
                r = _http("GET", "https://api.jamendo.com/v3.0/tracks/", params=dict(
                    client_id=cid, format="json", limit=n, search=query, audioformat="mp32", include="musicinfo", order="popularity_month")).json()
                if not r.get("results"):
                    raise ProviderError("nada encontrado")
                it = r["results"][0]
                _http("GET", it["audio"], stream_to=out)
                meta = dict(provider=p, title=it["name"], author=it["artist_name"], license=it.get("license_ccurl", "ver página"), url=it.get("shareurl", ""),
                            warn="Jamendo grátis costuma ser não comercial: confirme a licença antes de usar em cliente")
            elif p == "openverse":
                kind_ = "audio"
                r = _http("GET", f"https://api.openverse.org/v1/{kind_}/", params=dict(q=query, license_type="commercial", page_size=n,
                                                                                    category="music" if kind == "music" else "sound_effect")).json()
                if not r.get("results"):
                    raise ProviderError("nada encontrado")
                it = r["results"][0]
                _http("GET", it["url"], stream_to=out)
                meta = dict(provider=p, title=it.get("title"), author=it.get("creator"), license=f"{it.get('license')} {it.get('license_version', '')}".strip(),
                            url=it.get("foreign_landing_url", ""), attribution=it.get("attribution", ""))
            else:
                raise ProviderError(f"provedor desconhecido: {p}")
            meta.update(kind=kind, query=query, file=str(out))
            log_credit(meta)
            return out, meta
        except ProviderError as e:
            errs.append(f"{p}: {e}")
    raise ProviderError("busca sem resultado:\n  " + "\n  ".join(errs))


# ------------------------------------------------------------------ importação (Magnific, Suno, ElevenLabs web, etc.)
def import_file(src, kind: str, out=None, trim_silence=True, name=None) -> Path:
    """Normaliza qualquer áudio baixado de fora (mp3/wav/m4a) para WAV 44,1 kHz estéreo, sem silêncio nas pontas."""
    src = Path(src)
    if not src.exists():
        raise ProviderError(f"arquivo não encontrado: {src}")
    out = Path(out) if out else ROOT / "library" / "audio" / kind / f"{name or src.stem}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    af = []
    if trim_silence:
        af.append("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src)]
    if af:
        cmd += ["-af", ",".join(af)]
    cmd += ["-ar", "44100", "-ac", "2", str(out)]
    subprocess.run(cmd, check=True)
    log_credit(dict(kind=kind, provider="importado", origin=str(src), file=str(out)))
    return out


def duration(path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0
