#!/usr/bin/env python3
"""Map addresses from the US build (BLUS30394) to another build of the same game.

Finds each US code address in the other decrypted ELF by a masked instruction signature
(branch offsets and 16-bit immediates ignored), then lists instruction pairs that differ in a
window so changed constants (globals, string addresses, call targets) can be read off.

usage: port_map.py US.elf OTHER.elf ADDR [ADDR...]        map code addresses
       port_map.py US.elf OTHER.elf --diff US_ADDR N      show differing words in N-instruction window
"""
import struct, sys

def va2off(v): return v - 0x10000 if v < 0xb30000 else v - 0xb30000 + 0xb20000
def w(d, o): return struct.unpack('>I', d[o:o + 4])[0]
def mask(x):
    op = x >> 26
    if op == 18: return x & 0xfc000003
    if op == 16: return x & 0xffff0003
    if op in (14, 15, 24, 25, 32, 34, 36, 38, 40, 44, 48, 50, 52, 54, 58, 62): return x & 0xffff0000
    return x
TEXT_END = 0xb1e260

def sig(d, o, n): return tuple(mask(w(d, o + 4 * i)) for i in range(n))

def find(a, b, va, idx):
    o = va2off(va)
    for back in range(0, 64, 4):
        s = o - back
        c = [x for x in idx.get(sig(a, s, 8), []) if sig(b, x, 32) == sig(a, s, 32)]
        if len(c) == 1: return c[0] + back + 0x10000
    return None

def main():
    a = open(sys.argv[1], 'rb').read(); b = open(sys.argv[2], 'rb').read()
    if sys.argv[3] == '--diff':
        ua = int(sys.argv[4], 16); n = int(sys.argv[5])
        idx = {}
        for o in range(0, TEXT_END - 64, 4): idx.setdefault(sig(b, o, 8), []).append(o)
        ea = find(a, b, ua, idx); print(f'US {ua:#x} -> {ea and hex(ea)}')
        for i in range(n):
            x, y = w(a, va2off(ua) + 4 * i), w(b, va2off(ea) + 4 * i)
            if x != y: print(f'  +{4*i:#05x} US {ua+4*i:#x} {x:08x}   OTHER {ea+4*i:#x} {y:08x}')
        return
    idx = {}
    for o in range(0, TEXT_END - 64, 4): idx.setdefault(sig(b, o, 8), []).append(o)
    for s in sys.argv[3:]:
        va = int(s, 16); r = find(a, b, va, idx)
        print(f'{va:#x} -> {r:#x} ({r - va:+#x})' if r else f'{va:#x} -> NOT FOUND')

if __name__ == '__main__': main()
