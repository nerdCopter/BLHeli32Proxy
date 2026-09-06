# BLHeli32Proxy Research — Index

This folder is the research base for the `BLHeli32Proxy` project: a plan to build a
proxy/interception layer that lets the user keep installing their own archived BLHeli32
test-firmware onto owned ESC hardware, now that the original vendor (BLHeli AS, Norway) has shut
down entirely. See `../PLAN.md` (project root) for the actual design/architecture and
`../AGENTS.md` for working conventions on this project.

中文版索引见 [`README.zh.md`](README.zh.md)。

## How this research was done

All primary technical material comes from Chinese-language blog posts at
[elmagnifico.tech](https://elmagnifico.tech/tags/#BLHeli) (tags `BLHeli`, `Crack`, `DSHOT`, `ESC` —
deliberately not other unrelated tags on that same site, per project scope). Each post was:

1. Fetched and its `<article>` body extracted from the raw HTML.
2. Converted to Markdown with `pandoc` → `notes/<post>.zh.md` (Chinese, archival).
3. Every embedded image downloaded locally → `images/<post>/NN.png`.
4. Translated into a faithful **technical** note (not a loose paraphrase, code/hex kept verbatim,
   every embedded image actually opened and captioned from what it really shows) →
   `notes/<post>.en.md`. **This is the file to read for engineering work** — treat `.zh.md` as the
   archival source, not the working reference.

Two official PDF manuals bundled with the user's own local `BLHeliSuite32xl` install were also
extracted to plain text (`manuals/*.txt`), and the binary itself was inspected read-only
(`strings`, `file` — nothing executed) as a primary source in its own right — see
`notes/BLHeliSuite32xl-local-binary-analysis.en.md`.

`urls.txt` lists every post crawled with its date and canonical URL; `image_manifest.tsv` maps
every downloaded image back to its original URL and source post, in the order it appears in the
post.

## Index of research notes

Ranked by relevance to the project's actual goal (licensing/activation/protocol), not by post
date. Each row links the English technical note and, where useful, its Chinese source.

### Highest priority — protocol, cipher, and activation

