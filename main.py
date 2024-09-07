import asyncio
import nest_asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes,Application, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, filters,ConversationHandler
from telegram.constants import ParseMode
import json
import os
from datetime import datetime

# nest_asyncio'ni qo'llash
nest_asyncio.apply()

# Fayl nomini aniqlash
DATA_FILE = "accounts_data.json"
(WAITING_FOR_USER_NAME,) = range(1)


# JSON faylidan ma'lumotlarni yuklash
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

# Ma'lumotlarni JSON fayliga saqlash
def save_data():
    with open(DATA_FILE, 'w') as f:
        json.dump(accounts, f)

# Qarzdorlikni saqlash uchun yuklangan lug'at
accounts = load_data()

# Tarixni saqlash uchun fayl nomi
HISTORY_FILE = "history_data.json"

# JSON faylidan tarixni yuklash
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return {}

# Tarixni JSON fayliga saqlash
def save_history():
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)

# Amal tarixini saqlash uchun yuklangan lug'at
history = load_history()

# Ruxsat berilgan foydalanuvchilar ro'yxati
AUTHORIZED_USERS = [1517715653, 653894683,2193661,442624121,5444753695]  # Foydalanuvchi ID'larni shu yerga qo'shing

# Foydalanuvchini tekshirish
def is_authorized(update: Update):
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    return user_id in AUTHORIZED_USERS

# Ruxsat berilmagan foydalanuvchilar uchun xabar
async def unauthorized(update: Update):
    await update.message.reply_text("Sizga ushbu botdan foydalanishga ruxsat berilmagan.")

