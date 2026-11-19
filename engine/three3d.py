"""Clipes 3D com three.js (MIT, vendorizado em library/vendor/three) renderizados quadro a quadro no Chrome sem janela.

Saída: um .mp4 pronto para entrar no reel como cena `site-video` (photos: ["3d/xxx.mp4"]).
Clipes feitos por outras ferramentas (ex.: skill motion-3d-por-referencia) caem na mesma pasta `3d/` e são usados igual.
"""
from __future__ import annotations
import functools
import http.server
import json
import socketserver
import subprocess
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THREE = ROOT / "library" / "vendor" / "three"

PAGE = r"""<!doctype html><meta charset=utf-8><style>html,body{margin:0;background:__BG__}canvas{display:block}</style>
<script type="importmap">{"imports":{"three":"/vendor/three.module.js"}}</script>
<body><script type="module">
import * as THREE from 'three';
const P=__PARAMS__;
const W=P.w,H=P.h;
const r=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
r.setSize(W,H,false);r.setPixelRatio(1);r.outputColorSpace=THREE.SRGBColorSpace;r.toneMapping=THREE.ACESFilmicToneMapping;r.toneMappingExposure=1.05;
r.shadowMap.enabled=true;r.shadowMap.type=THREE.PCFSoftShadowMap;
document.body.appendChild(r.domElement);
const sc=new THREE.Scene();sc.background=new THREE.Color(P.bg);
// fundo em degradê suave
{const c=document.createElement('canvas');c.width=4;c.height=256;const g=c.getContext('2d'),gr=g.createLinearGradient(0,0,0,256);gr.addColorStop(0,P.bg2);gr.addColorStop(1,P.bg);g.fillStyle=gr;g.fillRect(0,0,4,256);const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;sc.background=t;}
const cam=new THREE.PerspectiveCamera(30,W/H,.1,100);
sc.add(new THREE.HemisphereLight(0xffffff,P.bg,.9));
const key=new THREE.DirectionalLight(0xffffff,2.4);key.position.set(-3,5,4);key.castShadow=true;key.shadow.mapSize.set(2048,2048);key.shadow.camera.left=-4;key.shadow.camera.right=4;key.shadow.camera.top=4;key.shadow.camera.bottom=-4;key.shadow.radius=6;sc.add(key);
const rim=new THREE.DirectionalLight(new THREE.Color(P.accent),2.2);rim.position.set(4,2,-3);sc.add(rim);
// aparelho: corpo com cantos arredondados (extrusão com bisel) + tela com a captura do site
function rr(w,h,rad){const s=new THREE.Shape(),x=-w/2,y=-h/2;s.moveTo(x+rad,y);s.lineTo(x+w-rad,y);s.quadraticCurveTo(x+w,y,x+w,y+rad);s.lineTo(x+w,y+h-rad);s.quadraticCurveTo(x+w,y+h,x+w-rad,y+h);s.lineTo(x+rad,y+h);s.quadraticCurveTo(x,y+h,x,y+h-rad);s.lineTo(x,y+rad);s.quadraticCurveTo(x,y,x+rad,y);return s}
const dev=new THREE.Group();sc.add(dev);
const BW=1.0,BH=2.05,BD=.11,SW0=BW-.11,SH0=BH-.11;
const body=new THREE.Mesh(new THREE.ExtrudeGeometry(rr(BW,BH,.17),{depth:BD,bevelEnabled:true,bevelThickness:.018,bevelSize:.018,bevelSegments:6,curveSegments:24}),new THREE.MeshStandardMaterial({color:P.body,metalness:.9,roughness:.28}));
body.position.z=-BD/2;body.castShadow=true;dev.add(body);
const bezel=new THREE.Mesh(new THREE.ShapeGeometry(rr(BW-.05,BH-.05,.14),24),new THREE.MeshBasicMaterial({color:0x050505}));bezel.position.z=BD/2+.0215;dev.add(bezel);
const tex=new THREE.TextureLoader().load(P.screen,(t)=>{const ia=t.image.width/t.image.height,sa=SW0/SH0;if(ia>sa){t.repeat.x=sa/ia;t.offset.x=(1-t.repeat.x)/2}else{t.repeat.y=ia/sa;t.offset.y=1-t.repeat.y}window.__ready=true});tex.colorSpace=THREE.SRGBColorSpace;tex.anisotropy=8;
const SW=BW-.11,SH=BH-.11;
const sg=new THREE.ShapeGeometry(rr(SW,SH,.115),24);const uv=sg.attributes.uv,pos=sg.attributes.position;for(let i=0;i<uv.count;i++){uv.setXY(i,(pos.getX(i)+SW/2)/SW,(pos.getY(i)+SH/2)/SH)}
const screen=new THREE.Mesh(sg,new THREE.MeshBasicMaterial({map:tex,toneMapped:false}));screen.position.z=BD/2+.0225;dev.add(screen);
// ilha da câmera frontal
const isl=new THREE.Mesh(new THREE.ShapeGeometry(rr(.3,.085,.042),16),new THREE.MeshBasicMaterial({color:0x000000}));isl.position.set(0,SH/2-.1,BD/2+.0235);dev.add(isl);
// vidro: brilho diagonal que varre a tela (recortado no formato da tela)
const gc=document.createElement('canvas');gc.width=512;gc.height=512;{const g=gc.getContext('2d'),gr=g.createLinearGradient(0,0,512,0);gr.addColorStop(.0,'rgba(255,255,255,0)');gr.addColorStop(.5,'rgba(255,255,255,.55)');gr.addColorStop(1,'rgba(255,255,255,0)');g.fillStyle=gr;g.fillRect(0,0,512,512)}
const gtex=new THREE.CanvasTexture(gc);gtex.wrapS=THREE.ClampToEdgeWrapping;gtex.repeat.set(.45,1);
const glare=new THREE.Mesh(sg.clone(),new THREE.MeshBasicMaterial({map:gtex,transparent:true,opacity:.0,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false}));glare.position.z=BD/2+.0235;dev.add(glare);
// chão que recebe sombra
const floor=new THREE.Mesh(new THREE.PlaneGeometry(30,30),new THREE.ShadowMaterial({opacity:.18}));floor.rotation.x=-Math.PI/2;floor.position.y=-1.25;floor.receiveShadow=true;sc.add(floor);
const ease=x=>1-Math.pow(1-x,3),sm=x=>x*x*(3-2*x);
window.__t3=(t)=>{ // determinístico: depende só de t (segundos)
  const d=P.dur,p=Math.min(1,t/d),e=ease(Math.min(1,t/1.4));
  const ry=THREE.MathUtils.lerp(-.9,.32,sm(p))+Math.sin(p*Math.PI)*.12;
  dev.rotation.set(THREE.MathUtils.lerp(.28,-.03,e)+Math.sin(p*Math.PI*2)*.015,ry,THREE.MathUtils.lerp(-.12,0,e));
  dev.position.set(0,THREE.MathUtils.lerp(-.5,0,e)+Math.sin(t*1.6)*.02,0);
  const dist=THREE.MathUtils.lerp(6.9,5.3,sm(p));cam.position.set(0,.15,dist);cam.lookAt(0,0,0);
  {const q=Math.min(1,Math.max(0,(p-.25)/.5));gtex.offset.x=THREE.MathUtils.lerp(-.5,1.05,sm(q));glare.material.opacity=.5*Math.sin(q*Math.PI)}
  r.render(sc,cam);
};
window.__t3(0);
</script>"""


