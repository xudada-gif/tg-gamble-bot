from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from database import *
from utils import admin_required, log_command


# 处理所有普通消息
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理所有普通消息"""
    message = update.message.text
    # 获取用户名，如果没有名字则使用默认值
    username = (update.effective_user.first_name or '') + (update.effective_user.last_name or '')
    chat_type = update.message.chat.type

    # 根据消息类型进行处理
    if chat_type == "private":
        # 如果是私聊，回复消息
        await update.message.reply_text(f"📩 你在私聊中说：{message}")
    else:
        # 如果是群组消息，删除无效消息 !!!取消将机器人设为管理员
        await update.message.delete()


# @admin_required
@log_command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    初始化用户
    """
    user_id = update.effective_user.id
    username = update.effective_user.first_name + update.effective_user.last_name

    conn, cursor = connect_to_db()
    if conn is None:
        await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
        return
    # 1、先查询该用户id在数据库当中是否存在
    res = get_user_info(cursor, user_id)
    if res is None:
        await update.message.reply_text(f"❌ {username}: 您已经不是新用户！请开始押注")
        conn.close()
        return

    # 2、如果不存在则添加，存在提示已经不是新用户
    add_user(conn, cursor, user_id, username)
    user_info = get_user_info(cursor, user_id)

    if user_info:
        await update.message.reply_text(f"🎮 欢迎 {user_info['name']}，你的初始余额是 {user_info['money']} 金币！")
    else:
        await update.message.reply_text("❌ 用户初始化失败，请稍后重试！")
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

    user_info = get_user_info(cursor, user_id)

    if user_info:
        await update.message.reply_text(f"💰 你的当前余额：{user_info['money']} 金币")
    else:
        await update.message.reply_text("❌ 你还未加入游戏，请使用 /start 加入！")
    conn.close()


@log_command
async def bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """用户押注"""
    user_id = update.effective_user.id
    args = context.args  # 获取用户输入的参数
    # 参数验证
    if len(args) < 2:
        await update.message.reply_text("❌ 请输入押注金额和方向（格式：/ya 金额 大/小）")
        return

    try:
        amount = int(args[0])  # 解析金额
        choice = args[1]  # 解析涨/跌
        print(amount, choice)
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

        # 查询用户余额
        user_info = get_user_info(cursor, user_id)
        if user_info['bet_amount'] != 0:
            await update.message.reply_text("❌ 你已经存在押注！")
            return
        if not user_info:
            await update.message.reply_text("❌ 你还未加入游戏，请使用 /start 加入！")
            return
        if user_info["money"] < amount:
            await update.message.reply_text(f"❌ 余额不足，你当前只有 {user_info['money']} 金币！")
            return

        # 更新余额并存储押注
        err = place_bet(conn, cursor, user_id, amount, choice)
        if err is None:
            update_balance(conn, cursor, user_id, -amount)  # 扣除押注金额
        await update.message.reply_text(f"✅ 你已成功押注 {amount} 金币，方向：{choice}")
        conn.close()

    except ValueError:
        await update.message.reply_text("❌ 金额必须是整数！")

@log_command
async def cancel_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """取消押注"""
    user_id = update.effective_user.id

    conn, cursor = connect_to_db()
    if conn is None:
        await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
        return

    delete_bet(conn, cursor, user_id)
    await update.message.reply_text(f"✅ 你已成功清空 {user_id} 押注内容。")
    conn.close()

@log_command
async def show_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询用户押注信息"""
    user_id = update.effective_user.id

    conn, cursor = connect_to_db()
    if conn is None:
        await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
        return

    user_info = get_user_info(cursor, user_id)

    if not user_info:
        await update.message.reply_text("❌ 你还未加入游戏，请使用 /start 加入！")
        return

    if user_info["bet_amount"] == 0:
        await update.message.reply_text("❌ 你还未押注！")
        return

    await update.message.reply_text(f"🎲 你押注了 {user_info['bet_amount']} 金币，方向：{user_info['bet_choice']}")
    conn.close()

