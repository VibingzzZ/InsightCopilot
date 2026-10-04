import customerData from './customerData.json';
import { Conversation, SourceSession, PromiseRow } from '../types';

export const featuredConversations: Conversation[] = [
  {
    id: 'S00015', customer: '林a**', avatar: '林', preview: '用了面膜脸红肿刺痛，我现在在医院', time: '09:41',
    scene: '不良反应 · 过敏就医', risk: 'urgent', pending: true, order: '6920394820174228019',
    ticket: '待创建', emotion: '紧急上升', visits: 1,
    messages: [
      { role: 'buyer', text: '必须给我个说法！用了你们面膜脸过敏，红肿刺痛，我人现在在医院！', time: '09:41' },
      { role: 'buyer', text: '资料给你，赔偿方案今天给我，不行我就走12315。', time: '09:42', attachment: '门诊资料.jpg' },
      { role: 'agent', text: '非常抱歉让您遇到这种情况，请先遵照医生建议治疗。我马上为您升级专项专员。', time: '09:43' },
    ],
    insight: '消费者使用面膜后出现红肿刺痛，已在医院并提及监管投诉。系统触发 L3 紧急流程，需要立即升级专员并建立回访任务。',
    facts: [
      { label: '使用商品', value: '测试B5多效修护面膜' }, { label: '症状', value: '全脸红肿、刺痛', tone: 'danger' },
      { label: '就医状态', value: '已就医', tone: 'danger' }, { label: '待补信息', value: '产品批次号', tone: 'warning' },
    ],
    actions: [
      { icon: 'shield', title: '升级不良反应专员', detail: '建议 5 分钟内完成分派', button: '立即升级' },
      { icon: 'ticket', title: '创建专项工单', detail: '已预填 8/9 项，缺少批次号', button: '预览工单' },
      { icon: 'clock', title: '建立次日上午回访', detail: '履约状态将同步到主管看板', button: '创建承诺' },
    ],
    draft: '很抱歉您现在这么难受，请先遵照医生建议治疗。我们已将您的情况升级给不良反应专员，也请您补充产品批次号。专员会在明天上午回访，并协助您继续处理。',
    promise: { title: '不良反应专员电话回访', deadline: '明天 12:00', owner: '专项服务组', status: '待确认' },
    history: [
      { date: '09:43', title: '识别为 L3 紧急风险', detail: '证据：已就医、红肿刺痛、提及 12315', tone: 'danger' },
      { date: '09:42', title: '收到门诊资料', detail: '资料类型已识别，等待人工确认', tone: 'warning' },
      { date: '09:41', title: '消费者首次进线', detail: '关联订单已自动定位' },
    ],
  },
  {
    id: 'S00005', customer: '魏h**', avatar: '魏', preview: '上次说会处理，退款到现在还没到账', time: '09:37',
    scene: '订单服务 · 退款延迟', risk: 'attention', pending: true, order: '6920223542160114724',
    ticket: 'XXDK-24051 · 处理中', emotion: '焦虑上升', visits: 3,
    messages: [
      { role: 'buyer', text: '退款到底去哪了，别踢皮球让我找银行。', time: '09:37' },
      { role: 'agent', text: '真的很抱歉让您久等了，我先帮您核对之前的处理记录。', time: '09:38' },
      { role: 'buyer', text: '上次就说会处理，到现在还没到账。', time: '09:39' },
    ],
    insight: '消费者第三次进线。上次退款核实工单仍在财务处理，原承诺尚未完成。建议先催办工单，再提供明确反馈时间，避免重复询问订单信息。',
    facts: [
      { label: '退款金额', value: '¥8.80' }, { label: '工单状态', value: '财务处理中', tone: 'warning' },
      { label: '原承诺', value: '3 个工作日内完成核实', tone: 'warning' }, { label: '责任人', value: '财务组 · G002' },
    ],
    actions: [
      { icon: 'ticket', title: '催办财务工单', detail: '已等待 2 个工作日', button: '发起催办' },
      { icon: 'clock', title: '明确本次反馈时间', detail: '建议今天 18:00 前回复', button: '加入承诺' },
    ],
    draft: '很抱歉让您再次联系。上次登记的退款核实还没有完成，我已经看到对应工单，当前正在财务处理。我先为您加急，并在今天 18:00 前向您回复明确结果。',
    promise: { title: '反馈退款核实结果', deadline: '今天 18:00', owner: '客服林林', status: '即将到期' },
    history: [
      { date: '今天', title: '第三次进线 · 退款仍未到账', detail: '情绪由焦虑转为明显不满', tone: 'warning' },
      { date: '2 天前', title: '创建退款核实工单', detail: '当前状态：财务处理中' },
      { date: '8 天前', title: '首次咨询退款延迟', detail: '客服承诺 3 个工作日内完成核实' },
    ],
  },
  {
    id: 'S00159', customer: '姚b**', avatar: '姚', preview: '会员日加赠礼怎么没有随包裹发来？', time: '09:22',
    scene: '补发换货 · 会员权益', risk: 'normal', pending: true, order: '6920208613936937938',
    ticket: 'BH959479214460 · 进行中', emotion: '平稳', visits: 3,
    messages: [
      { role: 'buyer', text: '会员日下单的加赠礼怎么没有随包裹发来？', time: '09:22' },
      { role: 'agent', text: '核实到您符合会员加赠条件，是系统没有自动关联赠品。', time: '09:23' },
      { role: 'buyer', text: '好的，那麻烦帮我盯一下，别又漏了。', time: '09:24' },
    ],
    insight: '消费者符合会员加赠条件，补发工单已经创建。当前等待补发物流单号，客服承诺 48 小时内发出。',
    facts: [
      { label: '会员权益', value: '护发精油小样 10ml' }, { label: '工单状态', value: '进行中' },
      { label: '补发时限', value: '48 小时内' }, { label: '当前缺口', value: '补发物流单号', tone: 'warning' },
    ],
    actions: [
      { icon: 'ticket', title: '跟踪补发物流', detail: '工单完成后自动同步单号', button: '查看工单' },
      { icon: 'clock', title: '设置到期提醒', detail: '剩余 27 小时', button: '设置提醒' },
    ],
    draft: '已经为您核实到会员加赠资格，这次是系统没有自动关联赠品。补发工单已经创建，会在 48 小时内发出，单号同步后我会第一时间通知您。',
    promise: { title: '会员赠品完成补发', deadline: '剩余 27 小时', owner: '仓配组 · B07', status: '进行中' },
    history: [
      { date: '今天', title: '创建会员赠品补发工单', detail: '等待仓配组生成物流单号', tone: 'success' },
      { date: '今天', title: '确认会员加赠资格', detail: '系统未自动关联赠品订单' },
      { date: '3 天前', title: '订单签收', detail: '订单商品签收，赠品缺失' },
    ],
  },
  {
    id: 'S00001', customer: '邓e**', avatar: '邓', preview: '新的泵头什么时候能发出？', time: '08:58',
    scene: '补发换货 · 包装破损', risk: 'normal', pending: false, order: '6920185815517983396',
    ticket: 'BH919209358357 · 已完结', emotion: '平稳', visits: 1,
    messages: [{ role: 'buyer', text: '你好，收到的粉底液泵头是坏的，按不出来东西。', time: '08:52' }, { role: 'agent', text: '照片已确认，我们会为您登记换货。', time: '08:55' }],
    insight: '消费者提交的破损照片已核验，换货工单完成，新包裹已发出。当前无待处理风险。',
    facts: [{ label: '换货状态', value: '已发出', tone: 'success' }, { label: '物流单号', value: 'SF1624484966688' }],
    actions: [{ icon: 'ticket', title: '发送物流信息', detail: '顺丰预计明日送达', button: '发送进度' }],
    draft: '新的商品已经通过顺丰发出，预计明日送达。我把物流单号同步给您，如有异常可以随时联系我们。',
    history: [{ date: '今天', title: '换货包裹已发出', detail: '承诺已履约', tone: 'success' }],
  },
];

