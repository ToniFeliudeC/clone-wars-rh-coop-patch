#!/bin/bash
# One-time: import + auto-analyze the decrypted US executable into ghidra/proj (takes a while).
# usage: ghidra/import.sh [path/to/EBOOT.elf]   (default re/us/EBOOT.elf)
H=$(cd "$(dirname "$0")" && pwd); G=${GHIDRA_HOME:-$HOME/tools/ghidra_12.2_PUBLIC}
ELF=${1:-$H/../re/us/EBOOT.elf}
"$G/support/analyzeHeadless" "$H" proj -import "$ELF" -processor "PowerPC:BE:64:A2ALT-32addr" -overwrite > "$H/import.log" 2>&1
tail -3 "$H/import.log"
