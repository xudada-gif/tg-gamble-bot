import asyncio
import base64
import os
from io import BytesIO

import aiofiles
import chardet
from telegram.error import RetryAfter, TimedOut, NetworkError
import logging
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from telegram.ext import CallbackContext


async def safe_send_message(context, chat_id, text, **kwargs):
    """ 安全发送消息，支持指数退避 """
    delay = 1  # 初始延迟 1 秒
    max_retries = 5  # 最多重试 5 次

    for attempt in range(max_retries):
        try:
            return await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
        except RetryAfter as e:
            delay = min(e.retry_after, delay * 2)  # 指数退避，但不超过 Telegram 限流时间
            logging.warning(f"Hit RetryAfter: Sleeping for {delay} seconds")
        except (TimedOut, NetworkError):
            logging.warning(f"Network issue, retrying in {delay} seconds...")

        await asyncio.sleep(delay)  # **真正等待**
        delay *= 2  # **等待时间翻倍**

    logging.error("Failed to send message after multiple retries")
    return None  # 失败后返回 None


async def safe_send_dice(context, chat_id, emoji="🎲"):
    """ 安全投掷骰子，失败最多重试 3 次 """
    for _ in range(3):  # 限制最多重试 3 次
        try:
            return await context.bot.send_dice(chat_id=chat_id, emoji=emoji)
        except RetryAfter as e:
            logging.warning(f"Hit RetryAfter: Sleeping for {e.retry_after} seconds")
            await asyncio.sleep(e.retry_after)
        except (TimedOut, NetworkError):
            logging.warning("Network issue, retrying in 5 seconds...")
            await asyncio.sleep(5)

    logging.error("投骰子失败，放弃本轮游戏")
    return None  # 失败后返回 None，避免死循环


async def detect_encoding(file_path):
    """异步检测文件编码"""
    async with aiofiles.open(file_path, "rb") as f:
        raw_data = await f.read(1024)  # 读取部分内容，提高检测速度
        result = chardet.detect(raw_data)

    encoding = result.get("encoding", "utf-8")  # 失败时默认 utf-8
    return encoding

# 定义一个锁，避免多个异步任务同时修改 counter.txt
counter_lock = asyncio.Lock()

async def issue():
    # 定义存储编号的文件路径
    file_path = "counter.txt"

    async with counter_lock:  # 保证只有一个任务能修改编号
        # 检查文件是否存在
        if not os.path.exists(file_path):
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write("1")  # 初始化编号为1

        # 读取当前编号
        encoding = await detect_encoding(file_path)  # 检测编码
        try:
            async with aiofiles.open(file_path, "r", encoding=encoding) as f:
                content = await f.read()
                current_number = int(content.strip())  # 解析为整数
        except (UnicodeDecodeError, ValueError):
            print("文件编码异常或数据格式错误，尝试使用 UTF-8 重新读取")
            async with aiofiles.open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = await f.read()
                current_number = int(content.strip())  # 再次尝试解析

        # 生成新的编号
        letter = "K"  # 可自定义字母
        new_code = f"{letter}{current_number:016d}"  # 16 位编号

        # 更新文件中的编号（加1）
        async with aiofiles.open(file_path, "w", encoding=encoding) as f:
            await f.write(str(current_number + 1))  # 递增编号

    return new_code


async def dice_photo(context: CallbackContext):
    # 固定表格大小
    rows, cols = 6, 14
    dice_list = context.bot_data["total_points"]

    # 将数据填充到 6×14 的表格中，并按照 "从左向下" 填充
    grid = np.full((rows, cols), np.nan)  # 先创建空表
    for index, value in enumerate(dice_list):
        col = index // rows  # 计算列索引（按列填充）
        row = index % rows  # 计算行索引
        grid[row, col] = value

    # 颜色映射：1-9（蓝色），10-18（红色）
    async def get_color(value_color):
        return "royalblue" if value_color <= 9 else "firebrick"

    # 计算“大”和“小”的数量
    count_big = np.sum(grid >= 10)  # 大于等于 10 的为“大”
    count_small = np.sum(grid <= 9)  # 小于等于 9 的为“小”

    # 创建画布
    fig, ax = plt.subplots(figsize=(cols, rows + 1.5))  # 增加更多的空间来显示统计行
    ax.set_xlim(0, cols)
    ax.set_ylim(0, rows)  # 保持表格区域不变
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_frame_on(False)

    # 绘制网格线
    for i in range(rows + 1):  # 仅绘制表格部分的网格
        ax.plot([0, cols], [i, i], color="gray", linewidth=1, alpha=0.5)  # 水平网格
    for j in range(cols + 1):
        ax.plot([j, j], [0, rows], color="gray", linewidth=1, alpha=0.5)  # 垂直网格

    # 绘制表格内容
    for i in range(rows):
        for j in range(cols):
            value = grid[i, j]
            if np.isnan(value):  # 为空格时跳过
                continue

            color = await get_color(value)

            # 立体球
            gradient = patches.Circle((j + 0.5, rows - i - 0.5), 0.45, color=color, transform=ax.transData, zorder=1)
            ax.add_patch(gradient)

            # 画高光（柔和效果）
            highlight = patches.Circle((j + 0.38, rows - i - 0.38), 0.15, color="white", alpha=0.15,
                                       transform=ax.transData, zorder=2)
            ax.add_patch(highlight)

            # 添加数字
            ax.text(j + 0.5, rows - i - 0.5, f"{int(value):02}", ha='center', va='center', fontsize=24,
                    color="white", fontweight="bold", zorder=3)

    # 添加背景色
    ax.add_patch(patches.Rectangle((cols / 4 - 1, rows + 0.6), 2, 0.2, linewidth=0, facecolor="royalblue", zorder=0))
    ax.add_patch(
        patches.Rectangle((3 * cols / 4 - 1, rows + 0.6), 2, 0.2, linewidth=0, facecolor="firebrick", zorder=0))
    if len(context.bot_data["total_points"]) == rows * cols:
        context.bot_data["total_points"] = []

    # 将图像保存到内存（Base64 编码）
    img_buffer = BytesIO()
    fig.savefig(img_buffer, format='jpg')
    img_buffer.seek(0)
    img_base64 = base64.b64encode(img_buffer.read()).decode('utf-8')

    return img_base64, count_big, count_small