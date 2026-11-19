# referencias-3d/

Coloque aqui as referências de movimento 3D (vídeos .mp4, imagens, links em `links.txt`).
O agente de Motion 3D lê esta pasta antes de criar qualquer clipe 3D e segue o que estiver aqui
(câmera, luz, cor, ritmo). Organize por assunto: `celular/`, `produto/`, `texto-3d/`...

## Como o 3D entra no reel
1. Clipe nativo: `python3 studio.py 3d samples/<site>` → `samples/<site>/3d/celular.mp4` (three.js, MIT, em `library/vendor/three`).
2. Clipe da skill do Felipe Borges (`/motion-3d-por-referencia`, instalada à parte): renderize o mp4 e copie para `samples/<site>/3d/`.
3. No roteiro, a cena usa o clipe como vídeo: layout `site-video`, `"photos": ["3d/arquivo.mp4"]`.

## Medir uma referência
`python3 studio.py pericia3d referencias-3d/celular/exemplo.mp4` → `pericia/MEDIDO.md` + `FICHA.md`. Detalhes em `agents/motion-3d.md`.

## Licenças
- three.js: MIT (LICENSE em library/vendor/three).
- Skill motion-3d-por-referencia: repositório sem licença declarada → NÃO copiar o código dela para este projeto;
  usar instalada à parte e aproveitar só os mp4 que ela gera. Pedir licença ao autor se quisermos embutir.
- Modelos 3D do repositório three.js: só CC0 (Flower, RobotExpressive, AnimatedMorphSphere) ou CC BY com crédito (MaterialsVariantsShoe).
  Nunca DamagedHelmet nem Nefertiti (uso não comercial).
