# Studio Reels — biblioteca local de modelos (Reels · Stories · Posts · Carrosséis)

Motor local: **layouts (HTML) × temas (JSON) × movimentos (CSS)** → PNG / MP4. Sem app, sem assinatura.

## Instalar
    pip install -r requirements.txt && playwright install chromium   # + ffmpeg para reels
    python studio.py doctor

## Usar
    python studio.py gallery                       # abre gallery/index.html (3.080 miniaturas)
    python studio.py list layouts | themes | carousels | reels | motions | bridges
    python studio.py render   --layout polaroid-stack --theme film-35mm --format story --content examples/conteudo-exemplo.json
    python studio.py carousel --recipe dicas --theme brand-dark --format post --bridge auto --content examples/conteudo-exemplo.json
    python studio.py reel     --recipe promo-4 --theme neon-night --motion pop --bpm 120 --audio musica.mp3
    python studio.py brand --name "Cliente" --handle @cliente --accent "#ff3d00" --bg "#0d0d0d"   # depois: --brand cliente --theme brand-dark

Sem `--content` os modelos mostram texto de exemplo. Fotos: `"photos": ["a.jpg","b.jpg"]` (vídeos .mp4 também entram nos slots). Use `*palavra*` para destacar.

## Aumentar a biblioteca
- **Novo tema:** acrescente um objeto em `library/themes/*.json` (cores, fontes, efeito de título, decor, moldura de foto).
- **Novo layout:** crie `library/layouts/<id>.html.j2` + entrada em `library/layouts.json`. Use unidades `cqw` para funcionar em 9:16, 4:5, 1:1 e 3:4.
- **Novo movimento:** keyframes em `engine/motions.css` + `library/motions.json`.
- **Nova receita** de carrossel/reel: `library/carousels.json` / `reels.json`.
Depois rode `python studio.py gallery` (só gera o que falta).

Os estilos são inspirados em categorias de apps como Muse e InStories (colagem, polaroid, filme, neon, Y2K, 90s…); nenhum template ou arte desses apps é copiado.


## Novidades (v2)
- **Fontes** — `studio.py fonts` (catálogo de ~99 famílias open source via Fontsource/Google Fonts, 35 pares curados, `suggest`, `check`, `specimen`; flag `--pair`).
- **Motion** — `studio.py motion` (41 movimentos do básico ao avançado, easings Penner/Material/física, `--pace --speed --stagger-scale --intensity --ease --kenburns --count-up --sync`).
- **Áudio** — `studio.py audio` (música e SFX 100% procedurais, sem direitos de terceiros; mix ≈ -14 LUFS; catálogo de fontes externas com licenças).
- **Imagens** — `studio.py stock` (Pexels/Unsplash/Pixabay com chave gratuita em PEXELS_API_KEY / UNSPLASH_ACCESS_KEY / PIXABAY_API_KEY; Openverse/Wikimedia sem chave; licenças em library/stock/credits.json). Sem imagem gerada por IA.
- **Cor** — `studio.py color` (contraste WCAG, harmonias, paleta a partir de foto, tema acessível).
- **QA** — `studio.py qa static|carousel|reel` (contraste real medido, texto cortado, palavra quebrada, safe zones, tamanho mínimo, hierarquia, loudness).
- **Conselho criativo** — `agents/` (14 especialistas + Diretor de Arte e Criação) e `agents/PROTOCOL.md`; `studio.py council init|build|status` cria a mesa, renderiza versões e roda o QA. Os agentes são papéis executados por Claude seguindo o protocolo; o QA é determinístico.

Limites honestos: busca em bancos de imagem exige internet e chave gratuita (não testada ao vivo no ambiente de desenvolvimento); a música procedural é trilha de fundo, não composição de artista.

## Referências de estilo (v2.1)
- `library/styles/thiago-rodrigues.json`: ficha de estilo extraída de 4 páginas (CSS medido) e 20 posts de Instagram (análise visual): escala tipográfica em % da largura, paletas, componentes (pager, CTA, faixa de vidro), receitas de composição, efeitos e ganchos.
- 6 temas `ref-*` (library/themes/refs.json) e fontes novas (Doto, Google Sans Flex, Geist, Geist Mono).
- Novo agente `project-planner` (Planejador de Projeto); agentes de Arte, Design, Tipografia, Imagem, Cor, Redação e Social atualizados.

## Usar em qualquer projeto (v3)
1. Anexe `studio-reels-slim.zip` ao projeto (ou deixe-o em ~/studio-reels).
2. `bash find_engine.sh` localiza (ou descompacta do zip anexado) o motor; `bash bootstrap.sh` instala dependências e roda o doctor.
3. Chame sempre `python <motor>/studio.py ...` de qualquer pasta: logos e recursos usam caminhos relativos à raiz do motor.
Marca Criative: `--brand criative --theme criative-dark|criative-light`; layouts `ds-*` e receitas `criative-*`; ícones Lucide via `icon('nome')`.

