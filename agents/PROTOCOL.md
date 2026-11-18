# Protocolo do Conselho Criativo

Os agentes são **papéis** executados por Claude (ou subagentes) seguindo este protocolo. O código (`studio.py council`, `qa`) faz as verificações determinísticas e o build; o julgamento criativo vem dos papéis. Não são processos autônomos.

## PORTÃO OBRIGATÓRIO (v5.1) — vale para toda peça: arte, post, carrossel, story, reel, vídeo de site
Nenhuma peça é entregue sem passar pelos agentes. O motor roda o **portão** sozinho em `render`, `carousel`, `reel` e `council build`:
mede (contraste, corte, fontes, logo visível, paleta, texto duplicado/truncado, print usado como foto) e grava em `<peça>.agentes/`
(`CHECKLIST.md`, `gate.json`, folhas de contato, `parecer.modelo.json`). A partir daí:
1. Quem executa (Claude) **abre as folhas com Read**, responde as perguntas de cada especialista e preenche `parecer.json`
   (`veredito` ok|refazer, `visto` com as folhas realmente abertas, `notas` P0/P1/P2; `diretor`: decisao `aprovar`, nota ≥ 8.0).
2. Bloqueio medido ou P0 → corrigir e renderizar de novo (máx. 3 rodadas).
3. `python studio.py agentes <saída>` valida (código de saída 2 = pendente); `python studio.py entregar <saída>` só copia a peça
   se estiver aprovada e **sem alteração depois do parecer** (sha256). Entregar sem isso é falha de processo.
`STUDIO_PORTAO=off` existe só para testes/galeria; nunca em trabalho de cliente.

## Regras duras (valem para todos)
1. **Sem imagem gerada por IA** e sem "cara de template de IA" (degradê genérico, ícones decorativos aleatórios, texto cliché). Fotos reais de bancos gratuitos (`studio.py stock`) ou do cliente; licença em `library/stock/credits.json`.
2. Placeholder de foto não passa em entrega final.
3. `studio.py qa` sem nenhum **bloqueio**; avisos justificados.
4. Contraste ≥4.5:1 (texto corpo) / ≥3:1 (grande); fonte ≥32px em 1080; safe zones respeitadas.
5. Máx. 2 famílias tipográficas; 1 ideia por slide; 1 movimento principal por cena.
6. Copy com promessa, preço, saúde, finanças → passar por `publicidade-legal-br`.

## Pasta de trabalho
`studio.py council init <pasta> --name "Cliente" --brief "…" --kind carousel|reel|static` cria a pasta com `brief.json`, `thread.md`, `spec.json`, `scorecard.json` e `v1/`, `v2/`…

## Referências de estilo
Fichas em `library/styles/*.json` (ex.: thiago-rodrigues). Servem de princípios — não copiar marca, logos, textos ou artes de terceiros. Temas derivados: `ref-*` (library/themes/refs.json).

## Rodadas
0. **Planejamento** — o Planejador de Projeto (`agents/project-planner.md`) escreve `plano.md`, escolhe a ficha de estilo (`library/styles/`) e o tema base, e define ordem e dependências.
1. **Brief** — Diretor lê o brief (objetivo, público, marca, formato, prazo). Faltou algo essencial → 1 pergunta ao cliente; senão assume e registra a suposição no thread.
2. **Propostas em paralelo** — estrategista, social, redator, arte, imagem, cor, tipografia, motion, som escrevem no `thread.md` (formato de cada papel).
3. **Conversa cruzada** — cada especialista lê os outros e responde com `@colega → pedido`. Conflitos típicos: redator × tipógrafo (texto longo), cor × imagem (foto fora da paleta), motion × som (BPM/cortes), social × arte (gancho × estética).
4. **Síntese** — Diretor resolve conflitos, escreve `spec.json` (layout/receita, tema, pair, brand, conteúdo, motion, audio, fotos).
5. **Build** — `studio.py council build <pasta>` renderiza `vN/` e roda o QA automático (`qa.json`).
6. **Crítica** — acessibilidade, composição e cada especialista avaliam `vN` (olhar a imagem renderizada, não só o spec). Preenchem `scorecard.json` (0–10 por critério: gancho, hierarquia, tipografia, cor, imagem, composição, motion, som, legibilidade, aderência à marca).
7. **Veredito do Diretor** — lista inconsistências **por especialista** ("@typographer: título quebra em 3 linhas curtas"), nota geral e decisão: `aprovar` | `refazer`.
8. **Refazer** — só os apontados refazem; novo `vN+1`. **Máximo 3 rodadas**; se na 3ª ainda houver bloqueio, o Diretor entrega a melhor versão com as pendências listadas.
9. **Entrega final** — parecer curto (o que foi decidido e por quê), arquivos, créditos de imagem/áudio, limites.

## Critério de aprovação do Diretor
Nota geral ≥ 8,0; nenhum critério < 6; QA sem bloqueios; sem placeholder; coerência entre peças da mesma campanha (mesma paleta, pair e linguagem de movimento).

