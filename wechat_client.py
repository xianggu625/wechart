# 微信公众号API封装
# wechat_client.py
import os
import requests
import json
from typing import Optional, Dict, Any
from loguru import logger
import time

class WeChatClient:
    """微信公众号API客户端"""
    
    def __init__(self):
        self.app_id = os.getenv("WECHAT_APP_ID")
        self.app_secret = os.getenv("WECHAT_APP_SECRET")
        self.access_token = None
        self.token_expires = 0
        
    def _get_access_token(self) -> Optional[str]:
        """获取access_token（自动缓存）"""
        if self.access_token and time.time() < self.token_expires:
            return self.access_token
        
        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret
        }
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            
            if "access_token" in data:
                self.access_token = data["access_token"]
                self.token_expires = time.time() + data["expires_in"] - 200  # 提前200秒刷新
                logger.info("access_token获取成功")
                return self.access_token
            else:
                logger.error(f"获取token失败: {data}")
                return None
        except Exception as e:
            logger.error(f"获取token异常: {e}")
            return None
    
    def upload_image(self, image_url: str) -> Optional[str]:
        """
        从URL下载图片并上传到公众号素材库
        
        Returns:
            media_id: 素材ID
        """
        token = self._get_access_token()
        if not token:
            return None
        
        # 下载图片
        try:
            img_resp = requests.get(image_url, timeout=30)
            if img_resp.status_code != 200:
                logger.error(f"图片下载失败: {image_url}")
                return None
        except Exception as e:
            logger.error(f"图片下载异常: {e}")
            return None
        
        # 上传到公众号
        url = f"https://api.weixin.qq.com/cgi-bin/media/upload"
        params = {
            "access_token": token,
            "type": "image"
        }
        
        files = {
            "media": ("image.jpg", img_resp.content, "image/jpeg")
        }
        
        try:
            resp = requests.post(url, params=params, files=files, timeout=30)
            data = resp.json()
            
            if "media_id" in data:
                logger.success(f"图片上传成功，media_id: {data['media_id']}")
                return data["media_id"]
            else:
                logger.error(f"图片上传失败: {data}")
                return None
        except Exception as e:
            logger.error(f"图片上传异常: {e}")
            return None
    
    def add_draft(self, article: Dict[str, Any], thumb_media_id: str) -> bool:
        """
        添加图文草稿
        
        Args:
            article: 文章内容（含title, content, author等）
            thumb_media_id: 封面图素材ID
        """
        token = self._get_access_token()
        if not token:
            return False
        
        url = "https://api.weixin.qq.com/cgi-bin/draft/add"
        params = {"access_token": token}
        
        # 构建草稿数据
        data = {
            "articles": [
                {
                    "title": article["title"],
                    "author": "AI测试助手",
                    "digest": article.get("summary", article["title"]),
                    "content": article["content"],
                    "thumb_media_id": thumb_media_id,
                    "need_open_comment": 1,
                    "only_fans_can_comment": 0,
                    "show_cover_pic": 1
                }
            ]
        }
        
        try:
            resp = requests.post(url, params=params, json=data, timeout=15)
            result = resp.json()
            
            if "media_id" in result:
                logger.success(f"草稿创建成功，media_id: {result['media_id']}")
                return True
            else:
                logger.error(f"草稿创建失败: {result}")
                return False
        except Exception as e:
            logger.error(f"草稿创建异常: {e}")
            return False
