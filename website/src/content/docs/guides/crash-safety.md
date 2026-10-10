---
title: Crash-safety
description: How CastMane guarantees your footage survives a crash.
---

CastMane is built around a single principle: **a crash must never cost you
the footage.**

## Layers of protection

| Layer       | Mechanism                                                                                          |
| ----------- | -------------------------------------------------------------------------------------------------- |
| Container   | MKV staging (`matroskamux` tolerates missing timestamps), MP4 via lossless `ffmpeg -c copy` remux |
| File handling | Write to `X.mp4.part`, `os.replace()` to `X.mp4` only on clean stop                             |
| Shutdown    | `SIGINT` → wait → `SIGTERM` → `SIGKILL` escalation                                                 |
| Monitoring  | Encoder watchdog reports early exits with the last log lines                                       |

## Reproduce the proof yourself

Kill a live MKV recording, then remux:

```bash
gst-launch-1.0 videotestsrc is-live=true ! videoconvert ! openh264enc \
  ! h264parse ! matroskamux ! filesink location=proof.mkv.part &
sleep 4; kill -9 $!
ffprobe -v error -show_entries stream=codec_name proof.mkv.part
ffmpeg -y -v error -i proof.mkv.part -c copy proof.mp4
ffprobe -v error -show_entries stream=codec_name,duration proof.mp4
```

The `.part` file remains fully playable (`h264`, `ffprobe`-checked) even
after `kill -9`.
