// verify-layers.jsx — 打开 .ai，dump 图层结构与元素 bounds（UTF-8 日志）
// 用法：改 DST/LOG 后 "Illustrator.exe -r verify-layers.jsx"
// 用于人工核对：图层配对是否正确、元素是否泄漏/丢失、bounds 是否符合预期。

#target illustrator
// ====== 配置 ======
var DST = "D:/path/to/xxx.ai";
var LOG = "D:/path/to/_verify.txt";
// =================

var f = new File(LOG);
f.encoding = "UTF-8";
f.open("w");
function log(s){ try{ f.writeln(s); f.flush(); }catch(e){} }
try {
  app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
  var doc = app.open(new File(DST));
  log("doc: " + doc.name + " artboards: " + doc.artboards.length);
  var ab = doc.artboards[0].artboardRect;
  log("artboard rect: " + ab);

  function dumpItem(it, ind){
    var b; try { b = it.visibleBounds; } catch(e){ b = "?"; }
    var nm = ""; try { nm = it.name; } catch(e){}
    log(ind + it.typename + " name='" + nm + "' bounds=" + b);
    if (it.typename === "GroupItem") {
      for (var i=it.pageItems.length-1; i>=0; i--) dumpItem(it.pageItems[i], ind + "  ");
    }
  }
  for (var li=0; li<doc.layers.length; li++){
    var ly = doc.layers[li];
    log("LAYER["+li+"] '" + ly.name + "' visible=" + ly.visible + " pageItems=" + ly.pageItems.length);
    for (var pi=ly.pageItems.length-1; pi>=0; pi--) dumpItem(ly.pageItems[pi], "  ");
  }
  doc.close(SaveOptions.DONOTSAVECHANGES);
  log("done");
  app.quit();
} catch(e){
  log("ERROR: " + (e && e.message ? e.message : e));
  try{ app.quit(); }catch(_){}
}
try{ f.close(); }catch(e){}
