# Issue 跟踪器：GitHub Issues

本仓库的 PRD 与实现 issue 以 **GitHub Issues** 形式存在于追踪仓库：

- **追踪仓库**：`Jun-Wu05/pdf2md-converter`（仅作 issue 看板，不含本项目代码）
- PRD 作为父 issue 发布并打 `prd` 标签；实现 issue 在「父 Issue」字段引用父 PRD issue 编号
- 分拣状态用标签：`needs-triage` / `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix`
- 类别标签：`bug` / `enhancement` / `design-input`（每个 issue 恰好 1 类别 + 1 状态）
- 评论与 Agent 简报追加到 issue 评论

## 当 skill 说「发布到 issue 跟踪器」

用 `gh issue create -R Jun-Wu05/pdf2md-converter --body-file <file> -l <labels>` 发布。

## 当 skill 说「获取相关工单」

用 `gh issue view <n> -R Jun-Wu05/pdf2md-converter` 读取。
