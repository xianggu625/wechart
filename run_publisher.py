import os
import sys
import time
import json
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger
import requests

# 导入你的模块
from qwen_client import QwenClient
from wechat_client import WeChatClient
from image_gen import ImageGenerator
from topic_generator import TopicGenerator

# 配置日志格式，输出到控制台和文件
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)
logger.add(
    "logs/publisher_{time:YYYYMMDD}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG"
)

def get_local_fallback_image() -> str:
    """获取本地备用图片的绝对路径"""
    # 获取当前脚本所在目录
    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.join(base_dir, "default_cover.jpg")
    
    if os.path.exists(local_path):
        return local_path
    else:
        logger.warning(f"本地备用图未找到: {local_path}，请确保该文件存在以防网络完全不可用。")
        return None

def extract_image_url_from_result(image_result) -> str:
    """从AI绘图返回的结果中提取图片URL"""
    if not image_result:
        return None
    
    # 情况1: 直接返回了URL字符串
    if isinstance(image_result, str):
        if image_result.startswith(('http://', 'https://')):
            return image_result
        # 情况2: 可能是JSON字符串
        elif image_result.startswith('{'):
            try:
                data = json.loads(image_result)
                # 尝试多种可能的路径提取URL
                if 'output' in data and 'choices' in data['output']:
                    for choice in data['output']['choices']:
                        if 'message' in choice and 'content' in choice['message']:
                            content = choice['message']['content']
                            if isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict) and 'image' in item:
                                        return item['image']
                            elif isinstance(content, dict) and 'image' in content:
                                return content['image']
                # 其他可能的格式
                elif 'data' in data and isinstance(data['data'], dict) and 'url' in data['data']:
                    return data['data']['url']
                elif 'url' in data:
                    return data['url']
            except Exception as e:
                logger.debug(f"JSON解析失败: {e}")
    
    # 情况3: 直接返回了字典
    elif isinstance(image_result, dict):
        # 尝试多种可能的路径
        if 'output' in image_result and 'choices' in image_result['output']:
            for choice in image_result['output']['choices']:
                if 'message' in choice and 'content' in choice['message']:
                    content = choice['message']['content']
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and 'image' in item:
                                return item['image']
        elif 'data' in image_result and isinstance(image_result['data'], dict) and 'url' in image_result['data']:
            return image_result['data']['url']
        elif 'url' in image_result:
            return image_result['url']
    
    return None

def upload_local_image(wechat_client, image_path: str) -> str:
    """上传本地图片到微信"""
    token = wechat_client._get_access_token()
    if not token:
        logger.error("无法获取 Token，无法上传本地图片")
        return None
    
    try:
        with open(image_path, 'rb') as f:
            files = {'media': ('cover.jpg', f.read(), 'image/jpeg')}
        url = "https://api.weixin.qq.com/cgi-bin/material/add_material"
        params = {"access_token": token, "type": "image"}
        resp = requests.post(url, params=params, files=files, timeout=30)
        data = resp.json()
        if "media_id" in data:
            media_id = data["media_id"]
            logger.success(f"本地图片上传成功，media_id: {media_id}")
            return media_id
        else:
            logger.error(f"本地图片上传失败: {data}")
            return None
    except Exception as e:
        logger.error(f"本地图片上传异常: {e}")
        return None

