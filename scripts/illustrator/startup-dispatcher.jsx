// startup-dispatcher.jsx — Illustrator 启动脚本派发器（零弹窗自动化的关键）
//
// 作用：放在 Illustrator 安装目录的 "Startup Scripts" 文件夹里，AI 每次启动会自动执行它。
//       它只做一件事：检查有没有排队中的任务文件，有就执行，没有就什么都不做。
//       因为启动时 AI 根本不接收任何命令行参数，所以彻底不会出现 "File not found" 弹窗。
//
// 官方依据：Adobe Illustrator Scripting Guide「Startup scripts (.jsx scripts only)」——
//   应用级目录：C:\Program Files\Adobe\Adobe Illustrator <版本>\Startup Scripts\
//   通用级目录：C:\Program Files\Common Files\Adobe\Startup Scripts CC\Illustrator\
//   .jsx 放进去会在「应用启动时」和「从脚本菜单运行任意脚本时」自动执行。
//
// 任务约定：
//   任务文件：%USERPROFILE%\Documents\Adobe\Scripts\_ai_job.jsx
//   完成标记：%USERPROFILE%\Documents\Adobe\Scripts\_ai_job.done
//   派发日志：%USERPROFILE%\Documents\Adobe\Scripts\_ai_dispatch.log
//   （用 Documents\Adobe\Scripts 是因为它是 Adobe 的受信任目录，脚本执行不再触发安全警告）
//
// 幂等：启动脚本有可能被执行不止一次（社区实测 macOS 上启动时会跑两次），
//       因此用 .done 标记做去重，任务方在排队前先清掉标记。

#target illustrator
#targetengine "session"

(function () {
  var JOB  = new File("~/Documents/Adobe/Scripts/_ai_job.jsx");
  var MARK = new File("~/Documents/Adobe/Scripts/_ai_job.done");
  var LOG  = new File("~/Documents/Adobe/Scripts/_ai_dispatch.log");

  function say(s) {
    try { LOG.open("a"); LOG.writeln(new Date().toString() + "  " + s); LOG.close(); } catch (e) {}
  }

  try {
    if (!JOB.exists) { say("no job queued - skip"); return; }
    if (MARK.exists) { say("job already processed - skip (idempotent guard)"); return; }

    var m = MARK.open("w"); m.write("processing " + new Date().toString()); m.close();
    say("dispatching: " + JOB.fsName);
    $.evalFile(JOB);
    say("job finished");
  } catch (e) {
    say("ERROR: " + (e && e.message ? e.message : e));
  }
})();
