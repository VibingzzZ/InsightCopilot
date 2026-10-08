# 知微客服副驾

面向美妆电商人工客服的本地可交互 Demo。页面使用官方业务数据的静态快照，支持会话检索、订单/工单查看、AI 草稿采纳、动作状态模拟和履约跟踪。

## 运行

```bash
npm install
npm run dev
```

生产构建：

```bash
npm run typecheck
npm run build
```

## 数据

`src/data/customerData.json` 由 `data/赛题 1：数据共情者-业务数据.xlsx` 预处理生成，包含：

- 998 条聊天消息
- 138 个会话
- 113 个订单
- 80 个工单

静态快照已移除支付宝账号、实名、电话和地址等不应进入浏览器端的字段。

当前动作、创建跟踪和模块切换均为前端本地状态模拟，不会写回 Excel，也不会调用后端接口。后续接入后端时，可将 `customerData.json` 替换为 API 数据源，并保留现有字段结构。
