#!/usr/bin/env python3
"""Resolve lis/addi (and lis/ori, lis/ld-off) address constructions in llvm-objdump PPC output.
usage: lisaddi.py eboot.asm eboot.elf LO HI   -> prints code_addr target string"""
import re,sys
asm,elf,lo,hi=sys.argv[1],sys.argv[2],int(sys.argv[3],16),int(sys.argv[4],16)
d=open(elf,'rb').read()
def va2off(v): return v-0x10000 if v<0xb30000 else v-0xb30000+0xb20000
def cstr(v):
    o=va2off(v); e=d.find(b'\0',o,o+64); s=d[o:e]
    return s.decode('latin1') if e>o and all(32<=c<127 for c in s) else ''
ln=re.compile(r'^\s*([0-9a-f]+):\s+(\S+)\s*(.*)$')
hiregs={}  # reg -> (value, addr)
for line in open(asm):
    m=ln.match(line)
    if not m: continue
    a=int(m.group(1),16); op=m.group(2); args=[x.strip() for x in m.group(3).split(',')]
    if op=='lis' and len(args)==2:
        try: hiregs[args[0]]=(int(args[1],0)<<16)&0xffffffff, a
        except: pass
        continue
    if op in('addi','ori','lwz','ld','lbz','lhz','stw','lfs','std','addic') and len(args)>=2:
        if op in('addi','ori','addic') and len(args)==3 and args[1] in hiregs:
            base,la=hiregs[args[1]]
            if a-la<0x200:
                imm=int(args[2],0); v=(base+imm)&0xffffffff if op!='ori' else base|imm
                if lo<=v<hi: print(hex(a),hex(v),cstr(v))
        else:
            mm=re.match(r'(-?\d+)\((\d+)\)',args[-1]) if args else None
            if mm and mm.group(2) in hiregs:
                base,la=hiregs[mm.group(2)]
                v=(base+int(mm.group(1)))&0xffffffff
                if a-la<0x200 and lo<=v<hi: print(hex(a),hex(v),'['+op+']',cstr(v))
    if args and op not in('stw','std','cmpwi','cmpw','cmplwi','b','bl','blr','beq','bne') and args[0] in hiregs and op!='lis':
        pass
    if op in('bl','blr','b','bctrl'): pass
