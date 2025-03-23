# bot made by RicoDEV, if you plan to use this, credit me

import logging
import telebot
import json
import time
import psutil
import os
import shutil
from datetime import datetime

# Function to load the server config
def load_config():
    try:
        with open('server_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading config: {e}")
        return {}

# Function to load accounts from the updated path
def load_accounts():
    try:
        with open("Database/Player/accounts.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading accounts: {e}")
        return {}

# Function to get system resource usage
def get_system_stats():
    cpu_usage = psutil.cpu_percent(interval=1)
    ram_usage = psutil.virtual_memory().percent
    disk_usage = psutil.disk_usage('/').percent
    return f"💾 RAM Usage: {ram_usage}%\n⚙️ CPU Usage: {cpu_usage}%\n🖴 Disk Usage: {disk_usage}%"

# Helper function for admin check
def is_admin(chat_id, admin_ids):
    return str(chat_id) in [str(x) for x in admin_ids]

# Telegram Bot Class
class TelegramBot:
    def __init__(self, token):
        self.bot = telebot.TeleBot(token)
        self.config = load_config()
        self.support_group_id = self.config.get("support_group_id")
        # Read admin_ids as a list; if not present, default to an empty list.
        self.admin_ids = self.config.get("admin_ids", [])
        
        # Dictionary to store user state for processes like login, support and news
        self.user_state = {}
        # Dictionary to store logged in users' account info keyed by chat id
        self.logged_in_users = {}
        # Set to track all users who have messaged the bot at least once
        self.all_users = set()

        @self.bot.message_handler(commands=['start'])
        def start(message):
            self.all_users.add(message.chat.id)
            self.bot.send_message(message.chat.id, "Welcome to Zerux Brawl Bot! Use /help to view available commands.")

        @self.bot.message_handler(commands=['help'])
        def help_command(message):
            self.all_users.add(message.chat.id)
            help_text = (
                "Available Commands:\n"
                "/status - Show server system stats\n"
                "/info - Get information about Zerux Brawl with images\n"
                "/support - Contact the support team\n"
                "/login - Login with your account name\n"
                "/profile - View your profile (requires login)\n"
                "/logout - Log out of your account\n"
                "/leaderboard - View trophy leaderboard\n"
                "/adminrequest - Request admin application\n\n"
                "Admin Commands:\n"
                "/resetaccdata - Full account database reset\n"
                "/resetgems <account name> - Reset gems to 0\n"
                "/reset <account name> - Reset gold, gems, trophies to 0\n"
                "/addgems <account name> <amount> - Set gems to a specific value\n"
                "/addgold <account name> <amount> - Set gold to a specific value\n"
                "/addtrophy <account name> <amount> - Set trophies to a specific value\n"
                "/resetclubs - Reset club-related files\n"
                "/resetall - Full database reset (Clubs & Player)\n"
                "/add_news - Send news update to all users (Admin Only)"
            )
            self.bot.send_message(message.chat.id, help_text)

        @self.bot.message_handler(commands=['status'])
        def status(message):
            self.all_users.add(message.chat.id)
            system_stats = get_system_stats()
            self.bot.send_message(message.chat.id, f"🖥 Server Status:\n{system_stats}")

        @self.bot.message_handler(commands=['info'])
        def info(message):
            self.all_users.add(message.chat.id)
            info_text = (
                "Zerux Brawl is a private Brawl Stars server with custom mods and features!\n"
                "Join our community and have fun with exclusive content!\n\n"
                f"Bot Version: {self.config.get('bot_version', 'Unknown')}\n"
                f"Server Version: {self.config.get('server_version', 'Unknown')}\n"
                f"Game Version: {self.config.get('version', 'Unknown')}\n"
                f"Changelog: {self.config.get('changelog', 'No changelog available')}"
            )
            info_images = self.config.get("info_images")
            if info_images:
                if isinstance(info_images, list) and len(info_images) > 1:
                    media = []
                    media.append(telebot.types.InputMediaPhoto(info_images[0], caption=info_text))
                    for img in info_images[1:]:
                        media.append(telebot.types.InputMediaPhoto(img))
                    self.bot.send_media_group(message.chat.id, media)
                else:
                    if isinstance(info_images, list):
                        img = info_images[0]
                    else:
                        img = info_images
                    self.bot.send_photo(message.chat.id, img, caption=info_text)
            else:
                self.bot.send_message(message.chat.id, info_text)

        # LOGIN SYSTEM
        @self.bot.message_handler(commands=['login'])
        def login(message):
            self.all_users.add(message.chat.id)
            self.bot.send_message(message.chat.id, "Please enter your account name:")
            self.user_state[message.chat.id] = "awaiting_login"

        @self.bot.message_handler(func=lambda msg: msg.chat.id in self.user_state and self.user_state[msg.chat.id] == "awaiting_login")
        def handle_login(msg):
            self.all_users.add(msg.chat.id)
            account_name = msg.text.strip()
            accounts_data = load_accounts()
            account_found = None
            for account_id, account in accounts_data.get("Accounts", {}).items():
                if account.get("name") == account_name:
                    account_found = account
                    break
            if account_found:
                self.logged_in_users[msg.chat.id] = account_found
                self.bot.send_message(msg.chat.id, f"Logged in successfully! You have {account_found.get('gems', 0)} gems.")
            else:
                self.bot.send_message(msg.chat.id, "Account not found. Please try again.")
            del self.user_state[msg.chat.id]

        @self.bot.message_handler(commands=['logout'])
        def logout(message):
            self.all_users.add(message.chat.id)
            if message.chat.id in self.logged_in_users:
                del self.logged_in_users[message.chat.id]
                self.bot.send_message(message.chat.id, "You have been logged out successfully.")
            else:
                self.bot.send_message(message.chat.id, "You are not currently logged in.")

        @self.bot.message_handler(commands=['profile'])
        def profile(message):
            self.all_users.add(message.chat.id)
            if message.chat.id not in self.logged_in_users:
                self.bot.send_message(message.chat.id, "Please log in first using /login.")
                return
            account = self.logged_in_users[message.chat.id]
            three_vs_three = account.get('3vs3Wins', 0)
            profile_text = (
                "<b>🎮 Profile:</b>\n"
                "<b>🏆 Trophies:</b> {trophies} (Max: {highesttrophies})\n"
                "<b>🎖️ Solo Wins:</b> {soloWins}\n"
                "<b>🤝 Duo Wins:</b> {duoWins}\n"
                "<b>⚔️ 3v3 Wins:</b> {three_vs_three}\n"
                "<b>💎 Gems:</b> {gems}\n"
                "<b>💰 Gold:</b> {gold}"
            ).format(
                trophies=account.get('trophies', 0),
                highesttrophies=account.get('highesttrophies', 0),
                soloWins=account.get('soloWins', 0),
                duoWins=account.get('duoWins', 0),
                three_vs_three=three_vs_three,
                gems=account.get('gems', 0),
                gold=account.get('gold', 0)
            )
            self.bot.send_message(message.chat.id, profile_text, parse_mode='HTML')

        @self.bot.message_handler(commands=['leaderboard'])
        def leaderboard(message):
            self.all_users.add(message.chat.id)
            accounts_data = load_accounts()
            accounts = accounts_data.get("Accounts", {})
            sorted_accounts = sorted(accounts.items(), key=lambda item: item[1].get("trophies", 0), reverse=True)
            leaderboard_text = "🏆 Leaderboard (by trophies):\n"
            for idx, (acc_id, account) in enumerate(sorted_accounts, 1):
                leaderboard_text += f"{idx}. {account.get('name')} - {account.get('trophies', 0)} trophies\n"
                if idx >= 10:
                    break
            self.bot.send_message(message.chat.id, leaderboard_text)

        # SUPPORT SYSTEM - Modified to send directly to developer team
        @self.bot.message_handler(commands=['support'])
        def support(message):
            self.all_users.add(message.chat.id)
            self.bot.send_message(message.chat.id, "Please enter your support message to send to the developer team:")
            self.user_state[message.chat.id] = "awaiting_support"

        @self.bot.message_handler(func=lambda msg: msg.chat.id in self.user_state and self.user_state[msg.chat.id] == "awaiting_support")
        def handle_support_message(msg):
            self.all_users.add(msg.chat.id)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            forward_text = f"Support message received at: {timestamp}\n\nMessage Content: \"{msg.text}\""
            target_id = self.support_group_id
            if target_id:
                forwarded_message = self.bot.send_message(target_id, forward_text)
                self.bot.reply_to(msg, "Your message has been sent to the developer team!")
                self.save_forwarded_message(forwarded_message.message_id, msg.chat.id)
            else:
                self.bot.reply_to(msg, "Failed to send message. Please try again.")
            del self.user_state[msg.chat.id]

        @self.bot.message_handler(func=lambda m: m.reply_to_message is not None)
        def handle_reply(m):
            self.all_users.add(m.chat.id)
            original_message_id = m.reply_to_message.message_id
            user_chat_id = self.get_user_chat_id(original_message_id)
            if user_chat_id:
                reply_text = f"Reply from Support Team: {m.text}"
                self.bot.send_message(user_chat_id, reply_text)
                self.bot.send_message(m.chat.id, "Message has been sent!")

        # Admin Commands (Admin Only)
        @self.bot.message_handler(commands=['resetaccdata'])
        def resetaccdata(message):
            if not is_admin(message.chat.id, self.admin_ids):
                self.bot.send_message(message.chat.id, "You are not authorized to use this command.")
                return
            try:
                if os.path.exists("Database/Player/accounts.json"):
                    os.remove("Database/Player/accounts.json")
                    self.bot.send_message(message.chat.id, "Accounts database has been reset (accounts.json deleted).")
                else:
                    self.bot.send_message(message.chat.id, "Accounts database file does not exist.")
            except Exception as e:
                self.bot.send_message(message.chat.id, f"Error resetting accounts database: {e}")

        @self.bot.message_handler(commands=['resetgems'])
        def resetgems(message):
            if not is_admin(message.chat.id, self.admin_ids):
                self.bot.send_message(message.chat.id, "You are not authorized to use this command.")
                return
            account_name = message.text[len("/resetgems "):].strip()
            if not account_name:
                self.bot.send_message(message.chat.id, "Usage: /resetgems <account name>")
                return
            accounts_data = load_accounts()
            accounts = accounts_data.get("Accounts", {})
            found = False
            for acc_id, account in accounts.items():
                if account.get("name") == account_name:
                    account["gems"] = 0
                    found = True
                    break
            if found:
                with open("Database/Player/accounts.json", "w", encoding="utf-8") as f:
                    json.dump(accounts_data, f)
                self.bot.send_message(message.chat.id, f"Gems for account '{account_name}' have been reset to 0.")
            else:
                self.bot.send_message(message.chat.id, f"Account '{account_name}' not found.")

        @self.bot.message_handler(commands=['reset'])
        def reset(message):
            if not is_admin(message.chat.id, self.admin_ids):
                self.bot.send_message(message.chat.id, "You are not authorized to use this command.")
                return
            account_name = message.text[len("/reset "):].strip()
            if not account_name:
                self.bot.send_message(message.chat.id, "Usage: /reset <account name>")
                return
            accounts_data = load_accounts()
            accounts = accounts_data.get("Accounts", {})
            found = False
            for acc_id, account in accounts.items():
                if account.get("name") == account_name:
                    account["gems"] = 0
                    account["gold"] = 0
                    account["trophies"] = 0
                    found = True
                    break
            if found:
                with open("Database/Player/accounts.json", "w", encoding="utf-8") as f:
                    json.dump(accounts_data, f)
                self.bot.send_message(message.chat.id, f"Account '{account_name}' has been reset (gems, gold, trophies set to 0).")
            else:
                self.bot.send_message(message.chat.id, f"Account '{account_name}' not found.")

        @self.bot.message_handler(commands=['addgems'])
        def addgems(message):
            if not is_admin(message.chat.id, self.admin_ids):
                self.bot.send_message(message.chat.id, "You are not authorized to use this command.")
                return
            parts = message.text.split()
            if len(parts) < 3:
                self.bot.send_message(message.chat.id, "Usage: /addgems <account name> <amount>")
                return
            try:
                amount = int(parts[-1])
            except ValueError:
                self.bot.send_message(message.chat.id, "Amount must be an integer.")
                return
            account_name = " ".join(parts[1:-1])
            accounts_data = load_accounts()
            accounts = accounts_data.get("Accounts", {})
            found = False
            for acc_id, account in accounts.items():
                if account.get("name") == account_name:
                    account["gems"] = amount
                    found = True
                    break
            if found:
                with open("Database/Player/accounts.json", "w", encoding="utf-8") as f:
                    json.dump(accounts_data, f)
                self.bot.send_message(message.chat.id, f"Gems for account '{account_name}' have been set to {amount}.")
            else:
                self.bot.send_message(message.chat.id, f"Account '{account_name}' not found.")

        @self.bot.message_handler(commands=['addgold'])
        def addgold(message):
            if not is_admin(message.chat.id, self.admin_ids):
                self.bot.send_message(message.chat.id, "You are not authorized to use this command.")
                return
            parts = message.text.split()
            if len(parts) < 3:
                self.bot.send_message(message.chat.id, "Usage: /addgold <account name> <amount>")
                return
            try:
                amount = int(parts[-1])
            except ValueError:
                self.bot.send_message(message.chat.id, "Amount must be an integer.")
                return
            account_name = " ".join(parts[1:-1])
            accounts_data = load_accounts()
            accounts = accounts_data.get("Accounts", {})
            found = False
            for acc_id, account in accounts.items():
                if account.get("name") == account_name:
                    account["gold"] = amount
                    found = True
                    break
            if found:
                with open("Database/Player/accounts.json", "w", encoding="utf-8") as f:
                    json.dump(accounts_data, f)
                self.bot.send_message(message.chat.id, f"Gold for account '{account_name}' has been set to {amount}.")
            else:
                self.bot.send_message(message.chat.id, f"Account '{account_name}' not found.")

        # FIXED: Updated /addtrophy command to also update highesttrophies if needed
        @self.bot.message_handler(commands=['addtrophy'])
        def addtrophy(message):
            if not is_admin(message.chat.id, self.admin_ids):
                self.bot.send_message(message.chat.id, "You are not authorized to use this command.")
                return
            parts = message.text.split()
            if len(parts) < 3:
                self.bot.send_message(message.chat.id, "Usage: /addtrophy <account name> <amount>")
                return
            try:
                amount = int(parts[-1])
            except ValueError:
                self.bot.send_message(message.chat.id, "Amount must be an integer.")
                return
            account_name = " ".join(parts[1:-1])
            accounts_data = load_accounts()
            accounts = accounts_data.get("Accounts", {})
            found = False
            for acc_id, account in accounts.items():
                if account.get("name") == account_name:
                    account["trophies"] = amount
                    # Update highesttrophies if new trophy count is higher
                    if amount > account.get("highesttrophies", 0):
                        account["highesttrophies"] = amount
                    found = True
                    break
            if found:
                with open("Database/Player/accounts.json", "w", encoding="utf-8") as f:
                    json.dump(accounts_data, f)
                self.bot.send_message(message.chat.id, f"Trophies for account '{account_name}' have been set to {amount}.")
            else:
                self.bot.send_message(message.chat.id, f"Account '{account_name}' not found.")

        @self.bot.message_handler(commands=['resetclubs'])
        def resetclubs(message):
            if not is_admin(message.chat.id, self.admin_ids):
                self.bot.send_message(message.chat.id, "You are not authorized to use this command.")
                return
            files = ["Database/Club/club.db", "Database/Club/clubs.json", "Database/Club/chat.db", "Database/Club/chats.json"]
            errors = []
            for file_path in files:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    errors.append(f"Error deleting {file_path}: {e}")
            if errors:
                self.bot.send_message(message.chat.id, "\n".join(errors))
            else:
                self.bot.send_message(message.chat.id, "Club related files have been reset successfully.")

        @self.bot.message_handler(commands=['resetall'])
        def resetall(message):
            if not is_admin(message.chat.id, self.admin_ids):
                self.bot.send_message(message.chat.id, "You are not authorized to use this command.")
                return
            dirs = ["Database/Clubs", "Database/Player"]
            errors = []
            for dir_path in dirs:
                try:
                    if os.path.exists(dir_path):
                        shutil.rmtree(dir_path)
                except Exception as e:
                    errors.append(f"Error deleting {dir_path}: {e}")
            if errors:
                self.bot.send_message(message.chat.id, "\n".join(errors))
            else:
                self.bot.send_message(message.chat.id, "Full database has been reset (Clubs and Player directories removed).")

        @self.bot.message_handler(commands=['add_news'])
        def add_news(message):
            if not is_admin(message.chat.id, self.admin_ids):
                self.bot.send_message(message.chat.id, "You are not authorized to use this command.")
                return
            self.bot.send_message(message.chat.id, "Please enter the news message to send to all users:")
            self.user_state[message.chat.id] = "awaiting_news"

        @self.bot.message_handler(func=lambda msg: msg.chat.id in self.user_state and self.user_state[msg.chat.id] == "awaiting_news")
        def handle_news(msg):
            self.all_users.add(msg.chat.id)
            news_text = msg.text
            for user_id in self.all_users:
                try:
                    self.bot.send_message(user_id, f"📰 News Update:\n{news_text}")
                except Exception as e:
                    logging.error(f"Failed to send news to {user_id}: {e}")
            self.bot.send_message(msg.chat.id, "News has been sent to all users!")
            del self.user_state[msg.chat.id]

        # Updated /adminrequest command to work like support
        @self.bot.message_handler(commands=['adminrequest'])
        def adminrequest(message):
            self.all_users.add(message.chat.id)
            admin_request_text = (
                "--------Message Expectations--------\n\n"
                "Name or Nickname\n"
                "Age\n"
                "For what do you need admin?\n"
                "Do you have previous Developing Experience?\n"
                "Do you have previous Modding Experience?\n"
                "Have you been a developer back then?\n"
                "Telegram user id (can be get with @userinfobot) - REQUIRED\n"
                "Your Telegram @ - (optional) so we can add you to our developer groups\n\n"
                "--------Admin Rules--------\n\n"
                "Be respectful to other people\n"
                "Do not leak things from our Developer channel\n"
                "Do not mess with the server unless I (@RicoDEVOfficial) allow it\n"
                "Actually be able to help us with something"
            )
            self.bot.send_message(message.chat.id, admin_request_text)
            self.bot.send_message(message.chat.id, "Please enter your admin application to send to the developer team:")
            self.user_state[message.chat.id] = "awaiting_admin_request"

        @self.bot.message_handler(func=lambda msg: msg.chat.id in self.user_state and self.user_state[msg.chat.id] == "awaiting_admin_request")
        def handle_admin_request(msg):
            self.all_users.add(msg.chat.id)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            forward_text = f"Admin request received at: {timestamp}\n\nRequest Content: \"{msg.text}\""
            target_id = self.support_group_id
            if target_id:
                forwarded_message = self.bot.send_message(target_id, forward_text)
                self.bot.reply_to(msg, "Your admin application has been sent to the developer team!")
                self.save_forwarded_message(forwarded_message.message_id, msg.chat.id)
            else:
                self.bot.reply_to(msg, "Failed to send application. Please try again.")
            del self.user_state[msg.chat.id]

        # Log every message sender to ensure we have all users
        @self.bot.message_handler(func=lambda msg: True)
        def log_user(msg):
            self.all_users.add(msg.chat.id)

    def save_forwarded_message(self, forwarded_message_id, user_chat_id):
        try:
            with open("forwarded_messages.json", "r", encoding="utf-8") as file:
                data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        data[str(forwarded_message_id)] = user_chat_id
        with open("forwarded_messages.json", "w", encoding="utf-8") as file:
            json.dump(data, file)

    def get_user_chat_id(self, forwarded_message_id):
        try:
            with open("forwarded_messages.json", "r", encoding="utf-8") as file:
                data = json.load(file)
            return data.get(str(forwarded_message_id))
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def run(self):
        self.bot.infinity_polling()
