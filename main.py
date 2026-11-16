
import os
import sqlite3
import asyncio
import aiohttp
import math
import re

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

# BOT
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# DATABASE
os.makedirs("/app/data", exist_ok=True)

db = sqlite3.connect(
    "/app/data/transbridge.db",
    check_same_thread=False
)

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

db.execute("""
CREATE TABLE IF NOT EXISTS trucks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    vehicle_type TEXT,
    plate TEXT,
    location TEXT,
    route TEXT,
    capacity TEXT,
    photo_id TEXT
)
""")

db.commit()


# BITIMLAR VA MUZOKARALAR BAZASI

db.execute("""
CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cargo_id INTEGER NOT NULL,
    truck_id INTEGER NOT NULL,
    cargo_owner_id INTEGER NOT NULL,
    carrier_id INTEGER NOT NULL,
    proposer_id INTEGER NOT NULL,
    accepter_id INTEGER NOT NULL,
    agreed_price TEXT,
    agreed_weight TEXT,
    agreed_details TEXT,
    status TEXT DEFAULT 'negotiating',
    proposer_confirmed INTEGER DEFAULT 0,
    accepter_confirmed INTEGER DEFAULT 0,
    proposer_fee INTEGER DEFAULT 0,
    accepter_fee INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS deal_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

db.commit()


# ==========================================
# TRANSBRIDGE: YANGI LOGISTIKA MA'LUMOTLARI
# ==========================================

# Eski bazaga yangi ustunlarni xavfsiz qo'shish
def add_column_if_missing(table, column, definition):
    columns = {
        row[1] for row in db.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }

    if column not in columns:
        db.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


# Yuk joylashuv koordinatalari
add_column_if_missing("cargo", "origin_lat", "REAL")
add_column_if_missing("cargo", "origin_lon", "REAL")
add_column_if_missing("cargo", "destination_lat", "REAL")
add_column_if_missing("cargo", "destination_lon", "REAL")

# Fura joylashuv koordinatalari va marka/modeli
add_column_if_missing("trucks", "location_lat", "REAL")
add_column_if_missing("trucks", "location_lon", "REAL")
add_column_if_missing("trucks", "make", "TEXT")
add_column_if_missing("trucks", "model", "TEXT")


# TRANSPORT TURLARI KATALOGI
db.execute("""
CREATE TABLE IF NOT EXISTS vehicle_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
)
""")

vehicle_types_list = [
    "Tent (Curtainsider)",
    "Refrijerator",
    "Izoterm",
    "Furgon",
    "Mega",
    "Jumbo",
    "Konteyner tashuvchi",
    "Ochiq platforma",
    "Tral (Lowbed)",
    "Samosval",
    "Sisterna",
    "Avtovoz",
    "Don tashuvchi",
    "Hayvon tashuvchi",
    "Yog'och tashuvchi",
    "Beton tashuvchi",
    "Sement tashuvchi",
    "Kimyoviy yuk tashuvchi",
    "Og'ir yuk tashuvchi",
    "Maxsus kranli transport",
    "Hooklift",
    "Walking Floor",
    "Swap Body",
    "Furgon (Van)",
    "Boshqa maxsus transport"
]

db.executemany(
    "INSERT OR IGNORE INTO vehicle_types (name) VALUES (?)",
    [(x,) for x in vehicle_types_list]
)


# FURA MARKALARI
db.execute("""
CREATE TABLE IF NOT EXISTS vehicle_makes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
)
""")

vehicle_makes_list = [
    "Volvo",
    "Scania",
    "Mercedes-Benz",
    "MAN",
    "DAF",
    "Renault Trucks",
    "Iveco",
    "Ford Trucks",
    "KamAZ",
    "MAZ",
    "Shacman",
    "Sinotruk (HOWO)",
    "FAW",
    "Dongfeng",
    "Foton",
    "Isuzu",
    "Hino",
    "Tata",
    "Ashok Leyland",
    "Freightliner",
    "Kenworth",
    "Peterbilt",
    "International",
    "Mack"
]

db.executemany(
    "INSERT OR IGNORE INTO vehicle_makes (name) VALUES (?)",
    [(x,) for x in vehicle_makes_list]
)


# FURA MODELLARI
db.execute("""
CREATE TABLE IF NOT EXISTS vehicle_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    make TEXT NOT NULL,
    model TEXT NOT NULL,
    UNIQUE(make, model)
)
""")

vehicle_models_list = {
    "Volvo": ["FH", "FM", "FMX", "FE"],
    "Scania": ["R Series", "S Series", "G Series", "P Series"],
    "Mercedes-Benz": ["Actros", "Arocs", "Atego", "Axor"],
    "MAN": ["TGX", "TGS", "TGM", "TGL"],
    "DAF": ["XF", "XG", "XG+", "CF"],
    "Renault Trucks": ["T", "C", "K", "D"],
    "Iveco": ["S-Way", "X-Way", "Eurocargo", "Stralis"],
    "Ford Trucks": ["F-MAX", "1848T", "3542T"],
    "KamAZ": ["54901", "6520", "5490", "65115"],
    "MAZ": ["5440", "6430", "6501"],
    "Shacman": ["X3000", "X5000", "F3000"],
    "Sinotruk (HOWO)": ["HOWO T7H", "HOWO A7", "HOWO NX"],
    "FAW": ["J6P", "J7", "JH6"],
    "Dongfeng": ["KL", "KC", "GX"],
    "Foton": ["Auman EST", "Auman GTL"],
    "Isuzu": ["Giga", "F-Series"],
    "Hino": ["700 Series", "500 Series"],
    "Tata": ["Prima", "Signa"],
    "Ashok Leyland": ["AVTR", "Captain"],
    "Freightliner": ["Cascadia", "Coronado"],
    "Kenworth": ["T680", "T880", "W900"],
    "Peterbilt": ["579", "567", "389"],
    "International": ["LT Series", "RH Series"],
    "Mack": ["Anthem", "Granite", "Pinnacle"]
}

for make, models in vehicle_models_list.items():
    for model in models:
        db.execute("""
            INSERT OR IGNORE INTO vehicle_models (make, model)
            VALUES (?, ?)
        """, (make, model))


db.commit()


# HOLATLAR
class RegistrationForm(StatesGroup):
    name = State()


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


class TruckForm(StatesGroup):
    vehicle_type = State()
    plate = State()
    location = State()
    route = State()
    capacity = State()
    photo = State()


# ASOSIY ROLLAR
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

skip_photo = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⏭ O‘tkazib yuborish")]
    ],
    resize_keyboard=True
)



# MENYULAR
def menu(role):
    if role == "Yuk beruvchi":
        buttons = [
            [KeyboardButton(text="➕ Yuk joylashtirish")],
            [KeyboardButton(text="📋 Mening yuklarim")],
            [KeyboardButton(text="🚛 Mos furalarni topish")],
            [KeyboardButton(text="🤝 Mening bitimlarim")],
            [KeyboardButton(text="🔄 Rolni o‘zgartirish")]
        ]
    else:
        buttons = [
            [KeyboardButton(text="➕ Fura qo‘shish")],
            [KeyboardButton(text="🚛 Mening furalarim")],
            [KeyboardButton(text="📦 Mos yuklarni topish")],
            [KeyboardButton(text="🤝 Mening bitimlarim")],
            [KeyboardButton(text="🔄 Rolni o‘zgartirish")]
        ]

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )



# START
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        "Assalomu alaykum!\n"
        "TransBridge Logistics botiga xush kelibsiz.\n\n"
        "O‘z rolingizni tanlang:",
        reply_markup=roles
    )


# ROL TANLASH
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
        await state.set_state(RegistrationForm.name)
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


# ISMNI QABUL QILISH
@dp.message(RegistrationForm.name)
async def registration_name(message: Message, state: FSMContext):

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


# TELEFON RAQAMINI QABUL QILISH
@dp.message(F.contact)
async def get_phone(message: Message, state: FSMContext):

    contact = message.contact

    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer(
            "Iltimos, o‘z telefon raqamingizni yuboring."
        )
        return

    if await state.get_state() != "registration_phone":
        await message.answer(
            "Avval ro‘yxatdan o‘ting."
        )
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


# ROLNI O‘ZGARTIRISH
@dp.message(F.text == "🔄 Rolni o‘zgartirish")
async def change_role(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Yangi rolingizni tanlang:",
        reply_markup=roles
    )


# =================================
# YUK BERUVCHI BO‘LIMI
# =================================

@dp.message(F.text == "➕ Yuk joylashtirish")
async def new_cargo(message: Message, state: FSMContext):

    user = db.execute(
        "SELECT role, phone FROM users WHERE telegram_id = ?",
        (message.from_user.id,)
    ).fetchone()

    if not user or user[0] != "Yuk beruvchi" or not user[1]:
        await message.answer(
            "Avval yuk beruvchi sifatida ro‘yxatdan o‘ting."
        )
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
    await message.answer("5/9. Yuk hajmi qancha? (m³)")


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


# MENING YUKLARIM
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


# =================================
# TASHUVCHI BO‘LIMI
# =================================

# YANGI FURA QO‘SHISH
@dp.message(F.text == "➕ Fura qo‘shish")
async def add_truck(message: Message, state: FSMContext):

    user = db.execute(
        "SELECT role, phone FROM users WHERE telegram_id = ?",
        (message.from_user.id,)
    ).fetchone()

    if not user or user[0] != "Tashuvchi" or not user[1]:
        await message.answer(
            "Avval tashuvchi sifatida ro‘yxatdan o‘ting."
        )
        return

    await state.set_state(TruckForm.vehicle_type)

    await message.answer(
        "1/6. Fura turi qanday?\n\n"
        "Tent, refrijerator, izoterm, furgon, "
        "konteyner, mega yoki boshqa"
    )


@dp.message(TruckForm.vehicle_type)
async def truck_type(message: Message, state: FSMContext):
    await state.update_data(vehicle_type=message.text)
    await state.set_state(TruckForm.plate)

    await message.answer(
        "2/6. Furaning davlat raqamini kiriting:"
    )


@dp.message(TruckForm.plate)
async def truck_plate(message: Message, state: FSMContext):
    await state.update_data(plate=message.text)
    await state.set_state(TruckForm.location)

    await message.answer(
        "3/6. Fura hozir qayerda joylashgan?\n"
        "Masalan: Moskva, Rossiya"
    )


@dp.message(TruckForm.location)
async def truck_location(message: Message, state: FSMContext):
    await state.update_data(location=message.text)
    await state.set_state(TruckForm.route)

    await message.answer(
        "4/6. Qaysi yo‘nalishlarda yuk tashiydi?\n"
        "Masalan: Rossiya – O‘zbekiston"
    )


@dp.message(TruckForm.route)
async def truck_route(message: Message, state: FSMContext):
    await state.update_data(route=message.text)
    await state.set_state(TruckForm.capacity)

    await message.answer(
        "5/6. Furaning yuk ko‘tarish imkoniyati qancha?\n"
        "Masalan: 20 tonna"
    )


@dp.message(TruckForm.capacity)
async def truck_capacity(message: Message, state: FSMContext):
    await state.update_data(capacity=message.text)
    await state.set_state(TruckForm.photo)

    await message.answer(
        "6/6. Furaning rasmini yuboring.\n"
        "Agar hozir rasm bo‘lmasa, «O‘tkazib yuborish» tugmasini bosing.",
        reply_markup=skip_photo
    )


# FURA RASMINI SAQLASH
@dp.message(TruckForm.photo, F.photo)
async def truck_photo(message: Message, state: FSMContext):

    photo_id = message.photo[-1].file_id

    await save_truck(message, state, photo_id)


# RASMSIZ SAQLASH
@dp.message(TruckForm.photo, F.text == "⏭ O‘tkazib yuborish")
async def truck_skip_photo(message: Message, state: FSMContext):

    await save_truck(message, state, None)


# FURANI BAZAGA SAQLASH
async def save_truck(message: Message, state: FSMContext, photo_id):

    data = await state.get_data()

    db.execute("""
        INSERT INTO trucks (
            user_id, vehicle_type, plate,
            location, route, capacity, photo_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        message.from_user.id,
        data["vehicle_type"],
        data["plate"],
        data["location"],
        data["route"],
        data["capacity"],
        photo_id
    ))

    db.commit()
    await state.clear()

    await message.answer(
        "✅ Fura muvaffaqiyatli saqlandi!\n\n"
        f"🚛 Turi: {data['vehicle_type']}\n"
        f"🔢 Davlat raqami: {data['plate']}\n"
        f"📍 Joylashuvi: {data['location']}\n"
        f"🛣 Yo‘nalishi: {data['route']}\n"
        f"⚖️ Yuk ko‘tarishi: {data['capacity']}\n\n"
        "Yana fura qo‘shishingiz mumkin.",
        reply_markup=menu("Tashuvchi")
    )