## Fonte oficial
Repositório privado: github.com/robsoncavalcante/studio-reels (branch main). Em qualquer projeto: anexe o repositório à sessão (add_repo) e rode `git clone --depth 1 https://github.com/robsoncavalcante/studio-reels ~/studio-reels && bash ~/studio-reels/bootstrap.sh`.

## Áudio profissional: voz, trilha e SFX (v4)

O sintetizador local (`audio gen`) serve só de reserva. Para áudio bom, use a cadeia de provedores:

| Necessidade | Opção grátis / offline | Opção por IA (conta/chave) |
|---|---|---|
| Locução pt-BR | **Kokoro** (offline, Apache-2.0: `pf_dora`, `pm_alex`, `pm_santa`) · Edge TTS (online) | **ElevenLabs** (`ELEVENLABS_API_KEY`) · Magnific `audio_tts` (vozes ElevenLabs/Gemini) |
| Trilha | Jamendo (`JAMENDO_CLIENT_ID`), Openverse, Pixabay/FMA (manual) | Magnific `audio_music_generate` (Lyria 3, ElevenLabs Music) · ElevenLabs Music |
| SFX | Freesound CC0 (`FREESOUND_API_KEY`), Openverse | Magnific `audio_sfx_generate` · ElevenLabs SFX |

Atenção às licenças: o plano grátis do ElevenLabs **não tem licença comercial** (serve para teste; cliente exige plano pago).

```bash
python studio.py audio providers                       # o que está disponível neste ambiente
python studio.py audio tts "Texto da locução" --out voz.wav            # auto: elevenlabs → kokoro → edge
python studio.py audio tts @roteiro.txt --provider kokoro --voice pm_alex --speed 1.05
python studio.py audio music "pop instrumental 108 bpm" --dur 60 --provider elevenlabs
python studio.py audio sfxgen "whoosh suave" --dur 1.5
python studio.py audio fetch "whoosh" --kind sfx --provider freesound   # baixa e registra licença em library/audio/credits.json
python studio.py audio brief corporate                 # prompts prontos + vozes pt-BR do Magnific
python studio.py audio import baixado.mp3 --kind music --as trilha-empapel
python studio.py reel ... --audio trilha.wav --voice voz.wav --duck 0.6   # trilha em loop, ducking sob a voz, −14 LUFS
python studio.py audio mix --video reel.mp4 --music-file trilha.wav --voice-file voz.wav   # refaz o som de um vídeo pronto
```

SFX próprios: solte `whoosh.wav`, `pop.wav`, `swipe.wav`… em `library/audio/sfx/` e eles substituem os sintéticos nos reels.
Magnific (conector do Claude): o sandbox não baixa o CDN deles; baixe o arquivo pelo Magnific (ou peça ao Claude para baixar com o computador conectado) e use `audio import`.

## Motion humanizado + legendas + export (v4)

Objetivo: sair do "visual de IA" (tudo no tempo exato, easing único) para motion graphics com cara de editor humano. Princípios próprios (não copiados de nenhum plugin): antecipação, overshoot/assentamento, follow-through, timing irregular (jitter com semente ±60 ms), câmera de mão leve, parallax por camadas, motion blur no whip, caixas/marca-texto animados.

Flags do `reel`:
- `--human` ativa jitter, drift de câmera e movimentos novos (settle, anticipate, whip, mask, stamp, rack).
- `--parallax` profundidade entre fundo/foto/texto.
- `--highlight box|marker|underline` anima o `*destaque*` do título.
- `--transition set:clean|energetic|cinematic|editorial|punch` conjuntos de transição com SFX casado.
- `--captions karaoke|pop|box|clean --script texto|@arquivo` legendas ASS queimadas (timing estimado pela fala).
- `--stems DIR` exporta cenas, stems de áudio, SRT/ASS, palavras.json, EDL CMX3600, marcadores JSON/CSV e projeto.json para Premiere/After Effects/DaVinci.

### v4.1
- 9 novas animações de texto: `bscale` `pbup` `pbdn` `blurfade` `stretch` `split` `glitch` `distort` `jump` (55 movimentos no total; prévia: `studio.py motion preview ID`).
- `studio.py autocut VIDEO --ritmo suave|ritmo|dinamico [--jcut 0.1]`: remove silêncios de vídeo falado, com J-cut opcional; grava `.cuts.json`.

