import json
import logging

from pypinyin import lazy_pinyin, Style
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes, CallbackContext
from database import DatabaseManager
from utils import log_command, user_exists
from game_logic_func import format_bet_data
import re
import os
def_money = int(os.getenv("DEF_MONEY"))


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
    """处理所有文本消息"""
    message = update.message.text
    if message is None:  # 避免 re.sub 处理 None
        return
    message = re.sub(r'\s+', ' ', message).strip()
    # 连接数据库
    db = DatabaseManager()
    try:
        user = update.effective_user
        user_id = user.id
        username = user.username
        # 逐个检查规则
        for rule_name, pattern in BETTING_RULES.items():
            match = re.match(pattern, message)
            if match and context.bot_data.get("running"):
                full_name = " ".join(filter(None, [update.effective_user.first_name, update.effective_user.last_name])).strip()
                user_info = db.get_user_info(user_id)
                # 如果数据库中没有用户先创建用户实例
                if not user_exists(user_id):
                    db.add_user(user_id, username, full_name, def_money)
                udb_money = int(user_info['money'])
                bet_data = {}
                if rule_name == '大小':
                    choice = match.group(1)  # 大或小
                    money = int(match.group(2))  # 金额
                    if udb_money < money:
                       return await update.message.reply_text(f"❌余额不足！")
                    choice = ''.join(lazy_pinyin(choice, style=Style.FIRST_LETTER))
                    bet_data = {"type": rule_name, "choice": choice, "money": money}
                elif rule_name == '大小单双':
                    choice = match.group(1)
                    money = int(match.group(2))
                    if udb_money < money:
                       return await update.message.reply_text(f"❌余额不足！")
                    choice = ''.join(lazy_pinyin(choice, style=Style.FIRST_LETTER))
                    bet_data = {"type": rule_name, "choice": choice, "money": money}
                elif rule_name == '和值':
                    choice = match.group(2)  # 和值
                    money = int(match.group(3))  # 金额
                    if udb_money < money:
                       return await update.message.reply_text(f"❌余额不足！")
                    bet_data = {"type": rule_name, "choice": choice, "money": money}
                elif rule_name == '对子':
                    money = int(match.group(2))  # 金额
                    if udb_money < money:
                       return await update.message.reply_text(f"❌余额不足！")
                    bet_data = {"type": rule_name, "money": money}
                elif rule_name == '指定对子':
                    choice = int(match.group(2))
                    money = int(match.group(3))  # 金额
                    if udb_money < money:
                       return await update.message.reply_text(f"❌余额不足！")
                    bet_data = {"type": rule_name, "choice": choice, "money": money}
                elif rule_name == '顺子':
                    money = int(match.group(2))  # 金额
                    if udb_money < money:
                       return await update.message.reply_text(f"❌余额不足！")
                    bet_data = {"type": rule_name, "money": money}
                elif rule_name == '豹子':
                    money = int(match.group(2))  # 金额
                    if udb_money < money:
                       return await update.message.reply_text(f"❌余额不足！")
                    bet_data = {"type": "豹子", "money": money}
                elif rule_name == '指定豹子':
                    choice = match.group(2)
                    money = int(match.group(3))  # 金额
                    if udb_money < money:
                       return await update.message.reply_text(f"❌余额不足！")
                    bet_data = {"type": "豹子", "choice": choice, "money": money}
                elif rule_name == '定位胆':
                    dice = match.group(2)  # 第几个筛子
                    number = match.group(3)  # 第筛子点数
                    money = int(match.group(4))  # 金额
                    if udb_money < money:
                       return await update.message.reply_text(f"❌余额不足！")
                    bet_data = {"type": rule_name, "position": dice, "dice_value": number, "money": money}
                elif rule_name == '定位胆y':
                    dice = match.group(1)
                    money = match.group(2)  # 金额
                    if udb_money < money:
                       return await update.message.reply_text(f"❌余额不足！")
                    bet_data = {"type": rule_name, "position": dice, "dice_value": dice, "money": money}
                db.place_bet(user_id, bet_data)
                await update.message.reply_text(f"{message} 下注成功！")
    except Exception as e:
        logging.error(f"❌ 初始化用户: {e}")
    finally:
        db.close()

