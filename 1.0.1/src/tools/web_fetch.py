"""Web 获取工具 - 获取网页内容"""
import os
from typing import Optional
from pydantic import BaseModel, Field
from .base import Tool, ToolResult, ToolError


class WebFetchInput(BaseModel):
    """WebFetch 输入参数"""
    url: str = Field(..., description="要获取的网页 URL")
    max_length: Optional[int] = Field(10000, description="最大内容长度")


class WebFetchTool(Tool):
    """
    获取网页内容
    
    功能：
    - 获取网页 HTML 内容
    - 提取主要文本内容
    - 支持截断长页面
    
    使用场景：
    - 获取技术文档
    - 阅读博客文章
    - 查看 API 文档
    
    注意：
    - 某些网站可能阻止爬虫访问
    - JavaScript 渲染的内容可能无法获取
    - 大型页面会自动截断
    
    依赖：需要安装 requests 和 beautifulsoup4
    pip install requests beautifulsoup4
    """
    
    name = "web_fetch"
    description = """获取网页内容并提取文本。

支持：
- 技术文档阅读
- 博客文章获取
- API 文档查看

注意：某些网站可能阻止访问，JS 渲染内容可能无法获取。"""
    search_hint = "fetch web page content"
    read_only = True
    
    input_schema = WebFetchInput
    max_result_size = 50_000
    
    async def call(self, url: str, max_length: int = 10000) -> ToolResult:
        """
        获取网页内容
        
        Args:
            url: 网页 URL
            max_length: 最大内容长度
        """
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            raise ToolError(
                "Required packages not installed. Run: pip install requests beautifulsoup4",
                error_code=1
            )
        
        try:
            # 发送请求
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 解析 HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 移除脚本和样式
            for script in soup(['script', 'style', 'nav', 'footer']):
                script.decompose()
            
            # 提取文本
            text = soup.get_text(separator='\n', strip=True)
            
            # 清理空行
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines)
            
            # 截断
            truncated = len(text) > max_length
            if truncated:
                text = text[:max_length] + "\n\n... [Content truncated]"
            
            # 获取标题
            title = soup.find('title')
            title_text = title.get_text() if title else "No title"
            
            return ToolResult(
                success=True,
                content=f"Title: {title_text}\n\n{text}",
                data={
                    "url": url,
                    "title": title_text,
                    "content_length": len(text),
                    "truncated": truncated,
                    "status_code": response.status_code
                }
            )
            
        except requests.exceptions.RequestException as e:
            raise ToolError(
                f"Failed to fetch URL: {str(e)}",
                error_code=2,
                details={"exception": str(e)}
            )
        except Exception as e:
            raise ToolError(
                f"Error processing page: {str(e)}",
                error_code=3,
                details={"exception": str(e)}
            )
