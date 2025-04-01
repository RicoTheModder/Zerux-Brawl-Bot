import logging
import telebot
import json
import time
import psutil
import os
import shutil
from datetime import datetime

# -------------------------
# Helper Functions
# -------------------------
def load_server_config():
    try:
        with open('server_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading server config: {e}")
        return {}

def load_user_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading user config: {e}")
        return {}

def save_user_config(user_config):
    try:
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(user_config, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving user config: {e}")

def load_accounts():
    try:
        with open("Database/Player/accounts.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading accounts: {e}")
        return {}

def save_accounts(accounts_data):
    try:
        with open("Database/Player/accounts.json", "w", encoding="utf-8") as f:
            json.dump(accounts_data, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving accounts: {e}")

def get_system_stats():
    cpu_usage = psutil.cpu_percent(interval=1)
    ram_usage = psutil.virtual_memory().percent
    disk_usage = psutil.disk_usage('/').percent
    return f"💾 RAM Usage: {ram_usage}%\n⚙️ CPU Usage: {cpu_usage}%\n🖴 Disk Usage: {disk_usage}%"

def is_admin(chat_id, admin_ids):
    return str(chat_id) in [str(x) for x in admin_ids]

def load_club_db():
    try:
        with open("Database/Club/club.db", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading club database: {e}")
        return {}

# -------------------------
# Telegram Bot Class
# -------------------------
class TelegramBot:
    def __init__(self, token):
        self.bot = telebot.TeleBot(token)
        self.server_config = load_server_config()  # server settings & token etc.
        self.user_config = load_user_config()        # user settings from config.json
        self.support_group_id = self.server_config.get("support_group_id")
        self.admin_ids = self.server_config.get("admin_ids", [])
        
        # State dictionaries
        self.user_state = {}         # For multi-step processes
        self.logged_in_users = {}    # chat_id -> account info
        self.all_users = set()       # All chat ids that have interacted
        self.rename_temp = {}        # Temporary storage for /rename command
        self.usernames = {}          # chat_id -> Telegram @username or name
        
        # Moderation state for support/admin messages
        self.muted_users = {}        # chat_id -> unmute timestamp
        self.banned_users = set()    # banned chat_ids

        # -------------------------
        # Basic Commands
        # -------------------------
        @self.bot.message_handler(commands=['start'])
        def start(message):
            self.all_users.add(message.chat.id)
            if message.from_user.username:
                self.usernames[message.chat.id] = "@" + message.from_user.username
            elif message.from_user.first_name:
                self.usernames[message.chat.id] = message.from_user.first_name
            else:
                self.usernames[message.chat.id] = str(message.chat.id)
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
                "/rename - Change your account name\n"
                "/adminrequest - Request admin application\n"
                "/latest - Get the latest client download link\n\n"
                "Admin Commands:\n"
                "/resetaccdata - Full account database reset\n"
                "/resetgems <account name> - Reset gems to 0\n"
                "/reset <account name> - Reset gold, gems, trophies to 0\n"
                "/addgems <account name> <amount> - Set gems to a specific value\n"
                "/addgold <account name> <amount> - Set gold to a specific value\n"
                "/addtrophy <account name> <amount> - Set trophies to a specific value\n"
                "/resetclubs - Reset club-related files\n"
                "/resetall - Full database reset (Clubs & Player)\n"
                "/add_news - Send news update to all known chats (Admin Only)\n"
                "/settheme - Set the bot theme (Admin only)\n"
                "/unban_support <@username> - Unban a support user (Admin Only)\n"
                "/ban_support <@username> - Ban a support user (Admin Only)\n"
                "/mute_support <@username> <minutes> - Mute a support user for specified minutes (Admin Only)\n"
                "/maintenance <value> - Set maintenance mode (Admin Only)"
            )
            self.bot.send_message(message.chat.id, help_text)

        @self.bot.message_handler(commands=['status'])
        def status(message):
            self.all_users.add(message.chat.id)
            stats = get_system_stats()
            self.bot.send_message(message.chat.id, f"🖥 Server Status:\n{stats}")

        @self.bot.message_handler(commands=['info'])
        def info(message):
            self.all_users.add(message.chat.id)
            info_text = (
                "Zerux Brawl tries to mimic the original Brawl Stars server to give you the OG Nostalgia of the Prime Brawl Stars times!\n"
                "Join our community and have fun with exclusive content!\n\n"
                f"Bot Version: {self.server_config.get('bot_version', 'Unknown')}\n"
                f"Server Version: {self.server_config.get('server_version', 'Unknown')}\n"
                f"Game Version: {self.server_config.get('version', 'Unknown')}\n"
                f"Changelog: {self.server_config.get('changelog', 'No changelog available')}"
            )
            info_images = self.server_config.get("info_images")
            if info_images:
                if isinstance(info_images, list) and len(info_images) > 1:
                    media = []
                    media.append(telebot.types.InputMediaPhoto(info_images[0], caption=info_text))
                    for img in info_images[1:]:
                        media.append(telebot.types.InputMediaPhoto(img))
                    self.bot.send_media_group(message.chat.id, media)
                else:
                    img = info_images[0] if isinstance(info_images, list) else info_images
                    self.bot.send_photo(message.chat.id, img, caption=info_text)
            else:
                self.bot.send_message(message.chat.id, info_text)

        # -------------------------
        # Updated /latest Command
        # -------------------------
        @self.bot.message_handler(commands=['latest'])
        def latest(message):
            self.all_users.add(message.chat.id)
            config = load_server_config()
            try:
                download_link = config["download_link"]
            except KeyError:
                download_link = "Download link is not configured in server_config.json!"
            msg_text = (
                "Here is the latest client of Zerux Brawl Legacy!\n"
                f"Download APK: {download_link}\n"
                "Thank you for downloading Zerux Brawl, made by RicoDEV"
            )
            self.bot.send_message(message.chat.id, msg_text)

        # -------------------------
        # Login/Logout & Profile
        # -------------------------
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
            club_id = account.get("clubID", 0)
            if club_id != 0:
                club_db = load_club_db()
                club_name = "Unknown Club"
                for group in club_db.values():
                    for club in group.values():
                        if club.get("clubID") == club_id:
                            club_name = club.get("info", {}).get("name", "Unknown Club")
                            break
                club_display = club_name
            else:
                club_display = "Not in club"
            profile_text = (
                "<b>🎮 Profile:</b>\n"
                "<b>Account Name:</b> {name}\n"
                "<b>Token:</b> {token}\n"
                "<b>Low ID:</b> {lowID}\n\n"
                "<b>🏆 Trophies:</b> {trophies} (Max: {highesttrophies})\n"
                "<b>🎖️ Solo Wins:</b> {soloWins}\n"
                "<b>🤝 Duo Wins:</b> {duoWins}\n"
                "<b>⚔️ 3v3 Wins:</b> {threeWins}\n"
                "<b>💎 Gems:</b> {gems}\n"
                "<b>💰 Gold:</b> {gold}\n"
                "<b>Club:</b> {club}"
            ).format(
                name=account.get('name', 'N/A'),
                token=account.get('token', 'N/A'),
                lowID=account.get('lowID', 'N/A'),
                trophies=account.get('trophies', 0),
                highesttrophies=account.get('highesttrophies', 0),
                soloWins=account.get('soloWins', 0),
                duoWins=account.get('duoWins', 0),
                threeWins=account.get('3vs3Wins', 0),
                gems=account.get('gems', 0),
                gold=account.get('gold', 0),
                club=club_display
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

        # -------------------------
        # Rename Command (User)
        # -------------------------
        @self.bot.message_handler(commands=['rename'])
        def rename(message):
            self.all_users.add(message.chat.id)
            if message.chat.id not in self.logged_in_users:
                self.bot.send_message(message.chat.id, "Please log in first using /login.")
                return
            self.bot.send_message(message.chat.id, "Please enter your current account name:")
            self.user_state[message.chat.id] = "awaiting_rename_current"

        @self.bot.message_handler(func=lambda msg: msg.chat.id in self.user_state and self.user_state[msg.chat.id] == "awaiting_rename_current")
        def handle_rename_current(msg):
            self.rename_temp[msg.chat.id] = msg.text.strip()
            self.bot.send_message(msg.chat.id, "Please enter your new account name:")
            self.user_state[msg.chat.id] = "awaiting_rename_new"

        @self.bot.message_handler(func=lambda msg: msg.chat.id in self.user_state and self.user_state[msg.chat.id] == "awaiting_rename_new")
        def handle_rename_new(msg):
            new_name = msg.text.strip()
            current_name = self.rename_temp.get(msg.chat.id, "")
            account = self.logged_in_users.get(msg.chat.id)
            if account.get("name") != current_name:
                self.bot.send_message(msg.chat.id, "Current name does not match your account. Rename cancelled.")
            else:
                account["name"] = new_name
                accounts_data = load_accounts()
                for acc_id, acc in accounts_data.get("Accounts", {}).items():
                    if acc.get("name") == current_name:
                        acc["name"] = new_name
                        break
                save_accounts(accounts_data)
                self.bot.send_message(msg.chat.id, f"Your account name has been changed to {new_name}.")
            del self.user_state[msg.chat.id]
            if msg.chat.id in self.rename_temp:
                del self.rename_temp[msg.chat.id]

        # -------------------------
        # SetTheme Command (Admin Only)
        # -------------------------
        @self.bot.message_handler(commands=['settheme'])
        def set_theme(message):
            self.all_users.add(message.chat.id)
            if not is_admin(message.chat.id, self.admin_ids):
                self.bot.send_message(message.chat.id, "You are not authorized to use this command.")
                return
            themes = {
                0: "Basic Brawl Stars Theme",
                1: "Brawlidays 2018 Theme",
                2: "Lunar New Year 2019 Theme"
            }
            theme_list = "\n".join([f"{key} - {value}" for key, value in themes.items()])
            self.bot.send_message(message.chat.id, f"Available Themes:\n{theme_list}\n\nSelect a theme by sending its number.")
            self.user_state[message.chat.id] = "awaiting_theme_selection"

        @self.bot.message_handler(func=lambda msg: msg.chat.id in self.user_state and self.user_state[msg.chat.id] == "awaiting_theme_selection")
        def handle_theme_selection(msg):
            user_conf = load_user_config()
            try:
                theme_id = int(msg.text.strip())
                if theme_id not in [0, 1, 2]:
                    self.bot.send_message(msg.chat.id, "Invalid theme ID. Please enter a valid number.")
                    return
                user_conf["ThemeID"] = theme_id
                save_user_config(user_conf)
                self.bot.send_message(msg.chat.id, f"Theme successfully set to {theme_id}.")
            except ValueError:
                self.bot.send_message(msg.chat.id, "Please enter a valid number.")
            del self.user_state[msg.chat.id]

        # -------------------------
        # Unban, Ban, and Mute Support/Admin Commands
        # (These now also work for admin requests forwarded messages)
        # -------------------------
        @self.bot.message_handler(commands=['unban_support'])
        def unban_support(message):
            self.all_users.add(message.chat.id)
            if not is_admin(message.chat.id, self.admin_ids):
                self.bot.send_message(message.chat.id, "You are not authorized to use this command.")
                return
            parts = message.text.split()
            if len(parts) < 2:
                self.bot.send_message(message.chat.id, "Usage: /unban_support <@username>")
                return
            target_username = parts[1].strip().lstrip("@").lower()
            unbanned = False
            for chat_id, username in self.usernames.items():
                if username.lstrip("@").lower() == target_username:
                    if chat_id in self.banned_users:
                        self.banned_users.remove(chat_id)
                        unbanned = True
                        self.bot.send_message(message.chat.id, f"User {username} has been unbanned.")
                    else:
                        self.bot.send_message(message.chat.id, f"User {username} is not banned.")
                    break
            if not unbanned:
                self.bot.send_message(message.chat.id, f"User @{target_username} not found or already unbanned.")

        @self.bot.message_handler(commands=['ban_support'])
        def ban_support(message):
            self.all_users.add(message.chat.id)
            if not is_admin(message.chat.id, self.admin_ids):
                self.bot.send_message(message.chat.id, "You are not authorized to use this command.")
                return
            parts = message.text.split()
            if len(parts) < 2:
                self.bot.send_message(message.chat.id, "Usage: /ban_support <@username>")
                return
            target_username = parts[1].strip().lstrip("@").lower()
            banned = False
            for chat_id, username in self.usernames.items():
                if username.lstrip("@").lower() == target_username:
                    self.banned_users.add(chat_id)
                    banned = True
                    self.bot.send_message(message.chat.id, f"User {username} has been banned.")
                    break
            if not banned:
                self.bot.send_message(message.chat.id, f"User @{target_username} not found or already banned.")

        @self.bot.message_handler(commands=['mute_support'])
        def mute_support(message):
            self.all_users.add(message.chat.id)
            if not is_admin(message.chat.id, self.admin_ids):
                self.bot.send_message(message.chat.id, "You are not authorized to use this command.")
                return
            parts = message.text.split()
            if len(parts) < 3 or not parts[2].isdigit():
                self.bot.send_message(message.chat.id, "Usage: /mute_support <@username> <minutes>")
                return
            target_username = parts[1].strip().lstrip("@").lower()
            minutes = int(parts[2])
            muted = False
            for chat_id, username in self.usernames.items():
                if username.lstrip("@").lower() == target_username:
                    unmute_time = time.time() + (minutes * 60)
                    self.muted_users[chat_id] = unmute_time
                    muted = True
                    self.bot.send_message(message.chat.id, f"User {username} has been muted for {minutes} minutes.")
                    self.bot.send_message(chat_id, f"You have been muted for {minutes} minutes by an admin.")
                    break
            if not muted:
                self.bot.send_message(message.chat.id, f"User @{target_username} not found.")

        # -------------------------
        # Support System & Admin Requests
        # -------------------------
        @self.bot.message_handler(commands=['support'])
        def support(message):
            self.all_users.add(message.chat.id)
            if message.chat.id in self.banned_users:
                return
            if message.chat.id in self.muted_users and time.time() < self.muted_users[message.chat.id]:
                self.bot.send_message(message.chat.id, "You are muted and cannot send support messages at this time.")
                return
            self.bot.send_message(message.chat.id, "Please enter your support message to send to the developer team:")
            self.user_state[message.chat.id] = "awaiting_support"

        @self.bot.message_handler(func=lambda msg: msg.chat.id in self.user_state and self.user_state[msg.chat.id] == "awaiting_support")
        def handle_support_message(msg):
            self.all_users.add(msg.chat.id)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sender = self.get_formatted_username(msg.chat.id, msg)
            forward_text = f"Support message received at: {timestamp}\nSender: {sender}\nMessage Content: \"{msg.text}\""
            target_id = self.support_group_id
            if target_id:
                forwarded_message = self.bot.send_message(target_id, forward_text)
                self.bot.reply_to(msg, f"Your message has been sent to the developer team!\n(Sender: {sender})")
                self.save_forwarded_message(forwarded_message.message_id, msg.chat.id)
            else:
                self.bot.reply_to(msg, "Failed to send message. Please try again.")
            del self.user_state[msg.chat.id]

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
            sender = self.get_formatted_username(msg.chat.id, msg)
            forward_text = f"Admin request received at: {timestamp}\nSender: {sender}\nRequest Content: \"{msg.text}\""
            target_id = self.support_group_id
            if target_id:
                forwarded_message = self.bot.send_message(target_id, forward_text)
                self.bot.reply_to(msg, f"Your admin application has been sent to the developer team!\n(Sender: {sender})")
                self.save_forwarded_message(forwarded_message.message_id, msg.chat.id)
            else:
                self.bot.reply_to(msg, "Failed to send application. Please try again.")
            del self.user_state[msg.chat.id]

        # -------------------------
        # Reply Handler for Support/Admin Moderation
        # (Now supports /ban_support, /unban_support, /mute_support when replying to forwarded messages)
        # -------------------------
        @self.bot.message_handler(func=lambda m: m.reply_to_message is not None)
        def handle_reply(m):
            self.all_users.add(m.chat.id)
            original_message_id = m.reply_to_message.message_id
            user_chat_id = self.get_user_chat_id(original_message_id)
            sender = self.get_formatted_username(m.chat.id, m)
            if m.chat.id in self.admin_ids:
                sender += " from Support Team"
            if user_chat_id:
                reply_text = m.text.strip()
                lower_reply = reply_text.lower()
                if lower_reply.startswith("accept"):
                    try:
                        invite_link = self.bot.export_chat_invite_link(self.support_group_id)
                        self.bot.send_message(user_chat_id, f"Your request has been accepted by {sender}.\nPlease join our support group: {invite_link}")
                        self.bot.send_message(m.chat.id, f"User accepted by {sender} and invite sent.")
                    except Exception as e:
                        self.bot.send_message(m.chat.id, f"Error sending invite: {e}")
                elif lower_reply.startswith("decline"):
                    reason = reply_text[7:].strip()
                    self.bot.send_message(user_chat_id, f"Your request has been declined by {sender}.\nReason: {reason}")
                    self.bot.send_message(m.chat.id, f"Decline message sent by {sender}.")
                elif lower_reply.startswith("mute") or lower_reply.startswith("/mute_support"):
                    parts = reply_text.split()
                    if len(parts) < 2 or not parts[1].isdigit():
                        self.bot.send_message(m.chat.id, "Invalid mute command. Use: mute <minutes> or /mute_support <@username> <minutes>")
                    else:
                        minutes = int(parts[1])
                        unmute_time = time.time() + (minutes * 60)
                        self.muted_users[user_chat_id] = unmute_time
                        self.bot.send_message(m.chat.id, f"User muted for {minutes} minutes by {sender}.")
                        self.bot.send_message(user_chat_id, f"You have been muted for {minutes} minutes by {sender}.")
                elif lower_reply.startswith("ban") or lower_reply.startswith("/ban_support"):
                    self.banned_users.add(user_chat_id)
                    self.bot.send_message(m.chat.id, f"User banned by {sender}.")
                elif lower_reply.startswith("unban") or lower_reply.startswith("/unban_support"):
                    if user_chat_id in self.banned_users:
                        self.banned_users.remove(user_chat_id)
                        self.bot.send_message(m.chat.id, f"User unbanned by {sender}.")
                    else:
                        self.bot.send_message(m.chat.id, "User is not banned.")
                else:
                    self.bot.send_message(user_chat_id, f"Reply from Support Team ({sender}): {reply_text}")
                    self.bot.send_message(m.chat.id, f"Message sent by {sender}.")


        # -------------------------
        # /maintenance Command (Admin Only)
        # -------------------------
        @self.bot.message_handler(commands=['maintenance'])
        def maintenance(message):
            self.all_users.add(message.chat.id)
            if not is_admin(message.chat.id, self.admin_ids):
                self.bot.send_message(message.chat.id, "You are not authorized to use this command.")
                return
            parts = message.text.split()
            if len(parts) != 2:
                self.bot.send_message(message.chat.id, "usage: /maintenance <value>")
                return
            arg = parts[1].strip().lower()
            if arg not in ["true", "false"]:
                self.bot.send_message(message.chat.id, "usage: /maintenance <value>")
                return
            new_value = True if arg == "true" else False
            config = load_user_config()
            config["Maintenance"] = new_value
            save_user_config(config)
            self.bot.send_message(message.chat.id, f"Maintenance mode has been set to {new_value}.")

        # -------------------------
        # Admin Commands (Existing)
        # -------------------------
        @self.bot.message_handler(commands=['resetaccdata'])
        def resetaccdata(message):
            self.all_users.add(message.chat.id)
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
            self.all_users.add(message.chat.id)
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
                save_accounts(accounts_data)
                self.bot.send_message(message.chat.id, f"Gems for account '{account_name}' have been reset to 0.")
            else:
                self.bot.send_message(message.chat.id, f"Account '{account_name}' not found.")

        @self.bot.message_handler(commands=['reset'])
        def reset(message):
            self.all_users.add(message.chat.id)
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
                save_accounts(accounts_data)
                self.bot.send_message(message.chat.id, f"Account '{account_name}' has been reset (gems, gold, trophies set to 0).")
            else:
                self.bot.send_message(message.chat.id, f"Account '{account_name}' not found.")

        @self.bot.message_handler(commands=['addgems'])
        def addgems(message):
            self.all_users.add(message.chat.id)
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
                save_accounts(accounts_data)
                self.bot.send_message(message.chat.id, f"Gems for account '{account_name}' have been set to {amount}.")
            else:
                self.bot.send_message(message.chat.id, f"Account '{account_name}' not found.")

        @self.bot.message_handler(commands=['addgold'])
        def addgold(message):
            self.all_users.add(message.chat.id)
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
                save_accounts(accounts_data)
                self.bot.send_message(message.chat.id, f"Gold for account '{account_name}' has been set to {amount}.")
            else:
                self.bot.send_message(message.chat.id, f"Account '{account_name}' not found.")

        @self.bot.message_handler(commands=['addtrophy'])
        def addtrophy(message):
            self.all_users.add(message.chat.id)
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
                    if amount > account.get("highesttrophies", 0):
                        account["highesttrophies"] = amount
                    found = True
                    break
            if found:
                save_accounts(accounts_data)
                self.bot.send_message(message.chat.id, f"Trophies for account '{account_name}' have been set to {amount}.")
            else:
                self.bot.send_message(message.chat.id, f"Account '{account_name}' not found.")

        @self.bot.message_handler(commands=['resetclubs'])
        def resetclubs(message):
            self.all_users.add(message.chat.id)
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
            self.all_users.add(message.chat.id)
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

        # -------------------------
        # Add News Command (Admin Only)
        # -------------------------
        @self.bot.message_handler(commands=['add_news'])
        def add_news(message):
            self.all_users.add(message.chat.id)
            if not is_admin(message.chat.id, self.admin_ids):
                self.bot.send_message(message.chat.id, "You are not authorized to use this command.")
                return
            self.bot.send_message(message.chat.id, "Please enter the news message to send to all known chats:")
            self.user_state[message.chat.id] = "awaiting_news"

        @self.bot.message_handler(func=lambda msg: msg.chat.id in self.user_state and self.user_state[msg.chat.id] == "awaiting_news")
        def handle_news(msg):
            self.all_users.add(msg.chat.id)
            news_text = msg.text
            all_chats = set(self.all_users)
            if self.support_group_id:
                all_chats.add(self.support_group_id)
            for chat_id in all_chats:
                try:
                    self.bot.send_message(chat_id, f"📰 News Update:\n{news_text}")
                except Exception as e:
                    logging.error(f"Failed to send news to {chat_id}: {e}")
            self.bot.send_message(msg.chat.id, "News has been sent to all known chats!")
            del self.user_state[msg.chat.id]

        # -------------------------
        # Log all messages and store usernames
        # -------------------------
        @self.bot.message_handler(func=lambda msg: True)
        def log_user(msg):
            self.all_users.add(msg.chat.id)
            if msg.from_user.username:
                self.usernames[msg.chat.id] = "@" + msg.from_user.username
            elif msg.from_user.first_name:
                self.usernames[msg.chat.id] = msg.from_user.first_name
            else:
                self.usernames[msg.chat.id] = str(msg.chat.id)

    # -------------------------
    # Helper method to format usernames with '@'
    # Updated to use message info when available.
    # -------------------------
    def get_formatted_username(self, chat_id, message=None):
        if message is not None and hasattr(message, "from_user"):
            user = message.from_user
            if user.username:
                return "@" + user.username
            elif user.first_name:
                return user.first_name
            else:
                return str(user.id)
        else:
            username = self.usernames.get(chat_id, str(chat_id))
            return "@" + username.lstrip("@")

    # -------------------------
    # Helpers for forwarded messages
    # -------------------------
    def save_forwarded_message(self, forwarded_message_id, user_chat_id):
        try:
            with open("JSON/forwarded_messages.json", "r", encoding="utf-8") as file:
                data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        data[str(forwarded_message_id)] = user_chat_id
        with open("JSON/forwarded_messages.json", "w", encoding="utf-8") as file:
            json.dump(data, file)

    def get_user_chat_id(self, forwarded_message_id):
        try:
            with open("JSON/forwarded_messages.json", "r", encoding="utf-8") as file:
                data = json.load(file)
            return data.get(str(forwarded_message_id))
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def run(self):
        self.bot.infinity_polling()
