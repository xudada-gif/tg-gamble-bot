import asyncio
import base64
from io import BytesIO
from telegram.ext import CallbackContext,MessageHandler, filters
from telegram import Update
from game_logic_func import issue, safe_send_message, safe_send_dice, dice_photo
from database import connect_to_db, get_users_info_db, update_balance_db
import logging
import os

# logging.basicConfig(level=logging.INFO)  # 设定日志级别
"""
1、游戏开始，用户开始下注，获取用户押注信息
2、摇骰子结束，统计用户下注内容，展示期间所有用户下注信息
3、同时开启摇骰子，@期间投骰子金额最大用户摇，其他用户摇则自动删除，如果25秒没有摇则机器人自动摇
4、获取摇骰子结果，对比用户下注内容，数据库用户金额发生相应改变（赢的扣除5%），押注内容清空
5、展示用户输赢结果，开启下一轮
"""


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

def get_filtered_users(users_info):
    """ 筛选下注用户，并获取最大下注金额和下注最多的用户 """
    filtered_users = [user for user in users_info if user['bet_amount'] > 0]
    max_bet = max((user['bet_amount'] for user in filtered_users), default=0)
    max_users = [user for user in filtered_users if user['bet_amount'] == max_bet]
    return filtered_users, max_users


async def countdown_task(update: Update, context: CallbackContext, chat_id: int, issue_num: int):
    """ 倒计时结束后处理下注和投骰子 """
    game_time = context.bot_data["game_num"]
    await asyncio.sleep(game_time)
    context.bot_data["running"] = False

    gif_stop_game = "./stop_game.gif"
    conn, cursor = connect_to_db()
    users_info = get_users_info_db(cursor)
    context.bot_data["users_info"] = users_info

    filtered_users, max_users = get_filtered_users(users_info)

    user_bets = "\n".join(
        f"{user['name']} {user['user_id']} {user['bet_choice']} {user['bet_amount']}u"
        for user in filtered_users
    ) if filtered_users else "暂无玩家下注"

    re_game = False
    if len(max_users) == 1:
        max_user_name = max_users[0]['name']
        max_user_amount = max_users[0]['bet_amount']
        roll_prompt = f"请掷骰子玩家：@{max_user_name}(总投注 {max_user_amount}u)"
    elif max_users:
        roll_prompt = "存在多个最大下注玩家，由机器人下注"
    else:
        roll_prompt = "无玩家下注，跳过掷骰子阶段"
        re_game = True

    caption_stop_game = f"""
     ----{issue_num}期下注玩家-----
{user_bets}

👉轻触【<code>🎲</code>】复制投掷。
{roll_prompt}

25秒内掷出3颗骰子，超时机器补发，无争议
    """
    # 直接使用缓存的 file_id
    stop_file_id = context.bot_data.get("stop_game_file_id")
    if not stop_file_id:
        await get_animation_file_id(
            context, chat_id, "stop_game_file_id", gif_stop_game,caption_stop_game)
    else:
        await context.bot.send_animation(
            chat_id=chat_id,
            animation=stop_file_id,
            caption=caption_stop_game,
            read_timeout=10,
            parse_mode='HTML'
        )
    if re_game:
        await start_round(update, context)
        return

    # 处理骰子逻辑
    context.bot_data["total_point"] = []
    if len(max_users) == 1:
        context.bot_data["highest_bet_userid"] = max_users[0]['user_id']
    else:
        await bot_dice_roll(update, context)


async def start_round(update: Update, context: CallbackContext):
    """ 开始新一轮游戏 """
    context.bot_data["running"] = True

    app = context.application
    dice_handler = MessageHandler(filters.Dice(), handle_dice_roll)
    app.add_handler(dice_handler)

    chat_id = update.effective_chat.id
    context.bot_data["bet_users"] = {}

    issue_num = await issue()
    gif_start_game = "./start_game.gif"

    caption_start_game = f"""
        <b>期号</b>: {issue_num}

发包手ID: user (id) 庄

🧧底注: 1u 余额(135904.54u)

手摇快三文字下注格式为:

组合: dd10 ds10 xd10 xs10 或 大单10 大双10 小单10 小双10

高倍: bz1 10 bz1 10 或 豹子1 10 豹子2 10

特码: 定位胆位置+数字，例如: 定位胆4 10, dwd4 10, 4y 10
    """
    # 获取或缓存 file_id
    start_file_id = context.bot_data.get("start_game_file_id")
    if not start_file_id:
        await get_animation_file_id(
            context, chat_id, "start_game_file_id", gif_start_game, caption_start_game
        )
    else:
        await context.bot.send_animation(
            chat_id=chat_id,
            animation=start_file_id,
            caption=caption_start_game,
            read_timeout=10,
            parse_mode='HTML'
        )

    context.bot_data["countdown_task"] = asyncio.create_task(countdown_task(update, context, chat_id, issue_num))
    logging.info("新倒计时任务已创建")


