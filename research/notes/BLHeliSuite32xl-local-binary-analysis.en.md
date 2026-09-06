# Local BLHeliSuite32xl Binary + Manual Analysis (primary source, not from blog posts)

Source: the user's own archived copies —
`$BLHELI32PROXY_ARCHIVE_DIR/BLHeliSuite32xl/` (Linux build of the configurator) and
`$BLHELI32PROXY_ARCHIVE_DIR/32.9.5_testcode/` (test firmware .Hex files). Read-only inspection only
(`file`, `strings`, `pdftotext`) — nothing executed, nothing modified. This is primary vendor
material, not reverse-engineered-by-a-third-party content, and complements/partially supersedes
the (Windows/Delphi, older-version) blog analysis in the `BLHeliSuite32-Reverse*.en.md` notes.

## What's in `BLHeliSuite32xl/`

- `BLHeliSuite32xl` — **ELF 64-bit x86-64 executable, stripped**, dynamically linked. This is a
  **native Linux build** of the configurator (Delphi/FireMonkey cross-compiled), version `1.0.4.4`
  per `Settings/BLHeliSuite32xl.ini` (`Version=1.0.4.4`, created 2023-11-26 — i.e. this specific
  copy predates the June 2024 BLHeli-END shutdown).
- `libhidapi-hidraw.so` — bundled HIDAPI shim, **unstripped, with debug_info** — confirms USB-COM
  adapters are accessed via Linux `hidraw`, not a plain CDC-ACM serial port, for at least some
  adapter models.
- `Readme Linux.txt` — setup notes: add user to `dialout` group for serial port access; a udev
  rule example for a specific adapter, the **"FVT_linker"** (`idVendor=10c4` = Silicon Labs,
  `idProduct=8468`), tagged `hidraw*` — confirms this specific commercial single-wire adapter is a
  HID device, not a virtual COM port.
- `Settings/BLHeliSuite32xl.ini` — live config. Interface section shows `FC-4wif_ComPort=/dev/ttyACM0`
  (Betaflight/Cleanflight passthrough over a CDC-ACM FC connection), `UseHidDevices=1`,
  `InterfaceType=14` (enum value, meaning not decoded here). **No server hostname/URL present in
  this config file** — any activation-server address is either hardcoded in the binary (and
  presumably runtime-decrypted, consistent with the Reverse-series findings that strings aren't
  left in plaintext) or resolved some other way not visible here.
- `Manuals/BLHeli_32 manual ARM Rev32.x.pdf`, `Manuals/BLHeliSuite32xlHistory.pdf` — official
  end-user manual and version changelog, extracted to `research/manuals/*.txt` via `pdftotext`.
- `Interfaces/Arduino1Wire/`, `Interfaces/Arduino4w-if/` — **bundled pre-built .hex firmware for
  Arduino-based 4-way-if/1-wire USB adapters** (multiple AVR chip/pin variants: Uno, Nano, Mega
  2560, ATmega168/328P/88/1280, several pin-mapping variants). These are official interface
  firmwares, distributed by BLHeli itself — potentially a cheap, well-documented reference
  implementation of the host-adapter side of the protocol (the adapter's own firmware, not the ESC
  side) if their source is ever needed; not decompiled in this pass.
- `BLHeli32_HexFiles/` — official production firmware images (as opposed to the separate
  `32.9.5_testcode/` archive, which holds test-firmware builds per-manufacturer/ESC-model).
- `BLHeli32DefaultsX.cfg`, `Music/` — default parameter presets and bundled startup-tune presets.

## LICENSING/ACTIVATION RELEVANT — binary symbol evidence (from `strings` on the stripped ELF)

Even stripped, Delphi RTTI/exception-handler metadata leaves readable identifier strings. Found
directly in the binary (not inferred, not from any blog post):

- `CheckUUID`, `SerialNum`, `serial_cb` — confirms a UUID-check routine and serial-number handling
  exist as named entities in this build, consistent with the `ReadDeviceUUID_Str` wire command
  identified in the Reverse-series blog analysis.
- **`mniEnterManufActivationEventSettings`** / **`actEnterManufActivationEventSettingsExecute`** —
  a menu item + its action handler for entering **"Manufacturer Activation Event Settings"** — a
  distinct manufacturer-facing settings screen for the activation workflow, built into the retail
  app.
- **`actManufPostSerialNumbersExecute`** (and a numbered duplicate `...Execute1`) — an action that
  **POSTs serial numbers** to somewhere — i.e. the manufacturer-side bulk-activation workflow
  described narratively in `BLHeli-END.en.md` (pre-purchase N licenses, consume one per activated
  unit) has a concrete client-side action tied to it.
