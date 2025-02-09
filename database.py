import json
from typing import Union
from functools import lru_cache
import pymysql
import os
from dotenv import load_dotenv


# 从环境变量中获取数据库连接信息
host = os.getenv("HOST")
db_user = os.getenv("DB_USER")
password = os.getenv("PASSWORD")
database = os.getenv("DATABASE")

# **定义下注类型映射**
BET_TYPE_MAPPING = {
    "大小": 1,  # 例如 "大小" 映射为 1
    "大小单双": 2,  # 例如 "单双" 映射为 2
    "和值": 3,
    "对子": 4,
    "指定对子": 5,
    "顺子": 6,
    "豹子": 7,
    "指定豹子": 8,
    "定位胆": 9
}

def connect_to_db():
    """
    连接到数据库
    :return:conn, cursor
    """
    try:
        conn = pymysql.connect(
            host=host,
            user=db_user,
            password=password,
            database=database,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
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
                amount INT NOT NULL,
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
                money INT NOT NULL,
                bet_type TINYINT NOT NULL,  -- 允许更多下注类型
                win TINYINT(1) NOT NULL DEFAULT 0,  -- 0: 输, 1: 赢
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

# 加载环境变量
load_dotenv()
@lru_cache(maxsize=10)
def get_db_connection():
    return connect_to_db()

class DatabaseManager:
    def __init__(self):
        self.conn, self.cursor = get_db_connection()

    def add_user(self, user_id:int, username: str, name: str, def_money: int):
        """添加新用户（如果不存在）"""
        self.cursor.execute("INSERT IGNORE INTO users (user_id, username, name, money) VALUES (%s, %s, %s, %s)", (user_id, username, name, def_money))
        self.conn.commit()

    def add_bet_info(self, user_id: int, money: int, bet_type:str, win):
        """添加用户押注信息"""
        bet_type = BET_TYPE_MAPPING.get(bet_type)
        self.cursor.execute("INSERT IGNORE INTO bets (user_id, money, bet_type, win) VALUES (%s, %s, %s, %s)", (user_id, money, bet_type, win))
        self.conn.commit()

    def get_user_id(self, username: str):
        """通过username获取用户id"""
        self.cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        result = self.cursor.fetchone()
        return result

    def update_money(self, user_ids: list, amounts: list):
        """更新用户余额"""
        updates = []
        for user_id, money in zip(user_ids, amounts):
            money = int(money)
            if isinstance(user_id, int):
                updates.append((money, user_id, None))  # None 作为占位符
            elif isinstance(user_id, str):
                updates.append((money, None, user_id))  # None 作为占位符

        self.cursor.executemany("UPDATE users SET money = money + %s WHERE user_id = %s OR username = %s", updates)
        self.conn.commit()

    def place_bet(self, user_id: int, bet: dict):
        """用户下注"""
        bets = self.get_user_bet_info(user_id)
        bet_list = json.loads(bets) if bets else []
        bet_list.append(bet)
        self.cursor.execute("UPDATE users SET bet = %s WHERE user_id = %s", (json.dumps(bet_list), user_id))
        self.conn.commit()

    def delete_bet(self,user_ids:list):
        """重置指定用户的押注信息"""
        if not user_ids:
            return  # 避免 SQL 语法错误
        placeholders = ",".join(["%s"] * len(user_ids))  # 根据 user_ids 的数量生成占位符
        sql = f"UPDATE users SET bet = JSON_ARRAY() WHERE user_id IN ({placeholders})"
        self.cursor.execute(sql, user_ids)
        self.conn.commit()

    def delete_bets_db(self):
        """重置所有用户的押注信息（JSON 类型）"""
        self.cursor.execute("UPDATE users SET bet = JSON_ARRAY()")
        self.conn.commit()

    def get_user_info(self, user_id: Union[int, str]):
        """查询用户信息"""
        if isinstance(user_id, int):  # user_id 是数字 ID
            self.cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        elif isinstance(user_id, str):  # user_id 是用户名
            self.cursor.execute("SELECT * FROM users WHERE username = %s", (user_id,))
        else:
            return None  # 处理错误情况
        return self.cursor.fetchone()  # 返回查询结果

    def get_users_info(self):
        """查询用户所有信息"""
        self.cursor.execute("SELECT * FROM users")
        result = self.cursor.fetchall()
        return result

    def get_user_bet_info(self, user_id: int):
        """查询指定用户押注信息"""
        self.cursor.execute("SELECT bet FROM users WHERE user_id = %s", (user_id,))
        result = self.cursor.fetchone()
        if not result['bet']:
            result['bet'] = '[]'
        return result['bet']

    def get_users_bet_info(self):
        """查询用户所有押注信息（仅返回 bet 不为空的用户）"""
        self.cursor.execute("""
            SELECT user_id, name, bet 
            FROM users 
            WHERE bet IS NOT NULL 
              AND TRIM(bet) != '[]' 
              AND TRIM(bet) != ''
        """)
        result = self.cursor.fetchall()
        return result

    def get_users_money_info(self):
        """查询用户所余额信息"""
        self.cursor.execute("SELECT user_id, name, money FROM users")
        result = self.cursor.fetchall()
        return result

    def get_user_today_bets(self, user_id):
        """获取用户今天的所有下注流水"""
        self.cursor.execute(
            "SELECT * FROM bets WHERE user_id = %s AND DATE(bet_time) = CURDATE()", (user_id,)
        )
        return self.cursor.fetchall()  # 返回所有符合条件的记录

    def close(self):
        """关闭数据库连接"""
        self.cursor.close()
        self.conn.close()