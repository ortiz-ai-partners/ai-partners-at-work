#!/usr/bin/env python3
"""家族の顔をミニPCの中だけで照合する（OpenCV YuNet + SFace、CPUで動く）

顔の判定はここで完結し、Claude には「映っている人: ゆうころ, はるくん」という文字だけを渡す。
写真・顔データ・特徴ベクトルは一切外に出さない。知らない顔は「知らない人」として数だけ返す。

準備:
  pip install opencv-python-headless numpy
  sh osanpo/faces/download_models.sh            # モデル2つを取得（Windowsは中のコメント参照）
  osanpo/faces/people/ゆうころ/*.jpg              # 本人の正面写真を3〜5枚ずつ
  osanpo/faces/people/はるくん/*.jpg
  osanpo/faces/people/たくみさん/*.jpg            # ← 本人の了解を先に
  python3 osanpo/faces/faces.py enroll           # → osanpo/faces/db.npz
確認:
  python3 osanpo/faces/faces.py who photo.jpg

知らない顔の候補帳（ゆうころの設計）:
  近くで正面で大きく映った知らない顔だけ、特徴ベクトルと小さな切り抜きを一時保管して数える。
  5回以上・2日以上にまたがって見たら、その子がこっそり「（この人だれ？覚えてもいい？ #3）」と聞く。
  ゆうころが「#3 はけんちゃんだよ」と答えたら登録、「#3 だめ」なら消す。30日見なければ自動で消える。
  python3 osanpo/faces/faces.py candidates      # 候補の一覧
"""
import json
import os
import shutil
import sys
import time
from datetime import date

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, 'models')
PEOPLE = os.path.join(HERE, 'people')
DB = os.path.join(HERE, 'db.npz')
YUNET = os.path.join(MODELS, 'yunet.onnx')
SFACE = os.path.join(MODELS, 'sface.onnx')
THRESHOLD = float(os.environ.get('OSANPO_FACE_THRESHOLD', '0.363'))  # SFace公式のcosine閾値
SCORE = 0.8  # 顔検出の確信度

CAND_JSON = os.path.join(HERE, 'candidates.json')
CAND_DIR = os.path.join(HERE, 'candidates')
ASK_AFTER = int(os.environ.get('OSANPO_FACE_ASK_AFTER', '5'))   # この回数見たら聞く
ASK_DAYS = int(os.environ.get('OSANPO_FACE_ASK_DAYS', '2'))     # かつ、この日数以上にまたがって
EXPIRE_DAYS = int(os.environ.get('OSANPO_FACE_EXPIRE_DAYS', '30'))
MAX_CAND = 50
MIN_PX = int(os.environ.get('OSANPO_FACE_MIN_PX', '60'))        # これより小さい顔（遠い人）は数えない

_det = _rec = None


def available():
    return os.path.exists(YUNET) and os.path.exists(SFACE)


def _load():
    global _det, _rec
    if _det is None:
        _det = cv2.FaceDetectorYN.create(YUNET, '', (320, 320), SCORE, 0.3, 5000)
        _rec = cv2.FaceRecognizerSF.create(SFACE, '')


def _faces(img):
    """検出した顔ごとに {feat, h, crop} を返す。"""
    _load()
    h, w = img.shape[:2]
    scale = 1.0
    if max(h, w) > 1280:  # 大きすぎると遅いので縮める
        scale = 1280 / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
        h, w = img.shape[:2]
    _det.setInputSize((w, h))
    _, dets = _det.detect(img)
    out = []
    if dets is None:
        return out
    for d in dets:
        aligned = _rec.alignCrop(img, d)
        feat = _rec.feature(aligned)
        out.append({'feat': feat, 'h': float(d[3]), 'crop': aligned})
    return out


def enroll():
    names, feats = [], []
    for name in sorted(os.listdir(PEOPLE)) if os.path.isdir(PEOPLE) else []:
        d = os.path.join(PEOPLE, name)
        if not os.path.isdir(d):
            continue
        n = 0
        for fn in sorted(os.listdir(d)):
            img = cv2.imread(os.path.join(d, fn))
            if img is None:
                continue
            fs = _faces(img)
            if len(fs) != 1:
                print(f'  skip {name}/{fn}: 顔が{len(fs)}つ（1つだけの写真を使って）')
                continue
            names.append(name)
            feats.append(fs[0]['feat'].flatten())
            n += 1
        print(f'{name}: {n}枚')
    if not feats:
        print('登録できる顔がない。people/<名前>/ に写真を置いて')
        return 1
    np.savez(DB, names=np.array(names), feats=np.stack(feats))
    print(f'saved {DB}')
    return 0


def who(path):
    """写真に映っている登録済みの人の名前（重複なし）と、知らない顔の数を返す。"""
    if not available() or not os.path.exists(DB):
        return [], 0
    img = cv2.imread(path)
    if img is None:
        return [], 0
    db = np.load(DB)
    names, feats = db['names'], db['feats']
    _load()
    known, unknown = [], 0
    for f in _faces(img):
        best, _ = _best_match(f['feat'], names, feats)
        if best is not None:
            if best not in known:
                known.append(best)
        else:
            unknown += 1
    return known, unknown


