import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
public class DeadFuncs extends GhidraScript {
  public void run() throws Exception {
    for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
      long sz = f.getBody().getNumAddresses();
      if (sz < 96) continue;
      var refs = getReferencesTo(f.getEntryPoint());
      if (refs.length == 0) println("DEAD " + f.getEntryPoint() + " size=" + sz + " " + f.getName());
    }
  }
}
