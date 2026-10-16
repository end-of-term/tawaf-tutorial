#!/usr/bin/env python3
"""
Iterate over every record in a WARC file and print a one-line summary of each.

A WARC file is a sequence of records. Each record has:
  1. WARC headers  (WARC-Type, WARC-Target-URI, WARC-Date, ...)
  2. a content block (for "response" records: the raw HTTP headers + body)

Common record types:
  warcinfo  information about the file and the crawl that made it
  request   the HTTP request the crawler sent
  response  the HTTP response it got back (what replay tools mostly use)
  metadata  extra information about a capture (see warc_metadata.py)
  revisit   a capture whose payload was identical to an earlier one, so it
            was not stored again (deduplication)
  resource  content captured without HTTP (e.g. dns: lookups, files)

Usage:
    python warc_iterate.py FILE.warc.gz

Output (tab-separated): WARC-Type, WARC-Date, HTTP status, Content-Type, URI
followed by a count of each record type (on stderr)
"""

import sys
from collections import Counter

from warcio.archiveiterator import ArchiveIterator


def main(path):
    type_counts = Counter()
    with open(path, "rb") as stream:
        # ArchiveIterator handles both compressed (.warc.gz) and plain (.warc)
        # files, reading one record at a time without loading the whole file.
        for record in ArchiveIterator(stream):
            rec_type = record.rec_type
            date = record.rec_headers.get_header("WARC-Date")
            uri = record.rec_headers.get_header("WARC-Target-URI", "-")

            # Only "response" records carry an HTTP status line and headers
            # describing the archived resource.
            status = mime = "-"
            if rec_type == "response" and record.http_headers:
                status = record.http_headers.get_statuscode()
                mime = record.http_headers.get_header("Content-Type", "-")

            print(rec_type, date, status, mime, uri, sep="\t")
            type_counts[rec_type] += 1

    # Only some of these record types end up in a CDX index (mostly response
    # and revisit), so iterating the file shows what an index hides.
    print("\nRecord types:", file=sys.stderr)
    for rec_type, count in type_counts.most_common():
        print(f"  {rec_type:10} {count}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
