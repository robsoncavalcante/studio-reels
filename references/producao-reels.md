# Produção de Reels: aprendizados de campo (v4.2)

Classificação: **[BP]** boa prática de produção; **[H]** hipótese a testar; **[Oficial]** só o que veio de fonte oficial (nada abaixo é especificação oficial do Instagram). Dados de cliente não entram aqui.

## A. Zona segura de texto
- [BP] A interface (nome, legenda, áudio, tags) cobre a parte baixa. Borda inferior de qualquer texto em ≤ ~69% da altura; centro de legenda de 1–2 linhas em ~64%, de 3–4 linhas em ~58%. `qa reel` avisa (`reel-ui-zone`); legendas do motor já usam pos 64%.
- [BP] Nada de texto sobre o rosto de quem fala: meça onde termina o queixo e ponha a legenda logo abaixo. Com rosto em cena, prefira legendas de 2 linhas sequenciais (≤ ~20 caracteres por linha) a blocos de 4.
- [BP] A capa/primeiro quadro também respeita a zona segura; teste se a chamada sobrevive à interface.
- Meça a altura real renderizando quadros; não estime.

## B. Legenda literal x texto de marketing
- [H] Produza as duas versões (marketing = síntese; literal = acessibilidade, quem vê sem som, retenção) e compare. Qual rende mais é hipótese, não fato.
- [BP] Literal: cada legenda começa na 1ª palavra falada e termina quando a próxima começa (sem sobreposição); 1–2 linhas; quebra por frase/respiração; efeito de digitação no máximo ~0,5 s à frente da voz.
- [BP] Texto sem fala nem efeito sonoro "fica solto": corte-o ou dê um gancho sonoro.
- [BP] Ao reaproveitar blocos após ajuste manual, releia texto, fonte e posição de TODAS as cópias antes de reanimar.

## C. Estrutura narrativa (local/imobiliário)
- [BP] 1) gancho com locução curta sobre capa estática; 2) pessoa real falando; 3) prova/localização em B-roll acelerado com locução; 4) tela final com CTA.
- [BP] Capa: marca + chamada entram estáticas e saem animadas quando o vídeo roda; textos da abertura ficam até o fim da locução e saem em cascata, sem corte seco.
- [BP] Teto prático ~50 s. Acelere trechos de deslocamento, não a fala. Para abrir espaço à locução sem deformar a capa, divida o 1º clipe após a capa e desacelere só a 2ª parte.

## D. Áudio
- [BP] Limpeza: `studio.py audio clean voz.wav` (corta ruído antes da 1ª palavra com folga ~0,1 s e ~0,15 s depois da voz; fade 0,03 s entrada / 0,13 s saída; `afftdn` moderado; ~-20 LUFS). Redução de ruído só se confirma de ouvido; confira pico com `audio levels` (acima de -1 dBFS = baixar).
- [BP] Referências: locução ~-20 LUFS; pessoa em cena ~-22 LUFS (locução 1–3 dB acima); música 12–16 dB abaixo da voz, com ducking; SFX baixos quando coincidem com fala.
- [BP] Música: cortar/emendar em múltiplos de compasso (`audio.bar_len(bpm)`: 4/4 a 120 bpm ≈ 2,0 s), manter continuidade da fonte, fades curtos na emenda.
- [BP] Locução e fala da pessoa não se sobrepõem: 0,2–0,5 s entre elas.

## E. Tela final (CTA)
- [BP] Dado faltante (telefone, site, WhatsApp) = **PROVISÓRIO**; peça ao cliente, não invente contato.
- [BP] Se a locução diz o CTA, o título pode ser a transcrição; o botão continua como elemento de interface. Entrada escalonada (logo, linha, título, botão); texto do botão logo após o botão, perto da palavra falada.

## F. Identidade visual
- [BP] Siga o design system do cliente (cores, fonte, legenda em caixa/pill da marca). Acento forte como texto sobre foto costuma destoar: acento em blocos pequenos, texto em cor de marca/neutra.
- [BP] Destaque do trecho-chave com tamanho maior e pulso curto de escala (`--highlight`, `bscale`), sem exagerar.
- [BP] Saída suave e consistente para todos os elementos (ex.: pop e encolher, em cascata). **Não implementado no motor ainda** (hoje só há entradas animadas).

## G. Processo
- Versões A/B: duplique o projeto (original + variante).
- Leia o estado atual antes de mexer (o cliente/editor ajusta entre rodadas); audite sincronia com quadros e tempos de palavra antes de afirmar "sincronizado".
- Não salve/exporte sem aprovação explícita; relate o que NÃO foi verificado (ex.: áudio de ouvido).
- Termine com passos objetivos para o usuário. Use `templates/checklist-reel.md`.
