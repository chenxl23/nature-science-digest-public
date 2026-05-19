"""
English-to-Chinese translation for article titles and abstracts.

Uses deep-translator with the Google Translate backend (no API key needed).
We translate in batches with retry+fallback so a transient failure doesn't
crash the whole job.
"""

import logging
import time

from deep_translator import GoogleTranslator
from deep_translator.exceptions import TranslationNotFound, RequestError

logger = logging.getLogger(__name__)

MAX_CHARS_PER_CHUNK = 4500
MAX_RETRIES = 3
RETRY_DELAY_SEC = 2


def _translate_one(text, translator):
    if not text or not text.strip():
        return ""

    if len(text) <= MAX_CHARS_PER_CHUNK:
        chunks = [text]
    else:
        chunks = []
        buf = ""
        for sentence in text.replace("\n", " ").split(". "):
            if len(buf) + len(sentence) + 2 > MAX_CHARS_PER_CHUNK:
                chunks.append(buf)
                buf = sentence
            else:
                buf = (buf + ". " + sentence) if buf else sentence
        if buf:
            chunks.append(buf)

    translated_chunks = []
    for chunk in chunks:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = translator.translate(chunk)
                translated_chunks.append(result or "")
                break
            except (TranslationNotFound, RequestError, Exception) as e:
                logger.warning(
                    "Translate attempt %d/%d failed: %s",
                    attempt, MAX_RETRIES, type(e).__name__
                )
                if attempt == MAX_RETRIES:
                    translated_chunks.append("[翻译失败]")
                else:
                    time.sleep(RETRY_DELAY_SEC * attempt)
    return " ".join(translated_chunks).strip()


def translate_articles(articles):
    """Add 'title_zh' and 'abstract_zh' fields to each article in-place."""
    if not articles:
        return articles

    translator = GoogleTranslator(source="en", target="zh-CN")
    total = len(articles)
    logger.info("Translating %d articles to Chinese...", total)

    for idx, article in enumerate(articles, start=1):
        try:
            article["title_zh"] = _translate_one(article.get("title", ""), translator)
            article["abstract_zh"] = _translate_one(article.get("abstract", ""), translator)
            if idx % 10 == 0 or idx == total:
                logger.info("  [%d/%d] translated", idx, total)
            time.sleep(0.3)
        except Exception as e:
            logger.exception("Failed to translate article %d: %s", idx, e)
            article.setdefault("title_zh", "[翻译失败]")
            article.setdefault("abstract_zh", "[翻译失败]")

    logger.info("Translation done.")
    return articles
