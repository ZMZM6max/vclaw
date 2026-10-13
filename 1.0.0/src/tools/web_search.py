"""Web 搜索工具 - 搜索网络信息"""
import os
import json
import asyncio
from typing import Optional, List
from pydantic import BaseModel, Field
from .base import Tool, ToolResult, ToolError


class WebSearchInput(BaseModel):
    """WebSearch 输入参数"""
    query: str = Field(..., description="搜索查询")
    num_results: Optional[int] = Field(5, description="返回结果数量（1-10）")


class WebSearchTool(Tool):
    """
    搜索网络获取最新信息
    
    功能：
    - 获取最新新闻、文档、教程
    - 查找技术文档和 API 参考
    - 搜索代码示例和最佳实践
    
    数据源：
    - Google Custom Search API（需要 API key）
    - Bing Search API（需要 API key）
    - 模拟模式（无需 API key，返回固定结果）
    
    环境变量配置：
    - GOOGLE_API_KEY + GOOGLE_CSE_ID - 使用 Google 搜索
    - BING_API_KEY - 使用 Bing 搜索
    
    注意：如果没有配置 API key，工具会工作在模拟模式
    """
    
    name = "web_search"
    description = """搜索网络获取最新信息。支持查找文档、教程、新闻、代码示例等。

配置（可选）：
- GOOGLE_API_KEY + GOOGLE_CSE_ID: 使用 Google 搜索
- BING_API_KEY: 使用 Bing 搜索

无配置时使用模拟模式。"""
    search_hint = "search the web for current information"
    read_only = True
    
    input_schema = WebSearchInput
    max_result_size = 50_000
    
    async def call(self, query: str, num_results: int = 5) -> ToolResult:
        """
        执行网络搜索
        
        Args:
            query: 搜索查询
            num_results: 结果数量
        """
        num_results = max(1, min(10, num_results))
        
        # 检查 API 配置
        google_key = os.getenv('GOOGLE_API_KEY')
        google_cse = os.getenv('GOOGLE_CSE_ID')
        bing_key = os.getenv('BING_API_KEY')
        
        try:
            if google_key and google_cse:
                results = await self._search_google(query, num_results, google_key, google_cse)
            elif bing_key:
                results = await self._search_bing(query, num_results, bing_key)
            else:
                # 模拟模式
                results = self._search_mock(query, num_results)
            
            # 格式化结果
            content_lines = [f"Web search results for: '{query}'\n"]
            for i, r in enumerate(results, 1):
                content_lines.append(f"\n{i}. {r['title']}")
                content_lines.append(f"   URL: {r['url']}")
                content_lines.append(f"   {r.get('snippet', '')}")
            
            return ToolResult(
                success=True,
                content='\n'.join(content_lines),
                data={
                    "query": query,
                    "results": results,
                    "source": "google" if google_key else ("bing" if bing_key else "mock")
                }
            )
            
        except Exception as e:
            raise ToolError(
                f"Search error: {str(e)}",
                error_code=1,
                details={"exception": str(e)}
            )
    
    async def _search_google(self, query: str, num: int, api_key: str, 
                             cse_id: str) -> List[dict]:
        """使用 Google Custom Search API"""
        import aiohttp
        
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': api_key,
            'cx': cse_id,
            'q': query,
            'num': num
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=30) as resp:
                data = await resp.json()
                
                items = data.get('items', [])
                return [
                    {
                        "title": item.get('title', ''),
                        "url": item.get('link', ''),
                        "snippet": item.get('snippet', '')
                    }
                    for item in items[:num]
                ]
    
    async def _search_bing(self, query: str, num: int, api_key: str) -> List[dict]:
        """使用 Bing Search API"""
        import aiohttp
        
        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {'Ocp-Apim-Subscription-Key': api_key}
        params = {'q': query, 'count': num}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params, timeout=30) as resp:
                data = await resp.json()
                
                items = data.get('webPages', {}).get('value', [])
                return [
                    {
                        "title": item.get('name', ''),
                        "url": item.get('url', ''),
                        "snippet": item.get('snippet', '')
                    }
                    for item in items[:num]
                ]
    
    def _search_mock(self, query: str, num: int) -> List[dict]:
        """模拟搜索（无需 API key）"""
        # 返回一些通用的搜索提示
        return [
            {
                "title": f"Search: {query}",
                "url": f"https://www.google.com/search?q={query.replace(' ', '+')}",
                "snippet": "(模拟模式) 配置 GOOGLE_API_KEY 和 GOOGLE_CSE_ID 获取真实搜索结果"
            },
            {
                "title": "如何配置 Web 搜索",
                "url": "https://developers.google.com/custom-search/v1/overview",
                "snippet": "配置 Google Custom Search API 获取真实搜索结果"
            }
        ]