### v4.2 (aprendizados de produção)
- Legendas: padrão em 2 linhas curtas (~20 car.), centro em 64% da altura; `qa reel` avisa texto abaixo de ~69% (boa prática, não regra oficial).
- `audio clean` (limpa locução, ~-20 LUFS), `audio levels` (LUFS/pico), `audio.bar_len(bpm)`.
- Guia completo: `references/producao-reels.md` e `templates/checklist-reel.md`.

## v4.3 — vídeo nas cenas, transcrição, gráficos, saída em cascata, prévia

- **Vídeo dentro das cenas**: em `photos`, use objeto `{src,start,speed,volume,loop}`. O quadro é buscado por tempo (determinístico); o áudio do clipe entra na mixagem e a música/voz abaixam (ducking).
- **Legendas reais**: `reel --words arquivo.srt|.json` (importa) ou `--transcribe` (Whisper local; precisa baixar o modelo uma vez, então rode no seu computador com internet).
- **Autocut por palavras**: `autocut --words arquivo.srt|--transcribe` remove vícios ("ahn", "né") e repetições, além dos silêncios.
- **Gráficos animados**: layouts `chart-bars`, `chart-donut`, `chart-line` (campo `items:[{title,value,text}]`). Não invente números.
- **Saída em cascata**: `--exit pop|fade|slide|drop|blur` (a última cena não sai).
- **Prévia rápida**: `--preview` (432×768, 15 fps) para aprovar antes do render final.
- `--human` agora usa mola (`spring-soft`) por padrão.
- **Testes**: `python tests/run_tests.py` (7 cenários) e `tests/cenarios.md` (cenários para rodar com Claude).

## v4.4 — lacunas do Remotion fechadas
- **Ajuste automático de texto**: além dos títulos, subtítulo, corpo, kicker e CTA encolhem sozinhos se vazarem a área segura.
- **Duração guiada pela locução**: `reel --voice voz.wav --fit-voice` distribui o tempo das cenas pelo tamanho da voz (peso = palavras da cena ou `content.say`).
- **GIF, vídeo com transparência e Lottie** nos slots de `photos`: `.gif` e `.mov` com alpha viram WebM VP9 com transparência (cache em /tmp); `.json` Lottie renderiza via lottie-web (MIT, em `library/vendor/`) e avança por tempo. Mídia com alpha entra sem moldura/fundo.

## v4.5 — Premiere e Whisper
- `--stems PASTA` agora grava também `sequencia.xml` (XML do Final Cut 7): no Premiere, File > Import abre a sequência com as cenas (V1/V2 alternadas, a sobreposição é a transição), os stems de áudio em faixas e marcadores por cena. Não foi aberto no Premiere de verdade; relate qualquer problema.
- `--transcribe` / `autocut --transcribe` aceitam faster-whisper, openai-whisper (módulo) ou o comando `whisper` do terminal. Primeiro uso baixa o modelo (internet).

## v4.6 — autocut com legendas
`python studio.py autocut video.mp4 --transcribe --captions karaoke` corta silêncios/vícios, e além do `_autocut.mp4` grava `.srt`, `.palavras.json` (tempos já na linha do tempo cortada) e `_autocut_legendado.mp4` com legenda por palavra (karaoke|pop|box|clean). As legendas começam uma nova frase a cada pausa maior que 0,5 s. Confirmado com Whisper (faster-whisper) em Mac Apple Silicon, Python 3.9.

## v4.7 — ffmpeg com legendas
O ffmpeg padrão do Homebrew (2026) não traz o filtro `ass`. `studio.py doctor` agora avisa; no Mac rode `brew install ffmpeg-full` (keg-only: o motor o detecta sozinho em /opt/homebrew/opt/ffmpeg-full). Sem o filtro, o autocut grava o .srt e explica o que fazer.

`autocut --captions` aceita `--cor "#FFD400"` (destaque), `--texto`, `--posicao 0.64`, `--tamanho 7.8`, `--fonte inter` e `--maiusculas`.

## v4.8 — câmera no autocut, legenda curta, hardware e SFX mais limpos
- `autocut --camera` alterna plano aberto (1,0) e fechado (`--zoom`, padrão 1,25) a cada corte, com aproximação lenta (`--push`, padrão 4 %) dentro de cada trecho. O plano fica em `.cuts.json`.
- `--captions curta` (autocut e reel): até 3 palavras, uma linha, entrada rápida, sem fade de saída; não termina em artigo/preposição e junta legendas relâmpago (< 0,3 s).
- `reel` ganhou `--cap-cor`, `--cap-texto`, `--cap-pos`, `--cap-tamanho`, `--cap-maiusculas` e `--vocab` (nomes para o Whisper acertar com `--transcribe`).
- `--rapido` (autocut) e `--preview` (reel) usam o codificador de hardware (`h264_videotoolbox` no Mac) quando ele existe e passa no teste; senão, libx264. O render final é sempre libx264. `STUDIO_HW=0` desliga.
- SFX: dois sons do mesmo tipo no mesmo instante viram um só (fica o mais forte) e no máximo 3 camadas por janela de 0,25 s.
- Premiere: `sequencia.xml` com áudio estéreo, taxa real e sem stems silenciosos (validado no Premiere).
Ideias vindas de luizflb/fluxo-de-edicao (MIT, a partir de LeiteZ/fluxo-de-edicao); nenhum código foi copiado.
- `autocut --min-trecho 0.5` descarta fiapos (palavra solta no começo/fim). Legenda curta não pisca mais o destaque em palavra relâmpago (< 0,14 s).
- O tamanho do quadro agora vem do ffmpeg (já com a rotação do iPhone), o que corrigiu `--camera` em MOV 4K vertical.


