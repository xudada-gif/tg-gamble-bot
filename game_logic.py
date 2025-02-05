import asyncio
import base64
import json
from collections import defaultdict
from io import BytesIO
from telegram.ext import CallbackContext,MessageHandler, filters
from telegram import Update
from game_logic_func import BetHandler, issue, safe_send_message, safe_send_dice, dice_photo, get_top_bettor, format_bet_data, get_animation_file_id
from database import connect_to_db, update_balance_db, get_users_bet_info_db, delete_bets_db
import logging

# 1、开始新一轮游戏
async def start_round(update: Update, context: CallbackContext):
    """ 开始新一轮游戏 """
    context.bot_data["running"] = True
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
            read_timeout=20,
            parse_mode='HTML'
        )

    context.bot_data["countdown_task"] = asyncio.create_task(countdown_task(update, context, chat_id, issue_num))
    logging.info("新倒计时任务已创建")

# 2、统计下注（不能投注后）
async def countdown_task(update: Update, context: CallbackContext, chat_id: int, issue_num: int):
    """ 倒计时结束后处理下注和投骰子 """
    game_time = context.bot_data["game_num"]
    await asyncio.sleep(game_time)
    context.bot_data["running"] = False

    gif_stop_game = "./stop_game.gif"
    conn, cursor = connect_to_db()
    users_bet = get_users_bet_info_db(cursor)
    context.bot_data["bet_users"] = users_bet
    # 获取本轮用户下注信息
    output = await format_bet_data(users_bet)
    # 获取押注金额最多的用户
    max_users = await get_top_bettor(users_bet)

    re_game = False
    if len(max_users) == 1:
        context.bot_data["highest_bet_userid"] = max_users[0]['user_id']
        roll_prompt = f"请掷骰子玩家：@{max_users[0]['name']} {max_users[0]['user_id']} (总投注 {max_users[0]['total_money']}u)"
    elif max_users:
        roll_prompt = "存在多个最大下注玩家，由机器人下注"
    else:
        roll_prompt = "无玩家下注，跳过掷骰子阶段"
        re_game = True

    caption_stop_game = f"""
     ----{issue_num}期下注玩家-----
{output}

👉轻触【<code>🎲</code>】复制投掷。
{roll_prompt}

<b>25秒内掷出3颗骰子，超时机器补发，无争议</b>
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
            read_timeout=20,
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


# 3、机器人自动投骰子
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

# 3、处理用户投骰子
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

# 4、处理投骰子的结果并执行后续逻辑
async def process_dice_result(update: Update, context: CallbackContext, chat_id: int):
    """ 处理投骰子的结果并执行后续逻辑 """
    try:
        total_point = context.bot_data["total_point"]

        # 确保收集到 3 次骰子点数
        if len(total_point) < 3:
            return

        total_points = sum(total_point)
        if "total_points" not in context.bot_data:
            context.bot_data["total_points"] = []  # 确保是列表

        context.bot_data["total_points"].append(total_points)
        # 下注类型处理映射
        bet_handlers = {
            "大小": BetHandler.handle_daxiao,
            "大小单双": BetHandler.handle_daxiao_danshuang,
            "和值": BetHandler.handle_hezhi,
            "对子": BetHandler.handle_duizi,
            "指定对子": BetHandler.handle_zhiding_duizi,
            "顺子": BetHandler.handle_shunzi,
            "豹子": BetHandler.handle_baozi,
            "指定豹子": BetHandler.handle_zhiding_baozi,
            "定位胆": BetHandler.handle_dingweidan,
            "定位胆y": BetHandler.handle_dingweidan,
        }

        result_message = f"🎲 开奖结果：{total_point}（总和：{total_points}）\n\n"
        bet_users = context.bot_data.get("bet_users")
        user_bet_res = []
        for user_bet in bet_users:
            user_id = user_bet['user_id']
            # 确保 bet 是列表
            bets = user_bet.get('bet', '[]')
            if isinstance(bets, str):
                try:
                    bets = json.loads(bets)  # 解析 JSON 字符串
                except json.JSONDecodeError:
                    logging.error(f"用户 {user_id} 的 bet 字段 JSON 解析失败: {bets}")
                    continue  # 跳过这个用户
            result_message += f"👤 玩家 {user_id} 的押注结果：\n"

            for bet in bets:

                bet_type = bet['type']
                if bet_type in bet_handlers:
                    message, matched = await bet_handlers[bet_type](bet,
                                                                    total_points if bet_type in ["大小", "大小单双","和值"]
                                                                    else total_point)
                    if not matched:
                        bet['money'] = -int(bet['money'])
                    user_bet_res.append({
                        'id':user_id,
                        'money':int(bet['money']),
                        'matched':matched
                    })
                    result_message += message
                else:
                    result_message += f"❌ 未知下注类型：{bet_type}，输了：{bet['money']}!\n"
        # 统计玩家输赢：[{ID:金额}]
        if not user_bet_res:
            money_sum = defaultdict(int)
            for item in user_bet_res:
                money_sum[item['id']] += item['money']
            result = dict(money_sum)
            # 1、更新用户余额
            conn, curses = connect_to_db()
            # 提取键和值
            ids, money_values = zip(*result.items())
            # 转换成列表
            ids = list(ids)
            money_values = list(money_values)
            update_balance_db(conn, curses, ids, money_values)
            # 2、清空用户下注内容
            delete_bets_db(conn, curses)
        # 生成骰子统计图片
        try:
            img_base64, count_big, count_small = await dice_photo(context)
            image_data = base64.b64decode(img_base64)
            image_io = BytesIO(image_data)
            image_io.seek(0)
            await context.bot.send_photo(photo=image_io, chat_id=chat_id, caption=result_message, read_timeout=20)
        except Exception as e:
            logging.error(f"生成或发送骰子统计图片时出错: {e}")

        # 开启新一轮
        await asyncio.sleep(2)
        await start_round(update, context)
    except Exception as e:
        logging.error(f"处理骰子结果时出错: {e}")
