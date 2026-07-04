import os
import re
import yaml

dirname = os.path.dirname(__file__)
DEFAULT_KEYWORDS_FILE = os.path.join(dirname, "keywords.yaml")

TITLE_SCORE = 5
CATCH_SCORE = 3
HASH_TAG_SCORE = 3
GROUP_SCORE = 4
DESCRIPTION_SCORE = 1
DESCRIPTION_MAX_MATCHES = 3
MAX_KEYWORDS = 5

HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


class KeywordExtractor:
    def __init__(self, keywords_file=DEFAULT_KEYWORDS_FILE):
        with open(keywords_file, "r") as yml:
            config = yaml.safe_load(yml)

        self.rules = []
        for item in config.get("keywords", []):
            patterns = [re.compile(pattern, re.IGNORECASE)
                        for pattern in item["patterns"]]
            self.rules.append((item["keyword"], patterns))

    def extract(self, event, max_keywords=MAX_KEYWORDS):
        title = event.title or ""
        catch = event.catch or ""
        hash_tag = event.hash_tag or ""
        group = f"{event.group_key or ''} {event.group_name or ''}"
        description = getattr(event, "description", None) or ""
        description = HTML_TAG_PATTERN.sub(" ", description)

        scores = {}
        for keyword, patterns in self.rules:
            score = 0
            for pattern in patterns:
                if pattern.search(title):
                    score += TITLE_SCORE
                if pattern.search(catch):
                    score += CATCH_SCORE
                if pattern.search(hash_tag):
                    score += HASH_TAG_SCORE
                if pattern.search(group):
                    score += GROUP_SCORE
                matches = len(pattern.findall(description))
                matches = min(matches, DESCRIPTION_MAX_MATCHES)
                score += matches * DESCRIPTION_SCORE
            if score > 0:
                scores[keyword] = score

        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return [keyword for keyword, _ in ranked[:max_keywords]]
