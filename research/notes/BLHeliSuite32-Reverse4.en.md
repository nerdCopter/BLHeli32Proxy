# BLHeliSuite32 Reverse Engineering, Part 4 — Test/Beta Firmware Uses a Different XTEA Key Set

Source: https://elmagnifico.tech/2021/09/02/BLHeliSuite32-Reverse4/ (2021-09-02)

No images in this post. Follow-up triggered by discovering a second configurator binary,
**`BLHeliSuite32TestActivator`**, needed to work with BLHeli's trial/test firmware variant
(test firmware can only be read, not written/flashed, using the normal retail configurator).
Reusing a raw capture from the Part 3 methodology against test firmware produced garbage on
decrypt — different key material was needed.

### LICENSING/ACTIVATION RELEVANT — separate tool + separate firmware channel for trial ESCs

Confirms the existence of a **distinct BLHeliSuite32TestActivator** binary specifically for
handling trial/beta ESC firmware (as opposed to the retail `BLHeliSuite32` and the
manufacturer-only `BLHeliSuite32Activator` documented in `BLHeli-END.en.md`) — i.e. there are
at least **three distinct host-side tool variants** in the BLHeli32 ecosystem, each with
different behavior around activation/trial state. A complete proxy/relicensing implementation
needs to account for which of these three a given client is.

## Confirmed algorithm: XTEA (not a proprietary cipher)

This post's disassembly is the first in the corpus to make the cipher family unambiguous. The
decrypt inner loop (function `sub_00718E7C` → round loop at `00718F35`) is textbook **XTEA**:

```asm
; per-round Feistel structure, operating on a 2x32-bit (8-byte) block:
00718F38  shl eax,4            ; v0 << 4
00718F3F  shr edx,5            ; v0 >> 5
00718F42  xor eax,edx
00718F44  add eax,esi          ; (esi = v0 itself, i.e. + v0)
00718F46  mov edx, ebx         ; ebx = running sum (delta accumulator)
00718F48  shr edx,0B
00718F4B  and edx,3
00718F4E  mov edx,[ebp+edx*4-34]   ; select 1 of 4 key words by (sum>>11)&3
00718F52  add edx,ebx
00718F58  add edx,ecx              ; ecx = extra tweak value, see below
00718F5A  xor eax,edx
00718F5C  sub [ebp-0C],eax         ; v1 -= (...)
00718F5F  sub ebx, 0x9E3779B9      ; sum -= delta   <-- THE canonical XTEA/TEA magic constant
```

`0x9E3779B9` is the standard TEA-family "magic constant" (⌊2³²/φ⌋, the golden-ratio-derived
delta used by TEA, XTEA, and XXTEA) — this is conclusive identification of the cipher as
**XTEA** (or a close, standard-structure variant of it), not a custom/proprietary algorithm.
This directly supersedes the "not Caesar cipher, no obvious pattern" negative-result note in
`BLHeli-Uart-Usb-Protocol.en.md` — the actual cipher family is now known, which makes
implementing a from-scratch encrypt/decrypt in this project's own tooling (e.g. Python, C, or
Rust) straightforward once the key(s) are known, using any standard XTEA reference
implementation with the parameters below.

## Key material — differs between production and test/beta firmware

Both variants use a **128-bit key = four 32-bit words**, consistent with standard XTEA (which
takes a 128-bit key split into 4x uint32):

```
Production (BLHeliSuite32, retail) firmware key:
  K0 = 0x318234B4
  K1 = 0x29A1FA54
  K2 = 0x9E81C901
  K3 = 0x81FBC617

Test/beta (BLHeliSuite32TestActivator) firmware key:
  K0 = 0x315534B4
  K1 = 0x20A5F454
  K2 = 0x1E88C901
  K3 = 0x71F1C617
```

Swapping in the test-variant key set was sufficient to correctly decode captures taken against
trial/beta firmware — confirming these are literally two different static 128-bit keys, not a
derived/computed difference.

## An overlooked fifth "key" component: the target address itself

A separate 16-bit value (`ecx`, loaded from `word ptr [ebp-6]`) is folded into every round via
`add edx,ecx` before the final XOR. The author initially assumed this was a constant (it read
as `0x7C00` on every ESC tested so far, matching the config block's flash address documented in
`BLHeli-Uart-Usb-Protocol.en.md`). Testing against an ESC identified as device-type `4703`
(see the device-type table in that same post) revealed the configurator actually runs
**decryption twice** for that device — once seeded with `0x7C00`, once with `0xF800` — and only
the second pass yields valid plaintext. Conclusion: **the flash address of the block being
decrypted (`0x7C00` and, for at least some device types, `0xF800`) is itself part of the
effective key material**, not a fixed constant — this address corresponds to the same "set
address" values sent over the wire in the connect/read/write protocol.

**Open question flagged by the author, not resolved in this post**: whether the
`0x9E3779B9` TEA delta constant itself is loaded from a fixed static location or could vary is
untested — the author notes it's always read from the same address and always multiplied by a
fixed round count (`0x20` = 32 rounds, standard for XTEA), so it wasn't treated as a variable
key component, but flags that it theoretically could be worth adding to the key-search space
for other device/firmware variants not yet tested.

**Not addressed in this post** (open item carried from `BLHeli-Uart-Usb-Protocol.en.md`): why
the wire-captured ciphertext for the *same* logical configuration differed on every single read
in that earlier post's raw capture. If the cipher is deterministic XTEA-ECB-per-block keyed only
by `(key, address)`, identical plaintext at a fixed address should produce identical ciphertext
on every read — the corpus does not explain this discrepancy. Possible explanations not
confirmed anywhere in this corpus: an additional per-session nonce/IV outside what Part 4
disassembled, a CBC/counter-style chaining using something that changes per session (e.g. a
power-on counter), or the "identical configuration" assumption across those particular reads
being incorrect. **This is a concrete open question this project should resolve empirically**
(e.g. capture two back-to-back reads with zero configuration changes and diff both ciphertext
and any state that could serve as an IV) before relying on a pure static-key XTEA decrypt.

## Relevance to this project

This is the most implementation-ready cryptographic finding in the corpus: **cipher = XTEA,
128-bit key (2 known key sets: production and test/beta), with the target flash address folded
into the per-round key schedule, 32 rounds**. A working decrypt/encrypt module for the 256-byte
config block can be built directly from this (any standard XTEA library, adapted to take the
address as extra key input), pending resolution of the same-plaintext/different-ciphertext
question noted above.
