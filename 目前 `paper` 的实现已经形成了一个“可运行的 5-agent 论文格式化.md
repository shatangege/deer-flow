目前 `paper` 的实现已经形成了一个“可运行的 5-agent 论文格式化流水线”，但代码组织上还是偏“核心服务 + 角色封装”，还没完全演进成强解耦的 agent 内核。

**当前架构**
主入口是 [orchestrator.py](/d:/workspace2/deer-flow/custom_agents/paper/paper/core/orchestrator.py)。`PaperPipelineService` 串起 4 个业务 agent，加上底层的 `AsposeExecutionAgent`，形成这条链：

1. `TemplateRuleAgent`
   读取模板，提取 `outline + structure + style_profile`，产出 `RuleBundle`
2. `FlowSchedulerAgent`
   基于模板规则和源文结构切出 `SectionChunk`
3. `SectionProcessorAgent`
   对单章节执行内容整理、最小补全、样式套用、片段校验
4. `AggregationReviewAgent`
   汇总章节结果、按模板合并、终验并生成报告
5. `AsposeExecutionAgent`
   作为唯一文档执行边界，负责 Aspose runtime、抽取、渲染、合并、校验

对 Deer Flow 的接入也已经成型，5 个 built-in subagent 都注册在 [__init__.py](/d:/workspace2/deer-flow/backend/packages/harness/deerflow/subagents/builtins/__init__.py)：
- `paper-template-rules`
- `paper-flow-scheduler`
- `paper-section-processor`
- `paper-aspose-executor`
- `paper-aggregation-review`

**当前流程**
从实现看，主流程是：

- 模板规则抽取：模板 outline、结构、样式快照
- 源文分片：按模板章节覆盖生成 `SectionChunk`
- 章节处理：每个 chunk 先重写内容，再应用样式，再局部校验
- 模板骨架合并：不是简单 append，而是按模板 section 回填
- 全局终验：检查缺失章节、样式/布局/分页风险

当前 `paper` 已经有两层 MCP：
- 高层 workflow 工具
- 低层 Aspose 工具

这一点和最初方案是对齐的。

**目前的优点**
- 模板优先这条主线是成立的，尤其是大纲约束已经比较稳
- Aspose 边界清晰，业务层没有直接散落操作 Word 对象
- 分片后合并已经不是最早那种“硬拼接”，分页控制开始纳入设计
- `front matter`、`table`、`reference` 已经开始有独立样式入口，而不只是正文 fallback

**目前的主要短板**
1. 角色分层还不够彻底  
5-agent 语义有了，但大量核心实现还集中在 [execution.py](/d:/workspace2/deer-flow/custom_agents/paper/paper/core/execution.py)。这会让后续增强 front matter、表格、分页时持续膨胀。

2. 模板样式抽取刚进入“快照化”，但还不够完整  
现在已经比只看 `style_name` 强很多，但还没到“模板块级样式槽位 + 完整视觉快照 + 稳定命中”的程度。

3. `SectionProcessorAgent` 仍偏章节级通用处理器  
前置页和复杂表格其实已经接近“特殊对象渲染器”的范畴，继续全塞进通用 section 流程会让规则越来越脆。

4. 终验还偏结果检查，不够“诊断式”  
已经有分页、空白、section break 风险，但还不够细到“哪一类标题、哪一类表格、哪一段 front matter 没贴模板”。

**优化建议**
1. 把 `execution.py` 继续拆薄  
建议把它收敛成编排壳，真正拆出：
- `style_snapshot.py`
- `front_matter_renderer.py`
- `table_renderer.py`
- `section_styler.py`
- `merge_flow.py`

2. 建立“模板槽位模型”  
现在最值得补的是模板语义槽位，而不是继续加 if/else。至少把这些槽位稳定下来：
- `front_matter.*`
- `section.heading.level*`
- `section.body.*`
- `table.caption/header/body`
- `reference.item`

3. 前置页单独建渲染链  
不要再把 front matter 只当普通 paragraph 列表处理。建议独立成“模板骨架 + 槽位替换”的 renderer。

4. 表格做成四层渲染  
建议显式分成：
- table container
- row
- cell
- cell content  
这样才能稳定对齐列宽、表头、表中字体、单元格段落和分页行为。

5. 合并后增加“二次版面整理”  
现在 merge 已经改进了，但还应再补一个专门的后处理阶段，集中修：
- section break 清理
- 标题 keep 规则
- caption-table 粘连
- terminal paragraph 去重
- 表格分页异常

6. 终验升级成“差异报告”  
建议把报告进一步结构化成：
- `heading_style_mismatches`
- `body_paragraph_mismatches`
- `front_matter_mismatches`
- `table_mismatches`
- `pagination_mismatches`

**一句话判断**
现在的 `paper` 已经不是 demo 了，属于“主链路可用、架构方向正确、正在从通用 formatter 向模板驱动论文排版引擎演进”的状态。下一阶段最关键的不是再加更多散点修复，而是把“模板槽位 + 样式快照 + 特殊对象渲染器”这三层彻底立起来。

如果你愿意，我下一步可以把这些优化建议整理成一份“v2 架构收敛方案”，直接细化到模块边界、数据结构和实施顺序。