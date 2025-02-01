import json

from pypinyin import lazy_pinyin, Style
from telegram import Update
from telegram.ext import ContextTypes, CallbackContext
from database import *
from utils import log_command
import re
def_money = int(os.getenv("DEF_MONEY"))

num = []
counter = 0
en_num = 0
# 存储玩家的下注记录
players_bets = {}
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
# 定义下注规则的正则表达式
BETTING_RULES = {
    '大小': r'^(大|小|d|x|da|xiao)\s*(\d+)$',
    '大小单双': r'^(dd|ds|xs|xd|xiaodan|dadan|大单|大双|小单|小双)\s*(\d+)$',
    '和值': r'^(和值|hz)\s*(4|5|6|7|8|9|10|11|12|13|14|15|16|17)\s*(\d+)$',
    '对子': r'^(对子|dz)\s*(\d+)$',
    '指定对子': r'^(对子|dz)\s*([1-6]) (\d+)$',
    '顺子': r'^(顺子|sz)\s*(\d+)$',
    '豹子': r'^(豹子|bz)\s*(\d+)$',
    '指定豹子': r'^(豹子|bz)\s*(1|2|3|4|5|6) (\d+)$',
    '定位胆': r'^(dwd|定位胆)\s*([1-3])\s*([1-6])\s*(\d+)$',
    '定位胆y': r'^([1-3])\s*y\s*(\d+)$',
}


# 处理所有普通消息
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理所有消息"""
    message = update.message.text
    message = re.sub(r'\s+', ' ', message).strip()
    user = update.message.from_user
    # 逐个检查规则
    for rule_name, pattern in BETTING_RULES.items():
        match = re.match(pattern, message)

        # if match and context.bot_data.get("running"):
        if match:
            bet_data = {}
            if rule_name == '大小':
                choice = match.group(1)  # 大或小
                money = int(match.group(2))  # 金额
                choice = ''.join(lazy_pinyin(choice, style=Style.FIRST_LETTER))
                bet_data = {"type": rule_name, "choice": choice, "money": money}
            elif rule_name == '大小单双':
                choice = match.group(1)
                money = int(match.group(2))
                choice = ''.join(lazy_pinyin(choice, style=Style.FIRST_LETTER))
                bet_data = {"type": rule_name, "choice": choice, "money": money}
            elif rule_name == '和值':
                choice = match.group(2)  # 和值
                money = int(match.group(3))  # 金额
                bet_data = {"type": rule_name, "choice": choice, "money": money}
            elif rule_name == '对子':
                money = int(match.group(2))  # 金额
                bet_data = {"type": rule_name, "money": money}
            elif rule_name == '指定对子':
                choice = int(match.group(2))
                money = int(match.group(3))  # 金额
                bet_data = {"type": rule_name, "choice": choice, "money": money}
            elif rule_name == '顺子':
                money = int(match.group(2))  # 金额
                bet_data = {"type": rule_name, "money": money}
            elif rule_name == '豹子':
                money = int(match.group(2))  # 金额
                bet_data = {"type": "豹子", "money": money}
            elif rule_name == '指定豹子':
                choice = match.group(2)
                money = int(match.group(3))  # 金额
                bet_data = {"type": "豹子", "choice": choice, "money": money}
            elif rule_name == '定位胆':
                dice = match.group(2)  # 第几个筛子
                number = match.group(3)  # 第筛子点数
                money = int(match.group(4))  # 金额
                bet_data = {"type": rule_name, "position": dice, "dice_value": number, "money": money}
            elif rule_name == '定位胆y':
                dice = match.group(1)
                money = match.group(2)  # 金额
                bet_data = {"type": rule_name, "position": dice, "dice_value": dice, "money": money}

            # 连接数据库
            conn, curses = connect_to_db()
            user_id = user.id
            first_name = user.first_name
            last_name = user.last_name or ""  # 可能为空
            full_name = f"{first_name} {last_name}".strip()
            user_info = get_user_info_db(curses, user_id)
            # 如果数据库中没有用户先创建用户实例
            if not user_info:
                add_user_db(conn, curses, user_id, full_name, def_money)
            place_bet_db(conn, curses, user_id, bet_data)

            await update.message.reply_text(f"{message} 下注成功！")

    # chat_type = update.message.chat.type
    # message = update.message.text
    #
    # # 根据消息类型进行处理 群 supergroup
    # if chat_type == "private" and message == "/start":
    #     # 如果是私聊，回复消息
    #     # 图片路径，可以是本地文件路径或者图片 URL
    #     image_path = './code.png'  # 本地图片路径
    #     # 你也可以使用 URL，例如：image_url = 'https://example.com/business_card.jpg'
    #     # 发送图片和文本
    #     await update.message.reply_photo(photo=image_path,
    #                                      caption="👋 欢迎！这是我的名片，期待与您的合作！\n\n可以随时联系我，有任何问题都可以询问。")
    #
    # if chat_type == "supergroup":
    #     # 如果是群组消息，删除无效消息 !!!需要将机器人设为管理员
    #     await update.message.delete()


@log_command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    开始游戏
    """
    user_id = update.effective_user.id
    username = " ".join(filter(None, [update.effective_user.first_name, update.effective_user.last_name]))

    conn, cursor = connect_to_db()
    if conn is None:
        await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
        return
    # 1、先查询该用户id在数据库当中是否存在
    res = get_user_info_db(cursor, user_id)
    if res and isinstance(res, list) and len(res) > 0 and "user_id" in res[0]:
        await update.message.reply_text(f"❌ {username}: 您已经不是新用户！请开始押注！")
        conn.close()
        return

    # 2、如果不存在则添加，存在提示已经不是新用户
    add_user_db(conn, cursor, user_id, username,def_money)
    user_info = get_user_info_db(cursor, user_id)

    # 新用户创建完发送一个广告
    if user_info:
        # 图片路径，可以是本地文件路径或者图片 URL, 你也可以使用 URL，例如：image_url = 'https://example.com/business_card.jpg'
        image_path = 'https://img95.699pic.com/desgin_photo/40045/0341_list.jpg!/fw/431/clip/0x300a0a0'  # 本地图片路径
        await update.message.reply_photo(photo=image_path,
                                         caption=f"👋 🎮 欢迎新用户 🌟{user_info[0]['name']}🌟，"
                                                 f"你的初始余额是 ${user_info[0]['money']} 金币！",
                                         read_timeout=10)

    else:
        await update.message.reply_text("❌ 用户初始化失败，请联系群主！")
    conn.close()


