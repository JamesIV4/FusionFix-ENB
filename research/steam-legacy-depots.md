# Steam legacy-build availability check — 2026-09-05

Historical manifest IDs are documented for 1.0.7.0 and 1.0.8.0. The user has now
tested both in Steam. The September 5 content log records **Access Denied** for
1.0.7.0 at 15:00:39 and an HTTP 200 manifest response plus active chunk download
for **1.0.8.0** at 15:00:53. The user subsequently reported completion. The
downloaded executable reports file/product version **1.0.8.0** and its shaders
have now been compared with CE; see [the reference analysis](steam1080-reference.md).

Steam is downloading 14,497,908,784 bytes and staging 16,137,894,089 bytes into:

`C:\Games\Steam\steamapps\content\app_12210\depot_12211\GTAIV`

The directory exists. It is separate from the current installation under
`steamapps\common`. The assistant only inspected the directory and log; the
user initiated the download. Preserve this reference separately for analysis.

All commands below use app 12210. The
[author-tested Steam guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2871168938)
identifies these builds and components:

| Version | Component | Depot | Manifest |
|---|---|---|---|
| 1.0.7.0 (2014 release) | Game data | 12211 | 164691614299318355 |
| 1.0.7.0 | Installers | 12218 | 4580003337930899901 |
| 1.0.8.0 (2016 release) | Game data | 12211 | 4406763129603688303 |
| 1.0.8.0 | Installers | 12218 | 5538672447096893223 |
| Both | English | 12213 | 8742857342288690692 |

The same guide obtains 1.0.4.0 by applying a separate patch; it does not identify
a Steam 1.0.4.0 manifest. No such manifest was verified in this check.

A [firsthand DepotDownloader report dated January 26, 2025](https://github.com/SteamRE/DepotDownloader/discussions/573)
states that the 1.0.7.0 manifest returned Access Denied in Steam and HTTP 401 in
DepotDownloader, while the 1.0.8.0 manifest worked. That is historical evidence,
not a current test of this account. The
[downloader's FAQ](https://github.com/SteamRE/DepotDownloader#frequently-asked-questions)
explains that publishers can block old manifests even when their IDs are known.

SteamDB corroborates the old
[installer manifests](https://steamdb.info/depot/12218/manifests/) and
[English manifest](https://steamdb.info/depot/12213/manifests/). Its current
[game-data history](https://steamdb.info/depot/12211/manifests/) requires sign-in
to show entries older than its ten public rows. These are metadata records, not
proof of CDN access. No alternate route around that sign-in was attempted.

The user's installed appmanifest remains build 14009960, main depot manifest
8070600747380932868. It contains no evidence that a legacy build has downloaded.

Commands used by the user for the two main manifests:

```text
download_depot 12210 12211 164691614299318355
download_depot 12210 12211 4406763129603688303
```

These commands request depot downloads; they are not metadata-only probes.
Establish access before requesting the installer/language components. Retain
any successful reference download separately for executable/shader comparison.
The user performed the client-side check directly, so computer use was not
needed. The main depot is now a verified-version static reference; the old game
has not been launched or installed over CE.
