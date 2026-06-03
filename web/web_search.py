import re
import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, unquote, parse_qs

import requests

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except Exception:
    _HAS_BS4 = False

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
_BAIDU_ENDPOINT = "https://www.baidu.com/s"
_BING_ENDPOINT = "https://www.bing.com/search"
_SEARCH_TIMEOUT = (8, 12)
_FETCH_TIMEOUT = (6, 10)
_RESOLVE_TIMEOUT = (4, 5)
_MAX_CHARS_PER_PAGE = 4000


def _is_safe_url(url):
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_reserved or addr.is_multicast or addr.is_unspecified):
            return False
    return True


def _resolve_baidu_link(url, session):
    if "baidu.com/link?" not in url:
        return url
    try:
        r = session.head(url, allow_redirects=True, timeout=_RESOLVE_TIMEOUT)
        if r.url and r.url.startswith("http"):
            return r.url
    except Exception:
        pass
    return url


def _search_baidu(query, max_results, session):
    resp = session.get(
        _BAIDU_ENDPOINT,
        params={"wd": query, "rn": max(10, max_results * 2)},
        headers={
            "User-Agent": _UA,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        timeout=_SEARCH_TIMEOUT,
    )
    if resp.status_code != 200:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    candidates = []
    for item in soup.select("div.result, div.c-container"):
        a = item.select_one("h3 a") or item.select_one("a")
        if not a:
            continue
        href = a.get("href", "")
        title = a.get_text(strip=True)
        if not href or not href.startswith("http") or not title:
            continue
        snippet = ""
        cap = item.select_one("div.c-abstract") or item.select_one("span.content-right_8Zs40")
        if cap:
            snippet = cap.get_text(" ", strip=True)
        candidates.append({"title": title, "href": href, "snippet": snippet})
        if len(candidates) >= max_results * 2:
            break

    def _resolve(c):
        c = dict(c)
        c["url"] = _resolve_baidu_link(c["href"], session)
        return c
    resolved = []
    if candidates:
        with ThreadPoolExecutor(max_workers=min(8, len(candidates))) as ex:
            for c in ex.map(_resolve, candidates):
                resolved.append(c)

    results = []
    seen = set()
    for c in resolved:
        real = c["url"]
        if not real.startswith("http") or real in seen:
            continue
        if "baidu.com" in urlparse(real).netloc:
            continue
        seen.add(real)
        results.append({"title": c["title"], "url": real, "snippet": c["snippet"]})
        if len(results) >= max_results:
            break
    return results


def _search_bing(query, max_results, session):
    resp = session.get(
        _BING_ENDPOINT,
        params={"q": query, "setlang": "zh-CN"},
        headers={
            "User-Agent": _UA,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        timeout=_SEARCH_TIMEOUT,
    )
    if resp.status_code != 200:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    seen = set()
    for item in soup.select("li.b_algo"):
        a = item.select_one("h2 a")
        if not a:
            continue
        url = a.get("href", "")
        if not url or not url.startswith("http") or url in seen:
            continue
        seen.add(url)
        title = a.get_text(strip=True)
        snippet = ""
        cap = item.select_one("div.b_caption p") or item.select_one("p")
        if cap:
            snippet = cap.get_text(" ", strip=True)
        results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= max_results:
            break
    return results


def search_links(query, max_results=5):
    if not _HAS_BS4:
        return []
    session = requests.Session()
    try:
        results = _search_baidu(query, max_results, session)
    except Exception:
        results = []
    if not results:
        try:
            results = _search_bing(query, max_results, session)
        except Exception:
            results = []
    return results


def fetch_text(url):
    if not _is_safe_url(url):
        return ""
    try:
        resp = requests.get(
            url, headers={"User-Agent": _UA}, timeout=_FETCH_TIMEOUT, stream=True
        )
        ctype = resp.headers.get("Content-Type", "")
        if "html" not in ctype and "text" not in ctype:
            resp.close()
            return ""
        raw = resp.raw.read(2_000_000, decode_content=True)
        resp.close()
        html = raw.decode(resp.encoding or "utf-8", errors="replace")
    except Exception:
        return ""

    if not _HAS_BS4:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
            tag.decompose()
        parts = []
        for el in soup.find_all(["p", "h1", "h2", "h3", "li"]):
            txt = el.get_text(" ", strip=True)
            if txt and len(txt) > 20:
                parts.append(txt)
        text = "\n".join(parts)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) > _MAX_CHARS_PER_PAGE:
            text = text[:_MAX_CHARS_PER_PAGE] + " ...(已截断)"
        return text
    except Exception:
        return ""


def search_and_fetch(query, max_results=5):
    links = search_links(query, max_results)
    if not links:
        return {"ok": False, "sources": [], "context": ""}

    fetched = []
    with ThreadPoolExecutor(max_workers=min(5, len(links))) as ex:
        future_map = {ex.submit(fetch_text, item["url"]): item for item in links}
        for fut in as_completed(future_map):
            item = future_map[fut]
            try:
                text = fut.result()
            except Exception:
                text = ""
            if text:
                fetched.append({"title": item["title"], "url": item["url"], "text": text})

    order = {item["url"]: i for i, item in enumerate(links)}
    fetched.sort(key=lambda x: order.get(x["url"], 999))

    if not fetched:
        sources = [{"title": l["title"], "url": l["url"]} for l in links]
        return {"ok": False, "sources": sources, "context": "", "pages": []}

    blocks = []
    for i, f in enumerate(fetched, 1):
        blocks.append(f"【来源{i}】{f['title']}\n{f['url']}\n{f['text']}")
    context = "\n\n".join(blocks)
    sources = [{"title": f["title"], "url": f["url"]} for f in fetched]
    return {"ok": True, "sources": sources, "context": context, "pages": fetched}


def build_search_prompt(query, search_result):
    if not search_result.get("context"):
        return ""
    return (
        "以下是针对用户问题的联网搜索结果（来自互联网，可能存在不准确信息，请甄别）：\n\n"
        f"{search_result['context']}\n\n"
        "请基于以上搜索结果回答用户的问题，并在回答末尾用「参考来源」列出你引用的网址。"
        "如果搜索结果不足以回答，请说明并结合你已有的知识作答。\n\n"
        f"用户问题：{query}"
    )


import json as _json


def _parse_json_obj(text):
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        return _json.loads(text)
    except Exception:
        return None


def plan_queries(user_query, llm_call, history_hint=""):
    prompt = (
        "你是一个联网搜索助理。请根据用户的问题，生成 1-2 个最有效的搜索引擎查询词，"
        "用于检索能回答该问题的网页。查询词要精准、包含关键实体和版本号，必要时用英文。\n"
        "只输出 JSON，格式：{\"queries\": [\"查询词1\", \"查询词2\"]}。不要输出其它内容。\n\n"
        f"{history_hint}"
        f"用户问题：{user_query}"
    )
    raw = llm_call([{"role": "user", "content": prompt}])
    obj = _parse_json_obj(raw)
    if obj and isinstance(obj.get("queries"), list):
        qs = [str(q).strip() for q in obj["queries"] if str(q).strip()]
        if qs:
            return qs[:2]
    return [user_query]


_BAD_DOMAINS = (
    "iciba.com", "dictionary.cambridge.org", "youdao.com", "dict.cn",
    "baike.baidu.com/item/s", "translate.google",
)

_STOPWORDS = set("的 了 吗 呢 啊 是 有 哪些 什么 怎么 如何 a an the of to in on for and or "
                 "what which how why when where is are new features".split())


def _tokenize(text):
    text = (text or "").lower()
    tokens = re.findall(r"[a-z0-9.]+|[\u4e00-\u9fff]+", text)
    out = []
    for t in tokens:
        if t in _STOPWORDS or len(t) <= 1:
            continue
        out.append(t)
    return out


def _keyword_filter(user_query, pages, min_hit=1):
    q_tokens = set(_tokenize(user_query))
    if not q_tokens:
        return pages
    kept = []
    for pg in pages:
        url = (pg.get("url") or "").lower()
        if any(bad in url for bad in _BAD_DOMAINS):
            continue
        blob = (pg.get("title", "") + " " + (pg.get("text", "")[:1500]))
        p_tokens = set(_tokenize(blob))
        hits = len(q_tokens & p_tokens)
        if hits >= min_hit:
            pg = dict(pg)
            pg["_score"] = hits
            kept.append(pg)
    kept.sort(key=lambda x: x.get("_score", 0), reverse=True)
    return kept


def evaluate_pages(user_query, pages, llm_call):
    if not pages:
        return {"enough": False, "relevant_urls": [], "new_queries": []}
    listing = []
    for i, p in enumerate(pages, 1):
        snippet = (p.get("text") or "")[:300]
        listing.append(f"[{i}] 标题：{p['title']}\nURL：{p['url']}\n摘要：{snippet}")
    pages_text = "\n\n".join(listing)
    prompt = (
        "你在做联网检索的相关性判断，标准要严格。下面是已检索到的网页列表（含摘要）。\n"
        "判断规则：\n"
        "1. 只有当网页摘要中确实包含能直接回答用户问题的具体信息时，才算相关；\n"
        "2. 用户问题中的核心实体、版本号、主题词（如具体版本、具体功能名）必须在网页中真正出现并被讨论；\n"
        "3. 仅仅是同领域的首页、教程目录、安装配置、广义介绍页，即使包含关键词，也不算相关，应排除；\n"
        "4. relevant_urls 只填真正能回答问题的网页URL；若没有任何网页满足，relevant_urls 必须为空数组；\n"
        "5. 当相关网页不足以充分回答问题时，enough 设为 false，并在 new_queries 给出更精准的搜索词"
        "（应更具体，例如补上版本号、官方文档站点、发布说明、changelog 等定位词）。\n"
        "只输出 JSON，格式：\n"
        "{\"enough\": true/false, \"relevant_urls\": [\"相关网页的URL\"], "
        "\"new_queries\": [\"更精准的搜索词\"]}。\n"
        "不要输出 JSON 以外的内容。\n\n"
        f"用户问题：{user_query}\n\n网页列表：\n{pages_text}"
    )
    raw = llm_call([{"role": "user", "content": prompt}])
    obj = _parse_json_obj(raw)
    if not obj:
        return {"enough": False, "relevant_urls": [], "new_queries": []}
    return {
        "enough": bool(obj.get("enough")),
        "relevant_urls": [str(u) for u in obj.get("relevant_urls", []) if u],
        "new_queries": [str(q).strip() for q in obj.get("new_queries", []) if str(q).strip()][:2],
    }


def agentic_search(user_query, llm_call, max_results=5, max_rounds=2, progress=None):
    def emit(msg):
        if progress:
            try:
                progress(msg)
            except Exception:
                pass

    collected = {}
    relevant = {}
    tried_queries = set()

    emit("正在生成搜索词…")
    queries = plan_queries(user_query, llm_call)

    for rnd in range(1, max_rounds + 1):
        round_queries = [q for q in queries if q not in tried_queries][:1]
        if not round_queries:
            break
        for q in round_queries:
            tried_queries.add(q)
            emit(f"第 {rnd} 轮检索：{q}")
            res = search_and_fetch(q, max_results)
            for pg in res.get("pages", []):
                collected[pg["url"]] = pg

        if not collected:
            queries = []
            continue

        pages_list = list(collected.values())[: max_results + 3]
        emit(f"正在评估 {len(pages_list)} 个网页的相关性…")
        verdict = evaluate_pages(user_query, pages_list, llm_call)

        for url in verdict["relevant_urls"]:
            if url in collected:
                relevant[url] = collected[url]

        if verdict["enough"] and relevant:
            break
        if rnd < max_rounds and verdict["new_queries"]:
            queries = verdict["new_queries"]
        else:
            break

    if relevant:
        final_pages = _keyword_filter(user_query, list(relevant.values()), min_hit=1) or list(relevant.values())
    else:
        final_pages = _keyword_filter(user_query, list(collected.values()), min_hit=1)
    if not final_pages:
        emit("未检索到相关网页")
        return {"ok": False, "sources": [], "context": "", "rounds": list(tried_queries)}

    emit(f"已锁定 {len(final_pages)} 个相关来源")
    blocks = []
    for i, f in enumerate(final_pages, 1):
        blocks.append(f"【来源{i}】{f['title']}\n{f['url']}\n{f['text']}")
    context = "\n\n".join(blocks)
    sources = [{"title": f["title"], "url": f["url"]} for f in final_pages]
    return {"ok": True, "sources": sources, "context": context, "rounds": list(tried_queries)}
