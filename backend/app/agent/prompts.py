from uuid import UUID


_DOCUMENT_WRITE_RULES = (
    "正文写入规则：\n"
    "- 不要把长正文只放在对话回复里；必须通过工具持久化到工作台。\n"
    "- 创建新章节并写入完整正文：调用 create_chapter_with_content。\n"
    "- 替换当前文档全部正文：调用 propose_document_update(document_id, content)。\n"
    "- 替换选中段落：调用 propose_selection_replace 或 propose_rewrite。\n"
    "- 只有工具成功返回后，才能告诉用户已写入或已生成待确认方案。"
)

_MATERIAL_MANAGEMENT_RULES = (
    "素材管理规则：\n"
    "- 创建、更新、删除创作资产、时间线、角色状态、人物关系时，直接调用相应工具，无需用户确认。\n"
    "- 修改或删除前先调用 list_* 获取目标 id，不要猜测 id。\n"
    "- 可用 list_material_changes 查看最近的素材变更记录。"
)


def append_agent_runtime_guidance(
    system_prompt: str,
    *,
    novel_id: UUID,
    document_id: UUID | None,
) -> str:
    lines = [
        system_prompt,
        f"\n\n当前小说 ID: {novel_id}",
        _DOCUMENT_WRITE_RULES,
        f"\n\n{_MATERIAL_MANAGEMENT_RULES}",
    ]
    if document_id is not None:
        lines.append(
            f"\n当前打开的文档 ID: {document_id}。"
            "用户要求写入/更新/润色当前章节正文时，必须调用 propose_document_update，"
            "传入该 document_id 和完整正文；不要只在回复里展示正文。"
        )
    else:
        lines.append(
            "\n当前没有打开的文档。"
            "用户要求写新章节时，调用 create_chapter_with_content 创建章节并写入正文。"
        )
    lines.append(
        "\n可用工具包括：read_document、propose_document_update、create_chapter_with_content、"
        "章节树增删改查、记忆读写、素材与时间线的增删改查及 list_material_changes。需要实际操作时请调用工具。"
    )
    return "".join(lines)
