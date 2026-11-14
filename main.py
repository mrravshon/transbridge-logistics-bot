
import os
import sqlite3
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton
)

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

db = sqlite3.connect("transbridge.db")
db.execute("""
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    role TEXT,
    name TEXT,
    phone TEXT
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS cargo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    origin TEXT,
    destination TEXT,
    cargo_type TEXT,
    weight TEXT,
    volume TEXT,
    vehicle TEXT,
    load_date TEXT,
    price TEXT,
    payment TEXT
)
""")
db.commit()


class CargoForm(StatesGroup):
    origin = State()
    destination = State()
    cargo_type = State()
    weight = State()
    volume = State()
    vehicle = State()
    load_date = State()
    price = State()
    payment = State()


roles = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Yuk beruvchi")],
        [KeyboardButton(text="🚛 Tashuvchi")]
    ],
    resize_keyboard=True
)

phone_button = ReplyKeyboardMarkup(
    keyboard=[[
        KeyboardButton(
            text="📱 Telefon raqamni yuborish",
            request_contact=True
        )
    ]],
    resize_keyboard=True
)

def menu(role):
    if role == "Yuk beruvchi":
        buttons = [
            [KeyboardButton(text="➕ Yuk joylashtirish")],
            [KeyboardButton(text="📋 Mening yuklarim")],
            [KeyboardButton(text="🔄 Rolni o‘zgartirish")]
        ]
    else:
        buttons = [
            [KeyboardButton(text="🚛 Fura ma’lumotlarini kiritish")],
            [KeyboardButton(text="🔄 Rolni o‘zgartirish")]
        ]

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Assalomu alaykum!\n"
        "TransBridge Logistics botiga xush kelibsiz.\n\n"
        "O‘z rolingizni tanlang:",
        reply_markup=roles
    )


@dp.message(F.text.in_(["📦 Yuk beruvchi", "🚛 Tashuvchi"]))
async def choose_role(message: Message, state: FSMContext):
    role = (
        "Yuk beruvchi"
        if message.text == "📦 Yuk beruvchi"
        else "Tashuvchi"
    )

    db.execute("""
        INSERT INTO users (telegram_id, role)
        VALUES (?, ?)
        ON CONFLICT(telegram_id)
        DO UPDATE SET role = excluded.role
    """, (message.from_user.id, role))
    db.commit()

    user = db.execute(
        "SELECT name, phone FROM users WHERE telegram_id = ?",
        (message.from_user.id,)
    ).fetchone()

    if not user[0]:
        await state.set_state("registration_name")
        await message.answer(
            "Ismingizni yoki kompaniyangiz nomini yozing:"
        )
    elif not user[1]:
        await state.set_state("registration_phone")
        await message.answer(
            "Telefon raqamingizni yuboring:",
            reply_markup=phone_button
        )
    else:
        await state.clear()
        await message.answer(
            "Xush kelibsiz! Kerakli xizmatni tanlang:",
            reply_markup=menu(role)
        )