def _serve(root_files: dict) -> tuple[socketserver.TCPServer, int]:
    class H(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            return str(root_files.get(path.split("?")[0], "/nonexistent"))

        def log_message(self, *a):
            pass
    srv = socketserver.TCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def _run(html: str, files: dict, out: Path, *, width, height, dur, fps, label="clipe 3D", verbose=True) -> Path:
    """Abre a página (que expõe window.__ready e window.__t3(t)), captura quadro a quadro e codifica em mp4."""
    from playwright.sync_api import sync_playwright
    from engine.core import _chrome_path
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="three3d-"))
    (tmp / "index.html").write_text(html, encoding="utf-8")
    files = {"/": tmp / "index.html", "/index.html": tmp / "index.html",
             "/vendor/three.module.js": THREE / "three.module.js", "/vendor/three.core.js": THREE / "three.core.js", **files}
    srv, port = _serve(files)
    n = int(round(dur * fps))
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
                           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    pw = sync_playwright().start()
    try:
        kw = dict(args=["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--force-color-profile=srgb"])
        cp = _chrome_path()
        if cp:
            kw["executable_path"] = cp
        br = pw.chromium.launch(**kw)
        pg = br.new_page(viewport={"width": width, "height": height})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(f"http://127.0.0.1:{port}/index.html")
        pg.wait_for_function("window.__ready===true", timeout=30000)
        for i in range(n):
            pg.evaluate(f"__t3({i / fps})")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=94))
        ff.stdin.close()
        ff.wait()
        br.close()
        if errs:
            print("  ! erros no WebGL:", errs[:2])
    finally:
        pw.stop()
        srv.shutdown()
    if verbose:
        print(f"  ✓ {label}: {out} ({n} quadros)")
    return out


def render_device(screen, out, *, width=1080, height=1920, dur=4.0, fps=30,
                  bg="#0b0b0f", bg2="#1d1d26", accent="#0A84FF", body="#9aa0a8", verbose=True) -> Path:
    """Look «celular»: aparelho 3D girando com a captura do site na tela."""
    params = dict(w=width, h=height, dur=dur, bg=bg, bg2=bg2, accent=accent, body=body, screen="/screen.png")
    html = PAGE.replace("__PARAMS__", json.dumps(params)).replace("__BG__", bg)
    return _run(html, {"/screen.png": Path(screen).resolve()}, out, width=width, height=height, dur=dur, fps=fps, label="clipe 3D (celular)", verbose=verbose)


