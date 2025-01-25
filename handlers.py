from telegram import Update
from telegram.ext import ContextTypes
from database import connect_to_db, add_user, get_user_info, update_balance, place_bet, reset_bets

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """初始化用户"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name

    conn, cursor = connect_to_db()
    if conn is None:
        await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
        return

    add_user(conn, cursor, user_id, username)
    user_info = get_user_info(cursor, user_id)

    if user_info:
        await update.message.reply_text(f"🎮 欢迎 {user_info['name']}，你的初始余额是 {user_info['money']} 金币！")
    else:
        await update.message.reply_text("❌ 用户初始化失败，请稍后重试！")
    conn.close()


async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """用户押注"""
    user_id = update.effective_user.id
    args = context.args  # 获取用户输入的参数

    # 参数验证
    if len(args) < 2:
        await update.message.reply_text("❌ 请输入押注金额和方向（格式：/bet 金额 涨/跌）")
        return

    try:
        amount = int(args[0])  # 解析金额
        choice = args[1]  # 解析涨/跌

        if amount <= 0:
            await update.message.reply_text("❌ 押注金额必须大于 0！")
            return

        if choice not in ["涨", "跌"]:
            await update.message.reply_text("❌ 押注方向必须是 '涨' 或 '跌'！")
            return

        conn, cursor = connect_to_db()
        if conn is None:
            await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
            return

        # 查询用户余额
        user_info = get_user_info(cursor, user_id)
        if not user_info:
            await update.message.reply_text("❌ 你还未加入游戏，请使用 /start 加入！")
            return

        if user_info["money"] < amount:
            await update.message.reply_text(f"❌ 余额不足，你当前只有 {user_info['money']} 金币！")
            return

        # 更新余额并存储押注
        update_balance(conn, cursor, user_id, -amount)  # 扣除押注金额
        place_bet(conn, cursor, user_id, amount, choice)

        await update.message.reply_text(f"✅ 你已成功押注 {amount} 金币，方向：{choice}")
        conn.close()

    except ValueError:
        await update.message.reply_text("❌ 金额必须是整数！")


async def check_bets(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