@log_command
async def show_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询余额"""
    user_id = update.effective_user.id

    conn, cursor = connect_to_db()
    if conn is None:
        await update.message.reply_text("❌ 数据库连接失败，请稍后重试！")
        return

    user_info = get_user_info_db(cursor, user_id)

    if user_info:
        await update.message.reply_text(f"💰 你的当前余额：{user_info[0]['money']} 金币")
    else:
        await update.message.reply_text("❌ 你还未加入游戏，请使用 /start 加入！")
    conn.close()


@log_command
async def bet(update: Update, context: CallbackContext):
    conn, curses = connect_to_db()
    res = get_users_bet_info_db(curses)
    print(res)

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
    if res[0]["bet_amount"] < 0:
        await update.message.reply_text(f"❌ {user_id}:你没有任何押注！")
        return
    # 2、情况押注大小，返回押注金额
    update_balance_db(cursor, [user_id], [res[0]["bet_amount"]])
    delete_bet_db(cursor, [user_id])
    await update.message.reply_text(f"✅ {user_id}:你已成功取消押注，押金已经返回账户。")
    conn.close()


@log_command
async def show_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询用户押注信息"""
    user_id = update.effective_user.id

    conn, cursor = connect_to_db()

    user_bet = get_user_bet_info_db(cursor, user_id)

    await update.message.reply_text(f"🎲 你押注了： {user_bet}")
    conn.close()

