# Motion 3D (agente)

Cria clipes 3D curtos com three.js (MIT, já vendorizado) e entrega como `.mp4` para entrar no reel como cena `site-video`.
Nada para instalar: o motor, a perícia e a folha de revisão fazem parte do Studio Reels.
Inspirado no método da skill «motion-3d-por-referencia» (Felipe Borges), reescrito do zero; nenhum código ou texto dela é copiado
(o repositório dela não tem licença). Ideias e método não têm dono; arquivos têm.

## Quando entra
- O Roteirista marcou uma cena como «3D» (celular, carrossel de mídia, produto girando…), ou
- a pessoa mandou uma referência de movimento 3D (vídeo/imagem na pasta `referencias-3d/`).
Sem uma das duas, não entra: 3D só onde conta a história.

## Entradas (nesta ordem de autoridade)
1. `referencias-3d/` (o que a pessoa colocou: mp4, imagens, `links.txt`). Se houver referência, ela manda em câmera, luz, cor e ritmo.
2. `samples/<site>/midia/` e `referencias/tela-NN.png` (a matéria-prima real do cliente).
3. `brand.json` (cores e fontes). O acento da marca vira o acento do 3D.

## Fluxo
1. **Perícia (≤ 5 min).** `python3 studio.py pericia3d <referencia> --destino <pasta>/pericia`
   → `MEDIDO.md` (cor, ritmo, cortes) + `FICHA.md`. Olhe a folha de 1 quadro por segundo e **preencha a ficha**: mecanismo em uma frase,
   câmera, luz, materiais, onde está o soco, o que nunca faz, o que da referência NÃO entra. Sem ficha preenchida não se constrói.
2. **Modo.** *Fidelidade* («igual», «bem próximo»): mundo e paleta da referência medidos. *Estilo* («nesse jeito, para X»): fica o método, o mundo é da marca.
   Diga em uma linha qual entendeu.
3. **Escolha o look** em `library/looks3d.json` (o que já existe nativo vem primeiro). Look que não existe = risco: declare no storyboard.
4. **Rascunho barato** (`--width 270 --height 480 --dur 2`) e `python3 studio.py folha3d <mp4>`. **Olhe a folha antes de qualquer outra coisa.**
5. **Um render final** (1080×1920) só depois que o rascunho passar na revisão abaixo.
6. **Entrega:** o mp4 fica em `samples/<site>/3d/`; no roteiro: `"photos": ["3d/arquivo.mp4"]` no layout `site-video`.

## Regras de engenharia (valem para qualquer look novo)
- A cena é função pura do tempo: `window.__t3(t)`. Sem relógio, sem acúmulo entre quadros, sem `Math.random` sem semente.
- Textura de imagem real do cliente sempre com `colorSpace = SRGB` e material sem tone mapping quando o objetivo é fidelidade de cor.
- Luz de lado e pouco ambiente; objeto principal com lado claro e lado escuro. Cena «chapada» = ambiente alto demais.
- Troca de estado é mistura (0,2–0,4 s), nunca um `if` seco.
- Câmera: ou ela anda, ou a ação acontece; as duas ao mesmo tempo achatam o soco.
- Um soco por clipe (o gesto principal) com calma antes e depois. Nunca «acelerar tudo».
- Sem marca, texto ou personagem de terceiros da referência. Da referência vêm método e sensação.

## Revisão de um minuto (antes de entregar)
Abra 3 quadros em tamanho cheio e a folha: tudo cabe no quadro? algo tapa o objeto principal? a tela/foto está legível e com a cor certa?
o movimento tem um soco e respiro? o último quadro está vivo (não vira foto)? Texto em PT-BR, com acento.
Corrija o que o olho achar, **uma** rodada; não refaça o que passou.

## Entrega (4 linhas)
O que é (look, duração, arquivo) · Contra a referência (o que bate / o que difere de propósito) · O que mudou desde o storyboard aprovado ·
**O que não foi verificado** (ex.: não assistido em velocidade real, câmera estimada, sem crítico independente).
Limite honesto: é cena estilizada em tempo real, não render fotorrealista.

## Licenças
three.js: MIT. Modelos 3D só CC0, ou CC BY com crédito; nunca uso-não-comercial. Referências de terceiros: não entram no repositório
nem no produto final; ficam em `referencias-3d/` só para medição.
