# Findings: why co-op Player 2 loses progress

All addresses are **USA build** (`BLUS30394`, APP_VER 01.00, `PPU-54c6e0f173e6780d6c1330cf298756aa5fb66672`)
unless noted; EU equivalents are in [PORTING.md](PORTING.md).

Legend: **[S]** static fact (read in code) · **[R]** runtime fact (RPCS3 log or live memory) · **[T]** confirmed by an in-game test.

## Engine background

Krome Studios "MK3" engine, ported from Xbox 360 (source paths in the binary, e.g.
`d:\JamesPodesta\Projects\clonewars09\Code\Game\GameUser\GameUser.cpp`). The Xbox 360 design
gives every controller its own signed-in profile with its own storage. The PS3 port kept that
per-user architecture but maps all users onto **one** PS3 save directory and file.

## Objects

| Object | Where | Notes |
|---|---|---|
| `PlayerMgr*` global | `[0xC283F0]` | `players[0]` at `+0x14`, `players[1]` at `+0x18`; `GetPlayer(mgr,i)` = `0x2086e0` [S] |
| `Player` | ctor `0x207590(this, idx)` | `+0x28` progress struct, `+0x2e` player index (s16), `+0x40` `GameUser*`, `+0x44` "loaded once" flag [S] |
| `GameUser` (0x120 bytes, 5 of them) | ctor `0x209e50`; array built by `0x209540`/`0x209630` | `users[0..3]` = pad slots (table `0xB8C398`), `users[4]` = **primary** (`[0xB8C390]`) [S] |
| GameUser fields | | `+0x00` pad slot, `+0x10` sign-in state, `+0x18` **"no I/O" flag** (set only on the primary), `+0x1c` Profile, `+0x20` **SaveData**, `+0x24` trophies, `+0x28..+0xF0` 50 per-user words (`Ach_01..Ach_50`) [S] |
| `SaveData` (`GameUserSaveData.cpp`) | ctor `0x20e218`, vtable `0xC3A650` | `+0x04` owner GameUser, `+0x08` **KV store**, `+0x18` state (1 request, 2 load, 3 save), `+0x1f` last disk load/save OK, `+0x21` save enabled [S] |
| SaveData vtable | `+0x8` Reset `0x20e688`, `+0xc` Update `0x20eea8`, `+0x10` RequestLoad `0x20f068`, `+0x14` RequestSave `0x20f0b8` | [S] |
| KV store | page list: `[0]` page headers, `[1]` page data, `[2]` page size (0x5000), `[3]` page count | entries are `{char key[8]; i32/f32 value}` [S] |

## Key functions

| Function | Address | Notes |
|---|---|---|
| `Player::Save(player, commit)` | `0x2056d0` | serializes progress into `player->user->SaveData` via SetInt/SetFloat; `commit==0` returns early unless save enabled; ends with `0x20a210` [S] |
| `Player::Load(player)` | `0x204410` | reverse via GetInt/GetFloat; **first call per player does nothing** (`+0x44`); applies global audio options only when `player+0x2e == 0` [S] |
| wipe player progress | `0x206db8` | zeroes the progress struct and the user's 50 `Ach` words [S] |
| bind player to user | `0x206e60(player, pad)` | wipes; `pad 0..3` → `storeTable[pad]` + sign-in; `pad == -1` → **primary user** [S] |
| sign-in | `0x209ac8(user, slot)` | only when state is 0/3; then `RequestLoad` [S] |
| sign-out | `0x209c10` | wipes the player bound to that user [S] |
| pad poll | `0x209d90` | per pad: connected → sign-in, disconnected → sign-out [S] |
| canSave / canLoad gate | `0x20a358(user)` | `!u[0x19] && !u[0x18] && slot != -1 && state != 0` [S] |
| RequestSave-if-enabled | `0x20a210(user)` | if `SaveData+0x21` → vtable RequestSave [S] |
| KV wrappers | GetInt `0x20e6e8`, GetFloat `0x20e710`, SetInt `0x20f4c8`, SetFloat `0x20f4f0` | each is `lwz r3,8(r3); bl inner` → `0x20d440` / `0x20d678` / `0x20d9f0` / `0x20ddd8` [S] |
| KV insert | `0x20d8b8` | appends `{key, value}` if the page has room (`count*12 + 0x14 <= page size`) [S] |
| **key compare** | `0x6be658(a, b, 8)` | **case-insensitive** (`strnicmp`: A–Z folded to lowercase) [S][R] |
| DoSave / DoLoad | `0x20e748` / `0x20eba8` | file name `"save.dat"` at `0x915618`, built at `0x20eadc/0x20eae8` and `0x20ec64/0x20ec6c` [S] |
| MKSave / MKLoad | `0x6bc188` / `0x6bbf50` | → storage worker `0x6bc828` → `cellSaveDataAutoSave2/AutoLoad2(dir = "<TITLEID>-CWRH")`; **slot index ignored** [S][R] |
| Title "Press Start" | `0x23c160` | signs in `players[0]->user` with slot 0 [S] |
| Menu transitions | `0x24c288`, `0x24c4a8`, `0x248aa8`, `0x248b98` | `bind(players[1], -1)`, then for both players: wipe; `Player::Load` only if the user is signed in and its SaveData `+0x1f` [S] |
| Other `Player::Load` callers | `0x24590` (call at `0x2461c`), `0x2056b0` | not analysed in detail; covered by the generic Load hook [S] |
| Drop-out (`Dropout_Actions`) | `0x242960` | `0x206d70(p1)`, then `bind(p1, -1)` → wipes P2 [S][T] |
| Commit sites | `0x18ceac` (options), `0x23c8a0`, `0x23fa4c` | hard-coded `Player::Save(GetPlayer(mgr, 0), 1)` [S] |
| Per-player save (shop) | `0x2439c8` | `Player::Save(GetPlayer(mgr, i), 0)` [S] |

