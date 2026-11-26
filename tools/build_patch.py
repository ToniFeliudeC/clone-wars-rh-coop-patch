#!/usr/bin/env python3
"""Build the RPCS3 patches for the Republic Heroes co-op Player 2 save fix.

One patch file per game build, from the address tables in tools/builds.py:
  patches/USA/BLUS30394_patch.yml   patches/EUR/BLES00692_patch.yml

Design: Player 2's progress is stored *inside P1's SAVE.DAT* under the same keys
with the high bit of the first character set (fcepts -> \xe6cepts). NB: the game's key
compare (0x6be658) is case-INSENSITIVE, so v0.2's case flip aliased P1's keys.

Why: P1 plays on a pad GameUser that loads/saves SAVE.DAT; P2 is bound to the
"primary" GameUser (users[4]) which is flagged as unable to do disk I/O, and P2 never
gets a user of its own. So instead of giving P2 a file, we piggy-back on P1's store:

  S  Player::Save entry   P2 -> serialize into P1's store (keys flipped) + request P1 file save
                          P1 -> first serialize P2 (or load it if not yet valid), then save P1
  L  Player::Load entry   P2 -> load from P1's store (keys flipped), only if P2 keys exist
                          P1 -> run it, then load P2 too (store is known-ready here)
  W  wipe entry           P2 wiped (menu transitions, sign-out) -> immediately reload P2
  D  drop-out             save P2 before the drop-out wipe ...
  R  drop-out             ... and reload it right after
  K1-K4  KV accessors     while FLAG.inP2: use P1's SaveData and key[0] ^= 0x80

State lives in a small rwx page allocated with `alloc` at 0x0FFE0000:
  +0 inP2 (redirect active)  +1 inWipe  +2 p2valid (P2 in memory matches store)  +3 inP1Load

Each hook is an RPCS3 `calloc` code cave: the instruction at HOOK is replaced by a
branch into the cave, and RPCS3 appends a branch back to HOOK+4 at the label `done`
(which must be last). Paths that fully replace a function return with their own blr.

usage: build_patch.py [us|eu ...]      (default: all builds)
"""
import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from builds import BUILDS

VERSION = '0.4'
STATE = 0x0FFE0000          # our rwx state page (same for every build)

def hi(a): return (a + 0x8000) >> 16
def lo(a): return a - (hi(a) << 16)

