import httpx
import json
import re
from typing import Optional, List, Dict
from config import load_llm_config
from pypdf import PdfReader, PdfWriter

class LLMService:
    def __init__(self):
        self.config = load_llm_config()
    
    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=120.0)
    
    async def test_connection(self, api_key: str, base_url: str, model: str) -> tuple[bool, str]:
        try:
            async with self._get_client() as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "Hello"}],
                        "max_tokens": 10
                    }
                )
                if response.status_code == 200:
                    return True, "连接成功"
                else:
                    error_detail = response.json().get("error", {}).get("message", "未知错误")
                    return False, f"连接失败: {error_detail}"
        except httpx.ConnectError:
            return False, "无法连接到服务器，请检查 Base URL"
        except httpx.TimeoutException:
            return False, "连接超时，请稍后重试"
        except Exception as e:
            return False, f"连接失败: {str(e)}"
    
    def _extract_json(self, content: str) -> List[Dict]:
        print(f"LLM raw response: {content[:500]}...")
        
        json_patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
            r'\[[\s\S]*\]',
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, content)
            if match:
                json_str = match.group(1) if '```' in pattern else match.group()
                json_str = json_str.strip()
                try:
                    result = json.loads(json_str)
                    if isinstance(result, list):
                        return result
                except json.JSONDecodeError as e:
                    print(f"JSON parse error: {e}")
                    continue
        
        raise Exception("无法从 LLM 响应中提取有效的 JSON 格式")
    
    async def generate_outline_from_toc(
        self,
        toc_text: str,
        page_offset: int = 0
    ) -> List[Dict]:
        if not self.config.get("api_key"):
            raise Exception("未配置 LLM API Key")
        
        prompt = f"""请分析以下目录文本，提取出文档的大纲结构。返回 JSON 格式，包含 title（标题）、page（页码）、children（子章节，可选）字段。

目录文本：
{toc_text}

要求：
1. 识别章节标题和对应的页码
2. 保持层级结构
3. 页码需要加上偏移量 {page_offset}
4. 只返回 JSON 数组，不要其他内容

示例格式：
[
    {{"title": "第一章", "page": 1, "children": [
        {{"title": "1.1 简介", "page": 2}}
    ]}}
]
"""
        
        try:
            async with self._get_client() as client:
                response = await client.post(
                    f"{self.config['base_url']}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.config['api_key']}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.config["model"],
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 4000
                    }
                )
                
                if response.status_code != 200:
                    raise Exception(f"LLM API 调用失败: {response.text}")
                
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                outline = self._extract_json(content)
                return self._apply_page_offset(outline, page_offset)
                    
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            raise Exception("LLM 返回的内容格式错误，请重试或检查 LLM 配置")
        except Exception as e:
            print(f"Generate outline error: {e}")
            raise
    
    async def generate_outline_from_content(
        self,
        content: str
    ) -> List[Dict]:
        if not self.config.get("api_key"):
            raise Exception("未配置 LLM API Key")
        
        prompt = f"""请分析以下 PDF 内容，生成文档大纲。返回 JSON 格式，包含 title（标题）、page（页码）、children（子章节，可选）字段。

内容：
{content[:15000]}

要求：
1. 总结主要章节和内容
2. 估计合理的页码（从1开始）
3. 保持层级结构
4. 只返回 JSON 数组，不要其他内容

示例格式：
[
    {{"title": "第一章", "page": 1, "children": [
        {{"title": "1.1 简介", "page": 2}}
    ]}}
]
"""
        
        try:
            async with self._get_client() as client:
                response = await client.post(
                    f"{self.config['base_url']}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.config['api_key']}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.config["model"],
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 4000
                    }
                )
                
                if response.status_code != 200:
                    raise Exception(f"LLM API 调用失败: {response.text}")
                
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                return self._extract_json(content)
                    
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            raise Exception("LLM 返回的内容格式错误，请重试或检查 LLM 配置")
        except Exception as e:
            print(f"Generate outline error: {e}")
            raise
    
    def _apply_page_offset(self, outline: List[Dict], offset: int) -> List[Dict]:
        def add_offset(items):
            for item in items:
                if "page" in item:
                    item["page"] = item["page"] + offset
                if "children" in item:
                    add_offset(item["children"])
            return items
        return add_offset(outline)
    
    def embed_outline_to_pdf(
        self,
        pdf_path: str,
        output_path: str,
        outline: List[Dict]
    ) -> bool:
        try:
            reader = PdfReader(pdf_path)
            writer = PdfWriter()
            
            for page in reader.pages:
                writer.add_page(page)
            
            def add_bookmarks(items, parent=None):
                for item in items:
                    page_num = max(0, min(item.get("page", 1) - 1, len(reader.pages) - 1))
                    bookmark = writer.add_outline_item(
                        item["title"],
                        page_num,
                        parent=parent
                    )
                    if "children" in item:
                        add_bookmarks(item["children"], bookmark)
            
            add_bookmarks(outline)
            
            with open(output_path, "wb") as f:
                writer.write(f)
            
            return True
        except Exception as e:
            raise Exception(f"嵌入大纲失败: {str(e)}")

llm_service = LLMService()
