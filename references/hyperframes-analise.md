# HyperFrames × Studio Reels — análise comparativa

Fonte: github.com/heygen-com/hyperframes (Apache-2.0, commit 81d73d2, nov/2026). Estudamos ideias e regras de ofício; não copiamos código. Se algo for portado literalmente, manter aviso de licença Apache-2.0.

## 1. O que é o HyperFrames

Framework Node que renderiza HTML + GSAP em MP4 de forma determinística (pausa a timeline e captura quadro a quadro, igual ao nosso `__seek`). Vem com: CLI (`init/check/snapshot/preview/render/transcribe/beats/media-treatment`), app desktop "Studio" de edição, ~210 blocos prontos (registry), 3 temas com contrato de 18 tokens, linter com regras próprias, e 9 skills para agentes (hyperframes, cli, registry, media-use, reverse-any-video, style-sampling, figma, slideshow, remotion-to-hyperframes). Partes Pro/pagas: reverse-any-video, style-sampling, modelos HeyGen.

## 2. Mesma base, escolhas diferentes

| Tema | HyperFrames | Studio Reels |
|---|---|---|
| Renderização | HTML+GSAP, seek por quadro, Node | HTML/CSS+Jinja, `__seek`, Python+Playwright+ffmpeg |
| Peças | filmes horizontais/verticais, explainers, launch | reels/stories/posts/carrosséis de Instagram (foco do negócio) |
| Marca | 3 temas, tokens `--bg --fg --brand --accent --accent-2 --surface --border --radius --space-* --dur-beat --ease-*` | `--brand`/temas por empresa, charts por CSS vars |
| Edição | Studio desktop + `data-var-*` editáveis | `content.json` + Premiere XML/EDL |
| Corte automático | não tem | autocut (silêncio, filler, câmera, legendas curtas) |
| Qualidade | `check` (lint) + `snapshot --review` + REVIEW.md P0/P1/P2 | QA determinístico + conselho de 14 agentes |
| Áudio | catálogo HeyGen, regras de efeitos por causa | procedural + `tidy_sfx` + loudnorm |
| Catálogo | ~210 blocos | layouts × temas × 41 movimentos × transições |

Conclusão: nosso motor é mais completo para Instagram e para edição (autocut, Premiere, council). O HyperFrames é mais forte em **método de revisão**, **regras de ofício medidas**, **biblioteca de blocos** e **captura de site**.

## 3. O que vale absorver (priorizado)

### A. Alto valor, esforço baixo/médio
1. **`qa review` — contact sheets** (de `snapshot --review`): folha por cena (início + meio), faixa em torno de cada corte (−0.2 s…+0.2 s) e quadros de beat em 360 px de largura (leitura no celular). Ffmpeg + PIL; nenhum novo componente.
2. **Checagens medidas de ofício** no QA: `line_unread` (leitura mínima ≈ 0.5 s + 0.3 s/palavra; última linha ≥ 2 s), `dead_stretch` (> 3 s sem mudança visual), texto < 2,6% do menor lado, zonas seguras 9:16 (topo ~168 px e rodapé ~590 px livres de texto), conteúdo dentro de 90% e texto-título dentro de 80%.
3. **Notas de revisão P0/P1/P2** em uma linha: `t=4.2s · onde · problema → mudança exata · o que fica`. Substitui nota 0–10. Entra no `agents/PROTOCOL.md` e gera `REVIEW.md` por peça.
4. **Guardas de legenda**: descartar palavras que o Whisper inventa em silêncio final (`silencedetect -35 dB`, fala real fica entre −16 e −26 dB); falhar a transcrição se > 20% tokens `♪`/`�`; nunca legenda no t=0 exato (começar 0,1–0,3 s); grupo sempre termina com "hard kill"; fundo claro/escuro decide blend ou scrim.
5. **Receita de movimento por papel**: chegada com ease longo (`expo.out`), câmera/flood `inOut`, saída acelerada `in`; saídas 40–50% mais curtas que entradas; sobreposição de 30–50%; título pousado fica parado; blur por velocidade (6–12 px texto, 15–20 px tela cheia); beat grid calculado por índice (sem acumular arredondamento). Vira constantes em `engine/motion` + checklist de "cara de gerado" (loops de respiração, título que continua deslizando).

### B. Alto valor, esforço médio/alto
6. **Motion blur real no render** (`data-motion-blur`): média de N sub-quadros em movimentos rápidos. Salto de qualidade perceptível; custa tempo de render (opcional, `--blur`).
7. **Transições com causa** (tabela do `motion.md`): zoom através de botão, objeto vira mundo, morph de contêiner, whip, iris a partir do clique, dip cut (escurece 40% por 3 quadros), blur swap. Regra: 3–5 tipos por peça, no máx. 1/3 das emendas em corte seco.
8. **Site → vídeo** (`capture <url>`): screenshot full-page 1x com sticky/fixed estáticos, tokens da marca (acento = cor que mais se repete; azul de link e vermelhos/verdes de status nunca são acento; fontes de ícone nunca são display), fontes e logo. Para a agência é ouro: todo cliente tem site. Proposta: `studio.py site <url>` → `brand.json` + screenshots + scroll-reel pronto.
9. **Biblioteca de blocos portáveis** (sem marca de terceiros): estilos de legenda (kinetic-slam, pill-karaoke, glitch-rgb, weight-shift, clip-wipe, neon, emoji-pop, gradient-fill), lower thirds (12 `lt-*`), before/after wipe, comparison-split, count-up, anel de progresso, news ticker, split-flap, mapa (criar **mapa do Brasil**, pois o deles é EUA/mundo), CTA close. Reescrever em CSS/`__seek` próprio.
10. **Som por causa**: efeito só com causa visível (clique, whoosh em corte, tick de digitação, pop de número, riser uma vez no payoff); pico do SFX 1 quadro depois da imagem; 3–6 dB acima da cama; alternar 2–3 takes; −1 dBTP e −16…−14 LUFS. Complementa `tidy_sfx`.

### C. Processo
11. **3 storylines em palavras antes de construir** + `SPEC.md`/`STORYBOARD.md`; cliente escolhe. Já cabe na Fase "propostas" do council.
12. **Reverse de referência** (ideia do `reverse-any-video`, versão leve): `studio.py analisar <video>` → cortes, duração de planos, paleta, banda de legenda e ritmo, gerando `spec.json` para recriar. Útil quando ele mandar exemplos. A comparação quadro a quadro (`diff --at`) serve de QA da recriação.
13. **Contrato de tokens**: alinhar nossos temas às 18 variáveis (`--surface`, `--border`, `--dur-beat`, `--ease-standard`, `--ease-emphasis`) para os layouts serem trocáveis por marca sem retoque.

### D. Não vale
- Studio desktop, nuvem/Lambda/Cloud Run, HeyGen/avatar/vozes (pagos, dependência de conta), style-sampling (Pro, estilos de canais de terceiros), 3D/shaders pesados (já decidimos pular), blocos com UI de marcas (ChatGPT, X, Reddit, TikTok, Spotify, macOS): risco de marca.

## 4. Ordem sugerida
1. A1–A5 (revisão em folhas + checagens + guardas de legenda + constantes de movimento)
2. B8 (site → marca/reel) e B9 (blocos: legendas, lower thirds, mapa do Brasil)
3. B6/B7 (motion blur e transições com causa)
4. C12 (analisar referência) quando chegarem os exemplos
