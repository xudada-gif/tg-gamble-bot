import asyncio
import base64
import os
from io import BytesIO
import json
import aiofiles
import chardet
from telegram.error import RetryAfter, TimedOut, NetworkError
import logging
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from telegram.ext import CallbackContext

# 定义一个锁，避免多个异步任务同时修改 counter.txt
counter_lock = asyncio.Lock()

# 赔率表
ODDS = {
    "大小": 0.95,
    "大小单双": 2.98,
    "和值": {
        4: 50, 5: 18, 6: 14, 7: 12, 8: 8, 9: 7, 10: 6, 11: 6, 12: 7, 13: 8, 14: 12, 15: 14, 16: 18, 17: 50
    },
    "指定豹子": 300,
    "豹子": 180,
    "对子": 11,
    "指定对子": 33,
    "定位胆": 9,
    "顺子": 30
}


# 发送消息
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


# 投掷骰子
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


# 检测文件编码
async def detect_encoding(file_path):
    """异步检测文件编码"""
    async with aiofiles.open(file_path, "rb") as f:
        raw_data = await f.read(1024)  # 读取部分内容，提高检测速度
        result = chardet.detect(raw_data)

    encoding = result.get("encoding", "utf-8")  # 失败时默认 utf-8
    return encoding


# 获取旗号
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


# 生成骰子点数表格
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


# 计算押注金额最多的用户
async def get_top_bettor(data):
    bet_sums = {}  # 存储每个用户的总押注金额
    for user in data:
        user_id = user['user_id']
        name = user['name']
        bets = json.loads(user['bet'])  # 解析 JSON 结构
        # 计算该用户的总押注金额
        total_money = 0
        for bet in bets:
            total_money += int(bet['money'])
        bet_sums[user_id] = {"name": name, "user_id": user_id, "total_money": total_money}
    # 找到押注金额最多的用户
    max_money = max(user["total_money"] for user in bet_sums.values())

    # 筛选出所有押注金额等于最高金额的用户
    top_bettors = [user for user in bet_sums.values() if user["total_money"] == max_money]

    return top_bettors


# 筛选下注用户，并获取最大下注金额和下注最多的用户
def get_filtered_users(users_info):
    """ 筛选下注用户，并获取最大下注金额和下注最多的用户 """
    filtered_users = [user for user in users_info if user['bet_amount'] > 0]
    max_bet = max((user['bet_amount'] for user in filtered_users), default=0)
    max_users = [user for user in filtered_users if user['bet_amount'] == max_bet]
    return filtered_users, max_users


# 获取 GIF 动画 file_id，如果没有缓存则发送新动画并存储 file_id
async def get_animation_file_id(context: CallbackContext, chat_id: int, key: str, file_path: str, caption: str):
    """ 获取 GIF 动画 file_id，如果没有缓存则发送新动画并存储 file_id """
    file_id = context.bot_data.get(key)
    if not file_id:
        try:
            # 确保文件存在
            if not os.path.exists(file_path):
                logging.error(f"文件不存在: {file_path}")
                return None

            # 发送动画
            msg = await context.bot.send_animation(
                chat_id=chat_id,
                animation=open(file_path, 'rb'),  # 以二进制模式打开文件
                caption=caption,
                read_timeout=20,  # 增加超时时间
                parse_mode='HTML'
            )
            if msg and msg.animation:
                file_id = msg.animation.file_id
                context.bot_data[key] = file_id  # 确保存储 file_id
                logging.info(f"新动画已发送并存储 file_id: {file_id}")
            else:
                logging.error(f"发送动画失败，msg.animation 为 None: {msg}")
                return None
        except Exception as e:
            logging.error(f"发送动画时发生错误: {e}")
            return None
    return file_id


# 格式化用户下注内容
async def format_bet_data(users_bet):
    output = []
    for user_bet in users_bet:
        user_id = user_bet['user_id']
        name = user_bet['name']
        bets = json.loads(user_bet['bet'])  # 解析 bet 字段的 JSON 字符串
        for bet in bets:
            bet_type = bet['type']
            money = bet['money']
            if bet_type == "大小":
                choice = bet['choice']
                choice = '大' if choice in ['d', 'da'] else '小' if choice in ['x', 'xiao'] else choice
                output.append(f"{name}  {user_id} {choice} {money}u")

            elif bet_type == "大小单双":
                choice = bet['choice']
                choice_map = {"dd": "大单", "ds": "大双", "xs": "小双", "xd": "小单"}
                choice = choice_map.get(choice, choice)
                output.append(f"{name}  {user_id} {choice} {money}u")

            elif bet_type == "豹子":
                choice = bet.get('choice', '')  # 有 choice 就取值，否则为空
                output.append(f"{name}  {user_id} 豹子{choice} {money}u")

            elif bet_type == "和值":
                choice = bet['choice']
                output.append(f"{name}  {user_id} 和值{choice} {money}u")

            elif bet_type == "指定对子":
                choice = bet['choice']
                output.append(f"{name}  {user_id} 指定对子{choice} {money}u")

            elif bet_type == "顺子":
                output.append(f"{name}  {user_id} 顺子 {money}u")

            elif "定位胆" in bet_type:  # 处理 '定位胆' 和 '定位胆y'
                position = bet['position']
                dice_value = bet['dice_value']
                output.append(f"{name}  {user_id} 定位胆{position} {dice_value} {money}u")
    return "\n".join(output)


