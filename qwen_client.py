# 阿里千问客户端封装
# qwen_client.py
import os
from openai import OpenAI
from typing import Dict, Any
from loguru import logger

class QwenClient:
    """阿里千问API客户端封装"""
    
    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.model = os.getenv("QWEN_MODEL", "qwen-plus")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        logger.info(f"千问客户端初始化完成，使用模型: {self.model}")
    
    def generate_article(self, topic: str = None) -> Dict[str, Any]:
        """
        生成AI软件测试相关文章
        
        Args:
            topic: 具体主题，为空则自动生成
            
        Returns:
            {
                "title": "文章标题",
                "content": "文章正文(HTML格式)",
                "summary": "摘要",
                "image_prompt": "配图生成提示词"
            }
        """
        system_prompt = """你是一位专业的AI软件测试领域专家，负责为「啄木鸟软件测试」公众号撰写高质量技术文章。

文章要求：
1. 标题：吸引人、包含关键词、20字以内
2. 内容：2000字左右，结构清晰，包含引言、2-4个小标题段落、结语
3. 风格：专业但不晦涩，有洞察力和前瞻性，可引用真实案例
4. 配图提示词：为文章配图生成英文提示词，用于文生图模型
5. 输出格式：严格按照JSON格式返回
"""

        user_prompt = f"请撰写一篇关于「{topic or 'AI软件测试'}」的技术文章"
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.8
            )
            
            result = completion.choices[0].message.content
            # 解析JSON
            import json
            article = json.loads(result)
            
            # 确保内容包含HTML标签，用于公众号排版
            article["content"] = self._format_content(article.get("content", ""))
            
            logger.success(f"文章生成成功: {article.get('title')}")
            return article
            
        except Exception as e:
            logger.error(f"文章生成失败: {e}")
            # 返回备用内容
            return self._get_fallback_article(topic)
    
    def _format_content(self, content: str) -> str:
        """将纯文本转换为带HTML标签的公众号格式"""
        # 分割段落
        paragraphs = content.split('\n\n')
        
        html_parts = []
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            
            # 判断是否为标题
            if p.startswith('# '):
                html_parts.append(f'<h2>{p[2:]}</h2>')
            elif p.startswith('## '):
                html_parts.append(f'<h3>{p[3:]}</h3>')
            else:
                html_parts.append(f'<p>{p}</p>')
        
        return '\n'.join(html_parts)
    
    def _get_fallback_article(self, topic: str) -> Dict[str, Any]:
        """API调用失败时的备用文章"""
        return {
            "title": f"今日AI测试洞察：{topic or 'AI软件测试'}",
            "content": "<p>内容生成服务暂时不可用，请稍后查看。</p>",
            "summary": "内容生成服务暂时不可用",
            "image_prompt": "AI software testing, futuristic, blue tone"
        }
