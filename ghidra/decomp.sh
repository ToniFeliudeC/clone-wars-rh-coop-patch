#!/bin/bash
# usage: ghidra/decomp.sh ADDR... -> ghidra/out/<addr>.c   (US build; uses the analyzed project, no re-analysis)
# needs GHIDRA_HOME (default ~/tools/ghidra_12.2_PUBLIC) and a project created by ghidra/import.sh
H=$(cd "$(dirname "$0")" && pwd); G=${GHIDRA_HOME:-$HOME/tools/ghidra_12.2_PUBLIC}
mkdir -p "$H/out"
"$G/support/analyzeHeadless" "$H" proj -process EBOOT.elf -noanalysis -readOnly -scriptPath "$H/scripts" -postScript Decomp.java "$H/out" "$@" > "$H/last.log" 2>&1
grep -E 'nofunc|ERROR' "$H/last.log"
