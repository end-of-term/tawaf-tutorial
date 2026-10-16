#!/usr/bin/env python3
"""
Count the most frequent words across all the pages in a WET file.

A first step towards full-text search or natural language processing: since a
WET file already holds plain text, there is no HTML or HTTP to deal with.

Things to keep in mind when reading the results:
  - Only textual captures (mostly HTML) are in a WET file; PDFs and other
    documents are not.
  - The text includes boilerplate (menus, footers, cookie banners), so words
    repeated on every page of a site will rank high.
  - Pages that build their content with JavaScript may have little text.
  - A site may have pages in several languages (fema.gov has many in
    Spanish), so the stopwords of another language may rank high.
  - Splitting text into words on spaces and punctuation does not work for
    every language (e.g. Chinese and Japanese do not separate words).

Usage:
    python wet_token_count.py FILE.warc.wet.gz [TOP_N]
"""

import re
import sys
from collections import Counter

from warcio.archiveiterator import ArchiveIterator

# A token is a run of letters; digits, punctuation, and spaces separate tokens.
TOKEN = re.compile(r"[^\W\d_]+")

# Very common words that would otherwise fill the top of the list.
# A demo-sized list; NLP libraries such as NLTK or spaCy ship complete ones.
STOPWORDS = set(
    "a an and are as at be by for from has have in is it its of on or that the "
    "this to was were will with you your we our not all can more".split()
)


def main(path, top_n=25):
    counts = Counter()
    pages = 0
    with open(path, "rb") as stream:
        for record in ArchiveIterator(stream):
            if record.rec_type != "conversion":
                continue
            text = record.content_stream().read().decode("utf-8", errors="replace")
            tokens = TOKEN.findall(text.lower())
            # Single letters are mostly leftovers, like the "s" of "it's".
            counts.update(t for t in tokens if len(t) > 1 and t not in STOPWORDS)
            pages += 1

    print(f"{sum(counts.values())} tokens, {len(counts)} distinct, in {pages} pages\n")
    for token, count in counts.most_common(int(top_n)):
        print(f"{count:8}  {token}")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    main(*sys.argv[1:])
