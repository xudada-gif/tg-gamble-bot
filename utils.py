from typing import Union

from telegram import Update
from telegram.ext import ContextTypes, CallbackContext
from functools import wraps
import requests
import datetime
import logging

from database import get_user_info_db

"""部署时启动"""
# # 配置日志记录
# logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)


async def check_admin(update: Update, context: CallbackContext):
    """检查是否为群管理员"""
    chat = update.effective_chat
    user = update.effective_user

    # **1️⃣ 检查是否在群聊**
    if chat.type == "private":
        await update.message.reply_text("❌ 该命令只能在群聊中使用！")
        await update.message.delete()
        return False

    # **2️⃣ 获取管理员列表**
    admins = await context.bot.get_chat_administrators(chat.id)

    # **3️⃣ 检查用户是否为管理员**
    for admin in admins:
        if admin.user.id == user.id:
            return True

    # **4️⃣ 如果不是管理员，发送提示**
    await update.message.reply_text("❌ 你不是管理员，无法使用该命令！")
    return False

def admin_required(func):
    """装饰器：仅允许群管理员使用"""
    @wraps(func)
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        if await check_admin(update, context):
            return await func(update, context, *args, **kwargs)
    return wrapper


# 使用 geopy 或其他服务来获取国家信息（地理定位）
def get_country(ip):
    # 使用一个公开的 GeoIP 服务
    try:
        response = requests.get(f'http://ip-api.com/json/{ip}')
        data = response.json()
        return data.get('country', 'Unknown')
    except requests.RequestException:
        return 'Unknown'


def log_command(func):
    """记录执行命令的 IP 地址、国家、时间和命令"""
    @wraps(func)
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):

        # 获取当前时间（精确到秒）
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 获取命令执行者的基本信息
        user_id = update.effective_user.id
        user_name = update.effective_user.full_name
        command = update.message.text

        # 记录日志到控制台或文件中
        print(f"时间: {timestamp} | 命令: {command} | 用户ID: {user_id} | 用户名: {user_name} | IP: ")
        with open('command_log.log', 'a') as log_file:
            log_file.write(f"时间: {timestamp} | 命令: {command} | 用户ID: {user_id} | 用户名: {user_name} | 位置: | IP: ")

        return await func(update, context, *args, **kwargs)

    return wrapper


def user_exists(cursor, user_id: Union[int, str]) -> bool:
    """检查用户是否存在"""
    result = get_user_info_db(cursor, user_id)
    return result is not None  # 如果查询到数据返回 True，否则返回 False