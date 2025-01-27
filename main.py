from telegram.ext import ApplicationBuilder, CommandHandler,MessageHandler, filters
from handlers import *
from database import connect_to_db, create_table_if_not_exists_db
from handlers_admin import start_game, end_game, show_bets, show_moneys

# 加载环境变量
load_dotenv()

# 获取 Bot Token
TOKEN = os.getenv("BOT_KEY")
if not TOKEN:
    print("❌ Bot Token 没有设置，请检查 .env 文件")
    exit(1)

conn, cursor = connect_to_db()
# 确保 users 表存在
create_table_if_not_exists_db(cursor, conn)
if not conn is None:
    print("✅ 数据库连接成功")

# 创建 Bot 应用
app = ApplicationBuilder().token(TOKEN).build()

# 管理员命令
app.add_handler(MessageHandler(filters.Text(["/start_game", "start_game"]), start_game))
app.add_handler(MessageHandler(filters.Text(["结束", "/结束", "/stop", "stop"]), end_game))
app.add_handler(MessageHandler(filters.Text(["所有余额", "/所有余额"]), show_moneys))
app.add_handler(MessageHandler(filters.Text(["所有押注", "/所有押注"]), show_bets))

# 普通用户命令
app.add_handler(MessageHandler(filters.Dice(), callback_method))
app.add_handler(MessageHandler(filters.Text(["开始", "/开始", "/start", "start"]), start))
app.add_handler(MessageHandler(filters.Text(["余额", "/余额", "/money", "money"]), show_money))
app.add_handler(MessageHandler(filters.Text(["取消", "/取消", "/cancel", "cancel"]), cancel_bet))
app.add_handler(CommandHandler("bet", bet))
app.add_handler(MessageHandler(filters.Text(["查看押注", "/查看押注", "/bet_show", "bet_show"]), show_bet))
# app.add_handler(MessageHandler(filters.Text(["bet", "/bet"]), bet))


# app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))  # 处理文字消息

app.add_handler(MessageHandler(filters.Dice(),callback_method))

# app.add_handler(MessageHandler(filters.PHOTO, handle_message))  # 处理图片
# app.add_handler(MessageHandler(filters.VOICE, handle_message))  # 处理语音
# app.add_handler(MessageHandler(filters.VIDEO, handle_message))  # 处理视频
# app.add_handler(MessageHandler(filters.ANIMATION, handle_message))  # 处理GIF动图
# app.add_handler(MessageHandler(filters., handle_message))  # 处理文件
# app.add_handler(MessageHandler(filters.LOCATION, handle_message))  # 处理位置
# app.add_handler(MessageHandler(filters.CONTACT, handle_message))  # 处理联系人
# app.add_handler(MessageHandler(filters.STICKER, handle_message))  # 处理表情包

# 运行 Bot
if __name__ == "__main__":
    print("🤖 Bot 正在运行...")
    try:
        app.run_polling()
        # 保持机器人运行直到停止
        app.idle()
    except Exception as e:
        print(f"❌ 发生错误：{e}")
