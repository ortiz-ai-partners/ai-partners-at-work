import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

// ---------- 基本セットアップ ----------
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(46, innerWidth / innerHeight, 0.1, 100);
camera.position.set(0, 5.4, 8.2);
camera.lookAt(0, 0.6, -0.6);

const hemi = new THREE.HemisphereLight(0xfff6e5, 0xc9b18a, 1.0);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xffffff, 0.9);
sun.position.set(4, 8, 5);
sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024);
sun.shadow.camera.left = -8; sun.shadow.camera.right = 8;
sun.shadow.camera.top = 8; sun.shadow.camera.bottom = -8;
scene.add(sun);

// ---------- 部屋 ----------
const floor = new THREE.Mesh(
  new THREE.CylinderGeometry(6.4, 6.6, 0.3, 48),
  new THREE.MeshStandardMaterial({ color: 0xf3ddb7 })
);
floor.position.y = -0.15;
floor.receiveShadow = true;
scene.add(floor);

const rug = new THREE.Mesh(
  new THREE.CylinderGeometry(2.6, 2.6, 0.02, 40),
  new THREE.MeshStandardMaterial({ color: 0xe9a97e })
);
rug.position.set(0, 0.02, 1.2);
rug.receiveShadow = true;
scene.add(rug);

function makeDesk(x) {
  const g = new THREE.Group();
  const wood = new THREE.MeshStandardMaterial({ color: 0xb98b5a });
  const top = new THREE.Mesh(new THREE.BoxGeometry(1.7, 0.1, 0.85), wood);
  top.position.y = 0.74; top.castShadow = true;
  g.add(top);
  for (const [lx, lz] of [[-0.75, -0.32], [0.75, -0.32], [-0.75, 0.32], [0.75, 0.32]]) {
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.045, 0.74, 8), wood);
    leg.position.set(lx, 0.37, lz);
    g.add(leg);
  }
  const mon = new THREE.Mesh(new THREE.BoxGeometry(0.78, 0.5, 0.06),
    new THREE.MeshStandardMaterial({ color: 0x4a4a55 }));
  mon.position.set(0, 1.18, -0.18); mon.castShadow = true;
  g.add(mon);
  const stand = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.07, 0.22, 8),
    new THREE.MeshStandardMaterial({ color: 0x4a4a55 }));
  stand.position.set(0, 0.9, -0.18);
  g.add(stand);
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(0.68, 0.4),
    new THREE.MeshStandardMaterial({ color: 0x222230, emissive: 0x000000 }));
  screen.position.set(0, 1.18, -0.147);
  g.add(screen);
  const chairMat = new THREE.MeshStandardMaterial({ color: 0x9a6f45 });
  const seat = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.07, 0.5), chairMat);
  seat.position.set(0, 0.4, 0.85); seat.castShadow = true;
  g.add(seat);
  const back = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.5, 0.06), chairMat);
  back.position.set(0, 0.68, 1.08); back.castShadow = true;
  g.add(back);
  for (const [lx, lz] of [[-0.22, 0.66], [0.22, 0.66], [-0.22, 1.04], [0.22, 1.04]]) {
    const cl = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.4, 8), chairMat);
    cl.position.set(lx, 0.2, lz);
    g.add(cl);
  }
  const lamp = new THREE.PointLight(0xffc36b, 0, 4, 2);
  lamp.position.set(0, 1.5, 0.3);
  g.add(lamp);
  g.position.set(x, 0, -2.6);
  scene.add(g);
  return { group: g, screen, lamp };
}
const desks = [makeDesk(-2.6), makeDesk(0), makeDesk(2.6)];

// ポスト（Phase 3で成果物ドロップ演出に使う）
const mail = new THREE.Group();
const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 1.0, 10),
  new THREE.MeshStandardMaterial({ color: 0x8a6a4a }));
pole.position.y = 0.5;
mail.add(pole);
const box = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.45, 0.45),
  new THREE.MeshStandardMaterial({ color: 0xd9534f }));
box.position.y = 1.15; box.castShadow = true;
mail.add(box);
const flag = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.28, 0.14),
  new THREE.MeshStandardMaterial({ color: 0xffd166 }));
