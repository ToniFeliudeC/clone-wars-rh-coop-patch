#!/bin/bash
# usage: ghidra/xrefs.sh ADDR...   -> prints references to each address (US build)
H=$(cd "$(dirname "$0")" && pwd); G=${GHIDRA_HOME:-$HOME/tools/ghidra_12.2_PUBLIC}
"$G/support/analyzeHeadless" "$H" proj -process EBOOT.elf -noanalysis -readOnly -scriptPath "$H/scripts" -postScript Xrefs.java "$@" 2>&1 | grep -o 'XREF.*'
