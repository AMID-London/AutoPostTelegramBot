import telebot
from telebot import types
from datetime import datetime, timedelta
import json
import threading
import time
import schedule
import pytz

# 🎯 Telegram bot token
TOKEN = '7356933942:AAGSKDy-Sh-llL6eBrFDHAudhJyPQ-hBGNg'
bot = telebot.TeleBot(TOKEN)

# 👑 ID власника (щоб ніхто інший не міг керувати ботом)
OWNER_ID = 7941911860

# 📍 Групи, куди бот може постити (ID + назва для кнопок)
GROUPS = {
    "🇬🇧 Англія": -1002008390518,  # @LondonUkrainePost
    "🌍 Європа": -1001971858438  # @your_driver_europe
}

# 🌍 Часовий пояс — Лондон
LONDON_TZ = pytz.timezone("Europe/London")

# 🧠 Стан користувача під час діалогу
user_state = {}
scheduled_posts = []


# ===== СТАРТ І ВИБІР ГРУПИ =====
@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "⛔️ У вас немає доступу.")
        return
    show_group_menu(message.chat.id)


def show_group_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for name in GROUPS.keys():
        markup.add(name)
    bot.send_message(chat_id,
                     "👋 Привіт! Обери групу для автопосту:",
                     reply_markup=markup)
    user_state[chat_id] = {"stage": "choose_group"}


@bot.message_handler(func=lambda m: m.text in GROUPS)
def group_selected(message):
    chat_id = message.chat.id
    group_name = message.text
    group_id = GROUPS[group_name]

    user_state[chat_id] = {
        "stage": "group_menu",
        "group_name": group_name,
        "group_id": group_id
    }

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📅 Запланувати пост", "📋 Переглянути заплановані")
    markup.add("🔙 Назад")
    bot.send_message(chat_id,
                     f"🔘 Обери дію для групи «{group_name}»",
                     reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "🔙 Назад")
def go_back(message):
    current_stage = user_state.get(message.chat.id, {}).get("stage")
    if current_stage == "group_menu":
        show_group_menu(message.chat.id)
    else:
        user_state.pop(message.chat.id, None)
        start(message)


@bot.message_handler(func=lambda m: m.text == "📅 Запланувати пост")
def start_post_planning(message):
    chat_id = message.chat.id
    state = user_state.get(chat_id)
    if not state or "group_id" not in state:
        return start(message)

    state["stage"] = "wait_post"
    state["buttons"] = []
    bot.send_message(chat_id, "📝 Надішли текст посту:")


@bot.message_handler(
    func=lambda m: user_state.get(m.chat.id, {}).get("stage") == "wait_post")
def receive_post_text(message):
    chat_id = message.chat.id
    user_state[chat_id]["post"] = message.text
    user_state[chat_id]["stage"] = "add_buttons"

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Додати кнопку", "➡️ Без кнопок")
    markup.add("🔙 Назад")
    bot.send_message(chat_id,
                     "🔘 Хочеш додати кнопки під пост?",
                     reply_markup=markup)


@bot.message_handler(
    func=lambda m: user_state.get(m.chat.id, {}).get("stage") == "add_buttons")
def buttons_step(message):
    chat_id = message.chat.id
    if message.text == "➕ Додати кнопку":
        user_state[chat_id]["stage"] = "button_text"
        bot.send_message(chat_id, "✏️ Введи текст кнопки:")
    elif message.text == "➡️ Без кнопок":
        show_date_options(chat_id)
    elif message.text == "🔙 Назад":
        group_selected(
            types.SimpleNamespace(chat=message.chat,
                                  text=user_state[chat_id]["group_name"]))
    else:
        bot.send_message(chat_id, "❌ Команда не розпізнана.")


@bot.message_handler(
    func=lambda m: user_state.get(m.chat.id, {}).get("stage") == "button_text")
def button_text_step(message):
    chat_id = message.chat.id
    user_state[chat_id]["temp_btn_text"] = message.text
    user_state[chat_id]["stage"] = "button_url"
    bot.send_message(chat_id, "🔗 Введи URL для кнопки:")


@bot.message_handler(
    func=lambda m: user_state.get(m.chat.id, {}).get("stage") == "button_url")
def button_url_step(message):
    chat_id = message.chat.id
    url = message.text
    if not url.startswith("http"):
        return bot.send_message(chat_id,
                                "⚠️ URL має починатися з http або https.")

    btn = {"text": user_state[chat_id].pop("temp_btn_text"), "url": url}
    user_state[chat_id]["buttons"].append(btn)
    user_state[chat_id]["stage"] = "add_buttons"

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Додати кнопку", "➡️ Без кнопок")
    markup.add("🔙 Назад")
    bot.send_message(chat_id,
                     f"✅ Кнопка додана. Ще кнопки?",
                     reply_markup=markup)


