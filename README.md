# dify_dingtalk_stream
本仓库包含一个基于钉钉开放平台 API 的 Python 实现，用于创建并流式更新钉钉卡片。用 `aiohttp` 进行异步 HTTP 请求，并使用 `loguru` 记录日志。机器人会处理接收到的文本消息，并通过创建和更新钉钉中的交互式卡片进行响应。

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
- 已注册的钉钉开放平台应用，获取开发者权限，并获取 `app_key` 和 `app_secret`。
- dify的应用API和鉴权API-KEY填入至代码第三十四行和第三十六行

---
运行机器人时，通过命令行参数传入这些凭据：

```bash
python main.py --client_id YOUR_APP_KEY --client_secret YOUR_APP_SECRET