def _best_match(feat, names, feats):
    best, best_score = None, -1.0
    for name, ref in zip(names, feats):
        sc = _rec.match(feat, np.asarray(ref, dtype=np.float32).reshape(1, -1), cv2.FaceRecognizerSF_FR_COSINE)
        if sc > best_score:
            best, best_score = name, sc
    if best is not None and best_score >= THRESHOLD:
        return str(best), best_score
    return None, best_score


def _load_db():
    if not os.path.exists(DB):
        return [], []
    db = np.load(DB)
    return [str(n) for n in db['names']], [f for f in db['feats']]


def _save_db(names, feats):
    if not feats:
        return
    np.savez(DB, names=np.array(names), feats=np.stack([np.asarray(f, dtype=np.float32).flatten() for f in feats]))


def _load_cands():
    try:
        with open(CAND_JSON, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {'next': 1, 'items': {}}


def _save_cands(c):
    with open(CAND_JSON, 'w', encoding='utf-8') as f:
        json.dump(c, f, ensure_ascii=False, indent=1)


def _expire(c):
    now = time.time()
    for cid in list(c['items']):
        if now - c['items'][cid]['last'] > EXPIRE_DAYS * 86400:
            _drop(c, cid)
    while len(c['items']) > MAX_CAND:
        oldest = min(c['items'], key=lambda k: c['items'][k]['last'])
        _drop(c, oldest)


def _drop(c, cid):
    c['items'].pop(cid, None)
    try:
        os.remove(os.path.join(CAND_DIR, f'{cid}.jpg'))
    except FileNotFoundError:
        pass


def observe(path):
    """写真1枚を見て (登録済みの名前, 知らない顔の数, 聞くべき候補IDのリスト) を返す。
    知らない顔のうち大きく映ったものは候補帳で数える。"""
    if not available():
        return [], 0, []
    img = cv2.imread(path)
    if img is None:
        return [], 0, []
    _load()
    names, feats = _load_db()
    c = _load_cands()
    _expire(c)
    today = date.today().isoformat()
    known, unknown, asks = [], 0, []
    for f in _faces(img):
        best, _ = _best_match(f['feat'], names, feats)
        if best is not None:
            if best not in known:
                known.append(best)
            continue
        unknown += 1
        if f['h'] < MIN_PX:
            continue  # 遠い人は数えない
        cid, _ = _best_match(f['feat'], list(c['items']), [it['feats'][0] for it in c['items'].values()])
        if cid is None:
            cid = str(c['next'])
            c['next'] += 1
            os.makedirs(CAND_DIR, exist_ok=True)
            cv2.imwrite(os.path.join(CAND_DIR, f'{cid}.jpg'), f['crop'])
            c['items'][cid] = {'feats': [], 'count': 0, 'days': [], 'first': time.time(), 'last': 0, 'asked': ''}
        it = c['items'][cid]
        it['count'] += 1
        it['last'] = time.time()
        if today not in it['days']:
            it['days'].append(today)
        if len(it['feats']) < 5:
            it['feats'].append(f['feat'].flatten().tolist())
        if it['count'] >= ASK_AFTER and len(it['days']) >= ASK_DAYS and it['asked'] != today:
            it['asked'] = today
            asks.append(cid)
    _save_cands(c)
    return known, unknown, asks


def pending():
    """聞く条件に達している候補の一覧 [{id, count, days}]。"""
    c = _load_cands()
    return [{'id': cid, 'count': it['count'], 'days': len(it['days'])}
            for cid, it in c['items'].items() if it['count'] >= ASK_AFTER and len(it['days']) >= ASK_DAYS]


def enroll_candidate(cid, name):
    """候補を名前つきで登録する（ゆうころが「#3 はけんちゃんだよ」と答えた時）。"""
    c = _load_cands()
    it = c['items'].get(str(cid))
    if not it:
        return False
    names, feats = _load_db()
    for f in it['feats']:
        names.append(name)
        feats.append(np.asarray(f, dtype=np.float32))
    _save_db(names, feats)
    src = os.path.join(CAND_DIR, f'{cid}.jpg')
    if os.path.exists(src):
        os.makedirs(os.path.join(PEOPLE, name), exist_ok=True)
        shutil.move(src, os.path.join(PEOPLE, name, f'from_candidate_{cid}.jpg'))
    c['items'].pop(str(cid), None)
    _save_cands(c)
    return True


def dismiss_candidate(cid):
    c = _load_cands()
    if str(cid) not in c['items']:
        return False
    _drop(c, str(cid))
    _save_cands(c)
    return True


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'enroll':
        sys.exit(enroll())
    if len(sys.argv) >= 2 and sys.argv[1] == 'candidates':
        for cid, it in _load_cands()['items'].items():
            print(f"#{cid}: {it['count']}回 / {len(it['days'])}日 / 最後 {time.strftime('%m-%d', time.localtime(it['last']))}")
        sys.exit(0)
    if len(sys.argv) >= 3 and sys.argv[1] == 'who':
        k, u = who(sys.argv[2])
        print('映っている人:', ', '.join(k) if k else '（登録済みの人はいない）', f'/ 知らない顔: {u}')
        sys.exit(0)
    print(__doc__)
