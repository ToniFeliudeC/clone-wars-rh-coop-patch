# clone-wars-rh-coop-patch: Player 2 save fix for *Star Wars: The Clone Wars – Republic Heroes* (PS3 / RPCS3)

In local co-op, **Player 2 loses everything** (points, upgrades, costumes) after relaunching the
game, after quitting to the main menu, and after dropping out and rejoining. Only Player 1's
progress is ever saved. This project is an **RPCS3 game patch** that fixes it.

With the patch, Player 2's progress is saved alongside Player 1's (in the same `SAVE.DAT`) and
restored after relaunch, quit-to-menu and drop-out/rejoin. Player 1's data is untouched.

No game files are modified or distributed: the patch is applied in memory by RPCS3.

## Supported builds

| Region | Title ID | Game version (`APP_VER`) | Patch file | Status |
|---|---|---|---|---|
| USA | `BLUS30394` | 01.00 (disc revision 01.04) | [`patches/USA/BLUS30394_patch.yml`](patches/USA/BLUS30394_patch.yml) | **Tested in-game** |
| Europe | `BLES00692` | 01.00 (disc revision 01.02) | [`patches/EUR/BLES00692_patch.yml`](patches/EUR/BLES00692_patch.yml) | **Tested in-game** |

Not supported: the **01.01 game update** (it replaces the executable; the patch simply won't
apply). RPCS3's game list shows the running version in the *Version* column, and it must read
`01.00`. (`Update available: 01.01` only means an update exists; it is not installed.)

Requires a recent RPCS3 (developed on v0.0.40-19343), as the patch uses the `calloc`/`alloc`
patch types of the patch format v1.2.

## Install

1. Back up your save folder:
   `<RPCS3>/dev_hdd0/home/00000001/savedata/BLUS30394-CWRH/` (USA) or `.../BLES00692-CWRH/` (Europe).
2. Download the patch file for your region from the
   [Releases](https://github.com/ToniFeliudeC/clone-wars-rh-coop-patch/releases) page (or from `patches/`)
   and copy it into RPCS3's `patches` folder, keeping its name
   (`BLUS30394_patch.yml` / `BLES00692_patch.yml`).
   - Linux: `~/.config/rpcs3/patches/` · Windows: `<RPCS3 folder>\patches\`
   - If you already have a file with that name, merge the entry into it instead.
3. In RPCS3: right-click the game → **Manage Game Patches** → tick
   **"Fix Player 2 progress not being saved"** → **Save**.
4. Boot the game. The RPCS3 log shows `Applied patch (... description='Fix Player 2 progress not being saved' ...)`.

## What to expect

- The first time, Player 2 starts from **0** (there is no stored P2 data yet).
- P2's progress is written whenever the game saves: changing an option, buying an item (P1 or P2),
  and the game's own save points. Like P1, anything earned since the last save is lost if you quit
  without one.
- P2's progress is restored when the game loads (boot, returning from menus) and after P2 drops out and rejoins.
- P2's data lives in `SAVE.DAT` as a second copy of each per-player entry whose name's first
  byte has its high bit set. Inspect it with `python3 tools/save.py players SAVE.DAT`.

To uninstall, untick the patch. The original game should ignore the extra entries (not tested);
restore your backup if anything looks wrong.

## Repository layout

```
patches/USA/, patches/EUR/   ready-to-use RPCS3 patch files (generated, do not edit by hand)
tools/build_patch.py         generates the patch files (PowerPC asm → RPCS3 YAML, needs LLVM)
tools/builds.py              per-build address tables (US, EU)
tools/save.py                SAVE.DAT dump / diff / P1-vs-P2 view / edit (fixes the CRC)
tools/port_map.py            maps US code addresses to another build of the game
tools/ppu_hash.py            computes RPCS3's PPU-<sha1> executable hash
tools/lisaddi.py             resolves lis/addi address constructions in a disassembly
ghidra/                      headless Ghidra helpers (import / decompile / xrefs)
docs/                        findings, patch design, porting and development notes
re/, captures/, backups/     local-only (game binaries, logs, saves), git-ignored
```

## Documentation

- [docs/FINDINGS.md](docs/FINDINGS.md): how the game handles users, players and saves; root cause.
- [docs/PATCH-DESIGN.md](docs/PATCH-DESIGN.md): what every hook does, invariants, RPCS3 patch mechanics.
- [docs/PORTING.md](docs/PORTING.md): how the EU build was ported and how to port to another build.
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md): tooling, rebuilding, live debugging, test procedure.

## Disclaimer

Fan-made fix, not affiliated with Lucasfilm, LucasArts, Krome Studios or Sony. You need your own
legally obtained copy of the game. Keep backups of your saves.

## License

[MIT](LICENSE). Covers this project's code and documentation only, not the game.
