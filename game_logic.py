import asyncio
import base64
import json
from collections import defaultdict
from io import BytesIO
from telegram.ext import CallbackContext,MessageHandler, filters
from telegram import Update
from game_logic_func import issue, safe_send_message, safe_send_dice, dice_photo
from database import connect_to_db, get_users_info_db, update_balance_db, get_users_bet_info_db, delete_bets_db
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
        bet_sums[user_id] = {"name": name, "user_id":user_id, "total_money": total_money}
    # 找到押注金额最多的用户
    max_money = max(user["total_money"] for user in bet_sums.values())

    # 筛选出所有押注金额等于最高金额的用户
    top_bettors = [user for user in bet_sums.values() if user["total_money"] == max_money]

    return top_bettors


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
            read_timeout=20,
            parse_mode='HTML'
        )

    context.bot_data["countdown_task"] = asyncio.create_task(countdown_task(update, context, chat_id, issue_num))
    logging.info("新倒计时任务已创建")


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
            update_balance_db(conn,curses,ids,money_values)
            # 2、清空用户下注内容
            delete_bets_db(conn,curses)
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
