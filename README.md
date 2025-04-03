# dify_dingtalk_stream
本本仓库基于官方钉钉AI示例，把通义千问的库换成了dify并写了流式的对应callback。用于创建并流式更新钉钉AI卡片。用 `aiohttp` 进行异步 HTTP 请求，并使用 `loguru` 记录日志。机器人会处理接收到的文本消息，并通过创建和更新钉钉中的交互式卡片进行响应。

---

## 功能

- **钉钉卡片创建：** 利用 [钉钉开放平台 API](https://open.dingtalk.com/document/orgapp/api-streamingupdate) 创建并投放交互式卡片。
- **异步流式更新：** 支持通过流式机制实时更新卡片内容。  
![56e298f5bc2700db6c4460908b3e9a75](https://github.com/user-attachments/assets/a496176c-7f2e-421e-bed4-6a79364e87cf)  
- **自定义回调：** 支持集成自定义逻辑来处理流式响应。
- **错误处理：** 包含对无效 JSON 响应和 HTTP 请求失败的健壮错误处理。

---

## 前置条件

- Python 3.7 或以上版本
- 安装dingtalk_stream 和 loguru 库
- 已注册的钉钉开放平台应用，获取开发者权限，并获取 `client_id` , `client_secret`以及卡片ID。    
具体步骤：  
1.先登录开放平台，创建一个机器人应用并发布版本，打开应用详情-凭证与基础信息，复制client_id和client_secret。    
2.去卡片平台创建卡片，新建模板，选择AI卡片，然后绑定你刚创建的应用。  
3.模板列表里复制卡片ID，以schema结尾。  
- dify的API和应用鉴权API-KEY。  
API：如http://10.20.101.126/v1/chat-messages  
鉴权API-KEY：如app-mrDD7HLYSyEODPgjeTe9NQtp  
卡片ID：abcdefgh-eb08-49ec-8c76-54dc7575d82d.schema    
---
运行机器人时，通过命令行参数传入这些凭据：

```bash
python main.py --client_id ding*********** --client_secret ********* --dify_api http://*.*.*.*/v1/chat-messages --dify_app_key app-******************** --schema ********-****-****-****-*************.schema
