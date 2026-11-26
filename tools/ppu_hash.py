#!/usr/bin/env python3
"""Compute RPCS3's PPU executable hash ("PPU-<sha1>") for a decrypted EBOOT.elf.
Mirrors ppu_load_exec(): for each program header hash be32 p_type, be32 p_flags and,
for non-empty LOAD segments, be64 p_vaddr, be64 p_memsz and the file bytes.
usage: ppu_hash.py EBOOT.elf"""
import hashlib, struct, sys
d = open(sys.argv[1], 'rb').read()
phoff, = struct.unpack('>Q', d[0x20:0x28]); phentsize, phnum = struct.unpack('>HH', d[0x36:0x3a])
h = hashlib.sha1()
for i in range(phnum):
    o = phoff + i * phentsize
    p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz = struct.unpack('>IIQQQQQ', d[o:o + 48])
    h.update(struct.pack('>II', p_type, p_flags))
    if p_type == 1 and p_memsz:
        h.update(struct.pack('>QQ', p_vaddr, p_memsz)); h.update(d[p_offset:p_offset + p_filesz])
print('PPU-' + h.hexdigest())