def show_date_options(chat_id):
    user_state[chat_id]["stage"] = "choose_date_mode"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    today = datetime.now(LONDON_TZ).date()
    markup.add(f"{today.strftime('%d.%m.%Y')} + місяць")
    markup.add("📅 Вибрати іншу дату", "🗓 Вибрати дні тижня")
    markup.add("🔙 Назад")
    bot.send_message(chat_id,
                     "📆 Обери спосіб публікації:",
                     reply_markup=markup)


@bot.message_handler(func=lambda m: user_state.get(m.chat.id, {}).get("stage")
                     == "choose_date_mode")
def handle_date_mode(message):
    chat_id = message.chat.id
    if "місяць" in message.text:
        today = datetime.now(LONDON_TZ).date()
        user_state[chat_id]["start_date"] = str(today)
        user_state[chat_id]["end_date"] = str(today + timedelta(days=30))
        user_state[chat_id]["days"] = []
        user_state[chat_id]["stage"] = "choose_time"
        bot.send_message(
            chat_id, "🕒 Введи час або два (напр. 10:00 або 10:00, 17:00):")
    elif "інша дата" in message.text:
        user_state[chat_id]["stage"] = "custom_date"
        bot.send_message(chat_id, "📆 Введи дату у форматі ДД.ММ.РРРР:")
    elif "дні тижня" in message.text:
        user_state[chat_id]["stage"] = "choose_days"
        user_state[chat_id]["days"] = []
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
        markup.add("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд", "✅ Готово")
        markup.add("🔙 Назад")
        bot.send_message(chat_id,
                         "✅ Обери дні публікацій:",
                         reply_markup=markup)
    elif message.text == "🔙 Назад":
        group_selected(
            types.SimpleNamespace(chat=message.chat,
                                  text=user_state[chat_id]["group_name"]))


@bot.message_handler(
    func=lambda m: user_state.get(m.chat.id, {}).get("stage") == "custom_date")
def custom_date(message):
    chat_id = message.chat.id
    try:
        date = datetime.strptime(message.text, "%d.%m.%Y").date()
        user_state[chat_id]["start_date"] = str(date)
        user_state[chat_id]["end_date"] = str(date + timedelta(days=30))
        user_state[chat_id]["days"] = []
        user_state[chat_id]["stage"] = "choose_time"
        bot.send_message(
            chat_id, "🕒 Введи час або два (напр. 10:00 або 10:00, 17:00):")
    except:
        bot.send_message(chat_id, "❌ Невірна дата. Спробуй ще раз.")


@bot.message_handler(
    func=lambda m: user_state.get(m.chat.id, {}).get("stage") == "choose_days")
def choose_days(message):
    chat_id = message.chat.id
    text = message.text
    if text == "✅ Готово":
        today = datetime.now(LONDON_TZ).date()
        user_state[chat_id]["start_date"] = str(today)
        user_state[chat_id]["end_date"] = str(today + timedelta(days=30))
        user_state[chat_id]["stage"] = "choose_time"
        bot.send_message(
            chat_id, "🕒 Введи час або два (напр. 10:00 або 10:00, 17:00):")
    elif text in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]:
        if text not in user_state[chat_id]["days"]:
            user_state[chat_id]["days"].append(text)
            bot.send_message(chat_id, f"✅ Додано {text}")
        else:
            bot.send_message(chat_id, f"⚠️ {text} вже вибрано")
    elif text == "🔙 Назад":
        show_date_options(chat_id)


@bot.message_handler(
    func=lambda m: user_state.get(m.chat.id, {}).get("stage") == "choose_time")
def choose_time(message):
    chat_id = message.chat.id
    times = [t.strip() for t in message.text.split(",")]
    if not all(t.count(":") == 1 and len(t) == 5 for t in times):
        return bot.send_message(
            chat_id, "❌ Невірний формат часу. Приклад: 10:00 або 10:00, 17:00")

    state = user_state[chat_id]
    new_post = {
        "group_id": state["group_id"],
        "group_name": state["group_name"],
        "post": state["post"],
        "start_date": state["start_date"],
        "end_date": state["end_date"],
        "times": times,
        "buttons": state["buttons"],
        "days": state["days"]
    }

    scheduled_posts.append(new_post)
    save_data()
    user_state.pop(chat_id, None)

    bot.send_message(
        chat_id,
        f"✅ Пост збережено та буде публікуватись з {new_post['start_date']} по {new_post['end_date']} у часи: {', '.join(times)}"
    )


