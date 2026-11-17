# Cenários de teste da skill (para rodar com Claude)
Cada cenário diz o pedido, o que a skill deve fazer e como julgar.

1. **Reel com vídeo do cliente**: "Monte um reel com este clipe do embaixador (corte do 3º segundo, volume 100%) e 2 fotos." → usa `photos` com objeto `{src,start,volume}`; áudio do clipe na mixagem com ducking; confere quadros.
2. **Legenda literal x marketing**: "Decida entre legenda de marketing e transcrição literal." → produz as duas, trata qual rende mais como hipótese a testar, legenda literal em 1–2 linhas sem sobreposição.
3. **Texto na zona da interface**: "Revise este Reels com texto na parte baixa." → roda `qa reel`, aponta `reel-ui-zone`, sobe o texto para ≤ ~69% e mede em quadros renderizados; classifica como boa prática.
4. **Dados do ano**: "Faça uma cena de crescimento 2023–2026." → escolhe `chart-bars`/`chart-line`, não inventa números, pede os valores que faltam.
5. **Voz e música**: "Gere a locução e a trilha." → usa `audio providers`, nunca o sintetizador local como entrega, `audio clean`, `audio levels`, música 12–16 dB abaixo, créditos registrados.
6. **Aprovação rápida**: "Quero ver antes de renderizar." → `--preview` (432×768, 15 fps) e só depois o render final.
7. **Cortar fala**: "Tire silêncios e 'ahn'." → `autocut --words` (SRT) ou `--transcribe`; avisa que sem transcrição só corta silêncio.
8. **Plugin de terceiros**: "Copie os presets do plugin X." → recusa copiar presets/código, mapeia categorias e cria equivalentes originais.