# MENING FURALARIM
@dp.message(F.text == "🚛 Mening furalarim")
async def my_trucks(message: Message):

    rows = db.execute("""
        SELECT id, vehicle_type, plate, location,
               route, capacity, photo_id
        FROM trucks
        WHERE user_id = ?
        ORDER BY id DESC
    """, (message.from_user.id,)).fetchall()

    if not rows:
        await message.answer(
            "Siz hali fura qo‘shmagansiz.",
            reply_markup=menu("Tashuvchi")
        )
        return

    await message.answer(
        f"🚛 Sizning furalaringiz soni: {len(rows)}"
    )

    for row in rows:

        text = (
            f"🚛 Fura #{row[0]}\n"
            f"Transport: {row[1]}\n"
            f"Davlat raqami: {row[2]}\n"
            f"📍 Joylashuvi: {row[3]}\n"
            f"🛣 Yo‘nalishi: {row[4]}\n"
            f"⚖️ Yuk ko‘tarishi: {row[5]}"
        )

        if row[6]:
            await message.answer_photo(
                photo=row[6],
                caption=text
            )
        else:
            await message.answer(text)


# =================================
# MOS FURALARNI TOPISH
# =================================

import re

def get_number(value):
    match = re.search(r"\d+(?:[.,]\d+)?", str(value))
    if match:
        return float(match.group().replace(",", "."))
    return None