flag.position.set(0.38, 1.32, 0);
mail.add(flag);
mail.position.set(4.4, 0, 0.6);
scene.add(mail);

// 星（夜用）
const starGeo = new THREE.BufferGeometry();
const starPos = [];
for (let i = 0; i < 220; i++) {
  const r = 28, a = Math.random() * Math.PI * 2, b = Math.random() * Math.PI * 0.42;
  starPos.push(r * Math.cos(a) * Math.cos(b), 4 + r * Math.sin(b), r * Math.sin(a) * Math.cos(b) - 6);
}
starGeo.setAttribute('position', new THREE.Float32BufferAttribute(starPos, 3));
const starMat = new THREE.PointsMaterial({ color: 0xfff2c9, size: 0.12, transparent: true, opacity: 0 });
scene.add(new THREE.Points(starGeo, starMat));

// ---------- キャラクター ----------
const KIND_LABEL = {
  reading: '📖 よみこみ中', coding: '⌨️ コーディング中', terminal: '🖥️ コマンド実行中',
  web: '🌐 しらべもの中', delegate: '🤝 おねがい中', talking: '💬 ほうこく中',
  working: '🔧 さぎょう中', thinking: '🤔 かんがえ中', idle: '☕ まったり中', done: '🎉 かんりょう！',
};

function makeLabel() {
  const canvas = document.createElement('canvas');
  canvas.width = 512; canvas.height = 112;
  const tex = new THREE.CanvasTexture(canvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true }));
  sprite.scale.set(2.3, 0.5, 1);
  function set(text) {
    const c = canvas.getContext('2d');
    c.clearRect(0, 0, 512, 112);
    c.fillStyle = 'rgba(255,255,255,0.92)';
    c.beginPath();
    c.roundRect(8, 8, 496, 96, 44);
    c.fill();
    c.fillStyle = '#4a3d30';
    c.font = '600 44px "Segoe UI", "Hiragino Sans", sans-serif';
    c.textAlign = 'center'; c.textBaseline = 'middle';
    c.fillText(text, 256, 60);
    tex.needsUpdate = true;
  }
  return { sprite, set };
}

function makeChar(conf) {
  const g = new THREE.Group();
  const bodyG = new THREE.Group();
  g.add(bodyG);
  const mat = new THREE.MeshStandardMaterial({ color: conf.color, roughness: 0.6 });
  const darkMat = new THREE.MeshStandardMaterial({ color: conf.dark, roughness: 0.5 });

  const body = new THREE.Mesh(new THREE.SphereGeometry(0.42, 24, 18), mat);
  body.scale.set(1, 0.82, 0.95); body.position.y = 0.4; body.castShadow = true;
  bodyG.add(body);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.55, 28, 22), mat);
  head.position.y = 1.13; head.castShadow = true;
  bodyG.add(head);
  const face = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.32, 0.08), darkMat);
  face.position.set(0, 1.15, 0.46);
  bodyG.add(face);
  const eyeMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
  for (const ex of [-0.14, 0.14]) {
    const eye = new THREE.Mesh(new THREE.SphereGeometry(0.055, 12, 10), eyeMat);
    eye.position.set(ex, 1.17, 0.51);
    bodyG.add(eye);
  }
  const cheekMat = new THREE.MeshBasicMaterial({ color: 0xff9d9d });
  for (const ex of [-0.34, 0.34]) {
    const cheek = new THREE.Mesh(new THREE.SphereGeometry(0.06, 10, 8), cheekMat);
    cheek.scale.z = 0.4;
    cheek.position.set(ex, 1.02, 0.42);
    bodyG.add(cheek);
  }
  for (const fx of [-0.18, 0.18]) {
    const foot = new THREE.Mesh(new THREE.SphereGeometry(0.13, 12, 10), darkMat);
    foot.scale.y = 0.55;
    foot.position.set(fx, 0.07, 0.06);
    foot.castShadow = true;
    bodyG.add(foot);
  }
  if (conf.accent === 'glasses') {
    const gm = new THREE.MeshBasicMaterial({ color: 0xfffbe8 });
    for (const ex of [-0.14, 0.14]) {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.105, 0.018, 8, 20), gm);
      ring.position.set(ex, 1.17, 0.52);
      bodyG.add(ring);
    }
  } else if (conf.accent === 'antenna') {
    const stick = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.26, 8), darkMat);
    stick.position.y = 1.78;
    bodyG.add(stick);
    const ball = new THREE.Mesh(new THREE.SphereGeometry(0.07, 12, 10),
      new THREE.MeshBasicMaterial({ color: 0xffd166 }));
    ball.position.y = 1.93;
    bodyG.add(ball);
  } else if (conf.accent === 'bowtie') {
    const bm = new THREE.MeshStandardMaterial({ color: 0x2d4a70 });
    for (const s of [-1, 1]) {
      const wing = new THREE.Mesh(new THREE.ConeGeometry(0.09, 0.16, 4), bm);
      wing.rotation.z = s * Math.PI / 2;
      wing.position.set(s * 0.09, 0.62, 0.36);
      bodyG.add(wing);
    }
  }
  const label = makeLabel();
  label.sprite.position.y = 2.25;
  label.set(conf.name);
  g.add(label.sprite);

  const shadow = new THREE.Mesh(new THREE.CircleGeometry(0.42, 24),
    new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.12 }));
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.y = 0.012;
  g.add(shadow);

  scene.add(g);
  return { group: g, bodyG, label, conf };
}

