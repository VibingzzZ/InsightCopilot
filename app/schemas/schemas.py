#用 Pydantic 实现对 detail_json 的严格白名单控制，禁止支付宝实名/账号等隐私字段进入

from typing import Optional
from pydantic import BaseModel, ConfigDict

class ExtraBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")  # 禁止白名单之外的字段

# 1. 补发换货工单
class ReplenishmentExchangeDetail(ExtraBaseModel):
    ship_sku: Optional[str] = None
    ship_product_name: Optional[str] = None
    quantity: Optional[int] = None
    warehouse: Optional[str] = None
    replacement_tracking_masked: Optional[str] = None
    expedite: Optional[bool] = False

# 2. 线下打款工单
class OfflinePaymentDetail(ExtraBaseModel):
    payment_type: Optional[str] = None
    refund_reason_type: Optional[str] = None
    refund_amount_cent: Optional[int] = None
    related_tracking_masked: Optional[str] = None
    transfer_status: Optional[str] = None
    alipay_name_masked: Optional[str] = None
    alipay_account_masked: Optional[str] = None

# 3. 物流工单
class LogisticsDetail(ExtraBaseModel):
    problem_type: Optional[str] = None
    carrier: Optional[str] = None
    package_tracking_masked: Optional[str] = None
    warehouse: Optional[str] = None
    solution: Optional[str] = None
    abnormal_flag: Optional[bool] = False

# 4. 不良反应工单
class AdverseReactionDetail(ExtraBaseModel):
    reaction_type: Optional[str] = None
    age_band: Optional[str] = None
    skin_type: Optional[str] = None
    product_name: Optional[str] = None
    batch_no_masked: Optional[str] = None
    affected_area: Optional[str] = None
    symptom_summary: Optional[str] = None
    onset_after: Optional[str] = None
    stopped_use: Optional[bool] = True
    sought_medical_help: Optional[bool] = False
    follow_up_status: Optional[str] = None

# 5. 售后退货工单
class ReturnDetail(ExtraBaseModel):
    package_type: Optional[str] = None
    return_reason: Optional[str] = None
    return_tracking_masked: Optional[str] = None
    refund_no_masked: Optional[str] = None
    receipt_advice: Optional[str] = None
    abnormal_flag: Optional[bool] = False