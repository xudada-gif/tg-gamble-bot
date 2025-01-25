
# Telegram 赌博裁判机器人

这是一个基于 Python 和 Telegram Bot API 开发的赌博裁判机器人。它支持在群聊中进行押注管理，用户可以加入游戏并进行押注，游戏结束后会根据押注结果发放奖励。

## 功能特性

- **用户管理**：
  - 使用 `/start` 命令加入游戏。
  - 查询余额：使用 `/balance` 查看当前余额。
  - 进行押注：使用 `/bet <金额> <涨/跌>` 命令进行押注。
  - 查看押注信息：使用 `/mybet` 查看自己当前的押注状态。
  - 结束游戏：管理员可以使用 `/endgame` 命令结束游戏并重置所有用户的押注信息。

- **管理员功能**：
  - 结束游戏：管理员可以通过 `/endgame` 命令结束当前游戏并重置押注。

- **数据库支持**：
  - 本项目使用 MySQL 数据库保存用户信息、余额和押注状态。
  - 自动创建用户表和管理用户数据。

## 技术栈

- Python 3.10+
- Telegram Bot API (`python-telegram-bot` 20+)
- MySQL 数据库（`pymysql` 库）

## 安装与运行

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/telegram-bot.git
cd telegram-bot
```

### 2. 创建虚拟环境并安装依赖

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境（Windows）
venv\Scripts\activate

# 激活虚拟环境（macOS/Linux）
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

创建一个 `.env` 文件，并填入以下内容：

```dotenv
BOT_KEY=your-telegram-bot-token
HOST=your-mysql-host
USER=your-mysql-user
PASSWORD=your-mysql-password
DATABASE=your-database-name
```

### 4. 运行机器人

```bash
python main.py
```

## 使用说明

### `/start` 命令

用户使用 `/start` 命令加入游戏，机器人会为新用户初始化余额并保存用户信息。

### `/balance` 命令

用户可以通过 `/balance` 命令查看当前余额。

### `/bet <金额> <涨/跌>` 命令

用户可以通过 `/bet` 命令进行押注。用户需要指定押注金额和选择方向（`涨` 或 `跌`）。

例如：

```
/bet 1000 涨
```

### `/mybet` 命令

用户可以使用 `/mybet` 命令查看自己当前的押注信息。

### `/endgame` 命令

管理员可以使用 `/endgame` 命令结束游戏并重置所有用户的押注信息。

## 数据库表结构

### 用户表 `users`

```sql
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    money INT DEFAULT 10000,
    bet_amount INT DEFAULT 0,
    bet_choice ENUM('涨', '跌') DEFAULT NULL
);
```

## 注意事项

1. 在使用 `/endgame` 命令时，只有群聊的管理员或创建者可以执行该命令。
2. 本机器人仅限群组使用，玩家在群组中使用机器人命令进行游戏。

## 开发者

- 维护者：[你的名字或用户名]
- 项目地址：[你的 GitHub 仓库链接]

## License

该项目使用 [MIT License](LICENSE) 许可协议。
