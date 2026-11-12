# AGENTS.md · design-tips 项目规则

> 📌 **文档基线**：2026-11-12（`4ead659`）完成 knowledge 契约迁移
> **更新文档/代码后，请更新此行**（日期 + 新 commit hash），并在 CHANGELOG 追加版本

本仓库整理**平面设计软件**实战技巧，按软件分区 `docs/<软件>/`，脚本在 `scripts/<软件>/`。
只收录**实际用过并验证过**的做法。回答相关问题前先按路由读对应页。

## 软件路由

- Figma → `docs/figma/`（细则 `rules/figma.md`）
- Illustrator → `docs/illustrator/` + `scripts/illustrator/`（细则 `rules/illustrator.md`）
- 跨软件通用 → `docs/common/`（目前无内容，出现再建）

## 核心约束

1. 只收真实环境验证过的内容；未验证的写「暂未验证」或不入库。
2. 新增/修改条目按 `DEVELOPMENT.md`「目录架构」的同步规则执行，本文件不重复细则。
3. 同一命令、报错表、坑清单只允许一处权威位置；别处链接，不复制。
4. `docs/_generated/` 与 `llms.txt` 由生成器产出，不要手改；frontmatter 是闭集，不自造字段。
5. 改脚本或改文档时更新对应页 `last_reviewed`，并在 `CHANGELOG.md` 追加版本。

## 常用命令

```bash
python tools/repo-kit/check_repo.py --root .
python tools/repo-kit/generate.py --root . --check
pwsh tools/update-repo-kit.ps1 -Check
```

## 详细规则（按需读取）

- @rules/figma.md
- @rules/illustrator.md

## 当前规模

- 页面：7（critical=0）
- 按 type：how-to=5, reference=2
- 词表版本：2.3.2

## 边界

机器只保结构、链接、真源与新鲜度；语义正确性靠人审。不要把本文件写成第二本规范。
