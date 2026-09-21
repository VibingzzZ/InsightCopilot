from operator import add
from typing import Annotated, TypedDict


# 实现Node间共享数据
class CustomerState(TypedDict):
    # 输入
    conversation_id: str
    current_message: str

    # 理解层
    intent: str
    emotion: str

    # 风险层
    risk: RiskInfo  # Risk Extraction 产出（LLM）  # noqa: F821
    risk_level: str  # Risk Engine 判定（代码）：normal / medium / high

    # 数据层
    order: dict[str, str]  # 工具查询结果

    # 证据层（用 add reducer 累加：节点返回新增条目，LangGraph 自动 append）
    evidence: Annotated[list[EvidenceItem], add]  # noqa: F821

    # 表达层
    reply_draft: str


class RiskInfo(TypedDict):
    """ "Risk Extraction 的结构化啊输出，由LLM提取"""

    adverse_reaction: bool
    symptoms: list[str]
    medical_visit: bool


class EvidenceItem(TypedDict):
    """统一证据结构：Reply 只信这一层，不信原始数据。"""

    source: str  # order / ticket / logistics / ...
    id: str
    content: str
