import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler
from handlers import start, check_balance, bet, check_bets
from database import connect_to_db

# 加载环境变量
load_dotenv()

# 获取 Bot Token
TOKEN = os.getenv("BOT_KEY")
if not TOKEN:
    print("❌ Bot Token 没有设置，请检查 .env 文件")
    exit(1)

conn, cursor = connect_to_db()
print(conn, cursor)
if not conn is None:
    print("✅ 数据库连接成功")

# 创建 Bot 应用
app = ApplicationBuilder().token(TOKEN).build()

# 绑定命令处理函数
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("balance", check_balance))
app.add_handler(CommandHandler("bet", bet))
app.add_handler(CommandHandler("mybet", check_bets))

# 运行 Bot
if __name__ == "__main__":
    print("🤖 Bot 正在运行...")
    try:
        app.run_polling()
    except Exception as e:
        print(f"❌ 发生错误：{e}")
