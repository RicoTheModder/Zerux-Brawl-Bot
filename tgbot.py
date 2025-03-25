import logging, telebot, json, time, psutil, os, shutil
from datetime import datetime

# --- Helper functions ---
def load_config(fn):
    try:
        with open(fn, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading {fn}: {e}")
        return {}

def save_config(data, fn):
    try:
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving {fn}: {e}")

def get_stats():
    return f"💾 RAM: {psutil.virtual_memory().percent}%\n⚙️ CPU: {psutil.cpu_percent(interval=1)}%\n🖴 Disk: {psutil.disk_usage('/').percent}%"

def is_admin(cid, admins):
    return str(cid) in [str(a) for a in admins]

# --- Persistent login helpers ---
def load_tglogin():
    try:
        with open("tglogin.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {}

def save_tglogin(data):
    try:
        with open("tglogin.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logging.error(f"Error saving tglogin.json: {e}")

# --- Main Bot Class ---
class TelegramBot:
    def __init__(self, token):
        self.bot      = telebot.TeleBot(token)
        self.server_cfg = load_config("server_config.json")
        self.user_cfg   = load_config("config.json")
        self.admins     = self.server_cfg.get("admin_ids", [])
        self.sup_grp    = self.server_cfg.get("support_group_id")
        self.tgban_fn   = "tgban.json"
        self.fwd_fn     = "forwarded_messages.json"
        self.tgban      = self.load_tgban()  # List of banned usernames (normalized: "@username")
        # Other state:
        self.state      = {}      # chat_id -> state string
        self.logged     = {}      # chat_id -> account info
        self.all_users  = set()   # encountered chat ids
        self.rename_tmp = {}      # chat_id -> temporary rename info
        self.usernames  = {}      # chat_id -> "@username"
        self.muted      = {}      # chat_id -> unmute timestamp
        self.temp_ban   = set()   # chat ids banned in current session

        # Load persistent login data and auto-login users:
        self._load_logged_in_users()

        # ------------------------- Basic Commands -------------------------
        @self.bot.message_handler(commands=['start'])
        def start(m):
            self.all_users.add(m.chat.id)
            if m.from_user.username:
                self.usernames[m.chat.id] = "@" + m.from_user.username
            self.bot.send_message(m.chat.id, "Welcome to Zerux Brawl Bot!\nUse /help for commands.")

        @self.bot.message_handler(commands=['help'])
        def help_cmd(m):
            self.all_users.add(m.chat.id)
            txt = ("Available Commands:\n"
                   "User:\n"
                   "  /status - Show server status\n"
                   "  /info - Server information\n"
                   "  /support - Contact support\n"
                   "  /login - Login to your account\n"
                   "  /profile - View your profile\n"
                   "  /logout - Log out\n"
                   "  /leaderboard - View leaderboard\n"
                   "  /rename - Change account name\n"
                   "  /adminrequest - Request admin access\n\n"
                   "Admin:\n"
                   "  /resetaccdata\n"
                   "  /resetgems <name>\n"
                   "  /reset <name>\n"
                   "  /addgems <name> <amt>\n"
                   "  /addgold <name> <amt>\n"
                   "  /addtrophy <name> <amt>\n"
                   "  /resetclubs\n"
                   "  /resetall\n"
                   "  /add_news\n"
                   "  /settheme\n"
                   "  /unban_support <@username>\n"
                   "  /ban_support <@username>\n"
                   "  /mute_support <@username> <minutes>")
            self.bot.send_message(m.chat.id, txt)

        @self.bot.message_handler(commands=['status'])
        def status(m):
            self.all_users.add(m.chat.id)
            self.bot.send_message(m.chat.id, f"🖥 Server Status:\n{get_stats()}")

        @self.bot.message_handler(commands=['info'])
        def info(m):
            self.all_users.add(m.chat.id)
            txt = (f"Zerux Brawl\n"
                   f"Bot Version: {self.server_cfg.get('bot_version', 'Unknown')}\n"
                   f"Server Version: {self.server_cfg.get('server_version', 'Unknown')}\n"
                   f"Game Version: {self.server_cfg.get('version', 'Unknown')}\n"
                   f"Changelog: {self.server_cfg.get('changelog', 'No changelog available')}")
            imgs = self.server_cfg.get("info_images")
            if imgs:
                if isinstance(imgs, list) and len(imgs) > 1:
                    media = [telebot.types.InputMediaPhoto(imgs[0], caption=txt)] + \
                            [telebot.types.InputMediaPhoto(i) for i in imgs[1:]]
                    self.bot.send_media_group(m.chat.id, media)
                else:
                    img = imgs[0] if isinstance(imgs, list) else imgs
                    self.bot.send_photo(m.chat.id, img, caption=txt)
            else:
                self.bot.send_message(m.chat.id, txt)

        # ---------------- Login/Logout/Profile/Leaderboard/rename/adminrequest ----------------
        @self.bot.message_handler(commands=['login'])
        def login(m):
            self.all_users.add(m.chat.id)
            self.bot.send_message(m.chat.id, "Enter your account name:")
            self.state[m.chat.id] = "awaiting_login"

        @self.bot.message_handler(func=lambda msg: msg.chat.id in self.state and self.state[msg.chat.id]=="awaiting_login")
        def handle_login(m):
            name = m.text.strip()
            accs = load_config("Database/Player/accounts.json").get("Accounts", {})
            found = None
            for acc in accs.values():
                if acc.get("name") == name:
                    found = acc
                    break
            if found:
                self.logged[m.chat.id] = found
                self.bot.send_message(m.chat.id, f"Logged in!\nGems: {found.get('gems', 0)}")
                # Save persistent login data:
                lg = load_tglogin()
                lg[str(m.chat.id)] = found.get("name")
                save_tglogin(lg)
            else:
                self.bot.send_message(m.chat.id, "Account not found.")
            del self.state[m.chat.id]

        @self.bot.message_handler(commands=['logout'])
        def logout(m):
            self.all_users.add(m.chat.id)
            if m.chat.id in self.logged:
                del self.logged[m.chat.id]
                self.bot.send_message(m.chat.id, "Logged out.")
                # Remove from persistent login:
                lg = load_tglogin()
                if str(m.chat.id) in lg:
                    del lg[str(m.chat.id)]
                    save_tglogin(lg)
            else:
                self.bot.send_message(m.chat.id, "You are not logged in.")

        @self.bot.message_handler(commands=['profile'])
        def profile(m):
            self.all_users.add(m.chat.id)
            if m.chat.id not in self.logged:
                self.bot.send_message(m.chat.id, "Login first using /login.")
                return
            acc = self.logged[m.chat.id]
            club = "Not in club"
            if acc.get("clubID", 0):
                club = load_config("Database/Club/club.db").get("clubName", "Unknown Club")
            txt = (f"🎮 Profile:\n"
                   f"Name: {acc.get('name', 'N/A')}\n"
                   f"Token: {acc.get('token', 'N/A')}\n"
                   f"LowID: {acc.get('lowID', 'N/A')}\n"
                   f"Trophies: {acc.get('trophies', 0)} (Max: {acc.get('highesttrophies', 0)})\n"
                   f"Solo Wins: {acc.get('soloWins', 0)}\n"
                   f"Duo Wins: {acc.get('duoWins', 0)}\n"
                   f"3v3 Wins: {acc.get('3vs3Wins', 0)}\n"
                   f"Gems: {acc.get('gems', 0)}\n"
                   f"Gold: {acc.get('gold', 0)}\n"
                   f"Club: {club}")
            self.bot.send_message(m.chat.id, txt, parse_mode="HTML")

        @self.bot.message_handler(commands=['leaderboard'])
        def leaderboard(m):
            self.all_users.add(m.chat.id)
            accs = load_config("Database/Player/accounts.json").get("Accounts", {})
            sorted_accs = sorted(accs.values(), key=lambda x: x.get("trophies", 0), reverse=True)
            txt = "🏆 Leaderboard:\n" + "\n".join(f"{i+1}. {a.get('name')} - {a.get('trophies', 0)}" for i, a in enumerate(sorted_accs[:10]))
            self.bot.send_message(m.chat.id, txt)

        @self.bot.message_handler(commands=['rename'])
        def rename(m):
            self.all_users.add(m.chat.id)
            if m.chat.id not in self.logged:
                self.bot.send_message(m.chat.id, "Login first using /login.")
                return
            self.bot.send_message(m.chat.id, "Enter your current account name:")
            self.state[m.chat.id] = "awaiting_rename_current"

        @self.bot.message_handler(func=lambda msg: msg.chat.id in self.state and self.state[msg.chat.id]=="awaiting_rename_current")
        def rename_current(m):
            self.rename_tmp[m.chat.id] = m.text.strip()
            self.bot.send_message(m.chat.id, "Enter your new account name:")
            self.state[m.chat.id] = "awaiting_rename_new"

        @self.bot.message_handler(func=lambda msg: msg.chat.id in self.state and self.state[msg.chat.id]=="awaiting_rename_new")
        def rename_new(m):
            new_name = m.text.strip()
            curr = self.rename_tmp.get(m.chat.id, "")
            acc = self.logged.get(m.chat.id, {})
            if acc.get("name") != curr:
                self.bot.send_message(m.chat.id, "Current name mismatch. Rename cancelled.")
            else:
                acc["name"] = new_name
                self.bot.send_message(m.chat.id, f"Renamed to {new_name}.")
                # Update persistent login storage:
                lg = load_tglogin()
                lg[str(m.chat.id)] = new_name
                save_tglogin(lg)
            del self.state[m.chat.id]
            if m.chat.id in self.rename_tmp:
                del self.rename_tmp[m.chat.id]

        @self.bot.message_handler(commands=['adminrequest'])
        def adminreq(m):
            self.all_users.add(m.chat.id)
            txt = ("--------Message Expectations--------\n"
                   "Name/Nickname\nAge\nReason for admin\nDev/Mod experience\n"
                   "Telegram user id (required) & @ (optional)\n\n"
                   "--------Admin Rules--------\nBe respectful, do not leak, no unauthorized actions.")
            self.bot.send_message(m.chat.id, txt)
            self.bot.send_message(m.chat.id, "Enter your admin application:")
            self.state[m.chat.id] = "awaiting_admin_request"

        @self.bot.message_handler(func=lambda msg: msg.chat.id in self.state and self.state[msg.chat.id]=="awaiting_admin_request")
        def handle_adminreq(m):
            self.all_users.add(m.chat.id)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sender = self.get_username(m.chat.id)
            txt = f"Admin request at: {ts}\nSender: {sender}\nRequest: \"{m.text}\""
            if self.sup_grp:
                fwd = self.bot.send_message(self.sup_grp, txt)
                self.bot.reply_to(m, f"Application sent!\n(Sender: {sender})")
                self.save_fwd(fwd.message_id, m.chat.id)
            else:
                self.bot.reply_to(m, "Failed to send application.")
            del self.state[m.chat.id]

        @self.bot.message_handler(commands=['settheme'])
        def settheme(m):
            self.all_users.add(m.chat.id)
            if not is_admin(m.chat.id, self.admins):
                self.bot.send_message(m.chat.id, "Not authorized.")
                return
            themes = {0: "Basic", 1: "Brawlidays 2018", 2: "Lunar New Year 2019"}
            txt = "\n".join(f"{k} - {v}" for k, v in themes.items())
            self.bot.send_message(m.chat.id, f"Available Themes:\n{txt}\nSelect theme by number:")
            self.state[m.chat.id] = "awaiting_theme"

        @self.bot.message_handler(func=lambda msg: msg.chat.id in self.state and self.state[msg.chat.id]=="awaiting_theme")
        def handle_theme(m):
            try:
                tid = int(m.text.strip())
                if tid not in [0, 1, 2]:
                    raise ValueError
                self.user_cfg["ThemeID"] = tid
                save_config(self.user_cfg, "config.json")
                self.bot.send_message(m.chat.id, f"Theme set to {tid}.")
            except ValueError:
                self.bot.send_message(m.chat.id, "Enter a valid number.")
            del self.state[m.chat.id]

        # ---------------- Persistent Ban/Mute Commands ----------------
        @self.bot.message_handler(commands=['ban_support'])
        def ban_sup(m):
            self.all_users.add(m.chat.id)
            if not is_admin(m.chat.id, self.admins):
                self.bot.send_message(m.chat.id, "Not authorized.")
                return
            parts = m.text.split()
            if len(parts) < 2:
                self.bot.send_message(m.chat.id, "Usage: /ban_support <@username>")
                return
            uname = "@" + parts[1].lstrip("@").lower()
            if uname in self.tgban:
                self.bot.send_message(m.chat.id, f"{uname} is already banned.")
                return
            self.tgban.append(uname)
            self.save_tgban()
            for cid, user in self.usernames.items():
                if user.lower() == uname:
                    self.temp_ban.add(cid)
                    break
            self.bot.send_message(m.chat.id, f"{uname} has been banned.")

        @self.bot.message_handler(commands=['unban_support'])
        def unban_sup(m):
            self.all_users.add(m.chat.id)
            if not is_admin(m.chat.id, self.admins):
                self.bot.send_message(m.chat.id, "Not authorized.")
                return
            parts = m.text.split()
            if len(parts) < 2:
                self.bot.send_message(m.chat.id, "Usage: /unban_support <@username>")
                return
            uname = "@" + parts[1].lstrip("@").lower()
            if uname not in self.tgban:
                self.bot.send_message(m.chat.id, f"{uname} is not banned.")
                return
            self.tgban.remove(uname)
            self.save_tgban()
            for cid, user in self.usernames.items():
                if user.lower() == uname:
                    self.temp_ban.discard(cid)
                    break
            self.bot.send_message(m.chat.id, f"{uname} has been unbanned.")

        @self.bot.message_handler(commands=['mute_support'])
        def mute_sup(m):
            self.all_users.add(m.chat.id)
            if not is_admin(m.chat.id, self.admins):
                self.bot.send_message(m.chat.id, "Not authorized.")
                return
            parts = m.text.split()
            if len(parts) < 3:
                self.bot.send_message(m.chat.id, "Usage: /mute_support <@username> <minutes>")
                return
            uname = "@" + parts[1].lstrip("@").lower()
            try:
                mins = int(parts[2])
            except ValueError:
                self.bot.send_message(m.chat.id, "Minutes must be an integer.")
                return
            for cid, user in self.usernames.items():
                if user.lower() == uname:
                    self.muted[cid] = time.time() + mins * 60
                    self.bot.send_message(m.chat.id, f"{uname} muted for {mins} minutes.")
                    return
            self.bot.send_message(m.chat.id, f"{uname} not found.")

        # ---------------- Support System ----------------
        @self.bot.message_handler(commands=['support'])
        def support(m):
            self.all_users.add(m.chat.id)
            if m.chat.id in self.temp_ban:
                return
            if m.chat.id in self.muted and time.time() < self.muted[m.chat.id]:
                self.bot.send_message(m.chat.id, "You are muted.")
                return
            self.bot.send_message(m.chat.id, "Enter your support message:")
            self.state[m.chat.id] = "awaiting_support"

        @self.bot.message_handler(func=lambda msg: msg.chat.id in self.state and self.state[msg.chat.id]=="awaiting_support")
        def handle_support(msg):
            self.all_users.add(msg.chat.id)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sender = self.get_username(msg.chat.id)
            txt = f"Support received at: {ts}\nSender: {sender}\nMessage: \"{msg.text}\""
            if self.sup_grp:
                fwd = self.bot.send_message(self.sup_grp, txt)
                self.bot.reply_to(msg, f"Message sent!\n(Sender: {sender})")
                self.save_fwd(fwd.message_id, msg.chat.id)
            else:
                self.bot.reply_to(msg, "Failed to send message.")
            del self.state[msg.chat.id]

        @self.bot.message_handler(commands=['add_news'])
        def add_news(m):
            if not is_admin(m.chat.id, self.admins):
                self.bot.send_message(m.chat.id, "Not authorized.")
                return
            self.bot.send_message(m.chat.id, "Enter news message to send to all users:")
            self.state[m.chat.id] = "awaiting_news"

        @self.bot.message_handler(func=lambda msg: msg.chat.id in self.state and self.state[msg.chat.id]=="awaiting_news")
        def handle_news(msg):
            self.all_users.add(msg.chat.id)
            txt = msg.text
            for uid in self.all_users:
                try:
                    self.bot.send_message(uid, f"📰 News Update:\n{txt}")
                except Exception as e:
                    logging.error(f"News failed for {uid}: {e}")
            self.bot.send_message(msg.chat.id, "News sent!")
            del self.state[msg.chat.id]

        # ---------------- Reply Handler (Only Accept/Decline) ----------------
        @self.bot.message_handler(func=lambda m: m.reply_to_message is not None)
        def reply_handler(m):
            self.all_users.add(m.chat.id)
            orig = m.reply_to_message.message_id
            uid = self.get_fwd_uid(orig)
            sender = self.get_username(m.chat.id)
            if m.chat.id in self.admins:
                sender += " from Support Team"
            if uid:
                txt = m.text.strip().lower()
                if txt.startswith("accept"):
                    try:
                        # Generate a one-time invite link and mark it as used immediately.
                        link = self.generate_one_time_link()
                        self.mark_link_used(link)
                        self.bot.send_message(uid, f"Your request was accepted by {sender}.\nJoin support group using this one-time link: {link}")
                        self.bot.send_message(m.chat.id, f"Accepted by {sender}, invite sent.")
                    except Exception as e:
                        self.bot.send_message(m.chat.id, f"Error: {e}")
                elif txt.startswith("decline"):
                    reason = m.text.strip()[7:].strip()
                    self.bot.send_message(uid, f"Your request was declined by {sender}.\nReason: {reason}")
                    self.bot.send_message(m.chat.id, f"Declined by {sender}.")
                else:
                    self.bot.send_message(m.chat.id, "Invalid reply. Only Accept or Decline allowed.")
            else:
                self.bot.send_message(m.chat.id, "Original user not found.")

        # ---------------- Log all messages & store usernames ----------------
        @self.bot.message_handler(func=lambda msg: True)
        def logger(msg):
            self.all_users.add(msg.chat.id)
            if msg.from_user.username:
                self.usernames[msg.chat.id] = "@" + msg.from_user.username

    # --- Helper methods ---
    def get_username(self, cid):
        return "@" + self.usernames.get(cid, str(cid)).lstrip("@")
    def load_tgban(self):
        return load_config(self.tgban_fn) if os.path.exists(self.tgban_fn) else []
    def save_tgban(self):
        save_config(self.tgban, self.tgban_fn)
    def save_fwd(self, fwd_id, uid):
        try:
            with open(self.fwd_fn, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data[str(fwd_id)] = uid
        save_config(data, self.fwd_fn)
    def get_fwd_uid(self, fwd_id):
        try:
            with open(self.fwd_fn, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get(str(fwd_id))
        except Exception:
            return None
    def _load_logged_in_users(self):
        """Load persistent login data from tglogin.json and auto-login users."""
        lg = load_tglogin()  # Expected format: { "<chat_id>": "<in-game name>" }
        accs = load_config("Database/Player/accounts.json").get("Accounts", {})
        for cid_str, ingame_name in lg.items():
            cid = int(cid_str)
            for acc in accs.values():
                if acc.get("name") == ingame_name:
                    self.logged[cid] = acc
                    break

    # --- One-Time Link Helpers (stored in tglink.json) ---
    def load_tglink(self):
        try:
            with open("tglink.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    def save_tglink(self, data):
        try:
            with open("tglink.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving tglink.json: {e}")
    def generate_one_time_link(self):
        # Generate a new invite link for the support group.
        link = self.bot.export_chat_invite_link(self.sup_grp)
        links = self.load_tglink()
        links[link] = False  # Mark as unused initially.
        self.save_tglink(links)
        return link
    def mark_link_used(self, link):
        links = self.load_tglink()
        if link in links:
            links[link] = True
            self.save_tglink(links)

    def run(self):
        self.bot.infinity_polling()