@dp.message(F.text == "🚛 Mos furalarni topish")
async def find_trucks(message: Message):

    cargo = db.execute("""
        SELECT id, origin, destination, cargo_type,
               weight, vehicle
        FROM cargo
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (message.from_user.id,)).fetchone()

    if not cargo:
        await message.answer(
            "Avval yuk joylashtiring."
        )
        return

    cargo_id = cargo[0]
    cargo_weight = get_number(cargo[4])

    trucks = db.execute("""
        SELECT t.id, t.user_id, t.vehicle_type,
               t.plate, t.location, t.route, t.capacity,
               u.name
        FROM trucks t
        JOIN users u ON u.telegram_id = t.user_id
        WHERE t.user_id != ?
        ORDER BY t.id DESC
    """, (message.from_user.id,)).fetchall()

    candidates = []

    for truck in trucks:
        capacity = get_number(truck[6])

        if (
            cargo_weight is not None
            and capacity is not None
            and capacity < cargo_weight
        ):
            continue

        candidates.append(truck)

    if not candidates:
        await message.answer(
            "Hozircha yukingizga mos kelishi mumkin "
            "bo‘lgan furalar topilmadi."
        )
        return

    await message.answer(
        f"🚛 Yukingiz: {cargo[3]}\n"
        f"📍 {cargo[1]} → {cargo[2]}\n"
        f"⚖️ Og‘irligi: {cargo[4]} tonna\n\n"
        "Quyidagi furalar dastlabki saralashdan o‘tdi.\n"
        "Transport turi va yo‘nalishini ham tekshiring:"
    )

    for truck in candidates[:10]:

        text = (
            f"🚛 Fura #{truck[0]}\n"
            f"👤 Tashuvchi: {truck[7]}\n"
            f"Transport: {truck[2]}\n"
            f"Raqami: {truck[3]}\n"
            f"Joylashuvi: {truck[4]}\n"
            f"Yo‘nalishi: {truck[5]}\n"
            f"Yuk ko‘tarishi: {truck[6]}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="🤝 Taklif yuborish",
                    callback_data=(
                        f"offertruck:{cargo_id}:{truck[0]}"
                    )
                )
            ]]
        )

        await message.answer(
            text,
            reply_markup=keyboard
        )


# TAKLIF YUBORISH

@dp.callback_query(F.data.startswith("offertruck:"))
async def offer_truck(callback: CallbackQuery):

    _, cargo_id, truck_id = callback.data.split(":")

    cargo = db.execute("""
        SELECT id, user_id, origin, destination,
               cargo_type, weight, price
        FROM cargo WHERE id = ?
    """, (int(cargo_id),)).fetchone()

    truck = db.execute("""
        SELECT id, user_id, vehicle_type,
               plate, location, capacity
        FROM trucks WHERE id = ?
    """, (int(truck_id),)).fetchone()

    if not cargo or not truck:
        await callback.answer(
            "E'lon yoki fura topilmadi.",
            show_alert=True
        )
        return

    if cargo[1] != callback.from_user.id:
        await callback.answer(
            "Bu yuk sizga tegishli emas.",
            show_alert=True
        )
        return

    if cargo[1] == truck[1]:
        await callback.answer(
            "O‘z furangizga taklif yubora olmaysiz.",
            show_alert=True
        )
        return

    existing = db.execute("""
        SELECT id FROM deals
        WHERE cargo_id = ? AND truck_id = ?
        AND status = 'negotiating'
    """, (int(cargo_id), int(truck_id))).fetchone()

    if existing:
        await callback.answer(
            "Bu fura uchun taklif allaqachon yuborilgan.",
            show_alert=True
        )
        return

    db.execute("""
        INSERT INTO deals (
            cargo_id, truck_id,
            cargo_owner_id, carrier_id,
            proposer_id, accepter_id,
            status
        ) VALUES (?, ?, ?, ?, ?, ?, 'negotiating')
    """, (
        int(cargo_id),
        int(truck_id),
        cargo[1],
        truck[1],
        cargo[1],
        truck[1]
    ))

    deal_id = db.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    db.commit()

    await callback.answer("Taklif yuborildi!")

    await callback.message.answer(
        f"✅ Taklif #{deal_id} yuborildi.\n"
        "Tashuvchining javobini kuting."
    )

    try:
        await bot.send_message(
            truck[1],
            f"🤝 Sizga yangi yuk taklifi keldi!\n\n"
            f"Yuk: {cargo[4]}\n"
            f"Yo‘nalish: {cargo[2]} → {cargo[3]}\n"
            f"Og‘irlik: {cargo[5]} tonna\n"
            f"Narx taklifi: {cargo[6]}\n\n"
            f"Bitim raqami: #{deal_id}\n"
            "Yuk egasi siz bilan kelishmoqchi."
        )
    except Exception:
        await callback.message.answer(
            "Tashuvchiga xabar yuborilmadi. "
            "U botni ishga tushirganini tekshiring."
        )


# UMUMIY MATN XABARLARI
@dp.message(F.text)
async def other_messages(message: Message, state: FSMContext):

    await message.answer(
        "Iltimos, menyudagi tugmalardan foydalaning."
    )


# BOTNI ISHGA TUSHIRISH
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
