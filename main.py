import os
import logging
import asyncio
import argparse
from loguru import logger
from dingtalk_stream import AckMessage
import dingtalk_stream
import aiohttp
import json
from http import HTTPStatus

from typing import Callable, Awaitable


def define_options():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client_id",
        dest="client_id",
        required=True,
        help="app_key or suite_key from https://open-dev.digntalk.com",
    )
    parser.add_argument(
        "--client_secret",
        dest="client_secret",
        required=True,
        help="app_secret or suite_secret from https://open-dev.digntalk.com",
    )
    # --- 参数用于 Dify API 调用 ---
    parser.add_argument(
        "--dify_api",
        dest="dify_api",
        required=True,
        help="Dify chat API endpoint URL (e.g., http://your-dify-host/v1/chat-messages)",
    )
    parser.add_argument(
        "--dify_app_key",
        dest="dify_app_key",
        required=True,
        help="Dify App API Key (e.g., app-xxxxxxxxxxxx)",
    )
    # --- 参数用于卡片模板 ---
    parser.add_argument(
        "--schema",
        dest="card_template_id",
        required=True,
        help="Card template ID from https://open-dev.dingtalk.com/fe/card (e.g., xxxxx.schema)",
    )
    options = parser.parse_args()
    return options


# 修改：增加 options 参数
async def call_with_stream(options: argparse.Namespace, request_content: str, callback: Callable[[str], Awaitable[None]]):
    # 使用 options 中的值
    url = options.dify_api
    headers = {
        # 使用 f-string 格式化 Bearer token
        'Authorization': f'Bearer {options.dify_app_key}',
        'Content-Type': 'application/json'
    }

    data = {
        "inputs": {},
        "query": request_content,
        "response_mode": "streaming",
        "conversation_id": "",
        "user": "abc-123" # 这个 user ID 可能也需要参数化，取决于你的应用场景
    }

    full_content = ""
    length = 0

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status != HTTPStatus.OK:
                    error_text = await response.text()
                    logger.error(f"API Call Failed! Status: {response.status}, URL: {url}, Response: {error_text}")
                    raise Exception(
                        f"Status code: {response.status}, Response: {error_text}"
                    )

                buffer = ""
                async for chunk in response.content.iter_any():
                    buffer += chunk.decode('utf-8')

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        if line.startswith("data: "):
                            try:
                                json_data = json.loads(line[len("data: "):])
                                answer = json_data.get("answer")

                                if answer is not None:
                                    full_content += answer
                                    current_length = len(full_content)

                                    if current_length - length > 20:
                                        await callback(full_content)
                                        # print(f"Callback triggered: {length} -> {current_length}") # 可以注释掉调试信息
                                        length = current_length
                            except json.JSONDecodeError as e:
                                logger.warning(f"Ignoring invalid JSON line: {line}, Error: {str(e)}")
        finally:
            # 确保最终结果被回调
            if length != len(full_content): # 只有当最后一部分内容没有触发回调时才调用
                 await callback(full_content)

    logger.info(
        f"Request Content: {request_content}\nFull response: {full_content}"
    )
    return full_content


