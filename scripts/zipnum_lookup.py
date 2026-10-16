#!/usr/bin/env python3
"""
Look up a URL in a large ZipNum index and fetch the closest capture's record.

A per-WARC CDX index (see cdx_lookup.py) covers a single file. To search a
whole collection, its CDX lines are merged into one sorted index, which for
the End of Term 2024 Archive is hundreds of GB. A ZipNum index makes that
searchable without downloading it:

  - The sorted CDXJ lines are split into shards (eot24-cdx-00000.cdxj.gz, ...),
    each compressed in blocks of a few thousand lines. Each block is a
    separate gzip member, so it can be read on its own.
  - A small summary file (cluster.summary) has one line per block: the block's
    first URL key and timestamp, its shard, and its offset and length:

        gov,fema)/about 20250115034501<TAB>eot24-cdx-00021.cdxj.gz<TAB>2489389683<TAB>262141

So a lookup takes three steps: a binary search in the summary, one HTTP Range
request for the block (or blocks) the URL is in, and one for the WARC record.

Usage:
    python zipnum_lookup.py URL DATETIME cluster.summary [INDEX_DIR [WARC_DIR]] > record.warc

    URL, DATETIME  as in cdx_lookup.py
    INDEX_DIR      where the shards are (default: the End of Term 2024 Archive,
                   https://eotarchive.s3.amazonaws.com/eot-index/collections/EOT-2024/indexes/)
    WARC_DIR       what the WARC file names are relative to
                   (default: https://eotarchive.s3.amazonaws.com/)

Download the summary (about 100 MB) once with:
    curl -O https://eotarchive.s3.amazonaws.com/eot-index/collections/EOT-2024/indexes/cluster.summary
"""

import gzip
import json
import sys
from bisect import bisect_left

from surt import surt

from cdx_lookup import read_range, read_record, to_datetime, warc_location

EOT_INDEX = "https://eotarchive.s3.amazonaws.com/eot-index/collections/EOT-2024/indexes/"
EOT_WARCS = "https://eotarchive.s3.amazonaws.com/"


def find_blocks(summary_path, key):
    """Return (shard, offset, length) for every block that may hold the key."""
    with open(summary_path, encoding="utf-8") as f:
        blocks = [line.rstrip("\n").split("\t") for line in f]
    firsts = [block[0] for block in blocks]  # "urlkey timestamp" of each block

    # The first block starting at or after the key; the captures of the key
    # may also begin at the end of the block before it.
    i = max(bisect_left(firsts, key + " ") - 1, 0)
    found = []
    while i < len(blocks) and firsts[i].split(" ")[0] <= key:
        shard, offset, length = blocks[i][1:4]
        found.append((shard, int(offset), int(length)))
        i += 1
    return found


def main(url, when, summary_path, index_dir=EOT_INDEX, warc_dir=EOT_WARCS):
    key = surt(url)
    target = to_datetime(when)

    # Steps 1 and 2: find the index blocks, fetch them, and keep this URL's lines.
    captures = []
    for shard, offset, length in find_blocks(summary_path, key):
        block = gzip.decompress(read_range(index_dir.rstrip("/") + "/" + shard, offset, length))
        for line in block.decode("utf-8").splitlines():
            urlkey, timestamp, fields = line.split(" ", 2)
            if urlkey == key:
                captures.append(dict(json.loads(fields), timestamp=timestamp))
    if not captures:
        sys.exit(f"No captures of {url} (SURT: {key})")
    best = min(captures, key=lambda e: abs(to_datetime(e["timestamp"]) - target))

    print(f"Found {len(captures)} capture(s) of {url} (SURT: {key})", file=sys.stderr)
    print(f"Closest to {target}:", file=sys.stderr)
    for field in ("timestamp", "url", "mime", "status", "filename", "offset", "length"):
        print(f"  {field:10} {best.get(field, '-')}", file=sys.stderr)

    # Step 3: fetch the WARC record.
    location = warc_location(best["filename"], warc_dir)
    sys.stdout.buffer.write(read_record(location, int(best["offset"]), int(best["length"])))


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5, 6):
        sys.exit(__doc__)
    main(*sys.argv[1:])