## v4.9 — revisão e guardas

- `python studio.py qa review reel.timeline.json --video reel.mp4 [--out pasta]`: gera `revisao/` com `sheet_cenas.png` (início + meio de cada cena), `sheet_cortes.png` (−0.2…+0.2 s em volta de cada emenda), `sheet_celular.png` (360 px) e `REVIEW.md` com notas **P0/P1/P2** (`P1 · t=4.2s · onde · problema → mudança · fica: …`).
- `qa reel` agora mede: leitura mínima por cena (`line_unread`: 1–2 palavras = 0.4 s, depois 0.5 s + 0.3 s/palavra), última cena < 2 s, primeiro quadro preto e trecho parado > 3 s (`dead_stretch`). O `.timeline.json` passa a registrar `words` por cena.
- Legendas: `captions.clean_words` descarta ♪/�/símbolos (falha se > 20% — tente `--model` maior ou `--script`), corta palavras que o Whisper inventa no silêncio final (−35 dB) e a legenda nunca nasce no 0 s exato. Fundo claro atrás da legenda (brilho da faixa > 150) liga automaticamente um scrim (caixa translúcida).
- `engine/motion.py`: `role_ease`, `exit_duration`, `overlap_start`, `hold_for`, `beat_times` (grade por índice, sem deriva) e `TELLS` (checklist «cara de gerado»); regras em `agents/motion-designer.md`, formato de revisão em `agents/PROTOCOL.md`.
- Ideias inspiradas no método de revisão do HyperFrames (Apache-2.0); implementação própria. Veja `references/hyperframes-analise.md`.

## v5.0 — site → vídeo

`python studio.py site <url> [--name "Marca"] [--render] [--rascunho] [--music faixa] [--salvar-marca]`

Abre o site (desktop 1440×900 para ler; celular 390 px para as telas 9:16), rola a página para disparar animações e contadores, esconde cookies/headers fixos e extrai:
- **marca**: acento = cor saturada que mais se repete entre papéis (botão pesa 1,5×; azul padrão de link e alertas são ignorados), fontes (fonte fora do catálogo é substituída e o aviso é impresso), logo;
- **conteúdo**: hero, serviços, números, depoimento, CTA → `content.json` com cenas planas (≤ 20 palavras por cena, duração pelo tempo de leitura);
- **telas** `tela-NN.png` + `fundo-01.png` (hero sem texto) + `logo.png`/`logo-avatar.png`.

Saída em `samples/site-<host>/` (`brand.json`, `content.json`, `site.json`). Com `--render` gera `reel.mp4` e roda o QA. Sem depender de empresa: qualquer URL.


## v5.1 — portão dos agentes obrigatório + site → vídeo fiel ao site
- **Portão dos agentes**: todo `render`/`carousel`/`reel`/`council build` mede a peça e gera `<peça>.agentes/` (checklist, folhas, parecer modelo).
  `studio.py agentes <saída>` valida o parecer; `studio.py entregar <saída> [--para pasta]` só entrega peça aprovada e inalterada.
  Bloqueios: logo invisível no fundo, fonte fora da marca, print do site usado como foto, texto duplicado. Avisos: cor fora da paleta, texto truncado, palavras coladas.
- **Logo sempre visível** (`engine/logo.py`): logo clara sobre fundo claro é recolorida só nos pixels neutros (o símbolo colorido fica); avatar quadrado só com o símbolo.
- **`studio.py site`**: lê a cor real dos títulos, caixa alta/espaçamento/raio de botão; baixa a logo original; cenas novas `site-hero`, `site-stats`, `site-list`,
  `site-cta` (texto completo, nada cortado com «…», números com rótulo, sem telas do site como foto); `--brand` usa o design system cadastrado
  (ex.: `--brand criative --theme criative-light`, hero e CTA no tema escuro par); `--handle @usuario`; música `corporate` + SFX por padrão no `--render`.
- Tema por cena: `theme` dentro de cada item de `scenes` no content.json.