# Asosiy menyuni ko'rsatish
async def show_main_menu(update: Update, context: CallbackContext) -> None:
    if not is_authorized(update):
        await unauthorized(update)
        return

    keyboard = [
        [InlineKeyboardButton("👥 Qarzdorlar ro'yxati", callback_data="list_debtors")],
        [InlineKeyboardButton("➕ Yangi foydalanuvchi qo'shish", callback_data="add_user")],
        [InlineKeyboardButton("📊 Hisobot yaratish", callback_data="generate_report")],
        [InlineKeyboardButton("📁 Bazada ma'lumotlarni fayl qilish", callback_data="send_file")],  # Fayl tugmasi
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Asosiy menyu:", reply_markup=reply_markup)

# Qarzdorlar ro'yxatini ko'rsatish
async def list_debtors_menu(update: Update, context: CallbackContext) -> None:
    if not is_authorized(update):
        await unauthorized(update)
        return

    query = update.callback_query
    await query.answer()

    today = datetime.now()

    if not accounts:
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")]]
        await query.edit_message_text("Hozircha hech qanday qarzdor yo'q.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = []
    for user, balance in accounts.items():
        oldest_date = None
        stiker = ""
        icon = "📈" if balance > 0 else "📉"

        if user in history and history[user]:
            for record in history[user]:
                date_str = record.split(" - ")[0]
                record_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                if oldest_date is None or record_date < oldest_date:
                    oldest_date = record_date

            if oldest_date:
                days_diff = (today - oldest_date).days
                if days_diff <= 10:
                    stiker = "🟢"
                elif days_diff <= 20:
                    stiker = "🟡"
                elif days_diff <= 30:
                    stiker = "🔴"
                else:
                    stiker = "⚫️"

        button_text = f"{stiker} {icon} {user} ({balance})"
        callback_data = f"manage_debt|{user}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Qarzdorlar ro'yxati:", reply_markup=reply_markup)

# Yangi foydalanuvchi qo'shish komandasini boshlash
async def add_user_prompt(update: Update, context: CallbackContext) -> int:
    if not is_authorized(update):
        await unauthorized(update)
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")]]
    await query.edit_message_text("Iltimos, yangi foydalanuvchi nomini kiriting:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Bu yerda context.user_data['current_action'] o'chiriladi
    context.user_data['current_action'] = 'add_user'
    return WAITING_FOR_USER_NAME

# Yangi foydalanuvchini qo'shish
async def add_user(update: Update, context: CallbackContext) -> int:
    user = update.message.text.strip()
    if not user:
        await update.message.reply_text("Foydalanuvchi nomi bo'sh bo'lishi mumkin emas.")
        return WAITING_FOR_USER_NAME
    if user in accounts:
        await update.message.reply_text(f"Foydalanuvchi '{user}' allaqachon mavjud.")
    else:
        accounts[user] = 0
        history[user] = []  # Tarixni boshlash
        save_data()
        save_history()
        await update.message.reply_text(f"Foydalanuvchi '{user}' muvaffaqiyatli qo'shildi.")
    
    # Harakat tugadi, 'current_action' o'chiriladi
    del context.user_data['current_action']
    await show_main_menu(update, context)
    return ConversationHandler.END

# Qarzdor ustida ishlash
# Qarzdor ustida ishlash
async def manage_debt(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if not is_authorized(update):
        await unauthorized(update)
        return

    data = query.data.split("|")
    user = data[1]

    # Agar tarix mavjud bo'lsa
    if user in history and history[user]:
        # Oxirgi 10 ta amalni olish va ularni birlashtirish
        history_text = "\n".join(history[user][-10:])
    else:
        # Tarix yo'q bo'lsa
        history_text = "Tarix mavjud emas."

    keyboard = [
        [InlineKeyboardButton("➖ Berdim", callback_data=f"add_debt|{user}"),
         InlineKeyboardButton("➕ Oldim", callback_data=f"add_credit|{user}")],
        [InlineKeyboardButton("❌ Foydalanuvchini o'chirish", callback_data=f"delete_user|{user}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="list_debtors")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_chat.send_message(f"{user} bilan ishlash:\n\nSo'nggi 10 ta amal:\n{history_text}", reply_markup=reply_markup)

# Foydalanuvchi uchun kredit yoki qarz qo'shgandan so'ng eski menyuni o'chirish
async def add_debt(update: Update, context: CallbackContext) -> None:
    await clear_previous_menu(update, context)

# Xabarni va menyularni yangilashdan oldingi eski xabarlarni o'chirish uchun funksiyani yaratamiz
async def clear_previous_menu(update: Update, context: CallbackContext):
    try:
        if update.message:
            await update.message.delete()
        elif update.callback_query:
            await update.callback_query.message.delete()
    except Exception as e:
        print(f"Xabarni o'chirishda xatolik yuz berdi: {e}")

# Funksiyani chaqirganingizda, `update` va `context` ni kiritishni unutmang:
    await clear_previous_menu(update, context)  # To'g'ri chaqiruv
async def add_debt(update: Update, context: CallbackContext) -> None:
    if not is_authorized(update):
        await unauthorized(update)
        return

    query = update.callback_query
    await query.answer()

    data = query.data.split("|")
    if len(data) != 2 or data[0] != "add_debt":
        await query.edit_message_text("Noto'g'ri so'rov.")
        return

    user = data[1]
    keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data=f"manage_debt|{user}")]]
    await query.message.reply_text(f"{user} uchun qo'shiladigan qarz miqdorini kiriting:", reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data['current_action'] = ('add_debt', user)

# Haq qo'shish
async def add_credit(update: Update, context: CallbackContext) -> None:
    if not is_authorized(update):
        await unauthorized(update)
        return

    query = update.callback_query
    await query.answer()

    data = query.data.split("|")
    if len(data) != 2 or data[0] != "add_credit":
        await query.edit_message_text("Noto'g'ri so'rov.")
        return

    user = data[1]
    keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data=f"manage_debt|{user}")]]
    await query.message.reply_text(f"{user} uchun qo'shiladigan haq miqdorini kiriting:", reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data['current_action'] = ('add_credit', user)

# Xabarni va menyularni yangilashdan oldingi eski xabarlarni o'chirish uchun funksiyani yaratamiz
async def clear_previous_menu(update: Update, context: CallbackContext):
    try:
        if update.message:
            await update.message.delete()
        elif update.callback_query:
            await update.callback_query.message.delete()
    except:
        pass  # Agar xabar o'chirilmasa, xato chiqmasligi uchun o'tkazib yuboramiz

# Foydalanuvchining matnli javobini qabul qilish (qarz yoki haq qo'shish)
# Yangi harakatlarni admin bilan birga tarixda saqlash
async def handle_message(update: Update, context: CallbackContext) -> None:
    if 'current_action' not in context.user_data:
        await update.message.reply_text("Nimani qilmoqchi ekanligingizni aniqlash uchun menyudan foydalaning.\nMenydan foydalanish uchun /start kamandasini bering")
        return

    current_action = context.user_data['current_action']

    if isinstance(current_action, str) and current_action == 'add_user':
        await add_user(update, context)
        return

    if isinstance(current_action, tuple) and current_action[0] in ['add_debt', 'add_credit']:
        try:
            action, user = current_action
        except ValueError:
            await update.message.reply_text("Noto'g'ri ma'lumot kiritilgan.")
            return

        try:
            amount = float(update.message.text)
        except ValueError:
            await update.message.reply_text("Iltimos, to'g'ri raqam kiriting.")
            return

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        admin_name = update.message.from_user.first_name  # Adminning ismini olish

        if user not in history:
            history[user] = []

        prev_balance = accounts.get(user, 0)

        if action == 'add_debt':
            new_balance = prev_balance - amount
            accounts[user] = new_balance
            # Tarixga admin ismi bilan yozish
            history[user].append(f"{now} - Qarz: -{amount} (Yangi balans: {new_balance}) - Admin: {admin_name}")
            await send_notification(update, context, f"{user} sizdan {amount} miqdorida qarz oldi. Admin: {admin_name}")

        elif action == 'add_credit':
            new_balance = prev_balance + amount
            accounts[user] = new_balance
            # Tarixga admin ismi bilan yozish
            history[user].append(f"{now} - Haq: +{amount} (Yangi balans: {new_balance}) - Admin: {admin_name}")

            if prev_balance == 0:
                message = f"Siz {user}dan {amount} miqdorda qarz oldingiz. Admin: {admin_name}"
            elif prev_balance < 0 and new_balance >= 0:
                if new_balance == 0:
                    message = f"Siz qarzingizdan qutuldingiz. Admin: {admin_name}"
                else:
                    message = f"Siz {user}dan ortiqcha {abs(new_balance)} miqdorda qarz oldingiz. Admin: {admin_name}"
            elif prev_balance < 0 and new_balance < 0:
                message = f"{user} sizga {amount} miqdorida qarz to'ladi. Hozirgi qarzi: {abs(new_balance)}. Admin: {admin_name}"
            elif prev_balance > 0:
                message = f"Siz {user}dan {amount} miqdorda pul oldingiz. Admin: {admin_name}"

            await send_notification(update, context, message)

        save_data()
        save_history()

        status = "Qarzdor" if accounts[user] < 0 else "Haqdor" if accounts[user] > 0 else "Balans nol"
        color = "red" if accounts[user] < 0 else "green" if accounts[user] > 0 else "black"
        message = f"<b>{user}</b> uchun o'zgartirish kiritildi.\n<b>Yangi balans:</b> {accounts[user]}"

        del context.user_data['current_action']

        await clear_previous_menu(update, context)  # To'g'ri
  # Eski menyularni o'chirish
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)
        await show_main_menu(update, context)
        return

    await update.message.reply_text("Nimani qilmoqchi ekanligingizni aniqlash uchun menyudan foydalaning.")

# Botni boshqa menyular o'rniga yangi menyuni ochishdan oldin eski xabarlarni o'chiradigan holatga moslaymiz
async def show_main_menu(update: Update, context: CallbackContext) -> None:
    await clear_previous_menu(update, context)  # Eski menyuni o'chirish
    if not is_authorized(update):
        await unauthorized(update)
        return

    keyboard = [
        [InlineKeyboardButton("👥 Qarzdorlar ro'yxati", callback_data="list_debtors")],
        [InlineKeyboardButton("➕ Yangi foydalanuvchi qo'shish", callback_data="add_user")],
        [InlineKeyboardButton("📊 Hisobot yaratish", callback_data="generate_report")],
        [InlineKeyboardButton("📁 Bazada ma'lumotlarni fayl qilish", callback_data="send_file")],  # Fayl tugmasi

    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_chat.send_message("Asosiy menyu:", reply_markup=reply_markup)

# Har bir menyuni yangilashdan oldin mavjud xabarlarni o'chirish
# Qarzdorlar ro'yxatini ko'rsatish
async def list_debtors_menu(update: Update, context: CallbackContext) -> None:
    if not is_authorized(update):
        await unauthorized(update)
        return

    query = update.callback_query
    await query.answer()

    today = datetime.now()

    if not accounts:
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")]]
        await query.edit_message_text("Hozircha hech qanday qarzdor yo'q.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = []
    for user, balance in accounts.items():
        oldest_date = None
        stiker = ""
        icon = "📈" if balance > 0 else "📉"

        # Formatlangan balans
        formatted_balance = f"{int(balance):,}".replace(",", " ")

        if user in history and history[user]:
            for record in history[user]:
                date_str = record.split(" - ")[0]
                record_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                if oldest_date is None or record_date < oldest_date:
                    oldest_date = record_date

            if oldest_date:
                days_diff = (today - oldest_date).days
                if days_diff <= 10:
                    stiker = "🟢"
                elif days_diff <= 20:
                    stiker = "🟡"
                elif days_diff <= 30:
                    stiker = "🔴"
                else:
                    stiker = "⚫️"

        button_text = f"{stiker} {icon} {user} ({formatted_balance})"
        callback_data = f"manage_debt|{user}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Qarzdorlar ro'yxati:", reply_markup=reply_markup)

# Notification (snackbar) xabarini yuborish
async def send_notification(update: Update, context: CallbackContext, message: str):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message, disable_notification=True)

# Hisobot yaratish
async def generate_report_menu(update: Update, context: CallbackContext) -> None:
    if not is_authorized(update):
        await unauthorized(update)
        return

    query = update.callback_query
    await query.answer()

    now = datetime.now()
    total_debt = 0  # Umumiy qarz
    total_credit = 0  # Umumiy haqq

    message = f"Hisobot - {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    for user, balance in accounts.items():
        status = "Haqdor" if balance > 0 else "Qarzdor" if balance < 0 else "Balans nol"
        if balance > 0:
            total_credit += balance
        elif balance < 0:
            total_debt += abs(balance)
        message += f"{user}: {balance} ({status})\n"

    net_balance = total_credit - total_debt
    net_status = "plusda" if net_balance > 0 else "minusda" if net_balance < 0 else "balans nol"

    message += "\nUmumiy natijalar:\n"
    message += f"Umumiy haqqingiz: {total_credit}\n"
    message += f"Umumiy qarzingiz: {total_debt}\n"
    message += f"Siz hozirgi paytda {net_balance} bilan {net_status} ekansiz.\n"

    keyboard = [
        [InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="main_menu")]
    ]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