async def bot_dice_roll(update: Update, context: CallbackContext):
    """ 机器人自动投骰子 """
    chat_id = update.effective_chat.id
    logging.info(f"开始投骰子 | Chat ID: {chat_id}")

    for _ in range(3):
        dice_message = await safe_send_dice(context, chat_id)
        if dice_message is None:
            await safe_send_message(context, chat_id, "⚠️ 投骰子失败，重试中...")
            await asyncio.sleep(2)
            continue

        context.bot_data["total_point"].append(dice_message.dice.value)

    await process_dice_result(update, context, chat_id)


async def handle_dice_roll(update: Update, context: CallbackContext):
    """ 处理用户投骰子 """
    chat_id = update.effective_chat.id
    logging.info(f"开始投骰子 | Chat ID: {chat_id}")
    # 如果投掷筛子
    if context.bot_data.get("running", False):
        return await update.message.delete()
    if update.message.from_user.id != context.bot_data["highest_bet_userid"]:
        return await update.message.delete()
    if len(context.bot_data["total_point"]) == 3:
        return await update.message.delete()

    dice_value = update.message.dice.value
    await safe_send_message(context, chat_id, f"筛子有效，点数:{dice_value}")
    context.bot_data["total_point"].append(dice_value)

    await process_dice_result(update, context, chat_id)


async def process_dice_result(update: Update, context: CallbackContext, chat_id: int):
    """ 处理投骰子的结果并执行后续逻辑 """
    total_point = context.bot_data["total_point"]

    # 确保收集到 3 次骰子点数
    if len(total_point) < 3:
        return

    total_points = sum(total_point)
    context.bot_data["total_points"].append(total_points)
    result = "大" if total_points > 9 else "小"

    # 获取数据库用户信息
    conn, cursor = connect_to_db()
    users_info = get_users_info_db(cursor)

    # 初始化 bet_users
    context.bot_data.setdefault("bet_users", {})

    # 处理投注信息
    for user in users_info:
        user_id = user['user_id']
        if user['bet_amount'] > 0 and user['bet_choice'] is not None:
            result_status = "赢" if user['bet_choice'] == result else "输"
            bet_user = {
                'name': user['name'],
                'bet_amount': user['bet_amount'],
                'bet_choice': user['bet_choice'],
                'money': user['money'],
                'result_status': result_status
            }
            # 使用 user_id 作为字典的键，存储用户信息
            context.bot_data["bet_users"][user_id] = bet_user
    bet_users = context.bot_data["bet_users"]

    # **生成赢家列表**
    winner_text = "\n".join(
        f"{data['name']} | {user_id} | {data['bet_amount']}"
        for user_id, data in bet_users.items()
    )

    # 生成骰子统计图片
    img_base64, count_big, count_small = await dice_photo(context)
    image_data = base64.b64decode(img_base64)
    image_io = BytesIO(image_data)
    image_io.seek(0)

    # 生成文本信息
    img_text = (
            f"统计：大{count_big}   小{count_small}\n\n\n"
            f"🎲 投掷结果：\n"
            + "\n".join([f"第 {i + 1} 次骰子: {num}" for i, num in enumerate(total_point)])
            + f"\n总点数: {total_points} ({result})\n\n\n"
              f"闲家:\n{winner_text}\n\n\n庄家:"
    )

    await context.bot.send_photo(photo=image_io, chat_id=chat_id, caption=img_text, read_timeout=10)

    # **批量更新数据库**
    win_users = [uid for uid, info in bet_users.items() if info["result_status"] == "赢"]
    lose_users = [uid for uid, info in bet_users.items() if info["result_status"] == "输"]
    win_users_money = [bet_users[uid]["bet_amount"] for uid in win_users]
    lose_users_money = [-bet_users[uid]["bet_amount"] for uid in lose_users]

    # 更新数据库余额
    try:
        if win_users:
            update_balance_db(cursor, win_users, win_users_money)
        if lose_users:
            update_balance_db(cursor, lose_users, lose_users_money)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logging.error(f"数据库更新失败: {e}")

    # 开启新一轮
    await asyncio.sleep(2)
    await start_round(update, context)
