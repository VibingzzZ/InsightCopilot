INTENT_PROMPT="""你是一个美妆电商客服分析助手。请判断用户当前消息的业务意图。用户消息：
{message}

只需要判断用户最主要的一个业务意图。

请严格按以下 JSON 格式输出（不要输出 JSON 以外的任何内容）：
{format_instructions}"""