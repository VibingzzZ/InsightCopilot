"""合并「意图 / 情绪 / 风险事实」三合一 Prompt（降本）。

原 intent / emotion / risk_extraction 三个节点各调一次模型，输入都只有当前消息。
这里合成一次调用：单次产出三组字段，每次分析少 2 次调用、少两遍重复的头部与消息体。

坑：deepseek-flash 只支持 response_format={"type": "json_object"}，且 prompt 里
必须出现 "json" 字样，故结尾显式写明「json 格式」。
"""

TRIAGE_PROMPT = """你是美妆电商客服分析助手。请只看用户消息，一次性完成下面三项判断。

用户消息：
{message}

一、意图
- intent_primary：从 订单服务 / 物流问题 / 不良反应 / 售前咨询 / 其他 中选一个。
- intent_secondary：二级场景短语，例如「退款迟迟不到账」「物流停滞未更新」；无法判断填「其他」。
- 判定优先级：以用户的「核心诉求 / 动作」为准，而非话题。若消息同时出现产品质量 / 不良反应描述和明确诉求（退款、赔偿、投诉、换货、曝光），intent_primary 应归到对应业务场景（如退款诉求→订单服务），并把质量 / 症状描述写入 intent_secondary（如「产品质量致损要求退款 / 投诉」）。仅当消息核心仅反映身体不适、无明确交易诉求时，才把 不良反应 作为 primary。
- entities：原样摘录消息里的订单号、商品名、金额、批次号、时间；没有则空列表。

二、情绪
- emotion：主要情绪，如 平静 / 焦虑 / 不满 / 愤怒 / 急切。
- emotion_trend：up 上升 / flat 持平 / down 缓和。

三、风险事实（只提取用户说过的，不要推断、不要补充用户没提到的）
- adverse_reaction：是否出现不良反应（脸红、肿、疼、起疹、瘙痒、爆痘等）。
- severity：none 无不适 / mild 轻微泛红、刺痒且未加重 / obvious 扩大、加重、明显红肿 / severe 呼吸困难、眼部严重异常、住院。
- symptoms：原样摘录症状关键词，无则空列表。
- medical_visit：是否明确表示已就医或已在医院。
- regulatory_complaint：是否提及监管投诉、平台投诉、曝光、律师或明确威胁（普通抱怨和「我要投诉」不算）。

请严格按以下 json 格式输出，不要输出 json 以外的任何内容：
{format_instructions}"""
