#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人脸情绪检测 — 功能性测试脚本

用法:
  1. 摄像头实时测试:  python tests/test_face_detect_live.py
  2. 指定图片测试:    python tests/test_face_detect_live.py path/to/photo.jpg
  3. 对比多个后端:    python tests/test_face_detect_live.py --compare path/to/photo.jpg

测试内容:
  - DeepFace 是否能正常加载
  - 人脸检测是否工作（opencv / ssd / retinaface）
  - 情绪分类结果是否合理
  - 与项目中 EmotionDetector 的调用方式一致
"""

import sys
import os
import time
import json
import numpy as np
from pathlib import Path

# 确保能导入项目模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_image(source):
    """从文件或摄像头加载图片，返回 (numpy_array, jpeg_bytes)"""
    from PIL import Image
    import io

    if source and os.path.isfile(source):
        print(f"[CAM] 从文件加载: {source}")
        img = Image.open(source).convert("RGB")
    else:
        print("[CAM] 从摄像头捕获...")
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[FAIL] 无法打开摄像头")
            sys.exit(1)
        # 预热几帧让自动曝光稳定
        for _ in range(10):
            cap.read()
        ret, frame = cap.read()
        cap.release()
        if not ret:
            print("[FAIL] 摄像头读取失败")
            sys.exit(1)
        # OpenCV BGR → RGB
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        print(f"   捕获尺寸: {img.size[0]}x{img.size[1]}")

    img_array = np.array(img)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    jpeg_bytes = buf.getvalue()

    return img_array, jpeg_bytes


def test_deepface_direct(img_array, backend="opencv"):
    """直接调用 DeepFace.analyze，打印完整原始返回"""
    from deepface import DeepFace

    print(f"\n{'='*60}")
    print(f"测试 DeepFace.analyze (backend={backend})")
    print(f"{'='*60}")
    print(f"   图片形状: {img_array.shape}, dtype={img_array.dtype}")

    t0 = time.time()
    try:
        results = DeepFace.analyze(
            img_path=img_array,
            actions=["emotion"],
            enforce_detection=False,
            detector_backend=backend,
            silent=True,
        )
        elapsed = (time.time() - t0) * 1000
    except Exception as e:
        print(f"   [FAIL] 异常: {type(e).__name__}: {e}")
        return None

    face = results[0] if isinstance(results, list) else results

    # 打印完整原始返回（方便调试）
    print(f"   耗时: {elapsed:.0f}ms")
    print(f"   dominant_emotion: {face.get('dominant_emotion')}")
    print(f"   face_confidence:  {face.get('face_confidence')}")
    print(f"   region:           {face.get('region')}")
    print(f"   emotion scores:")
    for emo, score in sorted(face.get("emotion", {}).items(), key=lambda x: -x[1]):
        bar = "#" * int(score / 2)
        print(f"     {emo:>10s}: {score:5.1f}%  {bar}")

    # 与项目 detector.py 相同的判断逻辑
    face_confidence = face.get("face_confidence", 0)
    region = face.get("region", {})
    region_area = region.get("w", 0) * region.get("h", 0)
    img_area = img_array.shape[0] * img_array.shape[1]
    ratio = region_area / max(img_area, 1)

    print(f"\n   [项目判断逻辑]")
    print(f"   face_confidence={face_confidence}, region_area={region_area}, "
          f"img_area={img_area}, ratio={ratio:.2%}")

    if face_confidence == 0 and (region_area == 0 or ratio > 0.9):
        print(f"   → has_face=False (置信度为0且区域占比{ratio:.0%}>90%)")
    else:
        print(f"   → has_face=True [OK]")

    return face


def test_project_detector(jpeg_bytes):
    """用项目中的 EmotionDetector 类测试（与实际 API 调用路径一致）"""
    import asyncio
    from emotion.detector import EmotionDetector

    print(f"\n{'='*60}")
    print("测试 EmotionDetector (项目实际调用路径)")
    print(f"{'='*60}")
    print(f"   JPEG 大小: {len(jpeg_bytes)} bytes")

    detector = EmotionDetector(deep_llm_call=None)

    t0 = time.time()
    result = asyncio.get_event_loop().run_until_complete(
        detector.detect(jpeg_bytes)
    )
    elapsed = (time.time() - t0) * 1000

    print(f"   耗时: {elapsed:.0f}ms")
    print(f"   has_face: {result['has_face']}")
    if result["local"]:
        print(f"   emotion:  {result['local']['emotion']} "
              f"({result['local']['confidence']*100:.1f}%)")
        print(f"   changed:  {result['changed']}")
    else:
        print("   [FAIL] 未检测到人脸")

    return result


def compare_backends(img_array):
    """对比多个检测后端"""
    print(f"\n{'='*60}")
    print("对比多个检测后端")
    print(f"{'='*60}")

    backends = ["opencv", "ssd", "mediapipe"]
    results = {}

    for backend in backends:
        try:
            face = test_deepface_direct(img_array, backend=backend)
            if face:
                fc = face.get("face_confidence", 0)
                results[backend] = {
                    "emotion": face.get("dominant_emotion"),
                    "confidence": fc,
                    "status": "[OK]" if fc > 0 else "⚠️ no face"
                }
            else:
                results[backend] = {"status": "[FAIL] failed"}
        except Exception as e:
            results[backend] = {"status": f"[FAIL] {e}"}

    print(f"\n{'='*60}")
    print("后端对比结果")
    print(f"{'='*60}")
    for backend, r in results.items():
        status = r["status"]
        emo = r.get("emotion", "")
        conf = r.get("confidence", 0)
        print(f"   {backend:>12s}: {status}  {emo}  (face_conf={conf})")


if __name__ == "__main__":
    args = sys.argv[1:]
    do_compare = "--compare" in args
    args = [a for a in args if a != "--compare"]
    source = args[0] if args else None

    img_array, jpeg_bytes = load_image(source)

    if do_compare:
        compare_backends(img_array)
    else:
        # 1. 直接调用 DeepFace（原始返回）
        test_deepface_direct(img_array, backend="ssd")

        # 2. 用项目 EmotionDetector 测试
        test_project_detector(jpeg_bytes)

    print("\n[OK] 测试完成")