def run_publish_task():
    """执行单次发布任务"""
    logger.info("="*30)
    logger.info("开始执行 AI 文章发布任务")
    logger.info(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*30)

    # 初始化客户端
    try:
        qwen = QwenClient()
        wechat = WeChatClient()
        image_gen = ImageGenerator()
    except Exception as e:
        logger.error(f"客户端初始化失败: {e}")
        return False

    # 1. 生成主题
    logger.info("步骤 1: 生成文章主题...")
    topic = TopicGenerator.generate("AI软件测试")
    logger.info(f"今日主题: {topic}")

    # 2. 生成文章内容
    logger.info("步骤 2: 生成文章内容...")
    article = qwen.generate_article(topic)
    
    if not article or not article.get("title"):
        logger.error("文章生成失败，内容为空")
        return False
    
    logger.success(f"文章生成成功: {article['title']}")

    # 3. 生成/获取配图
    logger.info("步骤 3: 准备配图...")
    image_url = None
    image_path = None
    media_id = None

    # 尝试方案 A: AI 生成
    image_prompt = article.get("image_prompt", "AI software testing, futuristic technology, blue tone, 4k")
    logger.info(f"正在调用 AI 绘图: {image_prompt[:40]}...")
    
    # 调用AI绘图
    image_result = image_gen.generate(image_prompt)
    
    # 从返回结果中提取图片URL
    image_url = extract_image_url_from_result(image_result)
    
    if image_url:
        logger.success(f"AI 绘图成功，获取到图片URL: {image_url}")
    else:
        logger.warning(f"AI 绘图未返回有效图片URL，返回内容: {str(image_result)[:100]}...")

    # 尝试方案 B: 网络备用图 (如果 AI 生成失败)
    if not image_url:
        logger.warning("AI 绘图失败，尝试使用网络备用图 (picsum)...")
        # 加时间戳防止缓存
        fallback_url = f"https://picsum.photos/1024/1024?random={int(time.time())}"
        try:
            # 先测试能否连通
            head_resp = requests.head(fallback_url, timeout=5, allow_redirects=True)
            if head_resp.status_code == 200:
                image_url = fallback_url
                logger.info(f"网络备用图可用: {fallback_url}")
            else:
                logger.warning(f"网络备用图连接失败，状态码: {head_resp.status_code}")
        except Exception as e:
            logger.warning(f"无法访问网络备用图: {e}")

    # 尝试方案 C: 本地备用图 (如果网络也挂了)
    if not image_url:
        logger.error("所有在线图片源均不可用，切换至本地备用模式...")
        local_img_path = get_local_fallback_image()
        if local_img_path:
            image_path = local_img_path
            logger.success(f"已加载本地图片: {image_path}")
        else:
            logger.critical("致命错误：无可用图片（在线离线均失败），任务中止。")
            return False

    # 4. 上传图片到微信
    logger.info("步骤 4: 上传图片到微信公众号...")
    
    # 处理图片上传
    if image_url:
        # 使用URL上传
        logger.info(f"使用图片URL: {image_url}")
        try:
            media_id = wechat.upload_permanent_image(image_url)
            if media_id:
                logger.success(f"图片上传成功，media_id: {media_id}")
            else:
                logger.error("图片上传失败，返回的media_id为空")
                
                # URL上传失败，尝试下载后上传
                logger.warning("尝试下载图片后上传...")
                try:
                    # 下载图片
                    img_resp = requests.get(image_url, timeout=30, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    })
                    if img_resp.status_code == 200:
                        # 保存到临时文件
                        temp_path = f"/tmp/temp_cover_{int(time.time())}.jpg"
                        with open(temp_path, 'wb') as f:
                            f.write(img_resp.content)
                        
                        # 上传本地文件
                        media_id = upload_local_image(wechat, temp_path)
                        
                        # 清理临时文件
                        try:
                            os.remove(temp_path)
                        except:
                            pass
                    else:
                        logger.error(f"下载图片失败，状态码: {img_resp.status_code}")
                except Exception as e:
                    logger.error(f"下载并上传图片失败: {e}")
                    
        except Exception as e:
            logger.error(f"图片上传异常: {e}")
            media_id = None
            
    elif image_path:
        # 上传本地图片
        logger.info(f"使用本地图片: {image_path}")
        media_id = upload_local_image(wechat, image_path)

    if not media_id:
        logger.error("图片上传最终失败，无法继续发布。")
        
        # 即使图片上传失败，也尝试保存文章为本地草稿
        logger.warning("尝试保存文章到本地草稿...")
        draft_dir = os.path.join(os.getcwd(), 'drafts')
        os.makedirs(draft_dir, exist_ok=True)
        
        # 生成安全的文件名
        safe_title = "".join(c for c in article['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
        draft_file = os.path.join(draft_dir, f"{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
        
        with open(draft_file, 'w', encoding='utf-8') as f:
            f.write(f"# {article['title']}\n\n")
            if image_url:
                f.write(f"![cover]({image_url})\n\n")
            elif image_path:
                f.write(f"![cover](file://{image_path})\n\n")
            f.write(article['content'])
        
        logger.success(f"文章已保存到本地草稿: {draft_file}")
        logger.info("在GitHub Actions中，此文件可作为artifact下载")
        
        # 返回False表示发布失败，但文章已保存
        return False

    # 5. 创建草稿
    logger.info("步骤 5: 创建公众号草稿...")
    success = wechat.add_draft(article, media_id)
    
    if success:
        logger.success("="*30)
        logger.success(f"🎉 任务完成！文章已保存草稿箱")
        logger.success(f"标题: {article['title']}")
        logger.success("="*30)
        return True
    else:
        logger.error("❌ 草稿保存失败")
        return False

if __name__ == "__main__":
    # 加载环境变量
    load_dotenv()
    
    # 确保 logs 目录存在
    if not os.path.exists("logs"):
        os.makedirs("logs")
    
    # 确保 drafts 目录存在（用于本地草稿备份）
    if not os.path.exists("drafts"):
        os.makedirs("drafts")

    # 运行任务
    is_success = run_publish_task()
    
    # 退出码：成功为 0，失败为 1 (方便 CI/CD 或定时任务脚本判断)
    sys.exit(0 if is_success else 1)
