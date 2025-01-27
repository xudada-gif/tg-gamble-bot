import asyncio

import requests
from telegram.ext import CallbackContext
from telegram import Update
from database import connect_to_db, get_users_info_db

# 机器人状态
class GameState:
    def __init__(self):
        self.running = False  # 游戏是否运行
        self.betting_open = False  # 是否可以押注
        self.bets = {}  # 用户押注记录
        self.highest_bet_userid = []  # 押注最高者
        self.countdown_task = None  # 倒计时任务
game_state = GameState()


# 新的一轮游戏
async def start_round(update:Update, context: CallbackContext):
    # 新的一轮开始可以押注
    game_state.betting_open = True
    # 新的一轮开始用户押注信息清空
    game_state.bets = {}
    # 新的一轮开始最高押注者id清空
    game_state.highest_bet_user = []
    if update.message:  # 确保消息有效
        await update.message.reply_text("🔔 新一轮游戏开始！请在 60 秒内押注！")

    # 启用倒计时60秒掷骰子
    game_state.countdown_task = asyncio.create_task(countdown(update,context, 20))



# 开始投筛子
async def countdown(update:Update,context: CallbackContext, seconds: int):
    await asyncio.sleep(seconds)
    # 停止下注
    game_state.betting_open = False
    print("11111111————————————————————————",update.message)
    print("22222222————————————————————————",update.message.dice.value)
    print(update.effective_chat.id)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="⏰ 押注结束，投掷筛子！")
    await handle_dice_roll(update,context)



async def handle_dice_roll(update:Update,context: CallbackContext):
    # 查询押注信息
    _, cursor = connect_to_db()
    res = get_users_info_db(cursor)
    print("3333333333333333————————————————————————",res)

    if not game_state.highest_bet_userid:
        await context.bot.send_message(context.job.chat_id, "无人押注，本轮结束。")
        await start_round(update,context)
        return

    conn, cursor = connect_to_db()
    res = get_users_info_db(cursor)
    print(res)


    # 机器人自动投三个骰子
    total_points = 0
    for _ in range(3):
        dice_message = await context.bot.send_dice(context.job.chat_id, emoji="\U0001F3B2")
        total_points += dice_message.dice.value
        await asyncio.sleep(2)

    result = "跌" if total_points >= 9 else "涨"
    await context.bot.send_message(context.job.chat_id, f"\U0001F3B2 投掷结果：{total_points} ({result})")
    await settle_bets(result, context)
    await start_round(context)

async def settle_bets(result: str, context: CallbackContext):
    for user_id, (amount, choice) in game_state.bets.items():
        if choice == result:
            await context.bot.send_message(user_id, f"恭喜，你赢了 {amount} 金币！")
        else:
            await context.bot.send_message(user_id, f"很遗憾，你输了 {amount} 金币！")



