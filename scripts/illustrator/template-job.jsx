// template-job.jsx — 无头脚本任务模板（照着改就能用）
//
// 用法：
//   1) 复制本文件为你的任务脚本，改下面的"配置区"
//   2) 运行：
//      powershell -ExecutionPolicy Bypass -File run-ai-headless.ps1 `
//          -Jsx "D:\work\my-job.jsx" -Log "D:\work\_ailog.txt" -TimeoutSec 540
//      启动器会自动把脚本复制到 AI 所在盘（%SystemDrive%\ai\jobs\）再启动 —— 这一步是
//      "零弹窗"的关键：跨盘会触发模态 File not found 并阻塞 AI。
//   3) 只看日志判断成功：出现 done 即成功，出现 ERROR 即失败。
//
// 必守的四条规则（否则外部运行会踩坑）：
//   a) #targetengine "session"：让变量在多次调用之间保留
//   b) 所有路径用绝对路径：外部启动时 $.fileName 为空，arguments 也不会转发
//   c) 顶层 try/catch 写日志：既证明脚本真跑了，也能把错误落盘
//   d) 结尾 app.quit()：AI 正常退出，偏好才会落盘

#target illustrator
#targetengine "session"

// ====== 配置区（改这里）======
var SRC  = "D:/path/to/input.svg";        // 输入文件
var DST  = "D:/path/to/output.ai";        // 输出文件
var LOG  = "D:/path/to/_ailog.txt";       // 日志（必须与启动器 -Log 传的一致）
// =========================

// 自我加固：关闭"外部脚本运行"安全警告（官方做法）。
// 首次运行仍会弹一次（警告发生在脚本执行之前），跑过一次之后就不再弹。
try { app.preferences.setBooleanPreference("ShowExternalJSXWarning", false); } catch (e) {}

// 批处理期间不要弹交互框
app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;

var f = new File(LOG);
f.encoding = "UTF-8";
f.open("w");
function log(s) { try { f.writeln(s); f.flush(); } catch (e) {} }

try {
  log("started " + new Date().toString());

  // ---- 你的主逻辑 ----
  // 示例：打开一个文件并做点事
  // var doc = app.open(new File(SRC));
  // ... 处理 ...
  // doc.saveAs(new File(DST));

  log("done");
} catch (e) {
  log("ERROR: " + (e && e.message ? e.message : e));
  log((e && e.line) ? ("line " + e.line) : "");
}

try { f.close(); } catch (e) {}

// 正常退出，让偏好落盘
try { app.quit(); } catch (e) {}
