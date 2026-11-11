// verify-layers.jsx — 打开 .ai，dump 图层结构与元素 bounds（UTF-8 日志）
// 用法：改 DST/LOG 后 "Illustrator.exe -r verify-layers.jsx"
// 用于人工核对：图层配对是否正确、元素是否泄漏/丢失、bounds 是否符合预期；
// 末尾输出画布收边核验（每层 clipped 组 + 裁剪矩形尺寸，应=画板尺寸）。

// 外部启动时 $.fileName 为空 → 路径一律绝对；位置参数不转发 → 改用顶部配置区。

#target illustrator
#targetengine "session"

// 自我加固：关闭"外部脚本运行"安全警告（官方做法）。详见 convert-to-ai.jsx 注释。
try { app.preferences.setBooleanPreference("ShowExternalJSXWarning", false); } catch (e) {}
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
    var cp = ""; try { if (it.typename === "GroupItem") cp = " clipped=" + it.clipped; } catch(e){}
    var bm = ""; try { bm = " blend=" + it.blendingMode; } catch(e){}   // 混合模式核验（soft-light 等）
    log(ind + it.typename + " name='" + nm + "'" + cp + bm + " bounds=" + b);
    if (it.typename === "GroupItem") {
      for (var i=it.pageItems.length-1; i>=0; i--) dumpItem(it.pageItems[i], ind + "  ");
    }
  }
  for (var li=0; li<doc.layers.length; li++){
    var ly = doc.layers[li];
    log("LAYER["+li+"] '" + ly.name + "' visible=" + ly.visible + " pageItems=" + ly.pageItems.length);
    for (var pi=ly.pageItems.length-1; pi>=0; pi--) dumpItem(ly.pageItems[pi], "  ");
  }

  // 画布收边核验：列出每个已 clipped 的组及其裁剪路径尺寸。
  // 流水线约定（convert-to-ai.jsx 的 CANVAS_CLIP）：每个命名层一个 "canvas-clip" 组，
  // 裁剪路径为画板矩形 → clipRect 应等于画板尺寸（w/h 与 artboardRect 一致）。
  log("--- clip verification ---");
  for (var li2=0; li2<doc.layers.length; li2++){
    var ly2 = doc.layers[li2];
    for (var gi=0; gi<ly2.groupItems.length; gi++){
      var grp = ly2.groupItems[gi];
      if (!grp.clipped) continue;
      var cb = null;
      for (var p=0; p<grp.pathItems.length; p++){ if (grp.pathItems[p].clipping) cb = grp.pathItems[p]; }
      if (cb){
        var b = cb.geometricBounds; // [left, top, right, bottom]，y 向上
        log("CLIP layer '" + ly2.name + "' group='" + grp.name +
            "' clipRect=[" + b.join(",") + "] w=" + (b[2]-b[0]) + " h=" + (b[1]-b[3]));
      } else {
        log("CLIP layer '" + ly2.name + "' group='" + grp.name + "' clipped but NO clipping path");
      }
    }
  }
  doc.close(SaveOptions.DONOTSAVECHANGES);
  log("done");
  app.quit();
} catch(e){
  log("ERROR: " + (e && e.message ? e.message : e));
  try{ app.quit(); }catch(_){}
}
try{ f.close(); }catch(e){}
