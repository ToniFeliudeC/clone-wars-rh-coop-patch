# Porting to another build

Each regional build has its own executable: different RPCS3 PPU hash, code shifted by small
amounts. The hook logic is identical; only the address table in
[`tools/builds.py`](../tools/builds.py) changes.

## Europe (`BLES00692`)

| | USA `BLUS30394` | Europe `BLES00692` |
|---|---|---|
| PPU hash | `PPU-54c6e0f173e6780d6c1330cf298756aa5fb66672` | `PPU-7de69573424c08c10dbbd4d242117199befad19c` |
| APP_VER / disc VERSION | 01.00 / 01.04 | 01.00 / 01.02 |
| Save directory | `BLUS30394-CWRH` | `BLES00692-CWRH` |
| `Player::Save` | `0x2056d0` | `0x2056e0` |
| `Player::Load` | `0x204410` | `0x204420` |
| wipe | `0x206db8` | `0x206dc8` |
| RequestSave-if-enabled | `0x20a210` | `0x20a220` |
| GetInt wrapper | `0x20e6e8` | `0x20e6f8` |
| drop-out helper | `0x206d70` | `0x206d80` |
| `PlayerMgr*` global | `0xC283F0` | `0xC283F0` (unchanged) |
| `"fcepts"` string | `0x914eec` | `0x914f4c` |
| K1 GetInt (`lwz` / inner / resume) | `0x20e6f4` / `0x20d440` / `0x20e700` | `0x20e704` / `0x20d450` / `0x20e710` |
| K2 GetFloat | `0x20e71c` / `0x20d678` / `0x20e728` | `0x20e72c` / `0x20d688` / `0x20e738` |
| K3 SetInt | `0x20f4d4` / `0x20d9f0` / `0x20f4e0` | `0x20f544` / `0x20da00` / `0x20f550` |
| K4 SetFloat | `0x20f4fc` / `0x20ddd8` / `0x20f508` | `0x20f56c` / `0x20dde8` / `0x20f578` |
| key compare | `0x6be658` | `0x6be6b8` |
| D (drop-out save site) | `0x2429d0` | `0x242a28` |
| R (drop-out reload site) | `0x2429e4` | `0x242a3c` |

How it was verified:

1. `tools/port_map.py US.elf EU.elf ADDR…` finds each US function in the EU binary by a masked
   instruction signature (branch offsets and 16-bit immediates ignored, 32-instruction match).
2. The four KV wrappers are byte-identical apart from their call target, so they were identified by
   the inner function they call (found via step 1).
3. Drop-out site and globals read from disassembly / `tools/lisaddi.py` (the EU `"fcepts"` is
   referenced from EU `Player::Load`; `PlayerMgr` has the same 371 references in both builds).
4. `port_map.py --diff` compared every function the patch relies on **without masking**: the only
   differences are string addresses (`addic` low halves) and call/branch offsets; **no struct
   field offset differs**. The wipe, bind, RequestSave, GetPlayer and KV functions are bit-identical.
5. `tools/ppu_hash.py` reproduces the known US hash exactly, so the computed EU hash is reliable.
6. Generated EU caves differ from the tested US caves in exactly 22 words, all address constants.

**Tested in-game** after porting, using the procedure in [DEVELOPMENT.md](DEVELOPMENT.md#in-game-test).

## Porting to a new build

1. Decrypt its `EBOOT.BIN` (`rpcs3 --decrypt <path>` writes `EBOOT.elf` next to it) and disassemble:
   `llvm-objdump -d --no-show-raw-insn --triple=powerpc64 EBOOT.elf > eboot.asm`.
2. `python3 tools/ppu_hash.py EBOOT.elf` → hash for the table.
3. `python3 tools/port_map.py re/us/EBOOT.elf NEW.elf 0x2056d0 0x204410 0x206db8 0x20a210 0x20e6e8 0x206d70 0x2429c0`
   and resolve the KV wrappers / drop-out sites / globals by hand as above.
4. Run `port_map.py --diff` over the functions listed in step 4 above and make sure only address
   constants differ. If field offsets or control flow differ, the hook bodies need review.
5. Add an entry to `BUILDS` (with `region`/`title_id`/`app_ver`/`hash`), run `tools/build_patch.py`,
   test in-game.

The 01.01 update (US) would be ported the same way, but it may have changed more than addresses
(it adds online co-op), so step 4 matters there.