## Integração com as skills existentes
- `creative-department-ai`: diagnóstico colaborativo, direção criativa, memória por cliente, Creative Review.
- `publicidade-legal-br`: compliance antes da aprovação final.


## Formato de revisão (P0/P1/P2)
Nenhuma nota de 0 a 10: uma nota que só dá número não aponta o que consertar. Cada problema vira uma linha:
`P? · t=4.2s · onde · problema → mudança exata · fica: o que não muda`
- **P0** quebra a leitura ou o contrato (ilegível, errado, quebrado, «cara de gerado» no plano principal) — sempre corrigir.
- **P1** enfraquece (trecho parado, payoff mole, emenda que pula) — corrigir os que valem o tempo.
- **P2** acabamento.
Rodar `python studio.py qa review reel.timeline.json --video reel.mp4`: gera `revisao/` com as folhas de contato (cenas, cortes, celular 360 px) e o `REVIEW.md` com as medições (leitura mínima, trecho parado > 3 s, primeiro quadro preto, última cena curta). Depois da medição, o Diretor de Arte descreve cada quadro de beat como um estranho, uma frase por quadro; objeto que precisa de explicação é P0. Corrigir texto primeiro, depois tempo, depois detalhe; refazer a folha só do que mudou, uma vez.


## v5.2 — Diretor de Movimento e material real do site
- `studio.py site <url>` agora baixa **vídeos, imagens e ícones** do site (`midia/`) e monta cenas `site-video`, `site-showcase` (vitrine 3D) e `site-icons` (ícones que pulsam, foco um a um).
- O **clima** (trilha, tom, transições, ritmo) é decidido por `site.pick_clima` a partir da marca e do material; `--clima` força outro.
- Câmera 3D por cena (`--camera`), foco sequencial dos itens e ícones animados são determinísticos (`__seek(t)`).
- O motion-designer escreve a lista de planos e passa o placar de crítica (8 critérios, 3 rodadas) antes do parecer.

## v5.4 — Fidelidade ao site (reel feito a partir de URL)

Regra: **o storyboard é o site**. Quem decide a identidade é o que foi capturado (`tela-NN.png`, `site.json`, `midia/`), nunca o modelo da casa.

1. Antes de qualquer parecer, abrir `sheet_telas_do_site.png` e as folhas do reel lado a lado. Se o reel parece o mesmo template de outra marca com as cores trocadas → `refazer`.
2. Checar a captura: `storyboard.md` → “Avisos da captura”. Título/h1 vazio, texto de erro (“Hubo un error…”), cor de erro como acento ou zero fotos/vídeos = **captura inválida**: refazer `studio.py site` (outra rede, ou fornecer a mídia), não produzir em cima.
3. Cada cena do reel cita a seção/tela de origem. Cena sem origem no site (texto ou mídia inventada) é cortada.
4. Mídia real primeiro: vídeo/foto do hero abre o reel; fotos dos cartões viram vitrine 3D; ícones do próprio site acendem/pingam; estatísticas do site viram números animados. Sem foto de banco quando o site tem a sua.
5. Variar por marca, não por sorteio: clima (trilha, transições, ritmo), layouts e câmera saem do que o site é (cores, densidade de mídia, tom do texto). Dois sites diferentes não podem sair com a mesma sequência de layouts.
6. O gate bloqueia automaticamente: captura sem título, aviso de captura sem mídia, reel que ignorou a mídia colhida. O parecer ainda precisa comparar visualmente com as telas.

## v6 — Partido visual (cada marca com a sua cara)

Regra: **o mesmo motor não pode entregar o mesmo vídeo com cores trocadas.** O Diretor de Arte decide como montar, em 3 níveis:

1. **Marca** → consistência. A mesma marca repete a mesma *linguagem visual* (memória em `library/history.json`): cores, tipografia real do site (`fontes/`), pele (raios, caixa-alta, peso) e família de layouts.
2. **Marcas diferentes** → linguagens diferentes. `studio.py site` escolhe entre `cards3d` (mídia em cartões 3D), `poster` (tipografia gigante), `editorial` (capa de revista, molduras) e `modular` (grade/passos) a partir de sinais do site (serifa, caixa-alta/peso, escuro/claro, quantidade de mídia, botões redondos/retos, nº de ofertas). Se as duas últimas peças de outras marcas já usaram a mesma, o motor sugere a segunda melhor.
3. **Peças da mesma marca** → variação. `--variante N` troca o layout dentro da linguagem; o portão avisa `reel-repetido` se a sequência de layouts repete a de outra peça.

Antes de montar/aprovar, o Diretor de Arte lê `partido.md` (por quê, pontuação, sequência, repetição), confirma ou troca (`--linguagem`, `--variante`) e escreve no `parecer.json` o campo **`partido_visual`** (1 linha: linguagem + por que serve a esta marca + o que a diferencia das outras). Sem essa linha a entrega não libera.
