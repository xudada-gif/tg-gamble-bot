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
def_amount = int(os.getenv("DEF_AMOUNT"))

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
        return conn, cursor
    except pymysql.MySQLError as err:
        print(f"❌ 数据库连接失败: {err}")
        return None, None
    except Exception as e:
        print(f"❌ 发生未知错误：{e}")
        return None, None

def create_table_if_not_exists(cursor, conn):
    """
    检查用户表是否存在，不存在则创建
    """
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT NOT NULL, # user_id 列为 BIGINT 类型，设置为主键，确保每个用户的 ID 唯一
                user_start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  # 用户加入时间
                name VARCHAR(255) NOT NULL, # name 列为 VARCHAR 类型，最大长度为 255，不能为空
                money INT DEFAULT 0,    # money 列为 INT 类型，默认值为 0，用于记录用户的金额
                top_up_num INT DEFAULT 0,   # top_up_num 列为 INT 类型，默认值为 0，用于记录用户充值次数
                sell_num INT DEFAULT 0,     # sell_num 列为 INT 类型，默认值为 0，用于记录用户出售次数
                bet_amount INT DEFAULT 0,   # bet_amount 列为 INT 类型，默认值为 0，用于记录用户的投注金额
                bet_choice ENUM('涨', '跌') DEFAULT NULL,  # bet_choice 列为 ENUM 类型，取值范围是 '涨' 或 '跌'，默认值为 NULL（表示用户未选择）
                PRIMARY KEY (user_id)  # 定义一个主键
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id BIGINT UNSIGNED NOT NULL,  # 使用 BIGINT 存储唯一 ID
                user_id BIGINT NOT NULL,  # 用户ID，关联到 users 表的 user_id
                amount INT NOT NULL,  # 充值或提取金额
                transaction_type TINYINT(1) NOT NULL,  # 交易类型，0 表示提取，1 表示充值
                transaction_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  # 交易时间，默认为当前时间
                FOREIGN KEY (user_id) REFERENCES users(user_id),  # 设置外键约束，确保 user_id 在 users 表中存在
                PRIMARY KEY (transaction_id)  # 定义一个主键
            );
        ''')
        conn.commit()
        print("✅ 用户表检查并创建成功（如果表不存在）")
    except pymysql.MySQLError as err:
        print(f"❌ 创建表失败：{err}")

def add_user(conn, cursor, user_id: int, name: str):
    """添加新用户（如果不存在）"""
    try:
        cursor.execute("INSERT IGNORE INTO users (user_id, name, bet_amount) VALUES (%s, %s, %s)", (user_id, name, def_amount))
        conn.commit()
    except pymysql.MySQLError as err:
        print(f"❌ 添加用户失败：{err}")


def get_user_info(cursor, user_id: int):
    """查询用户信息"""
    cursor.execute("SELECT name, money, bet_amount, bet_choice FROM users WHERE user_id = %s", user_id)
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
    print(f"UPDATE users SET bet_amount = {amount}, bet_choice = {choice} WHERE user_id = {user_id}")
    try:
        cursor.execute("UPDATE users SET bet_amount = %s, bet_choice = %s WHERE user_id = %s", (amount, choice, user_id))
        conn.commit()
    except pymysql.MySQLError as err:
        return err


def delete_bet(conn, cursor, user_id: int):
    """重置制定用户的押注信息"""
    cursor.execute("UPDATE users SET bet_amount = 0, bet_choice = NULL WHERE user_id = %s", user_id)
    conn.commit()


def delete_bets(conn, cursor):
    """重置所有用户的押注信息"""
    cursor.execute("UPDATE users SET bet_amount = 0, bet_choice = NULL")
    conn.commit()