# ===== ЗБЕРЕЖЕННЯ / ЗАВАНТАЖЕННЯ =====
def save_data():
    with open("posts.json", "w") as f:
        json.dump(scheduled_posts, f, indent=2)


def load_data():
    global scheduled_posts
    try:
        with open("posts.json", "r") as f:
            scheduled_posts = json.load(f)
    except:
        scheduled_posts = []


load_data()


# ===== ПЕРЕВІРКА РОЗКЛАДУ ТА НАДСИЛАННЯ =====
def check_scheduled_posts():
    now = datetime.now(LONDON_TZ)
    now_time = now.strftime("%H:%M")
    today = now.date()
    weekday_map = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
    weekday = weekday_map[now.weekday()]

    print(f"\n🕒 [{now_time}] Перевірка постів на {today} ({weekday})")

    for idx, post in enumerate(scheduled_posts):
        try:
            print(
                f"➡️ Перевірка поста для {post.get('group_name', 'Невідомо')}")

            # Перевірка ключів
            for key in ["group_id", "post", "start_date", "end_date", "times"]:
                if key not in post:
                    raise KeyError(
                        f"⛔️ В пості #{idx + 1} відсутній ключ: {key}")

            # Перевірка часу
            if now_time not in post["times"]:
                print("   ⏩ Пропущено (час не співпав)")
                continue

            # Перевірка дати
            start = datetime.strptime(post["start_date"], "%Y-%m-%d").date()
            end = datetime.strptime(post["end_date"], "%Y-%m-%d").date()
            if not (start <= today <= end):
                print("   ⏩ Пропущено (дата не підходить)")
                continue

            # Перевірка дня тижня
            if post.get("days") and weekday not in post["days"]:
                print("   ⏩ Пропущено (день тижня не вибраний)")
                continue

            # Створення кнопок
            markup = types.InlineKeyboardMarkup()
            for btn in post.get("buttons", []):
                markup.add(
                    types.InlineKeyboardButton(btn["text"], url=btn["url"]))

            # Надсилання посту
            bot.send_message(post["group_id"],
                             post["post"],
                             reply_markup=markup if post["buttons"] else None)
            print(f"✅ Пост НАДІСЛАНО в {post['group_name']}")

        except Exception as e:
            error_text = f"❌ ПОМИЛКА з постом #{idx + 1}:\n{e}"
            print(error_text)
            try:
                bot.send_message(OWNER_ID, error_text)
            except:
                print("⚠️ Не вдалося надіслати повідомлення власнику.")


# ===== ПЕРЕГЛЯД ТА ВИДАЛЕННЯ ЗАПЛАНОВАНОГО =====
@bot.message_handler(func=lambda m: m.text == "📋 Переглянути заплановані")
def view_posts(message):
    chat_id = message.chat.id
    group_id = user_state.get(chat_id, {}).get("group_id")
    posts = [p for p in scheduled_posts if p["group_id"] == group_id]

    if not posts:
        return bot.send_message(
            chat_id, "ℹ️ Немає запланованих постів для цієї групи.")

    for idx, post in enumerate(posts):
        btn = types.InlineKeyboardMarkup()
        btn.add(
            types.InlineKeyboardButton("❌ Скасувати",
                                       callback_data=f"del_{idx}"))
        preview = f"📝 {post['post'][:40]}...\n🕒 {', '.join(post['times'])} | з {post['start_date']} до {post['end_date']}"
        bot.send_message(chat_id, preview, reply_markup=btn)


@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def delete_post(call):
    idx = int(call.data.split("_")[1])
    group_id = user_state.get(call.message.chat.id, {}).get("group_id")
    group_posts = [p for p in scheduled_posts if p["group_id"] == group_id]
    if idx < len(group_posts):
        scheduled_posts.remove(group_posts[idx])
        save_data()
        bot.edit_message_text("❌ Пост скасовано.",
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id)


# ===== ПЛАНУВАЛЬНИК У ФОНІ =====
def scheduler_thread():
    schedule.every().minute.do(check_scheduled_posts)
    while True:
        schedule.run_pending()
        time.sleep(1)


threading.Thread(target=scheduler_thread, daemon=True).start()

# ===== СТАРТ БОТА =====
bot.polling(none_stop=True)
