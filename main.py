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
        default="2222222222222222222222222222222222222222222222222222222222222222",
        help="app_key or suite_key from https://open-dev.digntalk.com",
    )
    parser.add_argument(
        "--client_secret",
        dest="client_secret",
        default="1111111111111111111111111111111111111111111111111111111111111111",
        help="app_secret or suite_secret from https://open-dev.digntalk.com",
    )
    options = parser.parse_args()
    return options


async def call_with_stream(request_content: str, callback: Callable[[str], Awaitable[None]]):
    url = "http://*.*.*.*/v1/chat-messages" #dify url 手动填入
    headers = {
        'Authorization': 'Bearer app-*******************',
        'Content-Type': 'application/json'
    }
    
    data = {
        "inputs": {},
        "query": request_content,  # 将原始messages参数转换为API的查询格式
        "response_mode": "streaming",
        "conversation_id": "",
        "user": "abc-123"
    }

    full_content = ""
    length = 0

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status != HTTPStatus.OK:
                    error_text = await response.text()
                    raise Exception(
                        f"Status code: {response.status}, Response: {error_text}"
                    )

                # 处理流式响应
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
                                    
                                    # 每20字触发一次回调（保持与原始逻辑一致）
                                    if current_length - length > 20:
                                        await callback(full_content)
                                        print(f"Callback triggered: {length} -> {current_length}")
                                        length = current_length
                            except json.JSONDecodeError as e:
                                print(f"Ignoring invalid JSON line: {line}, Error: {str(e)}")
        finally:
            # 确保最终结果被回调（即使没有触发20字阈值）
            await callback(full_content)
    
    logger.info(
        f"Request Content: {request_content}\nFull response: {full_content}"
    )
    return full_content


async def handle_reply_and_update_card(self: dingtalk_stream.ChatbotHandler, incoming_message: dingtalk_stream.ChatbotMessage):
    # 卡片模板 ID
    card_template_id = "********-****-****-****-***********.schema"  #填AI卡片模板ID
    content_key = "content"
    card_data = {content_key: ""}
    card_instance = dingtalk_stream.AICardReplier(
        self.dingtalk_client, incoming_message
    )
    # 先投放卡片: https://open.dingtalk.com/document/orgapp/create-and-deliver-cards
    card_instance_id = await card_instance.async_create_and_deliver_card(
        card_template_id, card_data
    )

    # 再流式更新卡片: https://open.dingtalk.com/document/isvapp/api-streamingupdate
    async def callback(content_value: str):
        return await card_instance.async_streaming(
            card_instance_id,
            content_key=content_key,
            content_value=content_value,
            append=False,
            finished=False,
            failed=False,
        )

    try:
        full_content_value = await call_with_stream(
            incoming_message.text.content, callback
        )
        await card_instance.async_streaming(
            card_instance_id,
            content_key=content_key,
            content_value=full_content_value,
            append=False,
            finished=True,
            failed=False,
        )
    except Exception as e:
        self.logger.exception(e)
        await card_instance.async_streaming(
            card_instance_id,
            content_key=content_key,
            content_value="",
            append=False,
            finished=False,
            failed=True,
        )


class CardBotHandler(dingtalk_stream.ChatbotHandler):
    def __init__(self, logger: logging.Logger = logger):
        super(dingtalk_stream.ChatbotHandler, self).__init__()
        if logger:
            self.logger = logger

    async def process(self, callback: dingtalk_stream.CallbackMessage):
        incoming_message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
        self.logger.info(f"收到消息：{incoming_message}")

        if incoming_message.message_type != "text":
            self.reply_text("俺只看得懂文字喔~", incoming_message)
            return AckMessage.STATUS_OK, "OK"

        asyncio.create_task(handle_reply_and_update_card(self, incoming_message))
        return AckMessage.STATUS_OK, "OK"


def main():
    options = define_options()

    credential = dingtalk_stream.Credential(options.client_id, options.client_secret)
    client = dingtalk_stream.DingTalkStreamClient(credential)
    client.register_callback_handler(
        dingtalk_stream.ChatbotMessage.TOPIC, CardBotHandler()
    )
    client.start_forever()


if __name__ == "__main__":
    main()