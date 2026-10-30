// suppress-external-warning.jsx — 一次性关闭 Illustrator 的"外部脚本运行"安全警告
//
// 官方做法（Adobe 帮助中心 "Install and run scripts" / Adobe 官方员工在 UserVoice 的回复）：
//   运行下面这行 JSX 即可让后续所有外部脚本调用不再弹确认框：
//       app.preferences.setBooleanPreference("ShowExternalJSXWarning", false)
//
// 用法（一次性，共 1 次手动点击）：
//   Illustrator → 文件 > 脚本 > 其他脚本… → 选择本文件 → 运行
// 之后用 Illustrator.exe -r 或 COM DoJavaScriptFile 调用脚本，都不会再弹该警告。
//
// 注意：这个偏好是 Illustrator 的全局设置，作用范围是"任何外部程序触发的脚本执行"。

#target illustrator
#targetengine "session"

try {
  app.preferences.setBooleanPreference("ShowExternalJSXWarning", false);
  var f = new File("~/Documents/Adobe/Scripts/_suppress_external_warning.done");
  var d = f.parent;
  if (!d.exists) d.create();
  f.open("w");
  f.write("ShowExternalJSXWarning=false at " + new Date().toString() + "\n");
  f.close();
} catch (e) {
  // 写标记文件失败不影响偏好本身生效
}