## SAVE.DAT format

Not encrypted (the PS3 save container isn't protected either). Big-endian:

```
u32 crc32(bytes[4:])   u32 version = 1   u32 count
count × { char key[8] (NUL padded); i32 value (or f32) }
zero padding to 0x5004 bytes   → max (0x5004-12)/12 = 1706 entries
```

The original save has 817 keys: per-level (`lu%02d`, `lt%02d`, `diff%02d`, `med…`, `ch0l…`),
options (`optvol0..2`, `optsub`, `optvib`), points (`fcepts` spendable, `tfcepts` total),
`combat` (upgrade bitmask, 255 = all), `costumes` (bitmask), `cheats`, `atf…`, achievement
counters `Ach_01..50`, and stats (`totaltim`, `walkdist`, `jmpcount`, …). **No key is per-player.**

## Root cause

1. Player 1 is bound (at "Press Start") to a **pad GameUser**; that user loads and saves `SAVE.DAT`. [S][R]
2. Player 2 is bound to the **primary GameUser** after every menu transition and drop-out
   (`bind(p1, -1)`). The primary carries the "no I/O" flag (`+0x18`), so its SaveData can never
   load or save. Nothing ever binds P2 to a pad user. [S][R]
3. All explicit saves serialize **only player 0**; the shop path does call `Player::Save(P2, 0)`,
   but that writes into the primary's store, which can't reach disk. [S][T]
4. Menu transitions, sign-out and drop-out **wipe** P2 in memory and can't reload it (the primary
   never loaded anything). [S][T]

Observed before the fix [T]: buying with P2 wrote nothing to disk; drop-out + rejoin wiped P2 with
no I/O; quit-to-menu wrote nothing; an options change wrote exactly one `SAVE.DAT` with P1's data
only (P2's points never appear in the file).

Even if every user could save, all GameUsers would share one file (`cellSaveDataAuto*` ignores the
user index), so P2 would overwrite P1. The fix therefore stores P2 **inside P1's store**, see
[PATCH-DESIGN.md](PATCH-DESIGN.md).

## Pitfalls found the hard way

- The primary user (`users[4]`) is **not** P1's user: P1 plays on the pad user bound at "Press Start".
- `Player::Save/Load` also read/write the 50 `Ach` words **in the GameUser object**, so swapping
  `player->user` would corrupt the other player; redirect at the KV layer instead.
- The key compare is **case-insensitive**, so `Fcepts` aliases `fcepts`. P2 keys use `key[0] ^ 0x80`
  (no existing key has a byte ≥ 0x80, and the compare only folds A–Z).
- `Player::Load` returns without loading on its first call for a player (`+0x44`).
- A missing key reads as `-1`; loading P2 when no P2 data exists would set points to -1, so the
  patch checks for P2's `fcepts` first.
- At boot, P2's first reload can run before P1's file has finished loading (async worker), so the
  patch also reloads P2 right after `Player::Load(P1)`.
- There is no free space in `.text` and no unreferenced function to reuse; code caves come from
  RPCS3's `calloc` patch type.

## Runtime facts

- Patched builds log `PAT: Allocated 0x10000 for code at 0x…` per cave and `Applied patch (...)`.
- Boot performs two `cellSaveDataAutoLoad2` of `SAVE.DAT` (boot, then "Press Start").
- Live inspection (Linux, `ptrace_scope=0`): RPCS3 maps guest memory as a memfd at host
  `0x300000000` (read-only view) and `0x400000000` (writable view) in this build;
  read `/proc/<pid>/mem` at `base + guest_address`. See [DEVELOPMENT.md](DEVELOPMENT.md).
