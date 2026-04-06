"""Export vault article data to a portable JSON file for cloud deployment."""
import json
from pathlib import Path

from mouse_research.logger import get_logger

logger = get_logger(__name__)


def _extract_cleaned_text(article_md_path: Path) -> str:
    """Extract the ## Cleaned Text section from an article.md file."""
    if not article_md_path.exists():
        return ""
    content = article_md_path.read_text(encoding="utf-8")
    marker = "## Cleaned Text"
    idx = content.find(marker)
    if idx == -1:
        return ""
    text_start = idx + len(marker)
    end_marker = "***"
    end_idx = content.find(end_marker, text_start)
    if end_idx != -1:
        return content[text_start:end_idx].strip()
    return content[text_start:].strip()


def export_articles_json(vault_path: str, output_path: str) -> int:
    """Export all article metadata + cleaned text to a single JSON file."""
    articles_dir = Path(vault_path) / "Articles"
    articles: list[dict] = []

    if articles_dir.exists():
        for meta_file in sorted(articles_dir.glob("*/metadata.json")):
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                article_md = meta_file.parent / "article.md"
                meta["cleaned_text"] = _extract_cleaned_text(article_md)
                meta.pop("_dir", None)
                articles.append(meta)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Skipping %s: %s", meta_file, e)
                continue

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(articles, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Exported %d articles to %s", len(articles), output_path)
    return len(articles)
