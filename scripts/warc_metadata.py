#!/usr/bin/env python3
"""
Print what is recorded about captures beyond the content itself: DNS lookups
and metadata records.

This information never reaches a CDX index or a replay tool, but it is in WARC
files:

  dns: records      the DNS lookups the crawler made (hostname -> IP address)
  metadata records  "key: value" fields about a capture; which keys appear
                    depends on what wrote them.

Crawlers such as Heritrix write metadata records next to each capture, e.g.:

      via           the page where the crawler found this URL (referrer trail)
      hopsFromSeed  how it got here from the seed, one letter per hop
                    (crawler breadcrumb; L = link, E = embed, R = redirect,
                    P = prerequisite such as robots.txt)
      fetchTimeMs   how long the download took
      outlink       links the crawler extracted (there can be many)

The End of Term Archive also publishes a META file next to each WARC file,
with a metadata record per capture describing what was found in the content:

      Identified-Payload-Type  the file type detected from the content
      Preservation-Identifier  its PRONOM format identifier
      Charset-Detected         the character encoding
      Languages-cld2           the languages of the text

Not every WARC file has dns: or metadata records; e.g. those from
browser-based crawls (like the End of Term Archive WR segments) may have none.

Usage:
    python warc_metadata.py FILE.warc.gz
    python warc_metadata.py FILE.warc.meta.gz
"""

import sys
from collections import defaultdict

from warcio.archiveiterator import ArchiveIterator


def main(path):
    with open(path, "rb") as stream:
        for record in ArchiveIterator(stream):
            uri = record.rec_headers.get_header("WARC-Target-URI", "")

            # DNS lookups are stored as records with a dns: URI, whose content
            # is the lookup time followed by DNS answer lines.
            if uri.startswith("dns:"):
                answer = record.content_stream().read().decode("utf-8", errors="replace")
                print(uri)
                for line in answer.splitlines()[1:]:
                    print(f"    {line}")
                print()

            elif record.rec_type == "metadata":
                # The content is "key: value" lines; a key may repeat.
                fields = defaultdict(list)
                content = record.content_stream().read().decode("utf-8", errors="replace")
                for line in content.splitlines():
                    key, _, value = line.partition(":")
                    if value:
                        fields[key.strip()].append(value.strip())

                print(uri)
                for key, values in fields.items():
                    shown = values[0] if len(values) == 1 else f"({len(values)} values)"
                    print(f"    {key}: {shown}")
                print()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
