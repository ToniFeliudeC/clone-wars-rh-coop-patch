#!/usr/bin/env python3
"""Inspect the running game inside RPCS3 (Linux): patch state, players, save stores.

Reads guest memory through /proc/<pid>/mem. Needs ptrace access to the RPCS3 process:
    sudo sysctl kernel.yama.ptrace_scope=0     (and back to 1 when done)

RPCS3 maps PS3 memory as a memfd; the writable view starts where the memfd's file offset 0x10000
(guest 0x10000) is mapped. The base is found automatically from /proc/<pid>/maps.

usage: live.py [--pid PID] [--build us|eu] state      patch flags, players, users, SaveData flags
       live.py [--pid PID] [--build us|eu] kv         P1/P2 key counts and headline values in memory
"""
import argparse, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from builds import BUILDS

STATE = 0x0FFE0000

def find_pid():
    best = None
    for p in os.listdir('/proc'):
        if not p.isdigit(): continue
        try:
            comm = open(f'/proc/{p}/comm').read().strip()
            if 'rpcs3' not in comm.lower() and comm != 'AppRun.wrapped': continue
            rss = int(open(f'/proc/{p}/statm').read().split()[1])
        except OSError: continue
        if not best or rss > best[1]: best = (int(p), rss)
    return best and best[0]

def find_base(pid):
    for l in open(f'/proc/{pid}/maps'):
        m = l.split()
        if len(m) >= 6 and 'memfd' in l and m[2] == '00000000' and 'w' in m[1]:
            start = int(m[0].split('-')[0], 16)
            if start & 0xffff == 0x10000 or start & 0xffffffff == 0x10000: return start - 0x10000
    # fallback: first rw memfd mapping starting at guest 0x10000
    for l in open(f'/proc/{pid}/maps'):
        m = l.split()
        if 'memfd' in l and 'w' in m[1] and m[0].split('-')[0].endswith('10000'):
            return int(m[0].split('-')[0], 16) - 0x10000
    sys.exit('guest memory mapping not found')

class Mem:
    def __init__(s, pid, base): s.f = open(f'/proc/{pid}/mem', 'rb', 0); s.base = base
    def rd(s, a, n): s.f.seek(s.base + a); return s.f.read(n)
    def u32(s, a): return struct.unpack('>I', s.rd(a, 4))[0]
    def s32(s, a): return struct.unpack('>i', s.rd(a, 4))[0]
    def u8(s, a): return s.rd(a, 1)[0]

def kv_entries(m, sd):
    kv = m.u32(sd + 8); hdr, dat, psz, pc = (m.u32(kv + 4 * i) for i in range(4)); e = {}
    for i in range(pc):
        n = m.u32(m.u32(hdr + 4 * i) + 4); d = m.u32(dat + 4 * i)
        for j in range(n):
            r = m.rd(d + 12 * j, 12); e[r[:8].rstrip(b'\0').decode('latin1')] = struct.unpack('>i', r[8:])[0]
    return e

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--pid', type=int); ap.add_argument('--build', default='us')
    ap.add_argument('cmd', choices=['state', 'kv']); a = ap.parse_args()
    B = BUILDS[a.build]; pid = a.pid or find_pid()
    if not pid: sys.exit('RPCS3 process not found')
    try: m = Mem(pid, find_base(pid)); m.rd(0x10000, 4)
    except PermissionError: sys.exit('permission denied: run  sudo sysctl kernel.yama.ptrace_scope=0')
    mgr = m.u32(B['player_mgr'])
    if a.cmd == 'state':
        st = m.rd(STATE, 4)
        print(f'pid {pid} base {m.base:#x}  patch state: inP2={st[0]} inWipe={st[1]} p2valid={st[2]} inP1Load={st[3]}')
        for i in range(2):
            p = m.u32(mgr + 0x14 + 4 * i); u = m.u32(p + 0x40); sd = m.u32(u + 0x20)
            print(f'player{i} {p:#x}: user {u:#x} slot {m.s32(u)} state {m.u32(u + 0x10)} noIO {m.u8(u + 0x18)} | '
                  f'SaveData {sd:#x} state {m.u32(sd + 0x18)} loadedOK {m.u8(sd + 0x1f)} saveEnabled {m.u8(sd + 0x21)} | '
                  f'points {m.s32(m.u32(p + 0x28) + 0x844)}')
    else:
        p1sd = m.u32(m.u32(m.u32(mgr + 0x14) + 0x40) + 0x20); e = kv_entries(m, p1sd)
        p2 = {chr(ord(k[0]) ^ 0x80) + k[1:]: v for k, v in e.items() if k and ord(k[0]) >= 0x80}
        print(f'P1 store: {len(e)} entries ({len(p2)} are P2)')
        for k in ('fcepts', 'tfcepts', 'combat', 'costumes'): print(f'  {k:9} P1 {e.get(k)!s:>10}   P2 {p2.get(k)!s:>10}')

if __name__ == '__main__': main()
