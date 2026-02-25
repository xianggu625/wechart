# 新增 run_publisher.py
import os
from dotenv import load_dotenv
from qwen_client import QwenClient
from wechat_client import WeChatClient
from image_gen import ImageGenerator
from topic_generator import TopicGenerator
from loguru import logger

def main():
    load_dotenv()
    
    qwen = QwenClient()
    wechat = WeChatClient()
    image_gen = ImageGenerator()
    
    # 1. 生成主题
    topic = TopicGenerator.generate("AI软件测试")
    logger.info(f"今日主题: {topic}")
    
    # 2. 生成文章内容
    article = qwen.generate_article(topic)
    
    # 3. 生成配图
    image_prompt = article.get("image_prompt", "AI software testing, futuristic technology")
    image_url = image_gen.generate(image_prompt) or "https://example.com/default.jpg"
    
    # 4. 上传配图
    media_id = wechat.upload_image(image_url)
    if not media_id:
        logger.error("配图上传失败")
        return
    
    # 5. 创建草稿
    success = wechat.add_draft(article, media_id)
    if success:
        logger.success(f"文章已保存草稿: {article['title']}")
    else:
        logger.error("草稿保存失败")

if __name__ == "__main__":
    main()
