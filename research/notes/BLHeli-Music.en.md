# BLHeli Custom Startup Music — Notation Reference (Off-Topic, Brief)

Source: https://elmagnifico.tech/2020/06/12/BLHeli-Music/ (2020-06-12)

Confirmed genuinely off-topic to this project's licensing/protocol goal — this post is pure
music-theory documentation for BLHeli's custom startup-tune feature, not protocol/security
content. Kept brief per scope; see `BLHeliSuite32-Reverse3.en.md` for where the `Note_Config` /
`Note_Array` fields (offsets `0x1C` and `0x90` in the decrypted config block) that store this
data actually live in the wire format, if this project ever needs to read/write tune data
programmatically.

## Notation summary (for reference only)

- Note format: `[Note][Octave] [Length]`, e.g. `C52` = note C, octave 5, length 1/2.
- 12 chromatic note names (C, C#/Db, D, D#/Eb, ... B); 4 valid octaves (4-7); 4 note lengths
  (1/1, 1/2, 1/4, 1/8, with the leading "1" conventionally omitted in shorthand); rest/pause
  notated `P` with lengths down to 1/128.
- Two global parameters: **Gen. Length** (playback speed: 8 = normal, one note = 0.5 s; lower =
  faster) and **Gen. Interval** (gap between notes); the sum of Length+Interval settings is
  capped at 15 (e.g. 14+1 or 15+0, never 15+15 combined).
- Up to 48 note-slots total per ESC, including rests.
- Multi-ESC setups (up to 8 ESCs) can each play a different voice/harmony part for a
  multi-instrument effect; several worked examples (Game of Thrones theme, Super Mario theme,
  Axel F/Crazy Frog, Frozen's Let It Go across 4 motors, etc.) are given in the source post's
  raw note strings if ever needed for test-fixture audio.

## Relevance to this project

None beyond confirming where this feature's data lives in the config block layout (see
`BLHeliSuite32-Reverse3.en.md`, offsets `0x1C`/`0x90`). No licensing, activation, or protocol
security content in this post.
