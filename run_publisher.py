import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger

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
    media_id = None

    # 尝试方案 A: AI 生成
    image_prompt = article.get("image_prompt", "AI software testing, futuristic technology, blue tone, 4k")
    logger.info(f"正在调用 AI 绘图: {image_prompt[:40]}...")
    image_url = image_gen.generate(image_prompt)

    # 尝试方案 B: 网络备用图 (如果 AI 生成失败)
    if not image_url:
        logger.warning("AI 绘图失败，尝试使用网络备用图 (picsum)...")
        # 加时间戳防止缓存
        fallback_url = f"https://picsum.photos/1024/1024?random={int(time.time())}"
        try:
            import requests
            # 先测试能否连通
            head_resp = requests.head(fallback_url, timeout=5)
            if head_resp.status_code == 200:
                image_url = fallback_url
                logger.info(f"网络备用图可用: {fallback_url}")
            else:
                logger.warning("网络备用图连接失败")
        except Exception as e:
            logger.warning(f"无法访问网络备用图: {e}")

    # 尝试方案 C: 本地备用图 (如果网络也挂了)
    if not image_url:
        logger.error("所有在线图片源均不可用，切换至本地备用模式...")
        local_img_path = get_local_fallback_image()
        if local_img_path:
            image_url = local_img_path # 这里传递文件路径，wechat_client 需要能处理路径
            logger.success(f"已加载本地图片: {image_url}")
        else:
            logger.critical("致命错误：无可用图片（在线离线均失败），任务中止。")
            return False

    # 4. 上传图片到微信
    logger.info("步骤 4: 上传图片到微信公众号...")
    
    # 判断是 URL 还是 本地路径，调用不同的方法或复用逻辑
    # 注意：你的 wechat_client.py 中目前只有 upload_permanent_image(image_url)
    # 我们需要稍微变通一下，或者修改 wechat_client 以支持本地路径。
    # 为了保持兼容性，这里做一个简单的适配逻辑：
    
    if image_url.startswith(('http://', 'https://')):
        media_id = wechat.upload_permanent_image(image_url)
    else:
        # 如果是本地路径，我们需要手动读取并调用上传逻辑
        # 由于你的 WeChatClient 目前只写了从 URL 下载的逻辑，
        # 这里我们临时扩展一下逻辑，直接读取文件上传
        token = wechat._get_access_token()
        if token:
            try:
                with open(image_url, 'rb') as f:
                    files = {'media': ('cover.jpg', f.read(), 'image/jpeg')}
                url = "https://api.weixin.qq.com/cgi-bin/material/add_material"
                params = {"access_token": token, "type": "image"}
                resp = requests.post(url, params=params, files=files, timeout=30)
                data = resp.json()
                if "media_id" in data:
                    media_id = data["media_id"]
                    logger.success(f"本地图片上传成功，media_id: {media_id}")
                else:
                    logger.error(f"本地图片上传失败: {data}")
            except Exception as e:
                logger.error(f"本地图片上传异常: {e}")
        else:
            logger.error("无法获取 Token，无法上传本地图片")

    if not media_id:
        logger.error("图片上传最终失败，无法继续发布。")
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

    # 运行任务
    is_success = run_publish_task()
    
    # 退出码：成功为 0，失败为 1 (方便 CI/CD 或定时任务脚本判断)
    sys.exit(0 if is_success else 1)