def make_hooks(B):
    """Return the hook list (address, name, assembly) for one build's address table."""
    PLAYER_SAVE, PLAYER_LOAD, PLAYER_WIPE = B['player_save'], B['player_load'], B['player_wipe']
    REQ_SAVE, GET_INT, DROP_206D70 = B['req_save'], B['get_int'], B['drop_206d70']
    PLAYER_MGR, FCEPTS_STR = B['player_mgr'], B['fcepts_str']

    def call(a):
        return f"""
      lis 12, {a >> 16:#x}
      ori 12, 12, {a & 0xffff:#x}
      mtctr 12
      bctrl
    """
    
    def p1sd(r, fail):
        """r = players[0]->user->SaveData, branch to `fail` on any null."""
        return f"""
      lis {r}, {hi(PLAYER_MGR):#x}
      lwz {r}, {lo(PLAYER_MGR)}({r})
      cmpwi {r}, 0
      beq {fail}
      lwz {r}, 20({r})
      cmpwi {r}, 0
      beq {fail}
      lwz {r}, 64({r})
      cmpwi {r}, 0
      beq {fail}
      lwz {r}, 32({r})
      cmpwi {r}, 0
      beq {fail}
    """
    
    FRAME_IN = """
      mflr 0
      stdu 1, -128(1)
      std 0, 144(1)
      std 31, 120(1)
      std 30, 112(1)
    """
    FRAME_OUT = """
      ld 30, 112(1)
      ld 31, 120(1)
      ld 0, 144(1)
      mtlr 0
      addi 1, 1, 128
    """
    
    # ---- K: KV accessor wrappers -------------------------------------------------------
    def kv_hook(inner, cont):
        return f"""
      lis 12, {STATE >> 16:#x}
      lbz 0, 0(12)
      cmpwi 0, 0
      bne 1f
      lwz 3, 8(3)               # original
      b done
    1:
      lis 12, {hi(PLAYER_MGR):#x}
      lwz 12, {lo(PLAYER_MGR)}(12)
      lwz 12, 20(12)
      lwz 12, 64(12)
      lwz 3, 32(12)             # P1's SaveData (validated before inP2 was set)
      lwz 3, 8(3)               # its KV store
      stdu 1, -128(1)
      li 0, 0
      std 0, 112(1)
      std 0, 120(1)
      lbz 0, 0(4)
      xori 0, 0, 0x80           # set high bit of first char (key compare is case-insensitive!)
      stb 0, 112(1)
      addi 11, 1, 112
      li 9, 1
    2:
      lbzx 0, 4, 9
      cmpwi 0, 0
      beq 3f
      stbx 0, 11, 9
      addi 9, 9, 1
      cmpwi 9, 8
      blt 2b
    3:
      ori 4, 11, 0
    """ + call(inner) + f"""
      addi 1, 1, 128
      lis 12, {cont >> 16:#x}
      ori 12, 12, {cont & 0xffff:#x}
      mtctr 12
      bctr                      # resume wrapper epilogue (skips original bl)
      .p2align 2
    done:
    """
    
    # ---- S: Player::Save --------------------------------------------------------------
    HOOK_S = f"""
      lis 12, {STATE >> 16:#x}
      lbz 0, 0(12)
      cmpwi 0, 0
      bne pass                  # re-entry from our own P2 save
      lis 11, {hi(PLAYER_MGR):#x}
      lwz 11, {lo(PLAYER_MGR)}(11)
      cmpwi 11, 0
      beq pass
      lwz 0, 24(11)
      cmpw 3, 0
      beq p2
      lwz 0, 20(11)
      cmpw 3, 0
      bne pass
      # --- P1 is being saved: bring P2 into P1's store first
      lwz 0, 24(11)
      cmpwi 0, 0
      beq pass
    """ + FRAME_IN + f"""
      ori 31, 3, 0
      ori 30, 4, 0
      lwz 3, 24(11)
      lbz 0, 2(12)
      cmpwi 0, 0
      bne 5f
    """ + call(PLAYER_LOAD) + f"""
      ori 3, 31, 0
      lis 11, {hi(PLAYER_MGR):#x}
      lwz 11, {lo(PLAYER_MGR)}(11)
      lwz 3, 24(11)             # (re)load players[1] after the call
    5:
      li 4, 1
    """ + call(PLAYER_SAVE) + """
      ori 3, 31, 0
      ori 4, 30, 0
    """ + FRAME_OUT + """
      b pass
    p2:
      lbz 0, 2(12)
      cmpwi 0, 0
      beq ret                   # P2 in memory not known-good: never overwrite stored P2
    """ + p1sd(11, 'ret') + """
      lbz 0, 31(11)
      cmpwi 0, 0
      beq ret                   # P1 store not loaded
    """ + FRAME_IN + f"""
      ori 31, 3, 0
      li 0, 1
      stb 0, 0(12)              # inP2 = 1
      li 4, 1
    """ + call(PLAYER_SAVE) + f"""
      lis 12, {STATE >> 16:#x}
      li 0, 0
      stb 0, 0(12)              # inP2 = 0
      lis 3, {hi(PLAYER_MGR):#x}
      lwz 3, {lo(PLAYER_MGR)}(3)
      lwz 3, 20(3)
      lwz 3, 64(3)
    """ + call(REQ_SAVE) + FRAME_OUT + """
    ret:
      blr
    pass:
      stdu 1, -832(1)           # original
    done:
    """
    
    # ---- L: Player::Load --------------------------------------------------------------
    HOOK_L = f"""
      lis 12, {STATE >> 16:#x}
      lbz 0, 0(12)
      cmpwi 0, 0
      bne pass
      lis 11, {hi(PLAYER_MGR):#x}
      lwz 11, {lo(PLAYER_MGR)}(11)
      cmpwi 11, 0
      beq pass
      lwz 0, 24(11)
      cmpw 3, 0
      beq p2l
      # --- P1 is being loaded: run it, then (re)load P2 from the same store
      lwz 0, 20(11)
      cmpw 3, 0
      bne pass
      lbz 0, 3(12)
      cmpwi 0, 0
      bne pass                  # re-entry from ourselves
    """ + FRAME_IN + f"""
      li 0, 1
      stb 0, 3(12)              # inP1Load = 1
    """ + call(PLAYER_LOAD) + f"""
      lis 12, {STATE >> 16:#x}
      li 0, 0
      stb 0, 3(12)
      lis 11, {hi(PLAYER_MGR):#x}
      lwz 11, {lo(PLAYER_MGR)}(11)
      lwz 3, 24(11)
      cmpwi 3, 0
      beq 7f
    """ + call(PLAYER_LOAD) + """
    7:
    """ + FRAME_OUT + """
      blr
    p2l:
      li 0, 0
      stb 0, 2(12)              # p2valid = 0 until loaded
    """ + p1sd(11, 'ret') + """
      lbz 0, 31(11)
      cmpwi 0, 0
      beq ret
    """ + FRAME_IN + f"""
      ori 31, 3, 0
      ori 30, 11, 0
      li 0, 1
      stb 0, 0(12)              # inP2 = 1
      ori 3, 30, 0
      lis 4, {hi(FCEPTS_STR):#x}
      addi 4, 4, {lo(FCEPTS_STR)}
    """ + call(GET_INT) + """
      cmpwi 3, -1
      beq 6f                    # no P2 keys yet: P2 starts fresh
      li 0, 1
      stb 0, 68(31)             # skip Player::Load's "first call does nothing"
      ori 3, 31, 0
    """ + call(PLAYER_LOAD) + f"""
    6:
      lis 12, {STATE >> 16:#x}
      li 0, 0
      stb 0, 0(12)              # inP2 = 0
      li 0, 1
      stb 0, 2(12)              # p2valid = 1
    """ + FRAME_OUT + """
    ret:
      blr
    pass:
      stdu 1, -1056(1)          # original
    done:
    """
    
    # ---- W: wipe ----------------------------------------------------------------------
    HOOK_W = f"""
      lis 12, {STATE >> 16:#x}
      lbz 0, 1(12)
      cmpwi 0, 0
      bne pass
      lbz 0, 0(12)
      cmpwi 0, 0
      bne pass
      lis 11, {hi(PLAYER_MGR):#x}
      lwz 11, {lo(PLAYER_MGR)}(11)
      cmpwi 11, 0
      beq pass
      lwz 0, 24(11)
      cmpw 3, 0
      bne pass
    """ + FRAME_IN + f"""
      ori 31, 3, 0
      li 0, 1
      stb 0, 1(12)              # inWipe = 1
    """ + call(PLAYER_WIPE) + f"""
      lis 12, {STATE >> 16:#x}
      li 0, 0
      stb 0, 1(12)
      stb 0, 2(12)              # p2valid = 0
      ori 3, 31, 0
    """ + call(PLAYER_LOAD) + FRAME_OUT + """
      blr
    pass:
      stdu 1, -128(1)           # original
    done:
    """
    
    # ---- D / R: drop-out (r31 = players[1]) -------------------------------------------
    HOOK_D = """
      ori 3, 31, 0
      li 4, 1
    """ + call(PLAYER_SAVE) + """
      ori 3, 31, 0
    """ + call(DROP_206D70) + """
    done:
    """
    HOOK_R = """
      ori 3, 31, 0
    """ + call(PLAYER_LOAD) + """
    done:
    """
    
    K = B['kv']
    return [
        dict(addr=K[0][0], name='K1 GetInt', orig='lwz r3,8(r3)', asm=kv_hook(K[0][1], K[0][2])),
        dict(addr=K[1][0], name='K2 GetFloat', orig='lwz r3,8(r3)', asm=kv_hook(K[1][1], K[1][2])),
        dict(addr=K[2][0], name='K3 SetInt', orig='lwz r3,8(r3)', asm=kv_hook(K[2][1], K[2][2])),
        dict(addr=K[3][0], name='K4 SetFloat', orig='lwz r3,8(r3)', asm=kv_hook(K[3][1], K[3][2])),
        dict(addr=PLAYER_SAVE, name='S Player::Save', orig='stdu r1,-832(r1)', asm=HOOK_S),
        dict(addr=PLAYER_LOAD, name='L Player::Load', orig='stdu r1,-1056(r1)', asm=HOOK_L),
        dict(addr=PLAYER_WIPE, name='W wipe player', orig='stdu r1,-128(r1)', asm=HOOK_W),
        dict(addr=B['drop_save_site'], name='D save P2 before drop-out', orig=f'bl {DROP_206D70:#x}', asm=HOOK_D),
        dict(addr=B['drop_reload_site'], name='R reload P2 after drop-out', orig='nop', asm=HOOK_R),
    ]
    
