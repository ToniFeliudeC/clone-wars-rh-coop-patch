// Decompile functions at given hex addresses (args: outdir addr1 addr2 ...) into outdir/<addr>.c
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import java.io.*;
public class Decomp extends GhidraScript {
  public void run() throws Exception {
    String[] a = getScriptArgs();
    File out = new File(a[0]); out.mkdirs();
    DecompInterface di = new DecompInterface(); di.openProgram(currentProgram);
    for (int i = 1; i < a.length; i++) {
      Address ad = toAddr(Long.parseLong(a[i].replace("0x",""),16));
      Function f = getFunctionContaining(ad);
      if (f == null) { f = createFunction(ad, null); }
      if (f == null) { println("nofunc " + a[i]); continue; }
      DecompileResults r = di.decompileFunction(f, 120, monitor);
      try (PrintWriter w = new PrintWriter(new File(out, a[i] + ".c"))) {
        w.println("// " + f.getName() + " @ " + f.getEntryPoint());
        w.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : ("FAILED " + r.getErrorMessage()));
      }
    }
  }
}
