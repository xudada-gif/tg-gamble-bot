from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ChatMemberHandler
from handlers import start,show_money,cancel_bet,show_bet,handle_message,chat_member_update,fanshui,shuying
from database import connect_to_db, create_table_if_not_exists_db
from handlers_admin import start_game, end_game, show_bets, get_user_id, show_moneys, user_money_add, user_money_rev
from game_logic import handle_dice_roll
from dotenv import load_dotenv
import os


# 加载环境变量
load_dotenv()

# 获取 Bot Token
TOKEN = os.getenv("BOT_KEY")
if not TOKEN:
    print("❌ Bot Token 没有设置，请检查 .env 文件")
    exit(1)

conn, cursor = connect_to_db()
if conn:
    # 确保 users 表存在
    create_table_if_not_exists_db(cursor, conn)
    print("✅ 数据库连接成功")

# 创建 Bot 应用
app = ApplicationBuilder().token(TOKEN).build()

# 管理员命令
app.add_handler(CommandHandler('start_game',start_game))
app.add_handler(CommandHandler('stop',end_game))
app.add_handler(CommandHandler('show_moneys',show_moneys))
app.add_handler(CommandHandler('show_bets',show_bets))
app.add_handler(CommandHandler('add',user_money_add))
app.add_handler(CommandHandler('rev',user_money_rev))
app.add_handler(CommandHandler('getid',get_user_id))
# 普通用户命令
app.add_handler(MessageHandler(filters.Text(["开始", "/开始", "/start", "start"]), start))
app.add_handler(MessageHandler(filters.Text(["余额", "/余额", "/money", "money"]), show_money))
app.add_handler(MessageHandler(filters.Text(["取消", "/取消", "/cancel", "cancel"]), cancel_bet))
app.add_handler(MessageHandler(filters.Text(["查看押注", "/查看押注", "/bet_show", "bet_show"]), show_bet))
app.add_handler(MessageHandler(filters.Text(["反水"]), fanshui))
app.add_handler(MessageHandler(filters.Text(["slsy"]), shuying))

# 处理骰子消息
app.add_handler(MessageHandler(filters.Dice(), handle_dice_roll))

# 监听群成员变动
app.add_handler(ChatMemberHandler(chat_member_update, ChatMemberHandler.CHAT_MEMBER))

# 处理文字消息
app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))


# 运行 Bot
if __name__ == "__main__":
    print("🤖 Bot 正在运行...")
    try:
        app.run_polling()
        # 保持机器人运行直到停止
    except Exception as e:
        print(f"❌ 发生错误：{e}")
