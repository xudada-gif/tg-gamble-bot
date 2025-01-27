from telegram import Update
from telegram.ext import ContextTypes, CallbackContext
from database import *
from utils import admin_required, log_command
from game_logic import game_state, start_round
import asyncio
def_money = int(os.getenv("DEF_MONEY"))

num = []
counter = 0
en_num = 0

# 摇筛子
async def callback_method(update: Update, context: CallbackContext):
    global num, counter,en_num

    dice_value = update.message.dice.value  # 获取骰子的点数
    # chat_type = update.message.chat.type
    # if chat_type == "private":
    #     return
    # 判断骰子点数是否是 1, 2, 3，如果不是则替换为 1、2、3 中的一个点数
    print(dice_value)
    if dice_value in [1, 2, 3]:
        await update.message.reply_text(f"你摇到了点数: {dice_value}")
        num.append(dice_value)
        counter += 1
        if counter > 2:
            en_num = num[0] + num[1] + num[2]
            await update.message.reply_text(f"股子三次点数为: {num[0]}+{num[1]}+{num[2]}={en_num}")
    else:
        # 删除原始骰子消息
        while True:
            message = await update.message.reply_dice(emoji="🎲")  # 发送骰子
            await asyncio.sleep(0.1)  # 等待 Telegram 服务器返回点数
            if message.dice.value in [1, 2, 3]:  # 只允许点数 1、2、3
                num.append(message.dice.value)
                counter += 1
                await update.message.reply_text(f"机器人摇到了点数: {message.dice.value}")
                await update.message.delete()
                if counter > 2:
                    en_num = num[0] + num[1] + num[2]
                    await message.reply_text(f"股子三次点数为: {num[0]}+{num[1]}+{num[2]}={en_num}")
                break  # 结束循环，保留这个骰子
            else:
                await message.delete()  # 删除不符合要求的骰子
        # await update.message.chat.send_dice()
        # # await update.message.delete()
    print(f"counter: {counter},num: {num}")
    if counter > 2:
        num = []
        counter = 0


# 处理所有普通消息
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理所有普通消息"""
    # 检查文本消息
    if update.message.text:
        await update.message.reply_text(f"你发送了文字消息：{update.message.text}")
    # 检查图片消息
    elif update.message.photo:
        await update.message.reply_text(f"你发送了图片消息！")
    # 检查语音消息
    elif update.message.voice:
        await update.message.reply_text(f"你发送了语音消息！")
    # 检查视频消息
    elif update.message.video:
        await update.message.reply_text(f"你发送了视频消息！")
    # 检查GIF动图消息
    elif update.message.animation:
        await update.message.reply_text(f"你发送了GIF动图消息！")
    # 检查文件消息
    elif update.message.document:
        await update.message.reply_text(f"你发送了文件消息！")
    # 检查位置消息
    elif update.message.location:
        await update.message.reply_text(f"你发送了位置消息！")
    # 检查联系人消息
    elif update.message.contact:
        await update.message.reply_text(f"你发送了联系人消息！")
    # 检查表情包消息
    elif update.message.sticker:
        await update.message.reply_text(f"你发送了表情包消息！")
    elif update.message.dice:

        await update.message.reply_text(f"筛子！")
    else:
        await update.message.reply_text(f"未能识别此消息类型。")



    chat_type = update.message.chat.type
    message = update.message.text
    print(update.message)

    # 根据消息类型进行处理 群 supergroup
    if chat_type == "private" and message == "/start":
        # 如果是私聊，回复消息
        # 图片路径，可以是本地文件路径或者图片 URL
        image_path = './code.png'  # 本地图片路径
        # 你也可以使用 URL，例如：image_url = 'https://example.com/business_card.jpg'
        # 发送图片和文本
        await update.message.reply_photo(photo=image_path,
                                         caption="👋 欢迎！这是我的名片，期待与您的合作！\n\n可以随时联系我，有任何问题都可以询问。")

    if chat_type == "supergroup":
        # 如果是群组消息，删除无效消息 !!!需要将机器人设为管理员
        await update.message.delete()


@log_command
@admin_required
async def start_game(update: Update, context: CallbackContext):
    if game_state.running:
        await update.message.reply_text("游戏已经在进行中！")
        return
    game_state.running = True

    await update.message.reply_text("游戏开始！\U0001F3B2 倒计时 60 秒一轮！")
    await start_round(update, context)


@log_command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    开始游戏
    """
    user_id = update.effective_user.id
    username = update.effective_user.first_name + update.effective_user.last_name

    conn, cursor = connect_to_db()
    if conn is None:
        await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
        return
    # 1、先查询该用户id在数据库当中是否存在
    res = get_user_info_db(cursor, user_id)
    if res is not None:
        await update.message.reply_text(f"❌ {username}: 您已经不是新用户！请开始押注！")
        conn.close()
        return

    # 2、如果不存在则添加，存在提示已经不是新用户
    add_user_db(conn, cursor, user_id, username,def_money)
    user_info = get_user_info_db(cursor, user_id)
    print(user_info)
    # 新用户创建完发送一个广告
    if user_info:
        # 图片路径，可以是本地文件路径或者图片 URL, 你也可以使用 URL，例如：image_url = 'https://example.com/business_card.jpg'
        image_path = 'https://img95.699pic.com/desgin_photo/40045/0341_list.jpg!/fw/431/clip/0x300a0a0'  # 本地图片路径
        await update.message.reply_photo(photo=image_path,
                                         caption="👋 欢迎！这是我的名片，期待与您的合作！\n\n可以随时联系我，有任何问题都可以询问。",
                                         read_timeout=10)


        await update.message.reply_text(f"🎮 欢迎新用户 {user_info['name']}，你的初始余额是 {user_info['money']} 金币！")
    else:
        await update.message.reply_text("❌ 用户初始化失败，请联系群主！")
    conn.close()


