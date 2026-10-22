# Mission Control (LaBeau job lights)

One green / yellow / red light per LaBeau job, so a broken job shows up by 4 pm instead of at 7:25 am.

| Light | Green when | Red when |
|---|---|---|
| Daily email | today's and tomorrow's rows are in `data/logs/mail_sent.csv` (TEST rows don't count) | today's missing after 6:30 am, or tomorrow's missing after 4:30 pm |
| Captions written | every post tomorrow has a caption with no placeholder; nightly captions log is under 26 h old | a post tomorrow has no caption or a `[YOUR WORDS]`-style placeholder, or the captions log says "Not logged in" |
| Assets built | every visual post tomorrow has files in 04-posts | a visual post tomorrow has no files, or an IG/TikTok post is a single still (video-first rule) |
| Tomorrow ready | `packet_for(tomorrow)` (the real `labeau prepare` code) shows 0 HOLD | any HOLD |
| Background jobs | `ink.labeau.mail-daily` and `ink.labeau.captions-daily` are loaded and last exited 0 | one is not installed |

The two days after tomorrow are checked too and show yellow, never red.

It is read-only against labeau-ops: it never posts, writes a caption, or touches a poem, and it never shows a platform number.

## Where the lights go
- `~/.labeau/mission-control/status.json` and `status.html` on the Mac.
- `My Drive/LaBeau-Assets/mission-control/labeau-mission-status.json`, which the phone page reads through the Google Drive connector.
- An email to both of Chris's addresses (the same Gmail app password as `labeau mail`) when anything is red at 6:35 am, 4:05 pm or 4:35 pm. Each slot sends at most once a day, and the result is logged in `alerts.csv`. A Mac notification pops up as well.

launchd job `ink.labeau.mission-control` runs at :05 and :35 every hour, and once at load.

## Install (on the Mac)
```
bash mission-control/install.sh
```
It copies `mission_control.py` into `labeau-ops/scripts/`, installs the launchd job, adds a harness-map row (cloned from the mail-daily row), and prints the first check. Undo: `bash mission-control/uninstall.sh`.

## Tests
```
cd mission-control && python3 -m unittest test_mission_control
```