- **`actManufacturerInvalidateUUIDExecute`** — an action to **invalidate a UUID** — a
  manufacturer-side revoke/reset mechanism for a specific unit's identity, likely for RMA/warranty
  replacement (re-issue an activation to a replacement board without double-counting against the
  license pool).
- **`actEnterManufacturingSettingsExecute`** and a companion constant **`_NO_MANUF`** — a general
  "enter manufacturing settings" mode gated by a manufacturer-identity check (the `_NO_MANUF`
  constant is very likely the default/unauthenticated state).
- Modern Delphi networking stack in use: `System.Net.HttpClient` (incl. `TCookie`, `TURLClient`,
  `TCertificate`, `TCredentialsStorage.TCredential` — i.e. full cookie-jar + TLS client-cert-aware
  HTTP client), plus a JSON stack (`System.JSON.TJSONPair/TJSONValue`, and a third-party
  **TMS FNC JSON** component library `TTMSFNCJSONReader`/`TTMSFNCJSONWriter`/
  `TTMSFNCJSONStreamReader`). **Conclusion: the activation/manufacturer-API traffic is HTTPS +
  JSON**, using a full-featured HTTP client capable of cookies and client certificates — consistent
  with, and more specific than, the "activation runs over HTTPS" statement in `BLHeli-END.en.md`.
- No plaintext hostname/URL string was found via a direct `strings` grep — the actual endpoint(s)
  are not stored as a bare literal reachable this way (likely runtime-constructed/decrypted, same
  pattern as the config-block cipher documented in the Reverse-series posts).

### Changelog evidence (`BLHeliSuite32xlHistory.txt`, extracted from the official PDF)

- **v1.0.3.8**: *"Fixed remote connection failure, due to certificate change."* — direct
  confirmation that the activation/manufacturer server enforces TLS, and that a server-side
  certificate rotation broke older client versions until patched — i.e. the client does real
  certificate validation, not just a raw HTTPS connection with validation disabled.
- **v1.0.4.0**: *"Fixed showing all server error messages as 'Unknown Error'."* — confirms server
  error responses are structured/parsed (not just displayed raw), reinforcing the JSON-API
  conclusion above.
- No other activation/manufacturer/UUID-related changelog entries found in this history file
  (which only covers the Linux/xl-branded builds from roughly v1.0.3.x onward) — the deeper
  activation-protocol history is not documented here.

## Manual evidence — on-device activation enforcement (end-user-visible behavior)

From `BLHeli_32 manual ARM Rev32.x.pdf` (official end-user manual):

- *"At power on, an activated ESC beeps 3 beeps."*
- *"All ESCs shall be activated during manufacturing. If for some reason this is not done, the ESC
  will beep [a distinct pattern] upon powerup, before the normal operation beep sequence starts"*
  ("Not activated ESC").
- *"If for some reason activation has failed and the ESC is not regarded as a valid BLHeli_32
  unit, the ESC will beep [a distinct pattern]... **In this case the ESC will only accept 1-2ms
  pwm input signal.**"* ("Activation failed ESC").

**This is the concrete, functional enforcement mechanism**: an ESC that fails its activation check
is not fully disabled — it degrades to accepting only the oldest/simplest protocol (plain 1-2ms
PWM), with DSHOT/Oneshot/Multishot/telemetry all unavailable. This maps directly onto the
`FActivationStatus : TActivationStatus` and `FStatus : TSetupStatus` object fields identified in
`BLHeliSuite32-Reverse3.en.md`, and gives a testable, hardware-observable signal (which input
protocols the ESC actually accepts) for determining a real unit's activation state without needing
to fully decrypt anything.

## Practical follow-ups this local material enables (not yet done)

- `strings`/disassembly of the actual Linux ELF (rather than only the older Windows/Delphi
  disassembly in the blog posts) would give a currently-shipping build to verify the XTEA
  key/tweak findings from `BLHeliSuite32-Reverse4.en.md`/`...Reverse5.en.md` still hold, since this
  binary is dated after those posts.
- `strace`/`ltrace`/Wireshark-on-`usbmon` while running this actual Linux binary against a real ESC
  would give ground-truth USB/HID transaction captures without needing a Windows VM — directly
  testable given the user's own hardware/adapters and archived test firmware.
- The bundled Arduino 4-way-if/1-wire adapter `.hex` firmwares are official BLHeli-distributed
  interface implementations; if their source is available upstream (likely `4712/BLHeliSuite` or
  a linked Arduino sketch repo), that would give a vendor-sanctioned reference for the host-adapter
  side of the wire protocol, separate from the ESC-side protocol this project cares about most.
- `research/manuals/*.txt` (both PDFs, plain-text extracted) are available locally for any deeper
  keyword search without re-running `pdftotext`.
