import pymysql
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 从环境变量中获取数据库连接信息
host = os.getenv("HOST")
user = os.getenv("USER")
password = os.getenv("PASSWORD")
database = os.getenv("DATABASE")

def connect_to_db():
    """连接到数据库"""
    try:
        print(f"🔌 正在连接到数据库: {host}")
        # 使用 pymysql 连接数据库
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            charset='utf8mb4',  # 推荐使用 utf8mb4 字符集
            cursorclass=pymysql.cursors.DictCursor  # 返回字典形式的查询结果
        )
        cursor = conn.cursor()
        print("✅ 数据库连接成功")
        # 确保 users 表存在
        create_table_if_not_exists(cursor, conn)
        return conn, cursor
    except pymysql.MySQLError as err:
        print(f"❌ 数据库连接失败: {err}")
        return None, None
    except Exception as e:
        print(f"❌ 发生未知错误：{e}")
        return None, None

def create_table_if_not_exists(cursor, conn):
    """检查用户表是否存在，不存在则创建"""
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                money INT DEFAULT 10000,
                bet_amount INT DEFAULT 0,
                bet_choice ENUM('涨', '跌') DEFAULT NULL
            )
        ''')
        conn.commit()
        print("✅ 用户表检查并创建成功（如果表不存在）")
    except pymysql.MySQLError as err:
        print(f"❌ 创建表失败：{err}")

def add_user(conn, cursor, user_id: int, name: str):
    """添加新用户（如果不存在）"""
    try:
        cursor.execute("INSERT IGNORE INTO users (user_id, name) VALUES (%s, %s)", (user_id, name))
        conn.commit()
    except pymysql.MySQLError as err:
        print(f"❌ 添加用户失败：{err}")


def get_user_info(cursor, user_id: int):
    """查询用户信息"""
    cursor.execute("SELECT name, money, bet_amount, bet_choice FROM users WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    if result:
        return {"name": result["name"], "money": result["money"], "bet_amount": result["bet_amount"], "bet_choice": result["bet_choice"]}
    return None


def update_balance(conn, cursor, user_id: int, amount: int):
    """更新用户余额"""
    cursor.execute("UPDATE users SET money = money + %s WHERE user_id = %s", (amount, user_id))
    conn.commit()


def place_bet(conn, cursor, user_id: int, amount: int, choice: str):
    """用户押注"""
    cursor.execute("UPDATE users SET bet_amount = %s, bet_choice = %s WHERE user_id = %s", (amount, choice, user_id))
    conn.commit()


def reset_bets(conn, cursor):
    """重置所有用户的押注信息"""
    cursor.execute("UPDATE users SET bet_amount = 0, bet_choice = NULL")
    conn.commit()