| English note | Chinese source | What it covers |
|---|---|---|
| [`BLHeli-Uart-Usb-Protocol.en.md`](notes/BLHeli-Uart-Usb-Protocol.en.md) | [zh](notes/BLHeli-Uart-Usb-Protocol.zh.md) | **Master wire-protocol spec**: connect/keepalive/disconnect/read/write frames, CRC16, a full worked byte-level transcript. Start here to talk to a real ESC. |
| [`BLHeliSuite32-Reverse.en.md`](notes/BLHeliSuite32-Reverse.en.md) | [zh](notes/BLHeliSuite32-Reverse.zh.md) | Part 1: reverse-engineering toolchain, Delphi class/call-flow map, and the configurator's **own built-in debug log**, which independently confirms `0xEB00` = activation status and `0xF7AC` = further device info. |
| [`BLHeliSuite32-Reverse2.en.md`](notes/BLHeliSuite32-Reverse2.en.md) | [zh](notes/BLHeliSuite32-Reverse2.zh.md) | Part 2: the decryption routine found and broken for the first time — includes a **working, ready-to-adapt Python reference decrypt implementation** and the production XTEA key. |
| [`BLHeliSuite32-Reverse3.en.md`](notes/BLHeliSuite32-Reverse3.en.md) | [zh](notes/BLHeliSuite32-Reverse3.zh.md) | Part 3: the full decrypted 256-byte config-block field layout, byte by byte, plus the `ReadDeviceActivationStatus`/`ReadDeviceUUID_Str` calls named for the first time. |
| [`BLHeliSuite32-Reverse4.en.md`](notes/BLHeliSuite32-Reverse4.en.md) | [zh](notes/BLHeliSuite32-Reverse4.zh.md) | Part 4: cipher identified as **XTEA**, concrete production vs. test-firmware key sets, and the flash-address key-tweak. |
| [`BLHeliSuite32-Reverse5.en.md`](notes/BLHeliSuite32-Reverse5.en.md) | [zh](notes/BLHeliSuite32-Reverse5.zh.md) | Part 5: the post-shutdown "offline" configurator build — field-offset drift vs. the earlier parts, a new `FlashCounter` field, and confirmation that an activation-key UI and online-verification code paths exist in the app. |
| [`BLHeliSuite32xl-local-binary-analysis.en.md`](notes/BLHeliSuite32xl-local-binary-analysis.en.md) | *(no Chinese source — original analysis of the user's own local files)* | Findings from directly inspecting the user's own `BLHeliSuite32xl` Linux binary and official manuals: manufacturer-activation API symbols in the binary, and the manual's own description of on-device activation enforcement (protocol lockout to plain PWM). |
| [`BLHeli-END.en.md`](notes/BLHeli-END.en.md) | [zh](notes/BLHeli-END.zh.md) | **Why BLHeli died** and the license-pool business model — includes a real screenshot of the manufacturer `BLHeliSuite32Activator` tool's activation log (UUID + remaining-count protocol shape), the actual sanctions cease-letter, and community/manufacturer reaction. |

### Medium priority — practical protocol quirks

| English note | Chinese source | What it covers |
|---|---|---|
| [`BLH-Uart-Timeout.en.md`](notes/BLH-Uart-Timeout.en.md) | [zh](notes/BLH-Uart-Timeout.zh.md) | A firmware boot-timing quirk (guaranteed-fail first connect attempt, 5s reconnect timeout) and the workaround needed to automate ESC connections reliably. |

### Low priority — background only, not licensing-relevant

| English note | Chinese source | What it covers |
|---|---|---|
| [`bi-directional-DSHOT.en.md`](notes/bi-directional-DSHOT.en.md) | [zh](notes/bi-directional-DSHOT.zh.md) | Bidirectional DSHOT + eRPM telemetry (Betaflight's own open-source implementation). Only relevant to a future bench-test harness. |
| [`Dshot-STM32-PWM-HAL.en.md`](notes/Dshot-STM32-PWM-HAL.en.md) | [zh](notes/Dshot-STM32-PWM-HAL.zh.md) | Plain DSHOT protocol basics + STM32 HAL DMA-PWM implementation bugs. Same caveat — background only. Notably documents DSHOT commands 11/12 (get/save ESC settings) as a second, unexplored config channel. |
| [`BLHeli-Music.en.md`](notes/BLHeli-Music.en.md) | [zh](notes/BLHeli-Music.zh.md) | Startup-tune notation/encoding. No licensing or protocol-security content; kept only for completeness. |

## Official manuals (extracted from the vendor PDFs)

- [`manuals/BLHeli_32_manual_ARM_Rev32.x.txt`](manuals/BLHeli_32_manual_ARM_Rev32.x.txt) — the
  official end-user manual. Confirms on-device activation-failure behavior (protocol lockout to
  1-2ms PWM) directly from the vendor's own documentation.
- [`manuals/BLHeliSuite32xlHistory.txt`](manuals/BLHeliSuite32xlHistory.txt) — the Linux
  configurator's own version changelog. Confirms the activation server enforces real TLS
  certificate validation (a cert rotation broke old clients until patched).

## Local hardware/software archives referenced by this research (outside this folder)

Never delete either of these — standing project instruction:

- `$BLHELI32PROXY_ARCHIVE_DIR/BLHeliSuite32xl/` — the user's own archived Linux build of the BLHeli32
  configurator (used as a primary source, see the binary-analysis note above), plus bundled
  official manuals, official Arduino-adapter firmware, and official production `.Hex` files.
- `$BLHELI32PROXY_ARCHIVE_DIR/32.9.5_testcode/` — ~70 per-manufacturer test-firmware `.Hex` files —
  the actual binaries this whole project exists to keep flashable.

## A note on research process (worth knowing if extending this corpus)

Every embedded image cited in a `.en.md` note was actually opened and read, not just described
from its filename or surrounding text — an early pass on this project skipped that step and
missed the single most important finding in the whole corpus (the `BLHeliSuite32Activator`
manufacturer-tool activation-log screenshot in `BLHeli-END.en.md`) as a result. If this research
is ever extended to new posts, always view the images directly.
