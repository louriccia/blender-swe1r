"""Publish wiki/ to the GitHub wiki (https://github.com/louriccia/blender-swe1r/wiki).

    python scripts/publish_wiki.py            # show what would change
    python scripts/publish_wiki.py --push     # commit and push it

wiki/ in this repo is the source: the GitHub wiki is replaced by it, so pages that exist only on
the wiki are deleted. Edit pages here, not in GitHub's wiki editor. Needs git and push access to
the wiki repository.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIKI_SRC = os.path.join(REPO, "wiki")
WIKI_GIT = "https://github.com/louriccia/blender-swe1r.wiki.git"


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--push", action="store_true", help="commit and push (otherwise only show the changes)")
    args = parser.parse_args()

    commit = git("rev-parse", "--short", "HEAD", cwd=REPO).strip()
    with tempfile.TemporaryDirectory() as tmp:
        clone = os.path.join(tmp, "wiki")
        subprocess.run(["git", "clone", "-q", WIKI_GIT, clone], check=True)
        for name in os.listdir(clone):
            if name.endswith(".md"):
                os.remove(os.path.join(clone, name))
        for name in os.listdir(WIKI_SRC):
            if name.endswith(".md"):
                shutil.copy2(os.path.join(WIKI_SRC, name), os.path.join(clone, name))
        git("add", "-A", cwd=clone)
        status = git("status", "--short", cwd=clone)
        if not status.strip():
            print("The wiki is already up to date.")
            return 0
        print(status)
        if not args.push:
            print("Dry run: pass --push to publish these changes.")
            return 0
        git("commit", "-q", "-m", f"Publish wiki/ from blender-swe1r {commit}", cwd=clone)
        subprocess.run(["git", "push", "-q"], cwd=clone, check=True)
        print("Published.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
