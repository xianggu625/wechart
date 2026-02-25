# 主服务与定时任务
# main.py
from fastapi import FastAPI, BackgroundTasks
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import os
from datetime import datetime
from loguru import logger

from qwen_client import QwenClient
from wechat_client import WeChatClient
from image_gen import ImageGenerator
from topic_generator import TopicGenerator

# 配置日志
logger.add("logs/article_{time}.log", rotation="1 day", retention="7 days")

# 初始化客户端
qwen = QwenClient()
wechat = WeChatClient()
image_gen = ImageGenerator()

def publish_daily_article():
    """每日发布任务"""
    logger.info("开始执行每日文章生成任务")
    
    try:
        # 1. 生成主题
        topic = TopicGenerator.generate("AI软件测试")
        logger.info(f"今日主题: {topic}")
        
        # 2. 生成文章内容
        article = qwen.generate_article(topic)
        
        # 3. 生成配图提示词（如果文章中没有，则使用默认）
        image_prompt = article.get("image_prompt", 
                                  "AI software testing, futuristic technology, blue tone, 4k")
        
        # 4. 生成配图
        image_url = image_gen.generate(image_prompt)
        if not image_url:
            # 使用默认配图（可选：从备用图库选择）
            logger.warning("图片生成失败，使用默认图片")
            image_url = "https://example.com/default_cover.jpg"
        
        # 5. 上传配图到公众号
        media_id = wechat.upload_image(image_url)
        if not media_id:
            logger.error("配图上传失败，中止发布")
            return
        
        # 6. 创建草稿/发布
        save_to_draft = os.getenv("SAVE_TO_DRAFT", "true").lower() == "true"
        
        if save_to_draft:
            success = wechat.add_draft(article, media_id)
            if success:
                logger.info(f"文章已保存到草稿箱: {article['title']}")
            else:
                logger.error("草稿保存失败")
        else:
            # 直接发布（需要额外调用发布接口）
            logger.warning("直接发布功能暂未实现，已保存为草稿")
            wechat.add_draft(article, media_id)
        
        logger.success("每日文章任务执行完成")
        
    except Exception as e:
        logger.error(f"任务执行失败: {e}", exc_info=True)


# 调度器
scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时配置定时任务
    publish_time = os.getenv("PUBLISH_TIME", "08:00")
    hour, minute = map(int, publish_time.split(":"))
    
    scheduler.add_job(
        publish_daily_article,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="daily_article_publish",
        replace_existing=True
    )
    scheduler.start()
    
    logger.info(f"定时任务已启动，每日 {publish_time} 执行")
    
    yield
    
    # 关闭时停止调度器
    scheduler.shutdown()
    logger.info("应用关闭，调度器已停止")


# 创建FastAPI应用
app = FastAPI(
    title="AI软件测试公众号自动发布系统",
    description="每日自动生成AI软件测试文章并发布到公众号",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """健康检查"""
    return {
        "status": "running",
        "service": "AI测试文章自动发布系统",
        "next_run": os.getenv("PUBLISH_TIME", "08:00")
    }


@app.post("/trigger")
async def trigger_publish(background_tasks: BackgroundTasks):
    """手动触发发布（用于测试）"""
    background_tasks.add_task(publish_daily_article)
    return {"message": "发布任务已触发"}


@app.get("/health")
async def health():
    """详细健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "qwen_api": "configured" if os.getenv("DASHSCOPE_API_KEY") else "missing",
            "wechat_api": "configured" if os.getenv("WECHAT_APP_ID") else "missing"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
