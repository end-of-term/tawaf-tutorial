#!/usr/bin/env python3
"""
Look up a URL in a CDX index and extract the closest capture from its WARC file.

A CDX index has one line per capture. Each line records the capture's URL key,
timestamp, and where the record lives: WARC file name, byte offset, and
compressed length. With that, one record can be read straight out of a large
WARC file without iterating over the whole file, or even without downloading
it: over HTTP, a Range request fetches just those bytes.

Both common index formats are supported:

  CDX (space-separated; the first line is a legend, e.g. " CDX N b a m s k r M S V g")
    gov,fema)/ 20250202223207 https://www.fema.gov/ text/html 200 DIGEST - - 3211 1314473 file.warc.gz

  CDXJ (URL key, timestamp, JSON)
    gov,fema)/ 20250202223207 {"url": "https://www.fema.gov/", ..., "length": "3211", "offset": "1314473", "filename": "file.warc.gz"}

The file name may include a path, as in the End of Term Archive indexes, where
it is relative to https://eotarchive.s3.amazonaws.com/.

The URL key is a SURT (Sort-friendly URI Reordering Transform), e.g.
https://www.fema.gov/about -> gov,fema)/about, so the URL is converted to a SURT
before searching.

Usage:
    python cdx_lookup.py URL DATETIME INDEX.cdx [WARC_DIR] > record.warc

    URL       the archived URL to look up
    DATETIME  the desired time, as YYYYMMDDhhmmss or any prefix of it (e.g. 2024
              or 202408), separators allowed (e.g. 2024-08-03T01:28:24Z)
    INDEX     the CDX or CDXJ file (may be gzipped)
    WARC_DIR  where the WARC files are: a local directory (default: the index
              file's directory), or a URL that the index's file names are
              relative to, e.g. https://eotarchive.s3.amazonaws.com/

The capture closest in time is selected. Its index entry is printed to stderr
and the (decompressed) WARC record to stdout.
"""

import gzip
import json
import os
import sys
from datetime import datetime
from urllib.request import Request, urlopen

from surt import surt

# CDX legend letters for the fields this script uses.
# Full list: https://iipc.github.io/warc-specifications/specifications/cdx-format/cdx-2015/
CDX_FIELDS = {
    "N": "urlkey",
    "b": "timestamp",
    "a": "url",
    "m": "mime",
    "s": "status",
    "k": "digest",
    "S": "length",
    "V": "offset",
    "g": "filename",
}
DEFAULT_LEGEND = "N b a m s k r M S V g".split()  # the common 11-field CDX


def parse_index(path):
    """Yield one dict per index line, for both CDX and CDXJ formats."""
    opener = gzip.open if path.endswith(".gz") else open
    legend = DEFAULT_LEGEND
    with opener(path, "rt", encoding="utf-8") as lines:
        for line in lines:
            if line.startswith(" CDX"):
                legend = line.split()[1:]
                continue
            if line.rstrip().endswith("}"):
                # CDXJ: urlkey, timestamp, then a JSON block
                urlkey, timestamp, block = line.split(" ", 2)
                entry = json.loads(block)
            else:
                # CDX: space-separated values, named by the legend letters
                values = dict(zip(legend, line.split()))
                entry = {CDX_FIELDS[k]: v for k, v in values.items() if k in CDX_FIELDS}
                urlkey, timestamp = entry["urlkey"], entry["timestamp"]
            entry.update(urlkey=urlkey, timestamp=timestamp)
            yield entry


def to_datetime(value):
    """Turn a full or partial 14-digit timestamp into a datetime.

    Missing digits are filled in from the earliest possible moment, so "2024"
    means 2024-01-01 00:00:00.
    """
    digits = "".join(c for c in value if c.isdigit())
    return datetime.strptime(digits + "00000101000000"[len(digits):], "%Y%m%d%H%M%S")


def warc_location(filename, warc_dir):
    """Where the WARC file named in the index is, locally or on the web."""
    if warc_dir.startswith(("http://", "https://")):
        return warc_dir.rstrip("/") + "/" + filename
    # Locally, look for the file by its name alone, ignoring any path.
    return os.path.join(warc_dir, os.path.basename(filename))


def read_range(location, offset, length):
    """Read length bytes starting at offset, from a local file or a URL."""
    if location.startswith(("http://", "https://")):
        # An HTTP Range request fetches only these bytes, not the whole file.
        headers = {"Range": f"bytes={offset}-{offset + length - 1}"}
        with urlopen(Request(location, headers=headers)) as response:
            return response.read()
    with open(location, "rb") as f:
        f.seek(offset)
        return f.read(length)


def read_record(location, offset, length):
    """Read a single record's bytes from a WARC file by offset and length."""
    data = read_range(location, offset, length)
    # In a .warc.gz file each record is compressed separately (a gzip
    # "member"), which is what makes this random access possible.
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def main(url, when, index_path, warc_dir=None):
    key = surt(url)
    target = to_datetime(when)

    # Find all captures of this URL and pick the one closest to the target time.
    captures = [e for e in parse_index(index_path) if e["urlkey"] == key]
    if not captures:
        sys.exit(f"No captures of {url} (SURT: {key}) in {index_path}")
    best = min(captures, key=lambda e: abs(to_datetime(e["timestamp"]) - target))

    # Metadata goes to stderr, so stdout holds nothing but the WARC record.
    print(f"Found {len(captures)} capture(s) of {url} (SURT: {key})", file=sys.stderr)
    print(f"Closest to {target}:", file=sys.stderr)
    for field in ("timestamp", "url", "mime", "status", "filename", "offset", "length"):
        print(f"  {field:10} {best.get(field, '-')}", file=sys.stderr)

    location = warc_location(best["filename"], warc_dir or os.path.dirname(index_path))
    record = read_record(location, int(best["offset"]), int(best["length"]))
    sys.stdout.buffer.write(record)


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        sys.exit(__doc__)
    main(*sys.argv[1:])
