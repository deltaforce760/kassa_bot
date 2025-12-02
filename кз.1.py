# kassa_bot_final_2025.py — ИДЕАЛЬНАЯ КАССА (с остатком товара!)
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from decimal import Decimal
import asyncio, datetime, json, os, shutil

# ==================== НАСТРОЙКИ ====================
TOKEN = "8260507684:AAFoYPcyWDwMvOe3POUOWaPIXQuTUq78zoc"
ADMIN_ID = 8084351377
ADMIN_PASSWORD = "12345"            # ← ОБЯЗАТЕЛЬНО СМЕНИ!
PRICE_PER_GRAM = Decimal("32")

DATA_FILE = "kassa_data.json"
BACKUP_DIR = "backups"
os.makedirs(BACKUP_DIR, exist_ok=True)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

class Form(StatesGroup):
    value = State()
    password = State()

# ==================== ДАННЫЕ ====================
def load():
    if os.path.exists(DATA_FILE):
        try:
            return json.load(open(DATA_FILE, "r", encoding="utf-8"))
        except: return {}
    return {"goods_balance": "0"}  # остаток товара на старте

def save():
    if os.path.exists(DATA_FILE):
        shutil.copy2(DATA_FILE, os.path.join(BACKUP_DIR, f"backup_{datetime.datetime.now():%Y-%m-%d_%H-%M-%S}.json"))
    json.dump(data, open(DATA_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

data = load()

def is_admin(uid): return uid == ADMIN_ID
def dec(val, default="0"):
    if not val: return Decimal(default)
    try: return Decimal(str(val).replace(",", ".").strip())
    except: return Decimal(default)

# ==================== КЛАВИАТУРЫ ====================
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

kb_user = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="ПОКАЗАТЬ ОТЧЁТ")]], resize_keyboard=True)
kb_admin = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Касса"), KeyboardButton(text="Расходы")],
    [KeyboardButton(text="Поступление и вычеты")],
    [KeyboardButton(text="ПОКАЗАТЬ ОТЧЁТ"), KeyboardButton(text="Сброс дня")]
], resize_keyboard=True)