CARDS = r"""<!doctype html><meta charset=utf-8><style>html,body{margin:0;background:__BG__}canvas{display:block}</style>
<script type="importmap">{"imports":{"three":"/vendor/three.module.js"}}</script>
<body><script type="module">
import * as THREE from 'three';
const P=__PARAMS__,W=P.w,H=P.h,N=P.n;
const r=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});r.setSize(W,H,false);r.setPixelRatio(1);r.outputColorSpace=THREE.SRGBColorSpace;
document.body.appendChild(r.domElement);
const sc=new THREE.Scene();
{const c=document.createElement('canvas');c.width=4;c.height=256;const g=c.getContext('2d'),gr=g.createLinearGradient(0,0,0,256);gr.addColorStop(0,P.bg2);gr.addColorStop(1,P.bg);g.fillStyle=gr;g.fillRect(0,0,4,256);const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;sc.background=t;}
sc.fog=new THREE.Fog(new THREE.Color(P.bg),7,15);
const cam=new THREE.PerspectiveCamera(32,W/H,.1,60);
function rr(w,h,rad){const s=new THREE.Shape(),x=-w/2,y=-h/2;s.moveTo(x+rad,y);s.lineTo(x+w-rad,y);s.quadraticCurveTo(x+w,y,x+w,y+rad);s.lineTo(x+w,y+h-rad);s.quadraticCurveTo(x+w,y+h,x+w-rad,y+h);s.lineTo(x+rad,y+h);s.quadraticCurveTo(x,y+h,x,y+h-rad);s.lineTo(x,y+rad);s.quadraticCurveTo(x,y,x+rad,y);return s}
const ring=new THREE.Group();sc.add(ring);
const cards=[];let loaded=0;
const R=P.raio;
for(let i=0;i<N;i++){
  const g=new THREE.Group();
  const ar=Math.min(2.2,Math.max(.5,P.ars[i]));let w=1.5,h=w/ar;if(h>1.9){h=1.9;w=h*ar}
  const sg=new THREE.ShapeGeometry(rr(w,h,.09),20);const uv=sg.attributes.uv,pos=sg.attributes.position;for(let k=0;k<uv.count;k++)uv.setXY(k,(pos.getX(k)+w/2)/w,(pos.getY(k)+h/2)/h);
  const tex=new THREE.TextureLoader().load('/img'+i,()=>{if(++loaded===N)window.__ready=true});tex.colorSpace=THREE.SRGBColorSpace;tex.anisotropy=8;
  const face=new THREE.Mesh(sg,new THREE.MeshBasicMaterial({map:tex,toneMapped:false}));face.position.z=.012;
  const back=new THREE.Mesh(new THREE.ShapeGeometry(rr(w+.05,h+.05,.11),20),new THREE.MeshBasicMaterial({color:P.rim}));
  const sh=new THREE.Mesh(new THREE.ShapeGeometry(rr(w,h,.09),20),new THREE.MeshBasicMaterial({color:0x000000,transparent:true,opacity:.35}));sh.position.set(.05,-.07,-.02);
  g.add(sh,back,face);
  const a=i/N*Math.PI*2;g.userData.a=a;g.position.set(Math.sin(a)*R,0,Math.cos(a)*R);g.rotation.y=a;
  ring.add(g);cards.push(g);
}
const ease=x=>1-Math.pow(1-x,3),sm=x=>x*x*(3-2*x);
window.__t3=(t)=>{
  const d=P.dur,p=Math.min(1,t/d),e=ease(Math.min(1,t/1.2));
  const turn=-sm(p)*Math.PI*2*Math.max(1,Math.round(N*P.fracao))/N; // gira uma fração da roda, suave
  ring.rotation.y=turn+THREE.MathUtils.lerp(-.5,0,e);
  cards.forEach((g,i)=>{const wy=ring.rotation.y+g.userData.a;const front=Math.cos(wy);g.position.y=Math.sin(t*1.4+i*1.3)*.06;g.scale.setScalar(.82+.18*Math.max(0,front));});
  cam.position.set(0,.35+THREE.MathUtils.lerp(.5,0,e),R+THREE.MathUtils.lerp(8.2,6.2,sm(p)));cam.lookAt(0,0,R*.5);
  r.render(sc,cam);
};
window.__t3(0);
</script>"""


def render_cards(images, out, *, width=1080, height=1920, dur=4.5, fps=30,
                 bg="#0b0b0f", bg2="#1d1d26", rim="#f2f2f5", verbose=True) -> Path:
    """Look «carrossel»: até 8 imagens reais do site em cartões que giram numa roda."""
    from PIL import Image
    imgs = [Path(x).resolve() for x in images][:8]
    if len(imgs) < 3:
        raise ValueError("o look 'cards' precisa de pelo menos 3 imagens")
    ars = []
    for x in imgs:
        with Image.open(x) as im:
            ars.append(round(im.width / im.height, 3))
    params = dict(w=width, h=height, dur=dur, bg=bg, bg2=bg2, rim=rim, n=len(imgs), ars=ars, raio=1.9, voltas=1, fracao=.55)
    html = CARDS.replace("__PARAMS__", json.dumps(params)).replace("__BG__", bg)
    files = {f"/img{i}": p for i, p in enumerate(imgs)}
    return _run(html, files, out, width=width, height=height, dur=dur, fps=fps, label="clipe 3D (carrossel)", verbose=verbose)