const CONFS = [
  { name: 'ファーブル', color: 0x7fb77e, dark: 0x3e5c3e, accent: 'glasses' },
  { name: 'ヴェルティ', color: 0xff9f5a, dark: 0x4a3728, accent: 'antenna' },
  { name: 'オルティス', color: 0x6fa8dc, dark: 0x243b55, accent: 'bowtie' },
];
const chars = CONFS.map((conf, i) => {
  const c = makeChar(conf);
  return {
    ...c, i,
    state: 'idle', kind: 'idle',
    pos: new THREE.Vector3((i - 1) * 2.2, 0, 1.5 + i * 0.4),
    target: null, session: null, activeUntil: 0, celebrateUntil: 0,
    hop: 0, wanderAt: performance.now() + 1500 + i * 2200,
    deskPos: new THREE.Vector3(desks[i].group.position.x, 0, desks[i].group.position.z + 0.85),
  };
});
chars.forEach(c => c.group.position.copy(c.pos));
window.chars = chars;

// ---------- VRMアバター（VRoidで作ったデスクトップキャラを流用） ----------
// 入れ替えたいときはこの配列の並びを変えるだけ（null＝ちびキャラのまま）
const AVATARS = [
  '/avatars/hal001.vrm',              // ファーブル
  '/avatars/halanemon01sagyou01.vrm', // ヴェルティ（作業着）
  '/avatars/halanemom01normal01.vrm', // オルティス
];
const gltfLoader = new GLTFLoader();
gltfLoader.register(p => new VRMLoaderPlugin(p));
chars.forEach((ch, i) => {
  const url = AVATARS[i];
  if (!url) return;
  gltfLoader.load(url, (gltf) => {
    const vrm = gltf.userData.vrm;
    if (!vrm) return;
    VRMUtils.rotateVRM0(vrm);
    const bb = new THREE.Box3().setFromObject(vrm.scene);
    const s = 1.55 / Math.max(0.2, bb.max.y - bb.min.y);
    vrm.scene.scale.setScalar(s);
    vrm.scene.traverse(o => { if (o.isMesh) { o.castShadow = true; o.frustumCulled = false; } });
    ch.group.remove(ch.bodyG);
    ch.group.add(vrm.scene);
    ch.vrm = vrm;
    ch.label.sprite.position.y = 2.0;
    console.log('VRM loaded:', url);
  }, undefined, (e) => console.warn('VRM load failed: ' + url, e));
});

