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