@log_command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    初始化用户
    """
    user = update.effective_user
    user_id = user.id
    username = user.username
    full_name = " ".join(filter(None, [update.effective_user.first_name, update.effective_user.last_name])).strip()

    # 查询该用户id在数据库当中是否存在
    if user_exists(user_id):
        return
    db = DatabaseManager()
    try:
        db.add_user(user_id, username, full_name, def_money)
        user_info = db.get_user_info(user_id)

        # 新用户创建完发送一个广告
        if user_info:
            # 图片路径，可以是本地文件路径或者图片 URL, 你也可以使用 URL，例如：image_url = 'https://example.com/business_card.jpg'
            image_path = 'https://img95.699pic.com/desgin_photo/40045/0341_list.jpg!/fw/431/clip/0x300a0a0'  # 本地图片路径
            await update.message.reply_photo(photo=image_path,
                                             caption=f"👋 🎮 欢迎新用户 🌟{user_info['name']}({username})🌟，"
                                                     f"你的初始余额是 ${user_info['money']} 金币！",
                                             read_timeout=10)
        else:
            await update.message.reply_text("❌ 用户初始化失败，请联系群主！")
    except Exception as e:
        logging.error(f"❌ 处理所有文本消息: {e}")
    finally:
        db.close()


# 处理用户进群和退群
async def chat_member_update(update: Update, context: CallbackContext):
    chat_member = update.chat_member
    user = chat_member.new_chat_member.user
    chat_id = update.effective_chat.id
    user_id = user.id
    status = chat_member.new_chat_member.status  # 获取用户状态

    if status == "member":  # 只对新成员生效
        # 限制用户，仅允许阅读消息
        permissions = ChatPermissions(can_send_messages=False)
        await context.bot.restrict_chat_member(chat_id, user_id, permissions)

        # 提示用户必须输入 /start
        welcome_message = f"👋 欢迎 {user.full_name}！\n请发送 **/start** 以解锁聊天权限。"
        await context.bot.send_message(chat_id=chat_id, text=welcome_message)



@log_command
async def show_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询余额"""
    user_id = update.effective_user.id

    db = DatabaseManager()
    try:
        user_info = db.get_user_info(user_id)
        if user_info:
            await update.message.reply_text(f"💰 你的当前余额：{user_info['money']} 金币")
        else:
            await update.message.reply_text("❌ 你还未加入游戏，请使用 /start 加入！")
    except Exception as e:
        logging.error(f"❌ 查询余额: {e}")
    finally:
        db.close()

@log_command
async def cancel_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """取消押注"""
    user_id = update.effective_user.id

    db = DatabaseManager()
    try:
        # 1、先获取用户押注信息
        user_bet = db.get_user_bet_info(user_id)
        bet_list = json.loads(user_bet) if user_bet else []  # 如果 bets 为空，则默认 []
        bet_money = 0
        for i in bet_list:
            bet_money += int(i['money'])
        # 2、情况押注大小，返回押注金额
        db.update_money([user_id],[bet_money])
        # 3、清空押注信息
        db.delete_bet([user_id])
        if bet_money != 0:
            await update.message.reply_text(f"✅ {user_id}:你已成功取消押注，押金{bet_money}已经返回账户。")
        else:
            await update.message.reply_text(f"❌ {user_id}:你还没有押注！")
    except Exception as e:
        logging.error(f"❌ 取消押注: {e}")
    finally:
        db.close()

@log_command
async def show_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询用户押注信息"""
    user_id = update.effective_user.id
    username = " ".join(filter(None, [update.effective_user.first_name, update.effective_user.last_name]))

    db = DatabaseManager()
    try:
        db_user_bet = db.get_user_bet_info(user_id)
        user_bet = {
            'user_id':user_id,
            'name':username,
            'bet':db_user_bet
        }
        res =  await format_bet_data([user_bet])
        await update.message.reply_text(f"🎲 你押注了： \n{res}")
    except Exception as e:
        logging.error(f"❌ 查询用户押注信息: {e}")
    finally:
        db.close()

@log_command
async def fanshui(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """用户反水"""
    user_id = update.effective_user.id
    db = DatabaseManager()
    try:
        today_bets = db.get_user_today_bets(user_id)
        today_money = 0
        for today_bet in today_bets:
            if today_bet['money'] < 0:
                today_money -= today_bet['money']
            else:
                today_money += today_bet['money']
        if today_money < 100:
            await update.message.reply_text(f"您今日流水不足100,当前流水:{today_money}")
            return
        fs = round(today_money/100,2)
        await update.message.reply_text(f"当前流水: {today_money}, 反水: {fs}成功")
    except Exception as e:
        logging.error(f"❌ 用户反水: {e}")
    finally:
        db.close()

@log_command
async def shuying(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询用户当天流水"""
    user_id = update.effective_user.id
    full_name = update.effective_user.full_name
    username = update.effective_user.username
    db = DatabaseManager()
    try:
        today_bets = db.get_user_today_bets(user_id)
        today_money = 0
        for today_bet in today_bets:
            if today_bet['money'] < 0:
                today_money -= today_bet['money']
            else:
                today_money += today_bet['money']

        await update.message.reply_text(f"{full_name}(@{username}) 今日流水: {today_money}")
    except Exception as e:
        logging.error(f"❌ 查询用户当天流水: {e}")
    finally:
        db.close()


