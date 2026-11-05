"""
Fetcher for external DSA git repositories.
Clones or updates the 3 repositories into data/external_sources/ with shallow clones.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

REPO_URLS = {
    "awesome-leetcode-resources": "https://github.com/ashishps1/awesome-leetcode-resources.git",
    "DSA-KIT": "https://github.com/avinash201199/DSA-KIT.git",
    "Complete-DSA-Preparation": "https://github.com/helloworldbyprince/Complete-DSA-Preparation.git",
}

DEFAULT_EXTERNAL_DIR = Path(__file__).resolve().parent.parent / "data" / "external_sources"


def ensure_external_repos(
    target_dir: Path | str = DEFAULT_EXTERNAL_DIR,
    force_update: bool = False,
) -> dict[str, Path]:
    """
    Ensures the 3 external repositories are cloned and ready on disk.

    Returns
    -------
    dict[str, Path]
        Mapping from repository key to its local folder path.
    """
    dest = Path(target_dir)
    dest.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    for repo_name, repo_url in REPO_URLS.items():
        repo_path = dest / repo_name
        paths[repo_name] = repo_path

        if repo_path.exists() and (repo_path / "README.md").exists():
            if force_update:
                logger.info("Pulling latest updates for %s...", repo_name)
                try:
                    subprocess.run(
                        ["git", "pull", "--depth", "1"],
                        cwd=str(repo_path),
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                except Exception as exc:
                    logger.warning("Failed to git pull %s (%s). Using existing files.", repo_name, exc)
            else:
                logger.debug("Repo %s already cached at %s", repo_name, repo_path)
            continue

        logger.info("Cloning %s (--depth 1)...", repo_url)
        try:
            res = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(repo_path)],
                capture_output=True,
                text=True,
                timeout=90,
            )
            if res.returncode != 0:
                logger.error("Git clone failed for %s: %s", repo_name, res.stderr)
            else:
                logger.info("Successfully cloned %s", repo_name)
        except Exception as exc:
            logger.error("Error cloning %s: %s", repo_name, exc)

    return paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = ensure_external_repos()
    print("Repos verified:", res)
