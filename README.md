# tawaf-tutorial
Tiered Affordances in Web Archive Formats (TAWAF)

Minimal example scripts for the tutorial session. Each script works with a
single file, is short enough to read top to bottom, and explains itself in its
opening docstring (also shown when it is run without arguments).

## Setup

```sh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Sample data

The examples use the [End of Term 2024 Web Archive](https://eotarchive.org/data/data-2024/)
dataset. For every WARC file it has the derived WAT, WET, and META files, and a
CDXJ index, all at `https://eotarchive.s3.amazonaws.com/` (or
`s3://eotarchive/`). The lists of files are in
`https://eotarchive.s3.amazonaws.com/crawl-data/EOT-2024/{warc,wat,wet,meta,cdx}.paths.gz`.

The examples below use a small crawl of fema.gov (a 23 MB WARC file):

```sh
BASE=https://eotarchive.s3.amazonaws.com/crawl-data/EOT-2024/segments/WR-001
NAME=EOT24WR-0298_20250203072139554-ce949e6d-f13-0_eot-www-fema-gov-manual-20250125000654-ce949e6d-f13-20250202223202443-0

curl -O $BASE/warc/$NAME.warc.gz
curl -O $BASE/wat/$NAME.warc.wat.gz
curl -O $BASE/wet/$NAME.warc.wet.gz
curl -O $BASE/meta/$NAME.warc.meta.gz
curl -O $BASE/cdx/$NAME.cdxj.gz
```

## Scripts

The scripts follow the order of the session.

### Everything is a WARC

WAT, WET, and META files are WARC files too, derived from an original WARC.
So every script uses the same `ArchiveIterator` loop and differs only in what
it pulls out of each record.

| Script | What it shows |
|---|---|
| `scripts/warc_iterate.py FILE.warc.gz` | One line per record (type, date, HTTP status, content type, URL), then a count of each record type, including the ones a CDX index leaves out |
| `scripts/warc_record.py FILE.warc.gz [URL]` | The layers of one response record: WARC headers, HTTP headers, payload |
| `scripts/warc_metadata.py FILE.warc.gz` | What is recorded beyond the content: DNS lookups, referrer trail (`via`), crawler breadcrumb (`hopsFromSeed`), download time (`fetchTimeMs`); or, from a META file, the detected file type, format, character encoding, and languages |

```sh
python scripts/warc_iterate.py $NAME.warc.gz
python scripts/warc_record.py $NAME.warc.gz https://www.fema.gov/disaster/4580/notices
python scripts/warc_metadata.py $NAME.warc.meta.gz
```

The fema.gov crawl was made with a browser, which records no DNS lookups or
crawler metadata. To see those, try a Heritrix crawl, such as a WARC file from
an IA segment (about 1 GB):
`crawl-data/EOT-2024/segments/IA-000/warc/EOT24PRE-20240926172119-crawl804_EOT24PRE-20240926172119-00000.warc.gz`.

### WET: full text

| Script | What it shows |
|---|---|
| `scripts/wet_iterate.py FILE.warc.wet.gz` | The extracted text of each page, and the WARC record it came from (`WARC-Refers-To`) |
| `scripts/wet_token_count.py FILE.warc.wet.gz [TOP_N]` | The most frequent words across all pages, counted with `collections.Counter` |

```sh
python scripts/wet_iterate.py $NAME.warc.wet.gz
python scripts/wet_token_count.py $NAME.warc.wet.gz 25
```

### WAT: metadata and links

| Script | What it shows |
|---|---|
| `scripts/wat_iterate.py FILE.warc.wat.gz` | The JSON document of each record: original record type, HTTP status, number of links, page title |
| `scripts/wat_links.py FILE.warc.wat.gz` | Every outlink as written and normalized (made absolute, fragment removed), marked internal or external: the edges of a link graph |

```sh
python scripts/wat_iterate.py $NAME.warc.wat.gz
python scripts/wat_links.py $NAME.warc.wat.gz > links.tsv
```

### Index + WARC: random access

| Script | What it shows |
|---|---|
| `scripts/cdx_lookup.py URL DATETIME INDEX [WARC_DIR] > record.warc` | Finds the capture of a URL closest to a time, and reads only that record from the WARC file. The index entry goes to stderr, the record to stdout |
| `scripts/cdx_extract.py INDEX MIME OUTDIR [WARC_DIR]` | Saves every capture of one MIME type (e.g. `application/pdf`) as a file, reporting where the server's MIME type differs from the detected one |

`DATETIME` is `YYYYMMDDhhmmss` or any prefix of it, such as `2025` or
`202502`. Both CDX (11-field) and CDXJ indexes work, plain or gzipped.

`WARC_DIR` is where the WARC files are: a local directory (by default, the
directory of the index), or the URL the index's file names are relative to.
With the URL, only the needed records are fetched (with HTTP Range requests),
so the WARC file does not have to be downloaded at all.

```sh
# The capture of a page closest to 23:00 on 2 Feb 2025 (it has 62)
python scripts/cdx_lookup.py https://www.dhs.gov/ntas/ 20250202230000 $NAME.cdxj.gz > record.warc

# All PDFs, read from the WARC file on the web
python scripts/cdx_extract.py $NAME.cdxj.gz application/pdf pdfs/ https://eotarchive.s3.amazonaws.com/

# A JPEG that the server called a PNG is among these
python scripts/cdx_extract.py $NAME.cdxj.gz image/jpeg images/
```

### Collection indexes: ZipNum and Parquet

The per-WARC indexes above cover one file each. The End of Term 2024 Archive
also has indexes of the whole collection, both split into the same shards:

- a ZipNum index at `eot-index/collections/EOT-2024/indexes/`: sorted CDXJ
  shards compressed in blocks, plus `cluster.summary` with one line per block
- a Parquet index at `eot-index/table/eot-main/crawl=EOT-2024/`, for SQL queries

| Script | What it shows |
|---|---|
| `scripts/zipnum_lookup.py URL DATETIME cluster.summary > record.warc` | Finds the closest capture of a URL in the whole collection, with a binary search in the summary and two HTTP Range requests (an index block, then the WARC record) |
| `scripts/parquet_extract.py PARQUET DOMAIN MIME OUTDIR [LIMIT]` | Queries one Parquet shard on the web with DuckDB for a site's captures of one type, and saves them as files |

```sh
curl -O https://eotarchive.s3.amazonaws.com/eot-index/collections/EOT-2024/indexes/cluster.summary
python scripts/zipnum_lookup.py https://www.fema.gov/ 20250101 cluster.summary > record.warc

# Which shard has fema.gov? (eot24-cdx-00021)
grep -m1 '^gov,fema)' cluster.summary

pip install duckdb
python scripts/parquet_extract.py \
  https://eotarchive.s3.amazonaws.com/eot-index/table/eot-main/crawl=EOT-2024/eot24-cdx-00021.parquet \
  fema.gov application/pdf pdfs/ 5
```

A Parquet query over one shard can take from under a minute to several
minutes, so run it before the session if it is part of a live demo.

To make an index for your own WARC file:

```sh
pip install cdxj-indexer
cdxj-indexer -s FILE.warc.gz > FILE.cdxj        # CDXJ
cdxj-indexer -11 -s FILE.warc.gz > FILE.cdx     # 11-field CDX
```
