#!/bin/sh
# 顔検出(YuNet)と顔照合(SFace)のモデルを取得する。OpenCV公式のmodel zooから。
# Windowsなら PowerShell で:
#   curl.exe -L -o osanpo\faces\models\yunet.onnx https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
#   curl.exe -L -o osanpo\faces\models\sface.onnx https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
set -e
D="$(dirname "$0")/models"
mkdir -p "$D"
curl -L -o "$D/yunet.onnx" https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
curl -L -o "$D/sface.onnx" https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
ls -la "$D"
