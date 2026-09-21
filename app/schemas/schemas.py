#用 Pydantic 实现对 detail_json 的严格白名单控制，禁止支付宝实名/账号等隐私字段进入


from pydantic import BaseModel, ConfigDict


class ExtraBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")  # 禁止白名单之外的字段

# 1. 补发换货工单
class ReplenishmentExchangeDetail(ExtraBaseModel):
    ship_sku: str | None = None
    ship_product_name: str | None = None
    quantity: int | None = None
    warehouse: str | None = None
    replacement_tracking_masked: str | None = None
    expedite: bool | None = False

# 2. 线下打款工单
class OfflinePaymentDetail(ExtraBaseModel):
    payment_type: str | None = None
    refund_reason_type: str | None = None
    refund_amount_cent: int | None = None
    related_tracking_masked: str | None = None
    transfer_status: str | None = None
    alipay_name_masked: str | None = None
    alipay_account_masked: str | None = None

# 3. 物流工单
class LogisticsDetail(ExtraBaseModel):
    problem_type: str | None = None
    carrier: str | None = None
    package_tracking_masked: str | None = None
    warehouse: str | None = None
    solution: str | None = None
    abnormal_flag: bool | None = False

# 4. 不良反应工单
class AdverseReactionDetail(ExtraBaseModel):
    reaction_type: str | None = None
    age_band: str | None = None
    skin_type: str | None = None
    product_name: str | None = None
    batch_no_masked: str | None = None
    affected_area: str | None = None
    symptom_summary: str | None = None
    onset_after: str | None = None
    stopped_use: bool | None = True
    sought_medical_help: bool | None = False
    follow_up_status: str | None = None

# 5. 售后退货工单
class ReturnDetail(ExtraBaseModel):
    package_type: str | None = None
    return_reason: str | None = None
    return_tracking_masked: str | None = None
    refund_no_masked: str | None = None
    receipt_advice: str | None = None
    abnormal_flag: bool | None = False