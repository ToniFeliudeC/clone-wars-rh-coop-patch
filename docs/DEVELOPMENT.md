# Development

## Requirements

- Python 3 (+ PyYAML only for optional checks)
- LLVM tools on `PATH`: `llvm-mc`, `llvm-objcopy`, `llvm-objdump`, `llvm-readelf` (PowerPC target)
- RPCS3 (for decrypting and testing); Ghidra 12.x optional (decompilation)

## Rebuilding the patches

```
python3 tools/build_patch.py          # all builds → patches/USA/…, patches/EUR/…
python3 tools/build_patch.py eu       # one build
```

The output files are generated: change `tools/build_patch.py` (hook code) or `tools/builds.py`
(addresses), never the YAML. Each cave is listed with its disassembly as comments. The builder
refuses code that needs relocations. Bump `VERSION` in `build_patch.py` for any behaviour change.

Install for testing (Linux):

```
cp patches/USA/BLUS30394_patch.yml ~/.config/rpcs3/patches/
cp patches/EUR/BLES00692_patch.yml ~/.config/rpcs3/patches/
```

then enable it in *Manage Game Patches* (stored in `~/.config/rpcs3/patch_config.yml`, keyed by
hash + patch description; keep the description stable or the enable flag is lost).

## Local working files (git-ignored)

```
re/us/EBOOT.BIN, EBOOT.elf, eboot.asm      US executable: encrypted, decrypted, disassembly
re/eu/…                                    same for Europe
ghidra/proj.*  ghidra/out/                 Ghidra project (US) and decompiled functions
captures/                                  RPCS3 logs + save snapshots from test sessions
backups/                                   save backups
```

Recreate them:

```
cp "<game>/PS3_GAME/USRDIR/EBOOT.BIN" re/us/
rpcs3 --decrypt "$PWD/re/us/EBOOT.BIN"             # → re/us/EBOOT.elf
llvm-objdump -d --no-show-raw-insn --triple=powerpc64 re/us/EBOOT.elf > re/us/eboot.asm
ghidra/import.sh                                   # one-time Ghidra import + analysis (US)
ghidra/decomp.sh 2056d0 204410                     # → ghidra/out/<addr>.c
ghidra/xrefs.sh 0x914eec
```

(`rpcs3 --decrypt` must run without `--headless` in this version, or it silently does nothing.)

Address helpers: `tools/lisaddi.py re/us/eboot.asm re/us/EBOOT.elf LO HI` lists every `lis/addi`
(or `lis/ori`, `lis` + load) construction of an address in `[LO, HI)` with the string it points to.
`tools/port_map.py` maps addresses between builds ([PORTING.md](PORTING.md)).
`tools/ppu_hash.py EBOOT.elf` prints RPCS3's patch hash.

## Save files

```
python3 tools/save.py dump    SAVE.DAT            # all entries (P2 entries shown as P2:key)
python3 tools/save.py players SAVE.DAT            # P1 vs P2 points/upgrades/costumes
python3 tools/save.py diff    A/SAVE.DAT B/SAVE.DAT
python3 tools/save.py set     SAVE.DAT key=value   # edits + fixes the CRC
```

Location: `~/.config/rpcs3/dev_hdd0/home/00000001/savedata/<TITLEID>-CWRH/SAVE.DAT`.
The RPCS3 log (`~/.cache/rpcs3/RPCS3.log`) shows every `cellSaveDataAutoLoad2/AutoSave2` and the
file name, which tells exactly when the game reads/writes the save.

## Live inspection

RPCS3's debugger isn't needed: guest memory can be read from outside.

```
sudo sysctl kernel.yama.ptrace_scope=0
python3 tools/live.py state        # patch flags, both players' users and SaveData flags, points
python3 tools/live.py kv           # P1/P2 entries in the in-memory store
sudo sysctl kernel.yama.ptrace_scope=1
```

`--build eu` for the European game. The PS3 address space is a memfd mapped twice (read-only and
writable views); guest address `A` is at `base + A`.

Patches can't print, but `sys_tty_write` (syscall 403) from a cave would land in
`~/.cache/rpcs3/TTY.log` if tracing is ever needed.

## In-game test

Back up the save first. With both controllers:

1. Boot. Log shows `Applied patch (... 'Fix Player 2 progress not being saved' ...)`.
   P1 has their usual progress; P2 has 0 (first run) or their stored progress.
2. P2 earns points and buys something (purchase triggers a save → spinner).
3. `tools/save.py players SAVE.DAT`: P2 column shows the new points/costume; P1 unchanged
   (`tools/save.py diff backup/SAVE.DAT SAVE.DAT` must show only P2 entries and play stats).
4. Pause → quit to main menu → back into a level: P2 unchanged.
5. P2 → pause → drop out ("abandonar"/"Drop out") → rejoin: P2 unchanged.
6. Close the game completely, relaunch: P2 unchanged.

Before the patch, steps 4–6 each wiped P2.