// ---------- VRMモーション（プロシージャルアニメーション） ----------
function poseChar(ch, t, now, dt) {
  const P = {
    leftUpperArm: { z: 1.25 }, rightUpperArm: { z: -1.25 },
    leftLowerArm: {}, rightLowerArm: {},
    leftUpperLeg: {}, rightUpperLeg: {}, leftLowerLeg: {}, rightLowerLeg: {},
    spine: {}, head: {},
  };
  const st = ch.state;
  if (st === 'walk' || st === 'toDesk') {
    const w = t * 9 + ch.i * 2;
    P.leftUpperLeg.x = Math.sin(w) * 0.5;
    P.rightUpperLeg.x = -Math.sin(w) * 0.5;
    P.leftLowerLeg.x = -Math.max(0, Math.sin(w)) * 0.5;
    P.rightLowerLeg.x = -Math.max(0, -Math.sin(w)) * 0.5;
    P.leftUpperArm.x = -Math.sin(w) * 0.3;
    P.rightUpperArm.x = Math.sin(w) * 0.3;
    P.spine.x = 0.07;
  } else if (st === 'working') {
    P.leftUpperLeg.x = 1.35; P.rightUpperLeg.x = 1.35;
    P.leftLowerLeg.x = -1.25; P.rightLowerLeg.x = -1.25;
    if (ch.pondering && now < ch.pondering) {
      P.rightUpperArm.z = -0.55; P.rightUpperArm.x = -0.4; P.rightLowerArm.y = 2.4;
      P.head.z = 0.16; P.head.x = 0.08;
    } else {
      P.leftUpperArm.z = 1.0; P.rightUpperArm.z = -1.0;
      P.leftUpperArm.x = -0.3; P.rightUpperArm.x = -0.3;
      P.leftLowerArm.y = -0.9; P.rightLowerArm.y = 0.9;
      P.head.x = 0.1 + Math.sin(t * 6 + ch.i) * 0.03;
    }
  } else if (st === 'celebrate') {
    P.leftUpperArm.z = -1.05; P.rightUpperArm.z = 1.05;
    P.head.x = -0.15;
  } else {
    P.spine.x = Math.sin(t * 1.6 + ch.i) * 0.03;
    P.head.y = Math.sin(t * 0.6 + ch.i * 2) * 0.3;
  }
  const k = Math.min(1, dt * 8);
  for (const name in P) {
    const b = ch.vrm.humanoid.getNormalizedBoneNode(name);
    if (!b) continue;
    const r = P[name];
    b.rotation.x += ((r.x || 0) - b.rotation.x) * k;
    b.rotation.y += ((r.y || 0) - b.rotation.y) * k;
    b.rotation.z += ((r.z || 0) - b.rotation.z) * k;
  }
}

function updateFace(ch, now, dt) {
  const em = ch.vrm.expressionManager;
  if (!em) return;
  let expr = null, v = 0;
  if (ch.state === 'celebrate') { expr = 'happy'; v = 1; }
  else if (ch.pondering && now < ch.pondering) { expr = 'sad'; v = 0.5; }
  else if (ch.state === 'idle' || ch.state === 'walk') { expr = 'relaxed'; v = 0.3; }
  for (const n of ['happy', 'sad', 'relaxed', 'angry', 'surprised']) {
    const cur = em.getValue(n) || 0;
    const tgt = n === expr ? v : 0;
    em.setValue(n, cur + (tgt - cur) * Math.min(1, dt * 6));
  }
  if (!ch.nextBlink) ch.nextBlink = now + 2000 + Math.random() * 3000;
  if (now > ch.nextBlink) { ch.blinkT = 0; ch.nextBlink = now + 1800 + Math.random() * 3500; }
  if (ch.blinkT !== undefined && ch.blinkT <= 0.28) {
    ch.blinkT += dt;
    em.setValue('blink', Math.max(0, Math.sin(Math.min(1, ch.blinkT / 0.28) * Math.PI)));
  }
}

// ---------- テーマ（昼夜） ----------
const THEME = {
  day:   { bg: 0xfdeed7, floor: 0xf3ddb7, rug: 0xe9a97e, hemi: 1.0, sun: 0.9, lamp: 0, stars: 0 },
  night: { bg: 0x161d31, floor: 0x2b3550, rug: 0x3a4a72, hemi: 0.32, sun: 0.1, lamp: 1.4, stars: 1 },
};
let themeT = 0, themeTarget = 0;
const hour = new Date().getHours();
if (hour >= 18 || hour < 6) themeTarget = 1;
const btn = document.getElementById('themeBtn');
function syncBtn() { btn.textContent = themeTarget === 1 ? '🌙 よるモード' : '☀️ ひるモード'; }
btn.onclick = () => { themeTarget = 1 - themeTarget; syncBtn(); };
syncBtn();
scene.background = new THREE.Color(THEME.day.bg);

