"""Every "?" button in the sidebar opens a wiki page that exists in wiki/, and every link between
wiki pages points at a page that exists. Runs without Blender."""
import importlib.util
import os
import re
import unittest

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIKI_DIR = os.path.join(ADDON_DIR, "wiki")


def load_help_pages():
    spec = importlib.util.spec_from_file_location("help_pages", os.path.join(ADDON_DIR, "help_pages.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HELP_PAGES


def wiki_pages():
    return {name[:-3] for name in os.listdir(WIKI_DIR) if name.endswith(".md")}


class HelpPagesTest(unittest.TestCase):
    def test_every_help_page_has_a_wiki_page(self):
        missing = sorted(set(load_help_pages()) - wiki_pages())
        self.assertEqual(missing, [], "add wiki/<page>.md for these help pages")

    def test_panels_only_link_known_pages(self):
        with open(os.path.join(ADDON_DIR, "panels.py"), encoding="utf-8") as f:
            source = f.read()
        used = set(re.findall(r'help_page\s*=\s*"([^"]+)"', source))
        used |= set(re.findall(r'help_button\([^,]+,\s*"([^"]+)"', source))
        used |= set(re.findall(r'help_url\(URL_WIKI,\s*"([^"]+)"\)', source))
        self.assertTrue(used, "found no help links in panels.py")
        unknown = sorted(used - set(load_help_pages()))
        self.assertEqual(unknown, [], "add these pages to help_pages.HELP_PAGES")

    def test_wiki_links_resolve(self):
        pages = wiki_pages()
        broken = []
        for page in sorted(pages):
            with open(os.path.join(WIKI_DIR, page + ".md"), encoding="utf-8") as f:
                text = f.read()
            for target in re.findall(r'\]\(([^)\s]+)\)', text):
                if "://" in target or target.startswith("#"):
                    continue
                if target.split("#")[0] not in pages:
                    broken.append(f"{page}: {target}")
        self.assertEqual(broken, [])


if __name__ == "__main__":
    unittest.main()
