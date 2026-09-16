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
"""
import os
import sys

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

_det = _rec = None


def available():
    return os.path.exists(YUNET) and os.path.exists(SFACE)


def _load():
    global _det, _rec
    if _det is None:
        _det = cv2.FaceDetectorYN.create(YUNET, '', (320, 320), SCORE, 0.3, 5000)
        _rec = cv2.FaceRecognizerSF.create(SFACE, '')


def _faces(img):
    """検出した顔ごとに特徴ベクトルを返す。"""
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
        out.append(feat)
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
            feats.append(fs[0].flatten())
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
        best, best_score = None, -1.0
        for name, ref in zip(names, feats):
            s = _rec.match(f, ref.reshape(1, -1), cv2.FaceRecognizerSF_FR_COSINE)
            if s > best_score:
                best, best_score = name, s
        if best is not None and best_score >= THRESHOLD:
            if best not in known:
                known.append(str(best))
        else:
            unknown += 1
    return known, unknown


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'enroll':
        sys.exit(enroll())
    if len(sys.argv) >= 3 and sys.argv[1] == 'who':
        k, u = who(sys.argv[2])
        print('映っている人:', ', '.join(k) if k else '（登録済みの人はいない）', f'/ 知らない顔: {u}')
        sys.exit(0)
    print(__doc__)