function lerpColor(a, b, t) { return new THREE.Color(a).lerp(new THREE.Color(b), t); }
function applyTheme() {
  const t = themeT;
  scene.background = lerpColor(THEME.day.bg, THEME.night.bg, t);
  floor.material.color = lerpColor(THEME.day.floor, THEME.night.floor, t);
  rug.material.color = lerpColor(THEME.day.rug, THEME.night.rug, t);
  hemi.intensity = THREE.MathUtils.lerp(THEME.day.hemi, THEME.night.hemi, t);
  sun.intensity = THREE.MathUtils.lerp(THEME.day.sun, THEME.night.sun, t);
  starMat.opacity = t;
  for (const d of desks) d.lamp.intensity = THREE.MathUtils.lerp(0, THEME.night.lamp, t);
}

// ---------- イベント受信と割り当て ----------
const sessionMap = new Map(); // sessionKey -> char index
const logEl = document.getElementById('log');
const statusEl = document.getElementById('status');

function assignChar(key) {
  if (sessionMap.has(key)) return chars[sessionMap.get(key)];
  let idx = chars.findIndex(c => c.session === null);
  if (idx === -1) idx = sessionMap.size % chars.length;
  sessionMap.set(key, idx);
  chars[idx].session = key;
  return chars[idx];
}

function onEvent(ev) {
  const key = ev.project + '/' + ev.session;
  const ch = assignChar(key);
  ch.kind = ev.kind;
  ch.activeUntil = performance.now() + 12000;
  ch.hop = 1;
  if (ch.state !== 'working' && ch.state !== 'toDesk') {
    ch.state = 'toDesk';
    ch.target = ch.deskPos.clone();
  }
  ch.label.set(KIND_LABEL[ev.kind] || KIND_LABEL.working);
  desks[ch.i].screen.material.emissive.setHex(0x3a6ea8);
  logEl.textContent = ch.conf.name + ' … ' + (ev.tool || ev.kind) + '（' + ev.project.replace(/^C--Users-[^-]+-/, '') + '）';
}

function connect() {
  const es = new EventSource('/events');
  es.onopen = () => statusEl.classList.add('on');
  es.onerror = () => statusEl.classList.remove('on');
  es.onmessage = (m) => { try { onEvent(JSON.parse(m.data)); } catch (e) {} };
}
connect();

// ---------- 観察カメラ（右下ボタン） ----------
let followIdx = -1;
const followBtns = [];
const btnWrap = document.getElementById('charBtns');
for (const [label, idx] of [['🏢 ぜんたい', -1], ...CONFS.map((c, i) => [c.name, i])]) {
  const b = document.createElement('button');
  b.className = 'cbtn' + (idx === -1 ? ' active' : '');
  b.textContent = label;
  b.onclick = () => {
    followIdx = idx;
    for (const [bb, ii] of followBtns) bb.classList.toggle('active', ii === idx);
  };
  followBtns.push([b, idx]);
  btnWrap.appendChild(b);
}
const camTarget = new THREE.Vector3(0, 5.4, 8.2);
const lookTarget = new THREE.Vector3(0, 0.6, -0.6);
const smoothLook = new THREE.Vector3(0, 0.6, -0.6);
window.camera = camera;

// ---------- アニメーションループ ----------
const clock = new THREE.Clock();
function wanderTarget() {
  return new THREE.Vector3((Math.random() - 0.5) * 5.6, 0, 0.2 + Math.random() * 2.8);
}

