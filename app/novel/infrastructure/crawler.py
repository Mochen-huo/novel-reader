"""单章节网页请求与正文解析模块。"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag


CONTENT_ID_CANDIDATES = [
    "content",
    "chaptercontent",
    "chapter_content",
    "BookText",
    "TextContent",
]

CONTENT_CLASS_CANDIDATES = [
    "content",
    "chapter-content",
    "chapter_content",
    "read-content",
    "txt",
    "text",
]

AD_PATTERNS = [
    r"请收藏.*",
    r".*请收藏本站.*",
    r".*加入书签.*",
    r"上一章.*",
    r"下一章.*",
    r"返回目录.*",
    r".*最新网址.*",
    r".*手机用户请浏览.*",
    r".*本章未完.*",
]

GENERIC_TITLE_KEYWORDS = [
    "书库",
    "小说",
    "阅读",
    "最新章节",
    "全文",
    "目录",
    "首页",
]


@dataclass(frozen=True)
class Chapter:
    """解析后的章节数据。"""

    title: str
    book_title: str
    url: str
    content: str
    prev_url: str | None = None
    next_url: str | None = None


class ChapterCrawler:
    """负责温和请求单个章节 URL，并使用通用规则解析标题、正文和导航链接。"""

    def __init__(self, delay_seconds: float = 1.0, timeout: int = 15) -> None:
        self.delay_seconds = delay_seconds
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            }
        )

    def fetch_chapter(self, url: str) -> Chapter:
        """请求并解析单个章节 URL。"""
        clean_url = url.strip()
        self.validate_url(clean_url)
        time.sleep(self.delay_seconds)

        try:
            response = self.session.get(clean_url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"请求网页失败：{exc}") from exc

        response.encoding = self.detect_encoding(response)
        soup = BeautifulSoup(response.text, "lxml")

        content = self.extract_content(soup)
        title = self.refine_title(self.extract_title(soup), content)
        book_title = self.extract_book_title(soup, title)
        prev_url = self.extract_navigation_url(soup, clean_url, ["上一章", "上一页", "上章"])
        next_url = self.extract_navigation_url(soup, clean_url, ["下一章", "下一页", "下章"])
        return Chapter(
            title=title,
            book_title=book_title,
            url=clean_url,
            content=content,
            prev_url=prev_url,
            next_url=next_url,
        )

    def validate_url(self, url: str) -> None:
        """只接受普通 HTTP/HTTPS URL，避免无效输入。"""
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("请输入有效的 http 或 https 章节 URL。")

    def detect_encoding(self, response: requests.Response) -> str:
        """自动处理常见中文网页编码。"""
        if response.encoding and response.encoding.lower() not in {"iso-8859-1", "ascii"}:
            return response.encoding
        if response.apparent_encoding:
            return response.apparent_encoding
        return "utf-8"

    def extract_title(self, soup: BeautifulSoup) -> str:
        """提取章节标题，优先使用 h1/h2，再回退到页面 title。"""
        for selector in ("h1", "h2", ".chapter-title", ".title"):
            node = soup.select_one(selector)
            if node:
                title = self.normalize_space(node.get_text(" ", strip=True))
                if title:
                    return self.clean_title(title)

        if soup.title:
            title = self.normalize_space(soup.title.get_text(" ", strip=True))
            if title:
                return self.clean_title(title)

        return "未命名章节"

    def refine_title(self, page_title: str, content: str) -> str:
        """当页面标题是站点名时，从正文开头提取真正章节名。"""
        if page_title and not self.is_generic_title(page_title):
            return page_title

        for line in content.splitlines()[:8]:
            line = self.clean_title(self.normalize_space(line))
            if self.looks_like_chapter_title(line):
                return line

        for line in content.splitlines()[:3]:
            line = self.clean_title(self.normalize_space(line))
            if 2 <= len(line) <= 40:
                return line

        return page_title or "未命名章节"

    def clean_title(self, title: str) -> str:
        """清理页面 title 中常见的站点后缀。"""
        title = re.split(r"[_\-|—]+", title, maxsplit=1)[0]
        return self.normalize_space(title)

    def is_generic_title(self, title: str) -> bool:
        """判断标题是否更像站点名而不是章节名。"""
        return any(keyword in title for keyword in GENERIC_TITLE_KEYWORDS)

    def looks_like_chapter_title(self, text: str) -> bool:
        """判断文本是否像中文小说章节标题。"""
        if not 2 <= len(text) <= 60:
            return False
        return bool(re.search(r"第\s*[0-9零一二三四五六七八九十百千万两]+\s*[章节回卷集部]", text))

    def extract_book_title(self, soup: BeautifulSoup, chapter_title: str) -> str:
        """尽量从网页中提取书名，用于本地章节分组。"""
        meta_selectors = [
            {"property": "og:novel:book_name"},
            {"property": "og:book_name"},
            {"name": "book_name"},
        ]
        for attrs in meta_selectors:
            node = soup.find("meta", attrs=attrs)
            if isinstance(node, Tag):
                value = self.normalize_space(str(node.get("content") or ""))
                if self.is_valid_book_title(value, chapter_title):
                    return value

        for selector in (
            "#info h1",
            ".info h1",
            ".book-info h1",
            ".bookname h1",
            ".bookname",
            ".novel-title",
            ".book-title",
        ):
            node = soup.select_one(selector)
            if node:
                value = self.normalize_space(node.get_text(" ", strip=True))
                if self.is_valid_book_title(value, chapter_title):
                    return self.clean_book_title(value)

        breadcrumb_candidates: list[str] = []
        for link in soup.find_all("a"):
            if not isinstance(link, Tag):
                continue
            text = self.normalize_space(link.get_text(" ", strip=True))
            if self.is_valid_book_title(text, chapter_title):
                breadcrumb_candidates.append(self.clean_book_title(text))
        if breadcrumb_candidates:
            return breadcrumb_candidates[-1]

        if soup.title:
            raw_title = self.normalize_space(soup.title.get_text(" ", strip=True))
            for part in re.split(r"[_\-|—]+", raw_title):
                value = self.clean_book_title(part)
                if self.is_valid_book_title(value, chapter_title):
                    return value

        return "未分组书籍"

    def clean_book_title(self, title: str) -> str:
        """清理书名中的常见附加文本。"""
        title = re.sub(r"(最新章节|全文阅读|小说|目录|章节列表|无弹窗).*", "", title)
        return self.normalize_space(title)

    def is_valid_book_title(self, title: str, chapter_title: str) -> bool:
        """判断候选文本是否适合作为书名。"""
        title = self.clean_book_title(title)
        if not 2 <= len(title) <= 40:
            return False
        if title == chapter_title or title in chapter_title or chapter_title in title:
            return False
        if self.looks_like_chapter_title(title):
            return False
        return not self.is_generic_title(title)

    def extract_content(self, soup: BeautifulSoup) -> str:
        """按可扩展策略提取正文内容。"""
        candidates: list[Tag] = []

        candidates.extend(self.find_by_ids(soup, CONTENT_ID_CANDIDATES))
        candidates.extend(self.find_by_classes(soup, CONTENT_CLASS_CANDIDATES))

        article = soup.find("article")
        if isinstance(article, Tag):
            candidates.append(article)

        fallback = self.find_longest_text_div(soup)
        if fallback is not None:
            candidates.append(fallback)

        for node in candidates:
            content = self.clean_content(node)
            if self.is_valid_content(content):
                return content

        raise RuntimeError(
            "通用解析失败：没有找到足够长的正文内容，需要针对该网站单独配置正文选择器。"
        )

    def extract_navigation_url(
        self,
        soup: BeautifulSoup,
        current_url: str,
        keywords: list[str],
    ) -> str | None:
        """提取上一章或下一章链接；只解析页面已有导航，不自动搜索。"""
        for link in soup.find_all("a"):
            if not isinstance(link, Tag):
                continue

            text = self.normalize_space(link.get_text(" ", strip=True))
            href = str(link.get("href") or "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            if any(keyword in text for keyword in keywords):
                absolute_url = urljoin(current_url, href)
                if absolute_url != current_url and self.is_http_url(absolute_url):
                    return absolute_url

        rel_name = "next" if any("下" in keyword for keyword in keywords) else "prev"
        rel_link = soup.find("link", rel=lambda value: value and rel_name in value)
        if isinstance(rel_link, Tag):
            href = str(rel_link.get("href") or "").strip()
            absolute_url = urljoin(current_url, href)
            if href and absolute_url != current_url and self.is_http_url(absolute_url):
                return absolute_url

        return None

    def is_http_url(self, url: str) -> bool:
        """判断 URL 是否为普通 HTTP/HTTPS 链接。"""
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def find_by_ids(self, soup: BeautifulSoup, ids: Iterable[str]) -> list[Tag]:
        """按常见正文 id 查找候选节点。"""
        results: list[Tag] = []
        for content_id in ids:
            node = soup.find(id=content_id)
            if isinstance(node, Tag):
                results.append(node)
        return results

    def find_by_classes(self, soup: BeautifulSoup, classes: Iterable[str]) -> list[Tag]:
        """按常见正文 class 查找候选节点。"""
        results: list[Tag] = []
        for class_name in classes:
            nodes = soup.find_all(class_=class_name)
            results.extend(node for node in nodes if isinstance(node, Tag))
        return results

    def find_longest_text_div(self, soup: BeautifulSoup) -> Tag | None:
        """回退策略：选择文本最长的 div。"""
        divs = [node for node in soup.find_all("div") if isinstance(node, Tag)]
        if not divs:
            return None
        return max(divs, key=lambda node: len(node.get_text("", strip=True)))

    def clean_content(self, node: Tag) -> str:
        """清理正文中的脚本、样式、广告语和多余空白。"""
        copied = BeautifulSoup(str(node), "lxml")
        for bad_node in copied.find_all(["script", "style", "iframe", "noscript"]):
            bad_node.decompose()

        text = copied.get_text("\n", strip=True)
        lines = []
        for raw_line in text.splitlines():
            line = self.normalize_space(raw_line)
            if not line or self.is_ad_line(line):
                continue
            lines.append(line)

        return "\n\n".join(lines)

    def is_ad_line(self, line: str) -> bool:
        """判断一行文本是否属于常见广告或导航文本。"""
        return any(re.fullmatch(pattern, line) for pattern in AD_PATTERNS)

    def is_valid_content(self, content: str) -> bool:
        """判断提取结果是否像正文，避免误把导航或菜单当正文。"""
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", content))
        return len(content) >= 200 and chinese_chars >= 80

    def normalize_space(self, text: str) -> str:
        """压缩常见空白字符。"""
        return re.sub(r"\s+", " ", text).strip()
