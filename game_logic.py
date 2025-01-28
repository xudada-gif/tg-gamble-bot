import asyncio
from telegram.ext import CallbackContext
from telegram import Update
from database import connect_to_db, get_users_info_db, update_balance_db, delete_bet_db
from telegram.error import RetryAfter, TimedOut, NetworkError
import logging

logging.basicConfig(level=logging.INFO)  # 设定日志级别


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


async def start_round(update: Update, context: CallbackContext):
    """ 开始新一轮游戏 """
    if not context.bot_data.get("running", False):
        return

    # # 防止重复开启倒计时
    # old_task = context.bot_data.get("countdown_task")
    # if old_task:
    #     if not old_task.done():
    #         logging.warning("⏳ 倒计时任务仍在运行，跳过本次 start_round")
    #         await start_round(update, context)
    #         return  # 跳过启动新一轮


    chat_id = update.effective_chat.id
    context.bot_data["bet_users"] = {}  # 清空上轮押注信息


    await safe_send_message(context, chat_id, f"🔔 新一轮游戏开始！请在 {context.bot_data['game_num']} 秒内押注！")

    async def countdown():
        await asyncio.sleep(context.bot_data["game_num"])
        await safe_send_message(context, chat_id, "⏰ 押注结束，投掷骰子！")
        await handle_dice_roll(update, context)

    # 创建新的倒计时任务
    context.bot_data["countdown_task"] = asyncio.create_task(countdown())
    logging.info("新倒计时任务已创建")


async def handle_dice_roll(update: Update, context: CallbackContext):
    """ 处理投骰子 """
    chat_id = update.effective_chat.id
    logging.info(f"开始投骰子 | Chat ID: {chat_id}")

    conn, cursor = connect_to_db()  # 获取数据库连接
    try:
        res = get_users_info_db(cursor)
        if not res:
            logging.info("数据库查询结果为空")
            return

        if not any(i['bet_choice'] is not None for i in res):
            await safe_send_message(context, chat_id, "无人押注，本轮结束。")
            await asyncio.sleep(3)
            await start_round(update, context)
            return

        context.bot_data["bet_users"] = {
            i['user_id']: (i['bet_amount'], i['bet_choice'])
            for i in res if i['bet_choice'] is not None
        }

        logging.info("准备投骰子")
        total_points = 0
        dice_results = []

        for _ in range(3):
            dice_message = await safe_send_dice(context, chat_id)
            if dice_message is None:
                await safe_send_message(context, chat_id, "⚠️ 投骰子失败，重试中...")
                await asyncio.sleep(2)
                continue

            dice_results.append(dice_message.dice.value)
            total_points += dice_message.dice.value

        logging.info(f"投骰子结果：{dice_results}")
        result = "大" if total_points > 9 else "小"

        result_text = f"🎲 投掷结果：\n" + "\n".join(
            [f"第 {i + 1} 次骰子: {num}" for i, num in enumerate(dice_results)]
        ) + f"\n总点数: {total_points} ({result})"
        await safe_send_message(context, chat_id, result_text)

        winners = [user for user in res if user['bet_choice'] == result]

        if winners:
            winner_text = "\n".join(f"{user['name']} | {user['user_id']} | {user['bet_amount']}" for user in winners)
            await safe_send_message(context, chat_id, f"🎉 恭喜以下玩家押注正确！\n{winner_text}")

            user_ids = [user['user_id'] for user in winners]
            bet_amounts = [user['bet_amount'] for user in winners]
            print("123")
            # 批量 SQL 操作
            try:
                update_balance_db(cursor, user_ids, bet_amounts)  # 这里的函数需要支持列表批量更新
                delete_bet_db(cursor, user_ids)
                conn.commit()  # 提交事务
            except Exception as e:
                conn.rollback()  # 遇到错误回滚，防止数据库数据损坏
                logging.error(f"数据库更新失败: {e}")

        else:
            await safe_send_message(context, chat_id, "本轮没有用户押注胜利！")
    finally:
        conn.close()  # 确保数据库连接总是被关闭
    # 开启新一轮
    await start_round(update, context)

