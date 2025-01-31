from telegram import Update
from game_logic import  start_round
from utils import admin_required, log_command
from telegram.ext import ContextTypes, CallbackContext
from database import connect_to_db, get_users_bet_info_db, get_users_moneys_info_db
import os


@log_command
@admin_required
async def start_game(update: Update, context: CallbackContext):
    context.bot_data["game_num"] = int(os.getenv("GAME_NUM"))   #一轮游戏多少秒
    context.bot_data["running"] = False     #游戏是否在进行
    context.bot_data["highest_bet_userid"] = [] #最高押注用户id
    context.bot_data["bet_users"] = {}   #用户押注列表
    context.bot_data["countdown_task"] = None      #创建任务
    context.bot_data["total_point"] = []
    context.bot_data["total_points"]= []    #筛子点数列表
    if context.bot_data["running"]:
        await update.message.reply_text("游戏已经在进行中！")
        return

    await start_round(update, context)


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
    context.bot_data["running"] = False
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
    conn, cursor = connect_to_db()
    if conn is None:
        await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
        return

    users_info = get_users_bet_info_db(cursor)
    sorted_data = sorted(users_info, key=lambda x: x['bet_amount'], reverse=True)
    # 拼接成一段内容
    output = ""
    for user in sorted_data:
        if user['bet_amount'] == 0:
            break
        output += f"{user['name']}|{user['user_id']}|{user['bet_amount']}|{user['bet_choice']}\n"
    # 输出完整内容
    if output == "":
        await update.message.reply_text(f"还没人押注！")
        return
    await update.message.reply_text(f"名字——id——押注金额——押注方向\n{output.strip()}")


@log_command
@admin_required
async def show_moneys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询所有用户余额"""
    conn, cursor = connect_to_db()
    if conn is None:
        await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
        return
    # 排序：按余额从高到低
    users_info = get_users_moneys_info_db(cursor)
    sorted_data = sorted(users_info, key=lambda x: x['money'], reverse=True)
    # 拼接成一段内容
    output = ""
    for user in sorted_data:
        output += f"{user['name']}|{user['user_id']}|{user['money']}\n"
    # 输出完整内容
    await update.message.reply_text(f"名字——id——余额\n{output.strip()}")