function animate() {
  requestAnimationFrame(animate);
  const w = Math.max(1, innerWidth), h = Math.max(1, innerHeight);
  if (renderer.domElement.width !== Math.floor(w * renderer.getPixelRatio()) ||
      renderer.domElement.height !== Math.floor(h * renderer.getPixelRatio())) {
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }
  const dt = Math.min(clock.getDelta(), 0.05);
  const now = performance.now();
  const t = clock.elapsedTime;

  themeT += (themeTarget - themeT) * Math.min(1, dt * 2);
  applyTheme();

  for (const ch of chars) {
    const g = ch.group;
    // 状態遷移
    if ((ch.state === 'working' || ch.state === 'toDesk') && now > ch.activeUntil) {
      ch.state = 'celebrate';
      ch.celebrateUntil = now + 1700;
      ch.pondering = 0;
      ch.ponderAt = 0;
      ch.kind = 'done';
      ch.label.set(KIND_LABEL.done);
      desks[ch.i].screen.material.emissive.setHex(0x000000);
    }
    if (ch.state === 'celebrate' && now > ch.celebrateUntil) {
      ch.state = 'idle';
      ch.kind = 'idle';
      ch.session = null;
      for (const [k, v] of sessionMap) if (v === ch.i) sessionMap.delete(k);
      ch.label.set(KIND_LABEL.idle);
      ch.wanderAt = now + 1000;
    }
    // 移動
    if (ch.state === 'toDesk' || ch.state === 'walk') {
      const dir = ch.target.clone().sub(ch.pos);
      dir.y = 0;
      const dist = dir.length();
      if (dist < 0.08) {
        ch.state = ch.state === 'toDesk' ? 'working' : 'idle';
        if (ch.state === 'idle') ch.wanderAt = now + 2500 + Math.random() * 4000;
      } else {
        dir.normalize();
        ch.pos.addScaledVector(dir, dt * 1.7);
        g.rotation.y += (Math.atan2(dir.x, dir.z) - g.rotation.y) * Math.min(1, dt * 8);
        g.position.y = Math.abs(Math.sin(t * 10 + ch.i)) * 0.09;
      }
    } else if (ch.state === 'idle') {
      if (now > ch.wanderAt) {
        ch.state = 'walk';
        ch.target = wanderTarget();
      }
      g.position.y = Math.sin(t * 2 + ch.i * 2) * 0.02 + 0.02;
      g.rotation.y += dt * 0.15;
    } else if (ch.state === 'working') {
      g.rotation.y += (Math.PI - g.rotation.y) * Math.min(1, dt * 6);
      g.position.y = ch.vrm ? 0 : Math.abs(Math.sin(t * 7 + ch.i)) * 0.035;
      if (!ch.ponderAt) ch.ponderAt = now + 5000;
      if (now > ch.ponderAt) {
        ch.pondering = now + 2800;
        ch.ponderAt = now + 8000 + Math.random() * 9000;
        ch.label.set('🤔 うーん…');
      }
      if (ch.pondering && now > ch.pondering) {
        ch.pondering = 0;
        ch.label.set(KIND_LABEL[ch.kind] || KIND_LABEL.working);
      }
    } else if (ch.state === 'celebrate') {
      g.position.y = Math.abs(Math.sin(t * 9)) * 0.35;
      g.rotation.y += dt * 7;
    }
    // ツールイベントのぴょこん
    if (ch.hop > 0) {
      ch.hop = Math.max(0, ch.hop - dt * 3);
      g.scale.y = 1 - Math.sin(ch.hop * Math.PI) * 0.12;
      g.scale.x = g.scale.z = 1 + Math.sin(ch.hop * Math.PI) * 0.08;
    } else {
      g.scale.set(1, 1, 1);
    }
    g.position.x = ch.pos.x;
    g.position.z = ch.pos.z;
    if (ch.vrm) {
      poseChar(ch, t, now, dt);
      const sit = ch.state === 'working' ? -0.32 : 0;
      ch.vrm.scene.position.y += (sit - ch.vrm.scene.position.y) * Math.min(1, dt * 5);
      updateFace(ch, now, dt);
      ch.vrm.update(dt);
    }
  }

  if (followIdx >= 0) {
    const p = chars[followIdx].group.position;
    camTarget.set(p.x + 1.7, 1.5, p.z + 2.7);
    lookTarget.set(p.x, 1.1, p.z);
  } else {
    camTarget.set(Math.sin(t * 0.08) * 0.7, 5.4, 8.2);
    lookTarget.set(0, 0.6, -0.6);
  }
  camera.position.lerp(camTarget, Math.min(1, dt * 3));
  smoothLook.lerp(lookTarget, Math.min(1, dt * 3));
  camera.lookAt(smoothLook);
  renderer.render(scene, camera);
}
animate();

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});