def assemble(src):
    with tempfile.TemporaryDirectory() as t:
        s, o, b = (os.path.join(t, n) for n in ('a.s', 'a.o', 'a.bin'))
        open(s, 'w').write('.text\n' + src)
        subprocess.run(['llvm-mc', '-triple=powerpc64-unknown-linux-gnu', '-filetype=obj', s, '-o', o], check=True)
        subprocess.run(['llvm-objcopy', '-O', 'binary', '--only-section=.text', o, b], check=True)
        data = open(b, 'rb').read()
        dis = subprocess.run(['llvm-objdump', '-d', '--no-show-raw-insn', '--no-leading-addr', o],
                             capture_output=True, text=True, check=True).stdout
        rel = subprocess.run(['llvm-readelf', '-r', o], capture_output=True, text=True, check=True).stdout
    assert 'R_PPC64' not in rel, 'cave code must be position independent:\n' + rel
    assert len(data) % 4 == 0
    lines = [l.strip() for l in dis.splitlines() if l.startswith('\t') or l.startswith(' ')]
    words = [int.from_bytes(data[i:i + 4], 'big') for i in range(0, len(data), 4)]
    return words, lines

def render(key):
    B = BUILDS[key]
    hooks = make_hooks(B)
    y = [f'# RPCS3 patch: Star Wars The Clone Wars: Republic Heroes ({B["region"]}, {B["title_id"]}, APP_VER {B["app_ver"]})',
         '# Fixes co-op Player 2 losing points/upgrades/costumes. Generated by tools/build_patch.py - do not edit by hand.',
         'Version: 1.2', '', f'{B["hash"]}:', '  "Fix Player 2 progress not being saved":', '    Games:',
         '      "Star Wars The Clone Wars: Republic Heroes":', f'        {B["title_id"]}: [ "{B["app_ver"]}" ]',
         '    Author: "clone-wars-rh-coop-patch"', f'    Patch Version: {VERSION}',
         '    Notes: "Co-op Player 2 progress (points, upgrades, costumes) is stored inside SAVE.DAT next to Player 1 and restored after relaunch, quit-to-menu and drop-out/rejoin."',
         '    Patch:',
         f'      # state page (rwx): +0 inP2, +1 inWipe, +2 p2valid, +3 inP1Load   (offset%3==0 selects rwx)',
         f'      - [ alloc, 0x{STATE + 1:08x}, 0x10000 ]']
    for h in hooks:
        words, dis = assemble(h['asm'])
        y.append(f"      # {h['name']}  (replaces: {h['orig']})")
        y.append(f"      - [ calloc, 0x{h['addr'] | 2:08x}, {len(words)} ]")
        for i, w in enumerate(words):
            c = dis[i] if i < len(dis) else ''
            y.append(f"      - [ be32, 0x00000000, 0x{w:08x} ] # +0x{i*4:03x} {c}")
    return '\n'.join(y) + '\n'

def main():
    keys = sys.argv[1:] or list(BUILDS)
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'patches')
    for key in keys:
        B = BUILDS[key]
        out = os.path.normpath(os.path.join(root, B['region'], f'{B["title_id"]}_patch.yml'))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'w').write(render(key))
        print(f'{key}: wrote {out}')

if __name__ == '__main__':
    main()
