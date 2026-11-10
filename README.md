# tennis_database

Analysis of professional tennis match data (ATP and WTA): match results,
serve statistics, rankings and player information.

The raw data is **not** stored in this repository (it is large and
third-party). See "Data sources" below for where it comes from and how to
re-download it.

## Data sources

### TennisMyLife (`tml-data/`)

ATP match data (yearly files 1967 onwards, Challenger and qualifying files in
`atp_quali/`, plus some WTA and ongoing-tournament files) from
[TennisMyLife](https://stats.tennismylife.org) (© TennisMyLife), downloaded via
its data API: <https://stats.tennismylife.org/api/data-files>.
No explicit license is stated on the site; please credit TennisMyLife when
using this data.

Re-download (requires `curl` and `python3`):

```bash
mkdir -p tml-data && curl -s 'https://stats.tennismylife.org/api/data-files' | python3 -c 'import sys,json
for f in json.load(sys.stdin)["files"]: print(f["url"]+"\t"+f["name"])' | while IFS=$'\t' read -r url name; do mkdir -p "tml-data/$(dirname "$name")"; curl -sSL "$url" -o "tml-data/$name"; done
```

### WTA data (`wta/`: `matches.csv`, `players.csv`, `qualifying_matches.csv`, `rankings.csv`)

WTA matches, qualifying matches, players and rankings. The columns and player
IDs follow the format of Jeff Sackmann's
[tennis_wta](https://github.com/JeffSackmann/tennis_wta) dataset, which this
data appears to be derived from (the files here are a combined/reformatted
version; the exact intermediate source is not documented).

Tennis databases, files, and algorithms by
[Jeff Sackmann / Tennis Abstract](http://www.tennisabstract.com/) are licensed
under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](http://creativecommons.org/licenses/by-nc-sa/4.0/).
Based on a work at <https://github.com/JeffSackmann>.
