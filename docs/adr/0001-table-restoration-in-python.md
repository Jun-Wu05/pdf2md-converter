# ADR-0001:表格还原放在 Python 后处理层,不改 Rust 内核

- 状态:Accepted
- 日期:2026-08-05

## 背景

目标是用 pdf-inspector 把安全厂商的 PDF 手册完整转成 Markdown。在 R4.15.1 样本上跑通后,正文/标题/列表都正常,但无线框中文字段表(§5.3、§4.2)出现单元格错位、表头重复拆段、跨页续表被截断。

pdf-inspector 的表格检测有三套策略(rect → line → heuristic),都依赖 PDF 绘制操作或文本对齐线索;对「无线框 + 中文 + 多行合一」的语义表,Rust 侧的 `detect_heuristic` / `grid` 命中率不稳。要在这里改,得动 `src/tables/` 和 `src/extractor/layout.rs`,涉及 267+ 单测和 pdf-evals 语义评分回归,迭代周期长。

## 决策

**不改 pdf-inspector 的 Rust 源码。** 把它当成稳定的「文本+坐标+字体」提取器,表格还原的逻辑放到 Python 后处理层:

1. 调 pdf-inspector 的结构化输出(带 X/Y/字体 的 TextItems),不依赖已拍平的 Markdown。
2. 在 Python 里做表格再检测:按行聚类、列对齐推断、跨页续表合并、表头去重。
3. 对实在保不住结构的表,按 CONTEXT.md 的「降级表示」兜底,保证文本零丢失。

## 备选

- **A. 直接改 Rust 内核** —— 语义评分最准,但回归面大、迭代慢、需要 Rust 工具链(本机当前未装 cargo)。否决。
- **C. 混合:Rust 加一个 heuristic 钩子,Python 兜底** —— 边界模糊,两处都改容易扯皮。暂不取。

## 后果

- 优点:迭代在 conda 环境 `pdf-inspector` 内完成,改一行跑一次;Rust 内核升级时只需重装 wheel,无 merge 冲突。
- 代价:跨语言多一次序列化;部分能力(如 rect/line 检测结果)需从 Rust 结构化输出里取,若 Rust 未暴露则要绕路。
- 风险:若后处理依赖的坐标字段在 Rust 侧未导出,可能被迫回到方案 A;需先确认结构化输出的字段完备性(见下一个拷问问题)。