const sourceSessions = customerData.sessions as SourceSession[];

const formatTime = (value: string) => value?.match(/\d{2}:\d{2}/)?.[0] ?? value ?? '--:--';

function genericConversation(session: SourceSession): Conversation {
  const sourceTicket = session.tickets[0] as Record<string, string> | undefined;
  const sourceOrder = session.orders[0] as Record<string, string> | undefined;
  const ticketStatus = sourceTicket?.['工单状态'] || sourceTicket?.['任务状态'] || '待处理';
  const isReaction = session.sceneMajor === '不良反应';
  const hasOpenTicket = !!sourceTicket && !/(完成|关闭|完结)/.test(ticketStatus);
  const risk: Conversation['risk'] = isReaction && /(就医|医院|呼吸|赔偿|12315)/.test(session.messages.map(m => m.text).join(''))
    ? 'urgent' : hasOpenTicket ? 'attention' : 'normal';
  const order = sourceOrder?.['订单号'] || session.orderIds[0] || '未关联订单';
  const ticket = sourceTicket?.['工单号'] ? `${sourceTicket['工单号']} · ${ticketStatus}` : '暂无工单';
  return {
    id: session.id, customer: session.customer, avatar: session.customer[0] || '?', preview: session.preview,
    time: formatTime(session.lastTime), scene: `${session.sceneMajor} · ${session.sceneMinor}`, risk,
    pending: hasOpenTicket, order, ticket, emotion: risk === 'urgent' ? '紧急上升' : risk === 'attention' ? '关注' : '平稳',
    visits: sourceSessions.filter(x => x.customer === session.customer).length, messages: session.messages, insight: `已从官方业务数据关联 ${session.messages.length} 条消息、${session.orders.length} 个订单和 ${session.tickets.length} 个工单。当前场景为“${session.sceneMinor}”，建议根据最新一条消息确认下一步处理。`,
    facts: [
      { label: '业务场景', value: session.sceneMajor }, { label: '具体诉求', value: session.sceneMinor },
      { label: '关联订单', value: order }, { label: '工单状态', value: ticketStatus, tone: hasOpenTicket ? 'warning' : 'success' },
    ],
    actions: [{ icon: 'ticket', title: sourceTicket ? '查看关联工单' : '创建服务工单', detail: sourceTicket ? `当前状态：${ticketStatus}` : '基于当前会话信息预填工单', button: sourceTicket ? '查看工单' : '预览工单' }],
    draft: `已了解您关于“${session.sceneMinor}”的问题，我先为您核对相关订单和处理记录，并在确认后给您明确回复。`,
    history: [{ date: formatTime(session.lastTime), title: `当前会话 · ${session.sceneMinor}`, detail: `${session.messages.length} 条消息已纳入服务轨迹`, tone: risk === 'urgent' ? 'danger' : risk === 'attention' ? 'warning' : 'success' }],
  };
}

