# Protocolo do Conselho Criativo

Os agentes são **papéis** executados por Claude (ou subagentes) seguindo este protocolo. O código (`studio.py council`, `qa`) faz as verificações determinísticas e o build; o julgamento criativo vem dos papéis. Não são processos autônomos.

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
