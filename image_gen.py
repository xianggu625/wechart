# 图像生成模块（通义万相）
# image_gen.py
import os
import requests
import json
import time
from typing import Optional
from loguru import logger

class ImageGenerator:
    """通义万相图像生成"""
    
    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    
    def generate(self, prompt: str) -> Optional[str]:
        """
        根据提示词生成图片
        
        Returns:
            图片URL
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "model": "qwen-image-plus",
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"text": prompt}
                        ]
                    }
                ]
            },
            "parameters": {
                "negative_prompt": "text, watermark, signature, low quality, blurry",
                "prompt_extend": True,
                "size": "1024*1024"
            }
        }
        
        try:
            resp = requests.post(self.base_url, headers=headers, json=data, timeout=60)
            result = resp.json()
            
            # 解析返回结果
            if "output" in result and "results" in result["output"]:
                image_url = result["output"]["results"][0]["url"]
                logger.success(f"图片生成成功: {image_url}")
                return image_url
            else:
                logger.error(f"图片生成失败: {result}")
                return None
        except Exception as e:
            logger.error(f"图片生成异常: {e}")
            return None
