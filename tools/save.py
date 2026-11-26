#!/usr/bin/env python3
"""Republic Heroes (BLUS30394) SAVE.DAT tool.

Format (big-endian): u32 crc32(data[4:]), u32 version, u32 count,
count x {char key[8] (NUL padded), i32 value}, zero padded to 0x5004.

Player 2 entries written by the clone-wars-rh-coop-patch use the same key with the high bit of the
first character set (b"\xe6cepts" = P2's "fcepts"). `dump` shows them as "P2:fcepts".

usage:
  save.py dump  SAVE.DAT
  save.py players SAVE.DAT                          (P1 vs P2 points/unlocks side by side)
  save.py diff  A/SAVE.DAT B/SAVE.DAT
  save.py set   SAVE.DAT key=value [key=value...]   (rewrites in place + fixes CRC; adds missing keys)
"""
import struct, sys, zlib

SIZE = 0x5004

def load(path):
    d = open(path, 'rb').read()
    crc, ver, n = struct.unpack('>III', d[:12])
    ok = zlib.crc32(d[4:]) == crc
    ents = {}
    for i in range(n):
        o = 12 + i * 12
        k = d[o:o + 8].rstrip(b'\0').decode('latin1')
        ents[k] = struct.unpack('>i', d[o + 8:o + 12])[0]
    return ver, ents, ok

def build(ver, ents):
    body = struct.pack('>II', ver, len(ents))
    for k, v in ents.items():
        kb = k.encode('latin1')
        assert len(kb) <= 8, k
        body += kb.ljust(8, b'\0') + struct.pack('>i', v)
    body = body.ljust(SIZE - 4, b'\0')
    assert len(body) == SIZE - 4, 'too many keys'
    return struct.pack('>I', zlib.crc32(body)) + body

def show(k):
    return 'P2:' + chr(ord(k[0]) ^ 0x80) + k[1:] if k and ord(k[0]) >= 0x80 else k

def main():
    cmd = sys.argv[1]
    if cmd == 'dump':
        ver, e, ok = load(sys.argv[2])
        print(f'version={ver} keys={len(e)} crc_ok={ok}')
        for k, v in e.items():
            print(f'{show(k):12} {v:12}  0x{v & 0xffffffff:08x}')
    elif cmd == 'diff':
        _, a, oka = load(sys.argv[2]); _, b, okb = load(sys.argv[3])
        print(f'crc_ok A={oka} B={okb}')
        for k in list(dict.fromkeys(list(a) + list(b))):
            if a.get(k) != b.get(k):
                print(f'{show(k):12} {a.get(k)!s:>12} -> {b.get(k)!s:<12}')
    elif cmd == 'players':
        _, e, ok = load(sys.argv[2])
        p2 = {chr(ord(k[0]) ^ 0x80) + k[1:]: v for k, v in e.items() if k and ord(k[0]) >= 0x80}
        print(f'crc_ok={ok} entries={len(e)} (max {(SIZE - 12) // 12}) P2 entries={len(p2)}')
        if not p2: print('no Player 2 data (patch never saved P2)'); return
        print(f'{"key":10} {"P1":>12} {"P2":>12}')
        for k in ('fcepts', 'tfcepts', 'combat', 'costumes', 'cheats', 'dances', 'droids'):
            if k in p2: print(f'{k:10} {e.get(k)!s:>12} {p2[k]!s:>12}')
        print(f'({sum(1 for k in p2 if e.get(k) != p2[k])} of {len(p2)} per-player values differ; `dump` lists all)')
    elif cmd == 'set':
        ver, e, _ = load(sys.argv[2])
        for kv in sys.argv[3:]:
            k, v = kv.split('=', 1); e[k] = int(v, 0)
        open(sys.argv[2], 'wb').write(build(ver, e))
        print('written, crc fixed')
    else:
        print(__doc__)

if __name__ == '__main__':
    main()