@log_command
@admin_required
async def show_balances(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询所有用户余额"""
    user_id = update.effective_user.id

    conn, cursor = connect_to_db()
    if conn is None:
        await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
        return


    await update.message.reply_text(f"{user_id}，这个是查询所有用户余额")

# async def stop(update: Update, context: CallbackContext):
#     game_state.running = False
#     game_state.betting_open = False
#     if game_state.countdown_task:
#         game_state.countdown_task.cancel()
#     await update.message.reply_text("游戏已停止！")


@log_command
@admin_required
async def end_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    结束游戏
    1、机器摇骰子
    2、获取所有押注的用户获取值进行判断
    3、押注对的用户把押注翻倍增加到余额
    4、清空所有的用户押注
    """
    username = update.effective_user.first_name + update.effective_user.last_name
    conn, cursor = connect_to_db()
    if conn is None:
        await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
        return

    await update.message.reply_text(f"{username}，这个是结束游戏")


@log_command
@admin_required
async def show_bets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询所有用户押注信息"""
    user_id = update.effective_user.id

    conn, cursor = connect_to_db()
    if conn is None:
        await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
        return

    await update.message.reply_text(f"{user_id}，这个是查询所有用户押注信息")


@log_command
async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询余额"""
    user_id = update.effective_user.id

    conn, cursor = connect_to_db()
    if conn is None:
        await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
        return

    user_info = get_user_info_db(cursor, user_id)

    if user_info:
        await update.message.reply_text(f"💰 你的当前余额：{user_info['money']} 金币")
    else:
        await update.message.reply_text("❌ 你还未加入游戏，请使用 /start 加入！")
    conn.close()


@log_command
async def place_bet(update: Update, context: CallbackContext):
    if not game_state.betting_open:
        await update.message.reply_text("现在不能押注！")
        return

    try:
        amount, choice = context.args
        amount = int(amount)
        if amount <= 0:
            await update.message.reply_text("❌ 押注金额必须大于 0！")
            return
        if choice not in ["大", "小"]:
            await update.message.reply_text("❌ 押注方向必须是 '大' 或 '小'！")
            return

        conn, cursor = connect_to_db()
        if conn is None:
            await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
            return

        user_id = update.effective_user.id
        # 查询用户余额
        user_info = get_user_info_db(cursor, user_id)
        if user_info['bet_choice'] in ["大", "小"]:
            await update.message.reply_text("❌ 你本轮已经存在押注！")
            return
        if not user_info:
            await update.message.reply_text("❌ 您还未进行任何充值，请使用 /start 加入！")
            return
        if user_info["money"] < amount:
            await update.message.reply_text(f"❌ 余额不足，你当前只有 {user_info['money']} 金币！ 请添加机器人充值！")
            return

        # 更新余额并存储押注
        place_bet_db(conn, cursor, user_id, amount, choice)
        update_balance_db(conn, cursor, user_id, -amount)  # 扣除押注金额
        user_info = get_user_info_db(cursor, user_id)
        username = update.effective_user.first_name + update.effective_user.last_name
        await update.message.reply_text(f"{choice}{amount} 下注成功✅\n------------\n{username}  id:{user_id}\n------------\n余额：{user_info['money']}(冻结：{amount})")
        conn.close()

    except ValueError:
        await update.message.reply_text("押注格式错误！示例：/bet 100 大")
        return
    context.user_data[update.message.from_user.id] = (amount, choice)
    context.bot_data["global_counter"] = (amount, choice)
    game_state.bets[update.message.from_user.id] = (amount, choice)
    print(game_state.bets)

@log_command
async def cancel_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """取消押注"""
    user_id = update.effective_user.id

    conn, cursor = connect_to_db()
    if conn is None:
        await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
        return

    # 1、先获取用户押注信息
    res = get_user_info_db(cursor, user_id)
    if res["bet_amount"] < 0:
        await update.message.reply_text(f"❌ {user_id}:你没有任何押注！")
        return
    # 2、情况押注大小，返回押注金额
    update_balance_db(conn, cursor, user_id, res["bet_amount"])
    delete_bet_db(conn, cursor, user_id)
    await update.message.reply_text(f"✅ {user_id}:你已成功取消押注，押金已经返回账户。")
    conn.close()


@log_command
async def show_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询用户押注信息"""
    user_id = update.effective_user.id

    conn, cursor = connect_to_db()
    if conn is None:
        await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
        return

    user_info = get_user_info_db(cursor, user_id)

    if not user_info:
        await update.message.reply_text("❌ 你还未加入游戏，请使用 /start 加入！")
        return

    if user_info["bet_amount"] == 0:
        await update.message.reply_text("❌ 你还未押注！")
        return

    await update.message.reply_text(f"🎲 你押注了 {user_info['bet_amount']} 金币，方向：{user_info['bet_choice']}")
    conn.close()