# 修改：增加 options 参数
async def handle_reply_and_update_card(options: argparse.Namespace, self: dingtalk_stream.ChatbotHandler, incoming_message: dingtalk_stream.ChatbotMessage):
    # 使用 options 中的值
    card_template_id = options.card_template_id
    content_key = "content"
    card_data = {content_key: "Thinking..."} # 可以先显示思考中
    card_instance = dingtalk_stream.AICardReplier(
        self.dingtalk_client, incoming_message
    )

    card_instance_id = None # 初始化 card_instance_id
    try:
        # 先投放卡片
        card_instance_id = await card_instance.async_create_and_deliver_card(
            card_template_id, card_data
        )
        logger.info(f"Card delivered with instance ID: {card_instance_id}")

        # 定义流式更新的回调
        async def callback(content_value: str):
            # 增加日志记录更新动作
            # logger.debug(f"Streaming update: {content_value[:50]}...") # 记录部分内容避免日志过长
            return await card_instance.async_streaming(
                card_instance_id,
                content_key=content_key,
                content_value=content_value,
                append=False,
                finished=False,
                failed=False,
            )

        # 调用 API 并流式更新
        full_content_value = await call_with_stream(
            options, # 传递 options
            incoming_message.text.content,
            callback
        )

        # 最终完成状态更新
        await card_instance.async_streaming(
            card_instance_id,
            content_key=content_key,
            content_value=full_content_value,
            append=False,
            finished=True,
            failed=False,
        )
        logger.info("Card update finished successfully.")

    except Exception as e:
        self.logger.exception(e)
        # 如果 card_instance_id 已经创建，则更新为失败状态
        if card_instance_id:
            try:
                await card_instance.async_streaming(
                    card_instance_id,
                    content_key=content_key,
                    content_value="抱歉，处理时遇到错误。", # 提供错误提示
                    append=False,
                    finished=False, # 保持卡片交互性，或者设为 True 结束
                    failed=True,
                )
                logger.error("Card update marked as failed.")
            except Exception as inner_e:
                self.logger.error(f"Failed to update card to failed state: {inner_e}")
        else:
             # 如果卡片都还没发出去就出错了，可以考虑回复一条文本消息
             try:
                 await self.reply_text("抱歉，处理您的请求时遇到了问题。", incoming_message)
             except Exception as reply_e:
                 self.logger.error(f"Failed to send error text reply: {reply_e}")


class CardBotHandler(dingtalk_stream.ChatbotHandler):
    # 修改：__init__ 接收 options
    def __init__(self, options: argparse.Namespace, logger: logging.Logger = logger):
        super(dingtalk_stream.ChatbotHandler, self).__init__()
        self.options = options # 存储 options
        if logger:
            self.logger = logger
        else:
            # 确保 self.logger 存在
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO) # 或其他合适的级别
            if not self.logger.handlers:
                # 添加一个默认的 handler，避免 "No handlers could be found" 警告
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)


    async def process(self, callback: dingtalk_stream.CallbackMessage):
        incoming_message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
        self.logger.info(f"Received message: {incoming_message}")

        if not incoming_message.text or not incoming_message.text.content:
             self.logger.warning("Received non-text or empty message, skipping.")
             # 可以选择回复或直接忽略
             # await self.reply_text("我只能处理文本消息哦。", incoming_message)
             return AckMessage.STATUS_OK, "Skipped non-text/empty message"

        # 检查是否是 @机器人 的消息（如果需要）
        # if not incoming_message.is_at_robot():
        #     self.logger.info("Message is not @ me, skipping.")
        #     return AckMessage.STATUS_OK, "Skipped message not @ robot"

        content = incoming_message.text.content.strip()
        if not content:
            self.logger.info("Received empty content after stripping, skipping.")
            return AckMessage.STATUS_OK, "Skipped empty content"

        # 创建异步任务处理回复和卡片更新，传递 self.options
        asyncio.create_task(handle_reply_and_update_card(self.options, self, incoming_message))
        # 立即返回 ACK，表示已接收，后台任务会继续执行
        return AckMessage.STATUS_OK, "Processing in background"


def main():
    # 1. 获取解析后的参数
    options = define_options()

    # 打印关键配置（注意不要打印敏感信息如 secret 和 key）
    logger.info(f"Starting DingTalk Stream Client with:")
    logger.info(f"  Client ID: {options.client_id}")
    logger.info(f"  Dify API: {options.dify_api}")
    logger.info(f"  Card Template ID: {options.card_template_id}")
    # logger.info(f"  Client Secret: ***") # 不打印 secret
    # logger.info(f"  Dify App Key: ***") # 不打印 key

    credential = dingtalk_stream.Credential(options.client_id, options.client_secret)
    client = dingtalk_stream.DingTalkStreamClient(credential)

    # 2. 实例化 Handler 时传入 options
    client.register_callback_handler(
        dingtalk_stream.ChatbotMessage.TOPIC, CardBotHandler(options, logger=logger) # 传递 options
    )
    logger.info("Callback handler registered. Starting client...")
    client.start_forever()


if __name__ == "__main__":
    # 配置 loguru (可选，如果想用 loguru 替换 logging)
    # logger.add("file_{time}.log") # 可以将日志输出到文件
    main()
