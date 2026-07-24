"""
Модуль для быстрой публикации развернутых ТЗ задач в Telegraph (telegra.ph)
"""
import logging
import urllib.request
import json
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

TELEGRAPH_ACCESS_TOKEN: Optional[str] = None

def get_or_create_access_token() -> Optional[str]:
    global TELEGRAPH_ACCESS_TOKEN
    if TELEGRAPH_ACCESS_TOKEN:
        return TELEGRAPH_ACCESS_TOKEN
    
    url = "https://api.telegra.ph/createAccount"
    data = {
        "short_name": "WolfBot",
        "author_name": "Wolf MIREA IT Freelance"
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            if res_data.get("ok"):
                TELEGRAPH_ACCESS_TOKEN = res_data["result"]["access_token"]
                return TELEGRAPH_ACCESS_TOKEN
    except Exception as e:
        logger.warning(f"Failed to create Telegraph account: {e}")
    return None

def text_to_telegraph_nodes(text: str) -> List[Dict[str, Any]]:
    """Преобразует многострочный текст ТЗ в валидный набор узлов (DOM nodes) Telegraph."""
    nodes = []
    paragraphs = text.split("\n\n")
    
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        
        if p.startswith("<code>") or p.startswith("<pre>"):
            code_content = p.replace("<code>", "").replace("</code>", "").replace("<pre>", "").replace("</pre>", "")
            nodes.append({"tag": "pre", "children": [code_content]})
        elif "<b>" in p:
            # Упрощенная парсинг-очистка для заглавий
            clean_title = p.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "")
            nodes.append({"tag": "h4", "children": [clean_title]})
        else:
            clean_p = p.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "")
            nodes.append({"tag": "p", "children": [clean_p]})
            
    return nodes

def create_telegraph_page(title: str, author_name: str, text_content: str) -> Optional[str]:
    """Создает статью на telegra.ph и возвращает URL ссылки."""
    token = get_or_create_access_token()
    if not token:
        return None
        
    url = "https://api.telegra.ph/createPage"
    nodes = text_to_telegraph_nodes(text_content)
    
    data = {
        "access_token": token,
        "title": title[:64],
        "author_name": author_name[:32],
        "content": nodes,
        "return_content": False
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            if res_data.get("ok"):
                return res_data["result"]["url"]
    except Exception as e:
        logger.warning(f"Failed to create Telegraph page: {e}")
    return None
