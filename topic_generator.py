#主题生成模块
# topic_generator.py
import random
from datetime import datetime
from typing import List

class TopicGenerator:
    """AI软件测试主题生成器"""
    
    # 主题词库
    TOPICS = [
        "大模型测试", "AI驱动测试", "测试用例自动生成", "智能体测试",
        "LLM测试实践", "提示词测试", "RAG系统测试", "AI安全测试",
        "测试数据生成", "自愈测试脚本", "测试左移", "AI测试工具",
        "模型评估", "对抗测试", "AI在CI/CD中的应用", "测试覆盖率优化",
        "测试预测分析", "智能回归测试", "多模态测试", "A/B测试自动化"
    ]
    
    # 文章角度
    ANGLES = [
        "2026年最新趋势", "实战案例", "技术深度解析", "工具对比",
        "常见误区", "性能优化", "落地实践", "未来展望",
        "与传统的对比", "团队转型", "成本效益分析", "开源方案"
    ]
    
    @classmethod
    def generate(cls, base_topic: str = "AI软件测试") -> str:
        """生成具体文章主题"""
        topic = random.choice(cls.TOPICS)
        angle = random.choice(cls.ANGLES)
        
        # 随机组合
        templates = [
            f"{topic}：{angle}",
            f"{angle}：{topic}实战",
            f"2026年{topic}的{angle}",
            f"深度解读：{topic}{angle}",
            f"测试专家必看：{topic}{angle}"
        ]
        
        return random.choice(templates)
