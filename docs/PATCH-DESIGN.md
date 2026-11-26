# Patch design (v0.4)

Source: [`tools/build_patch.py`](../tools/build_patch.py) (hook assembly) + [`tools/builds.py`](../tools/builds.py)
(addresses). Addresses below are the US build.

## Idea

Player 2 has no user that can reach the disk (see [FINDINGS.md](FINDINGS.md)), so P2's progress is
stored **inside Player 1's key/value store**, which is written to `SAVE.DAT` by the game's normal
save path. Every key P2 reads or writes is renamed by setting the high bit of its first byte:

```
P1: "fcepts"            P2: "\xe6cepts"        (0x66 ^ 0x80 = 0xe6)
```

The renaming happens only while a P2 save/load runs, at the four KV accessor wrappers, so the
game's serializer code is reused unchanged.

## State page

`[ alloc, 0x0FFE0001, 0x10000 ]`: one 64 KiB page at guest `0x0FFE0000` (inside `vm::main`, which
spans at least 0x00010000–0x10000000; nothing else uses that address).

| Byte | Name | Meaning |
|---|---|---|
| `+0` | `inP2` | a P2 save/load is running → KV wrappers redirect to P1's store and rename keys |
| `+1` | `inWipe` | re-entry guard for the wipe hook |
| `+2` | `p2valid` | P2's in-memory progress equals what is stored (loaded, or confirmed fresh); P2 is only ever **saved** while this is set |
| `+3` | `inP1Load` | re-entry guard for the P1 branch of the load hook |

## Hooks

| ID | Site (US) | Replaces | Behaviour |
|---|---|---|---|
| K1–K4 | `0x20e6f4`, `0x20e71c`, `0x20f4d4`, `0x20f4fc` | `lwz r3,8(r3)` in GetInt/GetFloat/SetInt/SetFloat | if `inP2`: use `players[0]->user->SaveData`'s KV, copy the key to the stack with `key[0] ^= 0x80`, call the inner function, resume at the wrapper's epilogue. Otherwise run the original instruction |
| S | `0x2056d0` (`Player::Save` entry) | `stdu r1,-832(r1)` | **P2:** if `p2valid` and P1's store loaded (`+0x1f`): set `inP2`, run the real `Player::Save(P2, 1)`, clear `inP2`, call `RequestSave-if-enabled(P1 user)`. Otherwise do nothing. **P1:** first make P2 current (if not `p2valid`, load it), save P2 as above, then continue into the real save of P1 |
| L | `0x204410` (`Player::Load` entry) | `stdu r1,-1056(r1)` | **P2:** clear `p2valid`; if P1's store is loaded: set `inP2`, check that P2 data exists (GetInt `"fcepts"`, renamed → not `-1`), if so set `player+0x44` and run the real `Player::Load(P2)`; clear `inP2`, set `p2valid` (a missing P2 record = fresh P2 = valid). **P1:** run the real load, then load P2 too |
| W | `0x206db8` (wipe entry) | `stdu r1,-128(r1)` | **P2:** run the real wipe, clear `p2valid`, then `Player::Load(P2)` (→ L) |
| D | `0x2429d0` in drop-out | `bl 0x206d70` | `Player::Save(P2, 1)` (→ S), then the original call |
| R | `0x2429e4` in drop-out | `nop` after `bind(P2, -1)` | `Player::Load(P2)` (→ L) |

"P1"/"P2" means `r3 == players[0]` / `players[1]` read from `[0xC283F0]`. Re-entry: S, L and W call
the very function they hook; the guard flags make the inner call fall through to the original
instruction.

### Invariants

- P1's keys are never written by a P2 operation (all P2 keys have byte 0 ≥ 0x80; the compare folds
  only A–Z). Verified by diffing P1's values before/after every test save.
- Stored P2 data is never overwritten by an unloaded/wiped P2 (`p2valid` gate).
- Nothing runs unless P1's store reports a successful load (`SaveData+0x1f`).
- P1's global audio options are untouched: `Player::Load` applies them only when the player index is 0.
- The per-user `Ach_01..50` words of P2 are read/written in P2's own (primary) user object, as
  before; they are saved under P2 keys and never touch P1's trophies data.

### Capacity

817 P1 entries + 762 P2 entries = 1579 of the 1706 that fit in `SAVE.DAT`.

## RPCS3 patch mechanics used

- **`calloc` (code_alloc)**: `[ calloc, HOOK | prot, N ]` followed by N `[ be32, 0, word ]` entries.
  RPCS3 allocates a 64 KiB executable block, copies the N words, appends a branch back to
  `HOOK + 4`, and makes `HOOK` jump to the block. The jump is a **host-side far jump**, so guest
  memory at `HOOK` still holds the original instruction, so the cave must re-execute it and other
  code can't discover the cave address by reading memory. Low 2 bits of the offset select memory
  protection (`|2` = rx, used for all caves).
- **`alloc`**: `[ alloc, ADDR | prot, SIZE ]` maps memory at a fixed address. Quirk: protection is
  `offset % 3` (not `& 3`): `0` rwx, `1` ro, `2` rx, hence `0x0FFE0001` (rwx) for the state page.
- Cave code must be position-independent: calls use `lis/ori/mtctr/bctrl` to absolute addresses,
  data addresses come from `lis/addi` or `bcl 20,31` + `mflr`. The builder rejects any relocation.
- Paths that replace a whole function end with their own `blr`; the appended return branch is then
  unreachable.
- Caves that need a stack frame create one (`stdu r1,-128(r1)`, LR saved at `+144`), keeping the
  callee's parameter-save area (`+48..+111`) free.
- Patch header must quote the app version (`[ "01.00" ]`); unquoted YAML parses `01.00` as 1.0.
- Applying the patch changes RPCS3's PPU cache module; the first boot recompiles.