# 处理下注逻辑的类
class BetHandler:
    """处理下注逻辑的类"""

    @staticmethod
    async def handle_daxiao(bet, sum_dice):
        """处理大小下注"""
        choice = bet['choice']
        if choice in ['d', 'da']:
            choice = '大'
        elif choice in ['x', 'xiao']:
            choice = '小'
        bet_details = f"押注：{choice}，金额：{bet['money']}"
        if (sum_dice > 10 and choice == '大') or (sum_dice <= 10 and choice == '小'):
            return f"✅ {bet_details}，赢了：{bet['money'] * ODDS['大小']}!\n", True
        else:
            return f"❌ {bet_details}，输了：{bet['money']}!\n", False

    @staticmethod
    async def handle_daxiao_danshuang(bet, sum_dice):
        """处理大小单双下注"""
        choice = bet['choice']
        if choice in ['dd', '大单']:
            choice = '大单'
        elif choice in ['ds', '大双']:
            choice = '大双'
        elif choice in ['xs', '小双']:
            choice = '小双'
        elif choice in ['xd', '小单']:
            choice = '小单'
        bet_details = f"押注：{choice}，金额：{bet['money']}"
        if (sum_dice > 10 and sum_dice % 2 == 1 and choice == '大单') or \
                (sum_dice > 10 and sum_dice % 2 == 0 and choice == '大双') or \
                (sum_dice <= 10 and sum_dice % 2 == 1 and choice == '小单') or \
                (sum_dice <= 10 and sum_dice % 2 == 0 and choice == '小双'):
            return f"✅ {bet_details}，赢了：{bet['money'] * ODDS['大小单双']}!\n", True
        else:
            return f"❌ {bet_details}，输了：{bet['money']}!\n", False

    @staticmethod
    async def handle_hezhi(bet, sum_dice):
        """处理和值下注"""
        bet_details = f"押注：和值 {bet['choice']}，金额：{bet['money']}"
        if sum_dice == int(bet['choice']):
            return f"✅ {bet_details}，赢了：{bet['money'] * ODDS['和值'][int(bet['choice'])]}!\n", True
        else:
            return f"❌ {bet_details}，输了：{bet['money']}!\n", False

    @staticmethod
    async def handle_duizi(bet, jieguo):
        """处理对子下注"""
        bet_details = f"押注：对子，金额：{bet['money']}"
        if jieguo[0] == jieguo[1] or jieguo[1] == jieguo[2]:
            return f"✅ {bet_details}，赢了：{bet['money'] * ODDS['对子']}!\n", True
        else:
            return f"❌ {bet_details}，输了：{bet['money']}!\n", False

    @staticmethod
    async def handle_zhiding_duizi(bet, jieguo):
        """处理指定对子下注"""
        bet_details = f"押注：指定对子 {bet['choice']}，金额：{bet['money']}"
        if (jieguo[0] == jieguo[1] == bet['choice']) or (jieguo[1] == jieguo[2] == bet['choice']):
            return f"✅ {bet_details}，赢了：{bet['money'] * ODDS['指定对子']}!\n", True
        else:
            return f"❌ {bet_details}，输了：{bet['money']}!\n", False

    @staticmethod
    async def handle_shunzi(bet, jieguo):
        """处理顺子下注"""
        bet_details = f"押注：顺子，金额：{bet['money']}"
        sorted_dice = sorted(jieguo)
        if sorted_dice[0] + 1 == sorted_dice[1] and sorted_dice[1] + 1 == sorted_dice[2]:
            return f"✅ {bet_details}，赢了：{bet['money'] * ODDS['顺子']}!\n", True
        else:
            return f"❌ {bet_details}，输了：{bet['money']}!\n", False

    @staticmethod
    async def handle_baozi(bet, jieguo):
        """处理豹子下注"""
        bet_details = f"押注：豹子，金额：{bet['money']}"
        if jieguo[0] == jieguo[1] == jieguo[2]:
            return f"✅ {bet_details}，赢了：{bet['money'] * ODDS['豹子']}!\n", True
        else:
            return f"❌ {bet_details}，输了：{bet['money']}!\n", False

    @staticmethod
    async def handle_zhiding_baozi(bet, jieguo):
        """处理指定豹子下注"""
        bet_details = f"押注：豹子 {bet['choice']}，金额：{bet['money']}"
        if jieguo[0] == jieguo[1] == jieguo[2] == bet['choice']:
            return f"✅ {bet_details}，赢了：{bet['money'] * ODDS['指定豹子']}!\n", True
        else:
            return f"❌ {bet_details}，输了：{bet['money']}!\n", False

    @staticmethod
    async def handle_dingweidan(bet, jieguo):
        """处理定位胆下注"""
        bet_details = f"押注：位置 {bet['position']} 的点数 {bet['dice_value']}，金额：{bet['money']}"
        if jieguo[int(bet['position']) - 1] == int(bet.get('dice_value')):
            return f"✅ {bet_details}，赢了：{bet['money'] * ODDS['定位胆']}!\n", True
        else:
            return f"❌ {bet_details}，输了：{bet['money']}!\n", False