@dp.message(F.text == "🔄 Rolni o‘zgartirish")
async def change_role(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Yangi rolingizni tanlang:", reply_markup=roles)


@dp.message(lambda m: m.text == "➕ Yuk joylashtirish")
async def new_cargo(message: Message, state: FSMContext):
    user = db.execute(
        "SELECT role, phone FROM users WHERE telegram_id = ?",
        (message.from_user.id,)
    ).fetchone()

    if not user or user[0] != "Yuk beruvchi" or not user[1]:
        await message.answer("Avval yuk beruvchi sifatida ro‘yxatdan o‘ting.")
        return

    await state.set_state(CargoForm.origin)
    await message.answer(
        "1/9. Yuk qaysi shahardan yuklanadi?\n"
        "Masalan: Moskva, Rossiya"
    )


@dp.message(CargoForm.origin)
async def cargo_origin(message: Message, state: FSMContext):
    await state.update_data(origin=message.text)
    await state.set_state(CargoForm.destination)
    await message.answer("2/9. Yuk qaysi shaharga yetkaziladi?")


@dp.message(CargoForm.destination)
async def cargo_destination(message: Message, state: FSMContext):
    await state.update_data(destination=message.text)
    await state.set_state(CargoForm.cargo_type)
    await message.answer("3/9. Yuk turi qanday?")


@dp.message(CargoForm.cargo_type)
async def cargo_type(message: Message, state: FSMContext):
    await state.update_data(cargo_type=message.text)
    await state.set_state(CargoForm.weight)
    await message.answer("4/9. Yuk og‘irligi qancha? (tonnada)")


@dp.message(CargoForm.weight)
async def cargo_weight(message: Message, state: FSMContext):
    await state.update_data(weight=message.text)
    await state.set_state(CargoForm.volume)
    await message.answer("5/9. Yuk hajmi qancha? (m³, noma’lum bo‘lsa yozing: noma’lum)")


@dp.message(CargoForm.volume)
async def cargo_volume(message: Message, state: FSMContext):
    await state.update_data(volume=message.text)
    await state.set_state(CargoForm.vehicle)
    await message.answer(
        "6/9. Qanday transport kerak?\n"
        "Tent, refrijerator, izoterm, furgon, konteyner yoki boshqa"
    )


@dp.message(CargoForm.vehicle)
async def cargo_vehicle(message: Message, state: FSMContext):
    await state.update_data(vehicle=message.text)
    await state.set_state(CargoForm.load_date)
    await message.answer("7/9. Yuklash sanasi qachon?")


@dp.message(CargoForm.load_date)
async def cargo_load_date(message: Message, state: FSMContext):
    await state.update_data(load_date=message.text)
    await state.set_state(CargoForm.price)
    await message.answer("8/9. Tashish narxi va valyutasi qancha?")


@dp.message(CargoForm.price)
async def cargo_price(message: Message, state: FSMContext):
    await state.update_data(price=message.text)
    await state.set_state(CargoForm.payment)
    await message.answer("9/9. To‘lov sharti qanday?")


@dp.message(CargoForm.payment)
async def cargo_payment(message: Message, state: FSMContext):
    data = await state.get_data()

    db.execute("""
        INSERT INTO cargo (
            user_id, origin, destination, cargo_type,
            weight, volume, vehicle, load_date, price, payment
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        message.from_user.id,
        data["origin"],
        data["destination"],
        data["cargo_type"],
        data["weight"],
        data["volume"],
        data["vehicle"],
        data["load_date"],
        data["price"],
        message.text
    ))
    db.commit()

    await state.clear()

    await message.answer(
        "✅ Yuk e’loningiz saqlandi!\n\n"
        f"📍 Yuklash: {data['origin']}\n"
        f"🏁 Yetkazish: {data['destination']}\n"
        f"📦 Yuk: {data['cargo_type']}\n"
        f"⚖️ Og‘irlik: {data['weight']}\n"
        f"📐 Hajm: {data['volume']}\n"
        f"🚛 Transport: {data['vehicle']}\n"
        f"📅 Sana: {data['load_date']}\n"
        f"💰 Narx: {data['price']}\n"
        f"💳 To‘lov: {message.text}\n\n"
        "E’lon bazaga saqlandi.",
        reply_markup=menu("Yuk beruvchi")
    )


@dp.message(F.text == "📋 Mening yuklarim")
async def my_cargo(message: Message):
    rows = db.execute(
        "SELECT id, origin, destination, cargo_type "
        "FROM cargo WHERE user_id = ? ORDER BY id DESC",
        (message.from_user.id,)
    ).fetchall()

    if not rows:
        await message.answer("Sizda hali yuk e’lonlari yo‘q.")
        return

    result = "📋 Sizning yuk e’lonlaringiz:\n\n"
    for row in rows:
        result += (
            f"#{row[0]}\n"
            f"📍 {row[1]} → {row[2]}\n"
            f"📦 {row[3]}\n\n"
        )

    await message.answer(result)


@dp.message()
async def other_messages(message: Message, state: FSMContext):
    current = await state.get_state()

    if current == "registration_name":
        db.execute(
            "UPDATE users SET name = ? WHERE telegram_id = ?",
            (message.text, message.from_user.id)
        )
        db.commit()
        await state.set_state("registration_phone")
        await message.answer(
            "Telefon raqamingizni yuboring:",
            reply_markup=phone_button
        )
        return

    await message.answer(
        "Iltimos, menyudagi tugmalardan foydalaning."
    )


@dp.message(F.contact)
async def get_phone(message: Message, state: FSMContext):
    contact = message.contact

    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer("Iltimos, o‘z telefon raqamingizni yuboring.")
        return

    db.execute(
        "UPDATE users SET phone = ? WHERE telegram_id = ?",
        (contact.phone_number, message.from_user.id)
    )
    db.commit()

    user = db.execute(
        "SELECT role FROM users WHERE telegram_id = ?",
        (message.from_user.id,)
    ).fetchone()

    await state.clear()

    role = user[0] if user else "Yuk beruvchi"

    await message.answer(
        "✅ Ro‘yxatdan o‘tish muvaffaqiyatli yakunlandi!\n"
        "TransBridge Logistics xizmatiga xush kelibsiz.",
        reply_markup=menu(role)
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
