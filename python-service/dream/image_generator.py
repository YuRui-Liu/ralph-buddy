#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DreamImageGenerator — 梦境图片生成器
调用硅基流动 (SiliconFlow) Images API 生成梦境可视化图片。
"""

import os
import base64
import httpx
from datetime import datetime
from typing import Optional

DREAMS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'data', 'dreams')
)


class DreamImageGenerator:

    def __init__(self, config: dict):
        self.base_url = config.get("base_url", "https://api.siliconflow.cn/v1")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "black-forest-labs/FLUX.1-schnell")
        os.makedirs(DREAMS_DIR, exist_ok=True)

    async def generate(self, prompt: str) -> Optional[dict]:
        if not self.api_key or self.api_key == "sk-xxx":
            print("[DreamImage] 未配置 image.api_key，跳过图片生成")
            return None

        url = f"{self.base_url.rstrip('/')}/images/generations"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "prompt": prompt,
            "image_size": "512x512",
            "batch_size": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            images = data.get("images") or data.get("data") or []
            if not images:
                print(f"[DreamImage] API 返回无图片: {data}")
                return None

            img_item = images[0]
            img_url = img_item.get("url") or img_item.get("b64_json") or ""

            if img_url.startswith("data:"):
                b64_data = img_url.split(",", 1)[1] if "," in img_url else img_url
                img_bytes = base64.b64decode(b64_data)
            elif img_url.startswith("http"):
                async with httpx.AsyncClient(timeout=30) as client:
                    dl = await client.get(img_url)
                    dl.raise_for_status()
                    img_bytes = dl.content
                b64_data = base64.b64encode(img_bytes).decode()
            elif img_item.get("b64_json"):
                b64_data = img_item["b64_json"]
                img_bytes = base64.b64decode(b64_data)
            else:
                print(f"[DreamImage] 无法解析图片格式: {img_item.keys()}")
                return None

            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"{timestamp}.png"
            filepath = os.path.join(DREAMS_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(img_bytes)

            print(f"[DreamImage] 已保存: {filepath} ({len(img_bytes)} bytes)")
            return {
                "image_path": f"data/dreams/{filename}",
                "image_base64": b64_data,
            }

        except Exception as e:
            print(f"[DreamImage] 图片生成失败: {e}")
            return None