def inline(items):
    kb = [[InlineKeyboardButton(text=t, callback_data=c)] for t, c in items]
    kb.append([InlineKeyboardButton(text="Назад", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ==================== СТАРТ ====================
@dp.message(CommandStart())
async def start(m: Message):
    today = datetime.date.today().isoformat()
    if data.get("date") != today:
        data["prev_money"] = data.get("balance_money", "0")
        data["prev_goods"] = data.get("goods_balance", "0")  # остаток товара с прошлого дня
        data["date"] = today
        data[today] = {}
        save()
    text = "<b>Касса Кыргызстан</b>\n\n"
    if is_admin(m.from_user.id):
        text += f"Денег: <b>{data.get('prev_money', '0')}$</b>\nТовара: <b>{data.get('prev_goods', '0')} г</b>"
    else:
        text += "Ты можешь только смотреть отчёт"
    await m.answer(text, reply_markup=kb_admin if is_admin(m.from_user.id) else kb_user)

# ==================== МЕНЮ ====================
@dp.message(F.text == "Касса")
async def kassa(m: Message):
    if not is_admin(m.from_user.id): return await m.answer("Только админ!")
    await m.answer("Продажи:", reply_markup=inline([
        ("Автобот — грамм", "in_auto_g"), ("Автобот — $", "in_auto_d"),
        ("Ручные — грамм", "in_man_g"), ("Ручные — $", "in_man_d"),
        ("Скидки $", "in_skidki")
    ]))

@dp.message(F.text == "Расходы")
async def rashody(m: Message):
    if not is_admin(m.from_user.id): return await m.answer("Только админ!")
    await m.answer("Расходы:", reply_markup=inline([
        ("ЗП курьерам $", "in_zp_kur"), ("Реклама $", "in_reklama"), ("ЗП оператору $", "in_zp_oper")
    ]))

@dp.message(F.text == "Поступление и вычеты")
async def post(m: Message):
    if not is_admin(m.from_user.id): return await m.answer("Только админ!")
    await m.answer("Поступление и вычеты:", reply_markup=inline([
        ("Поступление курьеру (г)", "in_post"),
        ("НН / потери (г)", "in_nn"),
        ("Призы (г)", "in_prize"),
        ("Пробники (г)", "in_sample")
    ]))

# ==================== ВВОД ====================
@dp.callback_query(F.data.startswith("in_"))
async def input_value(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return await call.answer("Только админ!", show_alert=True)
    field = call.data[3:]
    names = {
        "auto_g": "Автобот — грамм", "auto_d": "Автобот — $", "man_g": "Ручные — грамм",
        "man_d": "Ручные — $", "skidki": "Скидки $", "zp_kur": "ЗП курьерам $",
        "reklama": "Реклама $", "zp_oper": "ЗП оператору $", "post": "Поступление (г)",
        "nn": "НН (г)", "prize": "Призы (г)", "sample": "Пробники (г)"
    }
    await state.update_data(field=field)
    await state.set_state(Form.value)
    await call.message.edit_text(f"Введи <b>{names.get(field, field)}</b>:")

@dp.message(Form.value)
async def save_value(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id): return await state.clear()
    field = (await state.get_data())["field"]
    val = m.text.strip()

    if field in ["auto_g","man_g","post","nn","prize","sample"]:
        if not val.replace(".","").lstrip("-").isdigit():
            return await m.answer("Ошибка! Только цифры и точку")
    else:
        if dec(val, None) is None:
            return await m.answer("Ошибка! Вводи число (например 1250.50)")

    today = datetime.date.today().isoformat()
    data.setdefault(today, {})[field] = val
    save()
    await m.answer(f"Записано {val}", reply_markup=kb_admin)
    await state.clear()

@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.delete()

# ==================== ОТЧЁТ С ОСТАТКОМ ТОВАРА ====================
@dp.message(F.text == "ПОКАЗАТЬ ОТЧЁТ")
async def report(m: Message):
    today = datetime.date.today().isoformat()
    d = data.get(today, {})

    # === ДЕНЬГИ ===
    prev_money = dec(data.get("prev_money", "0"))

    ag = dec(d.get("auto_g", "0"))
    ad = dec(d.get("auto_d", "0"))
    mg = dec(d.get("man_g", "0"))
    md = dec(d.get("man_d", "0"))

    if ag and not ad: ad = ag * PRICE_PER_GRAM
    if mg and not md: md = mg * PRICE_PER_GRAM
    if ad and not ag: ag = ad / PRICE_PER_GRAM
    if md and not mg: mg = md / PRICE_PER_GRAM

    income = ad + md
    sold_grams = ag + mg
    skidki = dec(d.get("skidki", "0"))
    zp_kur = dec(d.get("zp_kur", "0"))
    reklama = dec(d.get("reklama", "0"))
    zp_oper = dec(d.get("zp_oper", "0"))
    total_expenses = zp_kur + reklama + zp_oper + skidki

    final_money = prev_money + income - total_expenses
    data["balance_money"] = str(final_money.quantize(Decimal("0.01")))

    # === ТОВАР ===
    prev_goods = dec(data.get("prev_goods", "0"))
    postuplenie = dec(d.get("post", "0"))
    vychet = dec(d.get("nn", "0")) + dec(d.get("prize", "0")) + dec(d.get("sample", "0"))
    final_goods = prev_goods + postuplenie - sold_grams - vychet
    data["goods_balance"] = str(final_goods.quantize(Decimal("0.01")))

    save()

    text = f"""
<b>ОТЧЁТ КАССЫ — {datetime.datetime.now():%d.%m.%Y}</b>

<b>Деньги</b>
├ Остаток с прошлого дня:   <b>{prev_money}$</b>
├ Доход от продаж:          <b>+{income}$</b>
├ Расходы и скидки:         <b>-{total_expenses}$</b>
└ <b>Остаток денег:</b>          <u><b>{final_money}$</b></u>

<b>Товар (граммы)</b>
├ Остаток с прошлого дня:   <b>{prev_goods} г</b>
├ Поступление курьеру:      <b>+{postuplenie} г</b>
├ Продано за день:          <b>-{sold_grams} г</b>
├ Вычтено (НН+призы+пробники): <b>-{vychet} г</b>
└ <b>Остаток товара:</b>         <u><b>{final_goods} г</b></u>
    """.strip()

    await m.answer(text, reply_markup=kb_admin if is_admin(m.from_user.id) else kb_user)

# ==================== СБРОС ДНЯ ====================
@dp.message(F.text == "Сброс дня")
async def ask_pass(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id): return
    await state.set_state(Form.password)
    await m.answer("Введи пароль для сброса дня:")

@dp.message(Form.password)
async def reset_day(m: Message, state: FSMContext):
    if m.text.strip() == ADMIN_PASSWORD:
        today = datetime.date.today().isoformat()
        data["prev_money"] = data.get("balance_money", "0")
        data["prev_goods"] = data.get("goods_balance", "0")
        data["date"] = today
        data[today] = {}
        save()
        await m.answer("День сброшен! Новый день начат.", reply_markup=kb_admin)
    else:
        await m.answer("Неверный пароль")
    await state.clear()

# ==================== БЭКАП ====================
@dp.message(Command("backup"))
async def backup(m: Message):
    if is_admin(m.from_user.id) and os.path.exists(DATA_FILE):
        await m.answer_document(FSInputFile(DATA_FILE, filename="kassa_full_backup.json"))

# ==================== ЗАПУСК ====================
async def main():
    await bot.send_message(ADMIN_ID, "Бот кассы запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())