#foydalanuvchini o'chirish
async def delete_user(update: Update, context: CallbackContext) -> None:
    if not is_authorized(update):
        await unauthorized(update)
        return

    query = update.callback_query
    await query.answer()

    data = query.data.split("|")
    if len(data) != 2 or data[0] != "confirm_delete":
        await query.edit_message_text("Noto'g'ri so'rov.")
        return

    user = data[1]

    if user in accounts:
        del accounts[user]
        if user in history:
            del history[user]
        save_data()
        save_history()
        await query.edit_message_text(f"{user} muvaffaqiyatli o'chirildi.")
    else:
        await query.edit_message_text(f"{user} foydalanuvchisi topilmadi.")

    await show_main_menu(update, context)

#Foydalanuvchini o'chirishni tasdiqlash 
async def confirm_delete_user(update: Update, context: CallbackContext) -> None:
    if not is_authorized(update):
        await unauthorized(update)
        return

    query = update.callback_query
    await query.answer()

    data = query.data.split("|")
    if len(data) != 2 or data[0] != "delete_user":
        await query.edit_message_text("Noto'g'ri so'rov.")
        return

    user = data[1]
    
    keyboard = [
        [InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"confirm_delete|{user}")],
        [InlineKeyboardButton("❌ Yo'q, o'chirmaslik", callback_data=f"manage_debt|{user}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"{user} foydalanuvchisini o'chirishni xohlaysizmi?", reply_markup=reply_markup)

# Faylni yaratish va yuborish
# Ikkala ma'lumotni bitta faylda birlashtirish
# Faylni yaratish va yuborish
# Faylni yaratish va yuborish
async def send_file(update: Update, context: CallbackContext) -> None:
    if not is_authorized(update):
        await unauthorized(update)
        return

    query = update.callback_query
    await query.answer()

    combined_data = {}

    for user, balance in accounts.items():
        user_history = history.get(user, [])
        # Intga o'tkazish va 3 xonadan ajratish
        formatted_balance = f"{int(balance):,}".replace(",", " ")

        formatted_history = []
        for entry in user_history:
            try:
                # Ma'lumotlarni to'g'ri qismlarga ajratish
                date, transaction_type, balance_part, admin_part = entry.split(" - ")
                balance = int(float(balance_part.split(": ")[1]))  # Floatdan int ga o'girish
                # Int ga o'tkazib formatlash va 3 xonadan ajratish
                formatted_balance = f"{balance:,}".replace(",", " ")
                formatted_history.append(f"{date} - {transaction_type} - Balans: {formatted_balance} - {admin_part}")
            except (ValueError, IndexError):
                # Agar xato bo'lsa, bu qatorni o'tkazib yuboramiz
                continue

        combined_data[user] = {
            "history": formatted_history,
            "balance": formatted_balance
        }

    combined_filename = "combined_data_export.json"

    # Combined ma'lumotlarni faylga yozish
    with open(combined_filename, 'w') as combined_file:
        json.dump(combined_data, combined_file, indent=4, ensure_ascii=False)

    # Faylni yuborish
    await context.bot.send_document(chat_id=update.effective_chat.id, document=open(combined_filename, 'rb'), caption="Bazada barcha ma'lumotlar (tarix va balans)")

# Botni ishga tushirish
async def main():
    application = Application.builder().token("1804879860:AAGtvPp3GKuIk7KHRcHTU5S4ayR0dc-6aF8").build()

    # Komanda handlerlari
    application.add_handler(CommandHandler("start", show_main_menu))

    # CallbackQuery handlerlari
    application.add_handler(CallbackQueryHandler(list_debtors_menu, pattern="list_debtors"))
    application.add_handler(CallbackQueryHandler(add_user_prompt, pattern="add_user"))
    application.add_handler(CallbackQueryHandler(generate_report_menu, pattern="generate_report"))
    application.add_handler(CallbackQueryHandler(manage_debt, pattern="manage_debt\\|"))
    application.add_handler(CallbackQueryHandler(add_debt, pattern="add_debt\\|"))
    application.add_handler(CallbackQueryHandler(add_credit, pattern="add_credit\\|"))
    application.add_handler(CallbackQueryHandler(confirm_delete_user, pattern="delete_user\\|"))
    application.add_handler(CallbackQueryHandler(delete_user, pattern="confirm_delete\\|"))
    application.add_handler(CallbackQueryHandler(show_main_menu, pattern="main_menu"))
    application.add_handler(CallbackQueryHandler(send_file, pattern="send_file"))  # Yangi fayl tugmasi uchun handler


    # Matnli xabarlar uchun handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run polling
    await application.run_polling()

if __name__ == '__main__':
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
