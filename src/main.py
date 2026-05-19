"""
Entry point for the weekly multi-journal digest.

Reads configuration from environment variables (set as GitHub Secrets in CI):
  - SMTP_USER       : full QQ email address (the sender)
  - SMTP_PASS       : QQ Mail SMTP authorization code (NOT login password)
  - RECIPIENT       : recipient address (defaults to SMTP_USER)
  - DAYS_BACK       : how many days back to fetch (default 8)
  - SMTP_HOST       : SMTP server (default smtp.qq.com)
  - SMTP_PORT       : SMTP port (default 465)

Run:
  python -m src.main
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from .document import create_digest_document
from .email_sender import send_digest_email
from .scraper import JOURNAL_CONFIG, fetch_all_journals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("digest.main")


def _require_env(key):
    val = os.environ.get(key)
    if not val:
        logger.error("Required environment variable %s is not set", key)
        sys.exit(2)
    return val


def main():
    smtp_user = _require_env("SMTP_USER")
    smtp_pass = _require_env("SMTP_PASS")
    recipient = os.environ.get("RECIPIENT") or smtp_user
    days_back = int(os.environ.get("DAYS_BACK") or "8")
    smtp_host = os.environ.get("SMTP_HOST") or "smtp.qq.com"
    smtp_port = int(os.environ.get("SMTP_PORT") or "465")

    logger.info("=" * 60)
    logger.info("Multi-Journal Weekly Research Digest")
    logger.info("=" * 60)
    logger.info("Recipient:    %s", recipient)
    logger.info("Time window:  last %d days", days_back)
    logger.info("Journals:     %d (%s)",
                len(JOURNAL_CONFIG),
                ", ".join(c["display_short"] for c in JOURNAL_CONFIG))

    # ---- Fetch all journals ---------------------------------------------
    journal_results = fetch_all_journals(days_back)
    total = sum(len(v) for v in journal_results.values())

    logger.info("=" * 60)
    logger.info("FETCH SUMMARY")
    for cfg in JOURNAL_CONFIG:
        n = len(journal_results.get(cfg["name"], []))
        logger.info("  %-35s : %3d articles", cfg["name"], n)
    logger.info("  %-35s : %3d articles", "TOTAL", total)

    # ---- Translate to Chinese -------------------------------------------
    from .translator import translate_articles
    logger.info("=" * 60)
    logger.info("Translating titles and abstracts to Chinese...")
    for journal_name, articles in journal_results.items():
        if articles:
            logger.info("Translating %s (%d articles)...", journal_name, len(articles))
            try:
                translate_articles(articles)
            except Exception as e:
                logger.exception("Translation failed for %s: %s", journal_name, e)

    # ---- Classify into subject categories -------------------------------
    from .classifier import build_classification_report
    try:
        # Flatten all journal articles for classification
        all_nature = []
        all_science = []
        for name, arts in journal_results.items():
            if name == "Science":
                all_science.extend(arts)
            else:
                all_nature.extend(arts)
        classification_report = build_classification_report(all_nature, all_science)
    except Exception as e:
        logger.exception("Classification failed: %s", e)
        classification_report = None

    # ---- Build the document --------------------------------------------
    output_dir = Path("output")
    date_tag = datetime.now().strftime("%Y%m%d")
    doc_path = output_dir / f"MultiJournal_Digest_{date_tag}.docx"

    logger.info("Generating document...")
    create_digest_document(
        journal_results=journal_results,
        output_path=doc_path,
        days_back=days_back,
        classification_report=classification_report,
    )

    # ---- Compose email --------------------------------------------------
    today_str = datetime.now().strftime("%Y-%m-%d")
    subject = f"[Weekly Research] Multi-Journal Digest - {today_str}"

    if total == 0:
        body = (
            f"您好,\n\n"
            f"本周（截至 {today_str}）暂未检索到任何期刊在过去 {days_back} 天内的新文章。\n"
            f"如果连续两周收到此通知，请检查 GitHub Actions 日志。\n\n"
            f"—— Multi-Journal Weekly Research Digest"
        )
    else:
        per_journal_lines = []
        for cfg in JOURNAL_CONFIG:
            n = len(journal_results.get(cfg["name"], []))
            per_journal_lines.append(f"  • {cfg['name']}: {n} 篇")
        per_journal_str = "\n".join(per_journal_lines)

        body = (
            f"您好,\n\n"
            f"附件为本周覆盖 {len(JOURNAL_CONFIG)} 个高水平期刊的研究文章汇总。\n\n"
            f"本期统计:\n{per_journal_str}\n"
            f"  • 总计: {total} 篇\n"
            f"  • 时间窗口: 过去 {days_back} 天\n\n"
            f"打开附件 Word 文档查看完整列表（含题目、作者、英文摘要、中文翻译、DOI），\n"
            f"末尾附自动学科分类总结。\n\n"
            f"本邮件由 GitHub Actions 每周一 09:00（北京时间）自动发送。\n"
            f"数据源: Crossref REST API + nature.com + Semantic Scholar API\n\n"
            f"—— Multi-Journal Weekly Research Digest"
        )

    # ---- Send ----------------------------------------------------------
    send_digest_email(
        smtp_user=smtp_user,
        smtp_pass=smtp_pass,
        recipient=recipient,
        subject=subject,
        body=body,
        attachment_path=doc_path,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
    )

    logger.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