export const mockConversations: Conversation[] = sourceSessions.map(session => {
  const featured = featuredConversations.find(c => c.id === session.id);
  const sourceTicket = session.tickets[0] as Record<string, string> | undefined;
  const sourceOrder = session.orders[0] as Record<string, string> | undefined;
  const base = featured ?? genericConversation(session);
  const actions = featured && sourceTicket
    ? featured.actions.map(action => action.title === '创建专项工单'
      ? { ...action, title: '查看专项工单', detail: `已关联 ${sourceTicket['工单号']} · ${sourceTicket['工单状态'] || sourceTicket['任务状态'] || '处理中'}`, button: '查看工单' }
      : action)
    : base.actions;
  return {
    ...base,
    customer: session.customer, avatar: session.customer[0] || base.avatar, preview: session.preview,
    time: formatTime(session.lastTime), scene: `${session.sceneMajor} · ${session.sceneMinor}`,
    order: sourceOrder?.['订单号'] || session.orderIds[0] || base.order,
    ticket: sourceTicket?.['工单号'] ? `${sourceTicket['工单号']} · ${sourceTicket['工单状态'] || sourceTicket['任务状态'] || '处理中'}` : (featured ? base.ticket : '暂无工单'),
    messages: session.messages,
    visits: sourceSessions.filter(x => x.customer === session.customer).length,
    actions,
  };
});

export const mockPromiseRows: PromiseRow[] = [
  { customer: '芝g**', item: '不良反应专员电话回访', biz: '不良反应 · S00015', deadline: '今天 12:00', status: 'urgent', owner: '专项服务组' },
  { customer: '魏h**', item: '反馈退款核实结果', biz: '线下打款 · S00005', deadline: '今天 18:00', status: 'due', owner: '客服林林' },
  { customer: '姚b**', item: '会员赠品 48 小时内发出', biz: '补发换货 · S00159', deadline: '剩余 27 小时', status: 'active', owner: '仓配组 B07' },
  { customer: '周h**', item: '仓库反馈少件核实结果', biz: '物流异常 · S00006', deadline: '明天 09:20', status: 'active', owner: '仓配组 A05' },
  { customer: '邓e**', item: '换货包裹 48 小时内发出', biz: '补发换货 · S00001', deadline: '今天 08:36', status: 'done', owner: '仓配组 G001' },
];
