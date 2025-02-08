import json
from typing import Union

import pymysql
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 从环境变量中获取数据库连接信息
host = os.getenv("HOST")
db_user = os.getenv("DB_USER")
password = os.getenv("PASSWORD")
database = os.getenv("DATABASE")

def connect_to_db():
    """
    连接到数据库
    :return:conn, cursor
    """
    try:
        print(f"🔌 正在连接到数据库: {host}")
        # 使用 pymysql 连接数据库
        conn = pymysql.connect(
            host=host,
            user=db_user,
            password=password,
            database=database,
            charset='utf8mb4',  # 推荐使用 utf8mb4 字符集
            cursorclass=pymysql.cursors.DictCursor  # 返回字典形式的查询结果
        )
        print("✅ 数据库连接成功")
        return conn, conn.cursor()
    except (pymysql.MySQLError, Exception) as err:
        print(f"❌ 数据库连接失败: {err}")
        return None, None


def create_table_if_not_exists_db(cursor, conn):
    """
    检查用户表是否存在，不存在则创建
    """
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT UNSIGNED NOT NULL,  
                user_start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 用户加入时间
                username VARCHAR(255) NOT NULL,  -- 用户名
                name VARCHAR(255) NOT NULL,  -- 昵称
                money INT UNSIGNED DEFAULT 0,  -- 余额不允许负值
                top_up_num INT UNSIGNED DEFAULT 0,  
                sell_num INT UNSIGNED DEFAULT 0,  
                bet JSON NULL,  -- JSON 存储押注数据
                PRIMARY KEY (user_id)  -- 定义主键
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,  # 添加 AUTO_INCREMENT
                user_id BIGINT UNSIGNED  NOT NULL,
                amount INT UNSIGNED NOT NULL,
                transaction_type TINYINT NOT NULL,
                transaction_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (transaction_id),  
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,  -- 级联删除
                INDEX idx_user_id (user_id)  -- 索引优化查询
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bets (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,  
                user_id BIGINT UNSIGNED NOT NULL,  
                money INT UNSIGNED NOT NULL,  
                bet_type TINYINT NOT NULL,  -- 允许更多下注类型
                bet_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  
                PRIMARY KEY (id),  
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,  
                INDEX idx_user_id (user_id)  -- 索引优化查询
            );
        ''')
        conn.commit()
        print("✅ 用户表检查并创建成功（如果表不存在）")
    except pymysql.MySQLError as err:
        print(f"❌ 创建表失败：{err}")


def add_user_db(conn, cursor, user_id: int, username: str, name: str, def_money: int):
    """添加新用户（如果不存在）"""
    cursor.execute("INSERT IGNORE INTO users (user_id, username, name, money) VALUES (%s, %s, %s, %s)", (user_id, username, name, def_money))
    conn.commit()

def get_user_id_db(cursor, username:str):
    """通过username获取用户id"""
    cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    result = cursor.fetchone()
    return result

def update_balance_db(conn, cursor, user_ids: list, amounts: list):
    """更新用户余额"""
    for user_id, money in zip(user_ids, amounts):
        money = int(money)
        cursor.execute("UPDATE users SET money = money + %s WHERE user_id = %s OR username = %s", (money, user_id, user_ids))
    conn.commit()


def place_bet_db(conn, cursor, user_id: int, bet: dict):
    """用户押注"""
    bets = get_user_bet_info_db(cursor, user_id)  # 可能返回 None
    bet_list = json.loads(bets) if bets else []  # 如果 bets 为空，则默认 []
    bet_list.append(bet)  # 追加新押注
    cursor.execute("UPDATE users SET bet = %s WHERE user_id = %s", (json.dumps(bet_list), user_id))
    conn.commit()


def delete_bet_db(conn, cursor, user_ids: list):
    """重置指定用户的押注信息"""
    if not user_ids:
        return  # 避免 SQL 语法错误
    placeholders = ",".join(["%s"] * len(user_ids))  # 根据 user_ids 的数量生成占位符
    sql = f"UPDATE users SET bet = JSON_ARRAY() WHERE user_id IN ({placeholders})"
    cursor.execute(sql, user_ids)
    conn.commit()


def delete_bets_db(conn, cursor):
    """重置所有用户的押注信息（JSON 类型）"""
    cursor.execute("UPDATE users SET bet = JSON_ARRAY()")
    conn.commit()


def get_user_info_db(cursor, user_id: Union[int, str]):
    """查询用户信息"""
    cursor.execute("SELECT * FROM users WHERE user_id = %s OR username = %s", (user_id, user_id))  # 需要用 (user_id,) 作为元组
    result = cursor.fetchone()
    return result


def get_users_info_db(cursor):
    """查询用户所有信息"""
    cursor.execute("SELECT * FROM users")
    result = cursor.fetchall()
    return result


def get_user_bet_info_db(cursor, user_id: int):
    """查询指定用户押注信息"""
    cursor.execute("SELECT bet FROM users WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    if not result['bet']:
        result['bet'] = '[]'
    return result['bet']


def get_users_bet_info_db(cursor):
    """查询用户所有押注信息（仅返回 bet 不为空的用户）"""
    cursor.execute("""
        SELECT user_id, name, bet 
        FROM users 
        WHERE bet IS NOT NULL 
          AND TRIM(bet) != '[]' 
          AND TRIM(bet) != ''
    """)
    result = cursor.fetchall()
    return result

def get_users_moneys_info_db(cursor):
    """查询用户所余额信息"""
    cursor.execute("SELECT user_id, name, money FROM users")
    result = cursor.fetchall()
    return result

