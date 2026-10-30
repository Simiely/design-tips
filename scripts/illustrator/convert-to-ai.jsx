// convert-to-ai.jsx — Illustrator 2026 无头转换：分层 SVG → 带图层 .ai
// 用法：先改下方配置区，然后运行 run-ai-headless.ps1（推荐）
//       powershell -ExecutionPolicy Bypass -File run-ai-headless.ps1 -Jsx <本文件> -Log <日志路径>
//       裸调 "Illustrator.exe -r 本文件" 也行，但旧实例未完全退出时会弹一次
//       "File not found"（路径丢盘符）——多数情况脚本仍会执行，判据看日志是否出现 done；
//       若进程在、日志不生成，说明旧实例占位导致脚本没跑，必须结束旧实例重启。
// 配套文档：docs/illustrator/svg还原分层AI.md（含「常见故障」章节）

#target illustrator
// ====== 配置 ======
var SRC   = "D:/path/to/xxx.layered.svg";   // build_layered_svg.py 的输出
var DST   = "D:/path/to/xxx.ai";            // 输出 .ai
var PNG   = "D:/path/to/preview.png";       // 50% 缩放核验图；不需要就置 null
var LOG   = "D:/path/to/_ailog.txt";        // 运行日志（外层轮询它判断完成）
// 图层名按堆叠顺序：数组第一个 = 最底层（背景），最后一个 = 最顶层
// 必须与分层 SVG 里顶层 <g id="..."> 的 id 一一对应
var LAYERS = ["背景","顶部状态栏","左侧信息面板","地图区域","底部导航栏"];
// =================

var f = new File(LOG);
f.encoding = "UTF-8";
f.open("w");
function log(s){ try{ f.writeln(s); f.flush(); }catch(e){} }
try {
  app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
  var doc = app.open(new File(SRC));
  log("opened: " + doc.name);

  // 建图层：layers.add() 插入到最前 → 按数组顺序创建后，第一个在最后（最底）
  var layerByName = {};
  for (var i=0;i<LAYERS.length;i++){
    var ly = doc.layers.add();
    ly.name = LAYERS[i];
    layerByName[LAYERS[i]] = ly;
  }
  log("layers created: " + doc.layers.length);

  // 关键：按【组名】配对，只遍历各 layer 的顶层 pageItems
  // （doc.groupItems 含嵌套组且顺序≠文档顺序，用索引配对必错）
  var moved = 0;
  var allLayers = [];
  for (var li=0; li<doc.layers.length; li++) allLayers.push(doc.layers[li]);
  for (var s=0; s<allLayers.length; s++){
    var srcLayer = allLayers[s];
    if (layerByName[srcLayer.name]) continue; // 跳过新建的空图层
    for (var p=srcLayer.pageItems.length-1; p>=0; p--){
      var it = srcLayer.pageItems[p];
      if (it.typename === "GroupItem" && layerByName[it.name]) {
        it.move(layerByName[it.name], ElementPlacement.PLACEATEND);
        log("moved '" + it.name + "'");
        moved++;
      } else {
        log("left: " + it.typename + " '" + it.name + "'");
      }
    }
  }
  log("moved: " + moved);

  // 删空壳图层
  var ls = doc.layers;
  for (var j=ls.length-1; j>=0; j--){
    if (ls[j].pageItems.length === 0){ var n=ls[j].name; ls[j].remove(); log("removed empty: "+n); }
  }
  log("final layers: " + doc.layers.length);

  // 存原生 .ai
  var opts = new IllustratorSaveOptions();
  doc.saveAs(new File(DST), opts);
  log("saved: " + DST);

  // 导出 50% PNG24 核验图（注意：导出图带出血，像素比对前先对齐裁剪）
  if (PNG){
    var ex = new ExportOptionsPNG24();
    ex.horizontalScale = 50; ex.verticalScale = 50;
    ex.transparency = true; ex.antiAliasing = true;
    doc.exportFile(new File(PNG), ExportType.PNG24, ex);
    log("exported png");
  }

  doc.close(SaveOptions.DONOTSAVECHANGES);
  log("done");
  app.quit();
} catch(e){
  log("ERROR: " + (e && e.message ? e.message : e));
  try{ app.quit(); }catch(_){}
}
try{ f.close(); }catch(e){}
