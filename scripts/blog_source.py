"""
Le os artigos publicados no blog do escritorio (feed RSS publico do Wix) e extrai o
texto de cada artigo direto da pagina publicada. Nao precisa de credencial do Wix.

O feed do Wix atualiza o pubDate quando um artigo e editado, entao a identificacao de
"artigo novo" e feita pelo link (ver blog_to_carousel.py), nunca pela data.
"""
import re
import xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser
from urllib.parse import unquote

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (rrs-instagram-automation)"}
TEXT_TAGS = {"p", "h2", "h3", "h4", "li"}
SKIP_TAGS = {"script", "style", "noscript", "nav", "footer", "header", "svg"}


def fetch_feed(feed_url: str) -> list[dict]:
    resp = requests.get(feed_url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    posts = []
    for item in root.iter("item"):
        link = (item.findtext("link") or "").strip()
        posts.append({
            "link": link,
            "slug": unquote(link.rstrip("/").rsplit("/", 1)[-1]),
            "title": unescape((item.findtext("title") or "").strip()),
            "categories": [c.text.strip() for c in item.findall("category") if c.text],
            "pub_date": (item.findtext("pubDate") or "").strip(),
            "description": unescape(re.sub(r"<[^>]+>", " ", item.findtext("description") or "")).strip(),
        })
    return posts


class _ArticleTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._skip_depth = 0
        self._current_tag = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip_depth += 1
        elif tag in TEXT_TAGS and self._skip_depth == 0:
            self._flush()
            self._current_tag = tag

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag == self._current_tag:
            self._flush()

    def handle_data(self, data):
        if self._current_tag and self._skip_depth == 0:
            self._buffer.append(data)

    def _flush(self):
        if self._current_tag:
            text = re.sub(r"\s+", " ", "".join(self._buffer)).strip()
            if text:
                prefix = {"h2": "## ", "h3": "### ", "h4": "#### ", "li": "- "}.get(self._current_tag, "")
                self.blocks.append(prefix + text)
        self._current_tag = None
        self._buffer = []


def fetch_article_text(url: str, max_chars: int = 40000) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    parser = _ArticleTextParser()
    parser.feed(resp.content.decode("utf-8", errors="replace"))
    parser._flush()

    seen = set()
    blocks = []
    for block in parser.blocks:
        if block not in seen and len(block) > 2:
            seen.add(block)
            blocks.append(block)

    text = "\n\n".join(blocks)
    if len(text) < 1500:
        raise RuntimeError(f"Texto extraido do artigo muito curto ({len(text)} caracteres): {url}")
    return text[:max_chars]


if __name__ == "__main__":
    import sys

    feed = fetch_feed(sys.argv[1] if len(sys.argv) > 1 else "https://www.rochaesantosadvocacia.com.br/blog-feed.xml")
    for p in feed[:5]:
        print(p["categories"], "|", p["title"], "|", p["slug"])
    print("\n----- texto do primeiro artigo -----\n")
    print(fetch_article_text(feed[0]["link"])[:3000])
