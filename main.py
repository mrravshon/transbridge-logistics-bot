
import os
import sqlite3
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

db = sqlite3.connect("transbridge.db")
db.execute("""
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    role TEXT,
    name TEXT,
    phone TEXT
)
""")
db.commit()


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


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Assalomu alaykum!\n"
        "TransBridge Logistics botiga xush kelibsiz.\n\n"
        "O'z rolingizni tanlang:",
        reply_markup=roles
    )


@dp.message(F.text.in_(["📦 Yuk beruvchi", "🚛 Tashuvchi"]))
async def choose_role(message: Message):
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

    await message.answer(
        "Ismingizni yoki kompaniyangiz nomini yozing:"
    )


@dp.message(F.text)
async def get_name(message: Message):
    user = db.execute(
        "SELECT role, name FROM users WHERE telegram_id = ?",
        (message.from_user.id,)
    ).fetchone()

    if not user or not user[0]:
        return

    if not user[1]:
        db.execute(
            "UPDATE users SET name = ? WHERE telegram_id = ?",
            (message.text, message.from_user.id)
        )
        db.commit()

        await message.answer(
            "Telefon raqamingizni yuboring:",
            reply_markup=phone_button
        )


@dp.message(F.contact)
async def get_phone(message: Message):
    contact = message.contact

    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer("Iltimos, o'z raqamingizni yuboring.")
        return

    db.execute(
        "UPDATE users SET phone = ? WHERE telegram_id = ?",
        (contact.phone_number, message.from_user.id)
    )
    db.commit()

    await message.answer(
        "✅ Ro'yxatdan o'tish muvaffaqiyatli yakunlandi!\n\n"
        "TransBridge Logistics xizmatiga xush kelibsiz.",
        reply_markup=roles
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
