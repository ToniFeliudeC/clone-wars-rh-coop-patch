import ghidra.app.script.GhidraScript;
import ghidra.program.model.symbol.*;
import ghidra.program.model.listing.*;
public class Xrefs extends GhidraScript {
  public void run() throws Exception {
    for (String a : getScriptArgs()) {
      var ad = toAddr(Long.parseLong(a,16));
      for (Reference r : getReferencesTo(ad)) {
        Function f = getFunctionContaining(r.getFromAddress());
        println("XREF " + a + " <- " + r.getFromAddress() + " " + r.getReferenceType() + " in " + (f==null?"?":f.getName()+"@"+f.getEntryPoint()));
      }
    }
  }
}
