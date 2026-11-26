"""Per-build address tables for the Player 2 save fix.

Every game build (region) has its own executable, so RPCS3 identifies it by a different
PPU hash and every code/data address can differ. All hook code is shared (build_patch.py);
only the numbers below change.

US addresses come from the original reverse engineering (docs/FINDINGS.md).
EU addresses were mapped from US with tools/port_map.py (masked instruction signatures,
then hand-verified: the four KV wrappers by their call targets, the drop-out site by
disassembly, globals/strings by tools/lisaddi.py). See docs/PORTING.md.
"""

BUILDS = {
    'us': dict(
        region='USA', title_id='BLUS30394', app_ver='01.00', disc_ver='01.04',
        hash='PPU-54c6e0f173e6780d6c1330cf298756aa5fb66672',
        save_dir='BLUS30394-CWRH',
        player_save=0x2056d0,      # Player::Save(player, commit)          first insn: stdu r1,-832(r1)
        player_load=0x204410,      # Player::Load(player)                  first insn: stdu r1,-1056(r1)
        player_wipe=0x206db8,      # wipe player progress                  first insn: stdu r1,-128(r1)
        req_save=0x20a210,         # GameUser: RequestSave if save enabled
        get_int=0x20e6e8,          # SaveData::GetInt(sd, key) (-1 if missing)
        drop_206d70=0x206d70,      # called by drop-out before re-binding P2
        player_mgr=0xC283F0,       # PlayerMgr* global; players[0] +0x14, players[1] +0x18
        fcepts_str=0x914eec,       # "fcepts" (P2 presence marker key)
        # KV wrappers: (address of `lwz r3,8(r3)`, inner function, resume address after bl+nop)
        kv=[(0x20e6f4, 0x20d440, 0x20e700),   # GetInt
            (0x20e71c, 0x20d678, 0x20e728),   # GetFloat
            (0x20f4d4, 0x20d9f0, 0x20f4e0),   # SetInt
            (0x20f4fc, 0x20ddd8, 0x20f508)],  # SetFloat
        drop_save_site=0x2429d0,   # `bl drop_206d70` in Dropout_Actions (r31 = players[1])
        drop_reload_site=0x2429e4, # `nop` after `bl bind(players[1], -1)`
    ),
    'eu': dict(
        region='EUR', title_id='BLES00692', app_ver='01.00', disc_ver='01.02',
        hash='PPU-7de69573424c08c10dbbd4d242117199befad19c',
        save_dir='BLES00692-CWRH',
        player_save=0x2056e0,
        player_load=0x204420,
        player_wipe=0x206dc8,
        req_save=0x20a220,
        get_int=0x20e6f8,
        drop_206d70=0x206d80,
        player_mgr=0xC283F0,       # unchanged (same 371 references)
        fcepts_str=0x914f4c,
        kv=[(0x20e704, 0x20d450, 0x20e710),
            (0x20e72c, 0x20d688, 0x20e738),
            (0x20f544, 0x20da00, 0x20f550),
            (0x20f56c, 0x20dde8, 0x20f578)],
        drop_save_site=0x242a28,
        drop_reload_site=0x242a3c,
    ),
}
