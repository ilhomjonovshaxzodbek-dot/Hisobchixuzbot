"""
HisobchiXuzbot — Aiogram v3 + SQLite3 asosida yozilgan Telegram xarajat hisobchi boti.
Muallif: Professional Python dasturchi
"""

import asyncio
import logging
import random
import string
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

# ─────────────────────────────────────────────
# SOZLAMALAR
# ─────────────────────────────────────────────

API_TOKEN = "8940392800:AAFD6O1bxzFTgut69hy9Qwnr4-C--TG5Og0"
ADMIN_ID = 8314283278
DB_PATH = "hisobchi.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# FSM HOLATLARI
# ─────────────────────────────────────────────

class XarajatState(StatesGroup):
    """Xarajat qo'shish uchun FSM holatlari."""
    tavsif = State()   # Xarajat tavsifi
    summa  = State()   # Xarajat summasi


# ─────────────────────────────────────────────
# MA'LUMOTLAR BAZASI
# ─────────────────────────────────────────────

def db_init() -> None:
    """Ma'lumotlar bazasini yaratadi va jadvallarni sozlaydi."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Foydalanuvchilar jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id   INTEGER PRIMARY KEY,
            username  TEXT,
            full_name TEXT,
            joined_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Xarajatlar jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS xarajatlar (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            tavsif     TEXT    NOT NULL,
            summa      REAL    NOT NULL,
            cashback   TEXT    NOT NULL,
            yaratilgan TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    conn.commit()
    conn.close()


def user_register(user_id: int, username: str, full_name: str) -> None:
    """Yangi foydalanuvchini bazaga qo'shadi (agar mavjud bo'lmasa)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO users (user_id, username, full_name)
        VALUES (?, ?, ?)
    """, (user_id, username, full_name))
    conn.commit()
    conn.close()


def xarajat_qosh(user_id: int, tavsif: str, summa: float, cashback: str) -> None:
    """Yangi xarajatni bazaga yozadi."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO xarajatlar (user_id, tavsif, summa, cashback)
        VALUES (?, ?, ?, ?)
    """, (user_id, tavsif, summa, cashback))
    conn.commit()
    conn.close()


def oxirgi_xarajat(user_id: int) -> dict | None:
    """Foydalanuvchining eng oxirgi xarajatini qaytaradi."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, tavsif, summa, cashback, yaratilgan
        FROM xarajatlar
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "tavsif": row[1], "summa": row[2],
                "cashback": row[3], "yaratilgan": row[4]}
    return None


def xarajat_ochir(xarajat_id: int) -> None:
    """Berilgan ID bo'yicha xarajatni o'chiradi."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM xarajatlar WHERE id = ?", (xarajat_id,))
    conn.commit()
    conn.close()


def hisobot_olish(user_id: int) -> list[dict]:
    """
    Foydalanuvchining so'nggi 30 ta xarajatini ro'yxat ko'rinishida qaytaradi.
    Yolg'iz 48 soatda yaratilgan keshbek kodlari hali ham amal qiladi.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT tavsif, summa, cashback, yaratilgan
        FROM xarajatlar
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 30
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return [{"tavsif": r[0], "summa": r[1], "cashback": r[2], "yaratilgan": r[3]}
            for r in rows]


def admin_statistika() -> dict:
    """Admin uchun umumiy statistika ma'lumotlarini qaytaradi."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    foydalanuvchilar = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*), COALESCE(SUM(summa), 0) FROM xarajatlar")
    row = cur.fetchone()
    jami_xarajatlar, jami_summa = row[0], row[1]

    # Bugungi xarajatlar
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(summa), 0) FROM xarajatlar
        WHERE date(yaratilgan) = date('now')
    """)
    row = cur.fetchone()
    bugun_xarajatlar, bugun_summa = row[0], row[1]

    conn.close()
    return {
        "foydalanuvchilar": foydalanuvchilar,
        "jami_xarajatlar": jami_xarajatlar,
        "jami_summa": jami_summa,
        "bugun_xarajatlar": bugun_xarajatlar,
        "bugun_summa": bugun_summa,
    }


def eski_keshbeklar_tozala() -> None:
    """
    48 soatdan oshgan xarajat yozuvlarini emas,
    lekin keshbek kodlari haqida eslatish uchun
    baza oddiy saqlanadi — faqat kod muddati tekshiriladi.
    """
    pass  # Kodning muddati hisobot ko'rsatilganda dinamik tekshiriladi


# ─────────────────────────────────────────────
# YORDAMCHI FUNKSIYALAR
# ─────────────────────────────────────────────

def cashback_kod_yarat() -> str:
    """
    3 qatorli noyob keshbek kodi generatsiya qiladi:
      [AA12345678]
      [12345678]
      [ASDF]
    """
    # 1-qator: 2 ta harf + 8 ta raqam
    q1_harf  = "".join(random.choices(string.ascii_uppercase, k=2))
    q1_raqam = "".join(random.choices(string.digits, k=8))
    qator1 = f"[{q1_harf}{q1_raqam}]"

    # 2-qator: 8 ta raqam
    qator2 = f"[{''.join(random.choices(string.digits, k=8))}]"

    # 3-qator: 4 ta harf
    qator3 = f"[{''.join(random.choices(string.ascii_uppercase, k=4))}]"

    return f"{qator1}\n{qator2}\n{qator3}"


def kod_muddati_tekshir(yaratilgan_str: str) -> bool:
    """Keshbek kodi hali ham amal qiladimi (48 soat) — True qaytaradi."""
    try:
        yaratilgan = datetime.strptime(yaratilgan_str, "%Y-%m-%d %H:%M:%S")
        return datetime.now() - yaratilgan < timedelta(hours=48)
    except Exception:
        return False


# ─────────────────────────────────────────────
# KLAVIATURA MENYULAR
# ─────────────────────────────────────────────

def asosiy_menyu() -> ReplyKeyboardMarkup:
    """Asosiy foydalanuvchi menyusini qaytaradi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Xarajat qo'shish")],
            [KeyboardButton(text="📊 Hisobot"), KeyboardButton(text="❌ Oxirgisini o'chirish")],
            [KeyboardButton(text="❓ Yordam")],
        ],
        resize_keyboard=True,
    )


# ─────────────────────────────────────────────
# BOT VA DISPATCHER
# ─────────────────────────────────────────────

bot = Bot(token=API_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())


# ─────────────────────────────────────────────
# HANDLERLAR — ASOSIY
# ─────────────────────────────────────────────

@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    """
    /start buyrug'i — foydalanuvchini ro'yxatdan o'tkazadi
    va asosiy menyuni ko'rsatadi.
    """
    user = message.from_user
    user_register(user.id, user.username or "", user.full_name or "")

    await message.answer(
        f"👋 Salom, <b>{user.full_name}</b>!\n\n"
        "🧾 <b>HisobchiXuzbot</b> — xarajatlaringizni kuzatib boruvchi bot.\n\n"
        "Pastdagi menyudan foydalaning:",
        reply_markup=asosiy_menyu(),
        parse_mode="HTML",
    )


@dp.message(Command("admin"))
async def admin_panel(message: Message) -> None:
    """
    /admin — faqat ADMIN_ID uchun ishlaydi.
    Statistika ma'lumotlarini ko'rsatadi.
    """
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizda bu buyruq uchun ruxsat yo'q.")
        return

    stat = admin_statistika()
    matn = (
        "🔐 <b>Admin paneli</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{stat['foydalanuvchilar']}</b>\n"
        f"📋 Jami xarajatlar: <b>{stat['jami_xarajatlar']}</b>\n"
        f"💰 Jami summa: <b>{stat['jami_summa']:,.0f} so'm</b>\n\n"
        f"📅 Bugungi xarajatlar: <b>{stat['bugun_xarajatlar']}</b>\n"
        f"💵 Bugungi summa: <b>{stat['bugun_summa']:,.0f} so'm</b>"
    )
    await message.answer(matn, parse_mode="HTML")


# ─────────────────────────────────────────────
# HANDLERLAR — XARAJAT QO'SHISH (FSM)
# ─────────────────────────────────────────────

@dp.message(F.text == "➕ Xarajat qo'shish")
async def xarajat_boshlash(message: Message, state: FSMContext) -> None:
    """Xarajat qo'shish jarayonini boshlaydi — tavsif so'raydi."""
    await state.set_state(XarajatState.tavsif)
    await message.answer(
        "📝 Xarajat tavsifini kiriting:\n(masalan: Oziq-ovqat, Transport, Kiyim...)",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(XarajatState.tavsif)
async def xarajat_tavsif(message: Message, state: FSMContext) -> None:
    """Tavsifni qabul qilib, summa so'raydi."""
    await state.update_data(tavsif=message.text.strip())
    await state.set_state(XarajatState.summa)
    await message.answer("💰 Xarajat summasini kiriting (faqat raqam, so'mda):")


@dp.message(XarajatState.summa)
async def xarajat_summa(message: Message, state: FSMContext) -> None:
    """
    Summani qabul qiladi, xarajatni bazaga yozadi
    va faqat shu paytda keshbek kodini generatsiya qilib chiqaradi.
    """
    # Summani tekshirish
    try:
        summa = float(message.text.strip().replace(" ", "").replace(",", "."))
        if summa <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Iltimos, to'g'ri raqam kiriting (masalan: 50000):")
        return

    data = await state.get_data()
    tavsif = data["tavsif"]

    # Keshbek kodi faqat xarajat kiritilganda yaratiladi
    cashback = cashback_kod_yarat()

    # Bazaga yozish
    xarajat_qosh(message.from_user.id, tavsif, summa, cashback)
    await state.clear()

    # Natijani ko'rsatish
    javob = (
        "✅ <b>Xarajat qo'shildi!</b>\n\n"
        f"📌 Tavsif: <b>{tavsif}</b>\n"
        f"💸 Summa: <b>{summa:,.0f} so'm</b>\n\n"
        "🎁 <b>Sizning keshbek kodingiz (48 soat amal qiladi):</b>\n\n"
        f"<code>{cashback}</code>\n\n"
        "⚠️ Ushbu kodni saqlab qo'ying!"
    )
    await message.answer(javob, reply_markup=asosiy_menyu(), parse_mode="HTML")


# ─────────────────────────────────────────────
# HANDLERLAR — HISOBOT
# ─────────────────────────────────────────────

@dp.message(F.text == "📊 Hisobot")
async def hisobot_handler(message: Message) -> None:
    """
    Foydalanuvchining so'nggi xarajatlarini ro'yxat ko'rinishida chiqaradi.
    Keshbek kodining muddati ham ko'rsatiladi.
    """
    xarajatlar = hisobot_olish(message.from_user.id)

    if not xarajatlar:
        await message.answer(
            "📭 Hozircha xarajatlaringiz yo'q.\n"
            "➕ Xarajat qo'shish tugmasini bosing!",
            reply_markup=asosiy_menyu(),
        )
        return

    jami = sum(x["summa"] for x in xarajatlar)
    qatorlar = [f"📊 <b>So'nggi {len(xarajatlar)} ta xarajat:</b>\n"]

    for i, x in enumerate(xarajatlar, 1):
        muddat = "✅ amal qiladi" if kod_muddati_tekshir(x["yaratilgan"]) else "⌛ muddati o'tgan"
        qatorlar.append(
            f"{i}. <b>{x['tavsif']}</b> — {x['summa']:,.0f} so'm\n"
            f"   🔑 Kod: {muddat}\n"
            f"   🕐 {x['yaratilgan']}"
        )

    qatorlar.append(f"\n💰 <b>Jami: {jami:,.0f} so'm</b>")
    await message.answer("\n\n".join(qatorlar), parse_mode="HTML", reply_markup=asosiy_menyu())


# ─────────────────────────────────────────────
# HANDLERLAR — OXIRGISINI O'CHIRISH
# ─────────────────────────────────────────────

@dp.message(F.text == "❌ Oxirgisini o'chirish")
async def oxirgini_ochir(message: Message) -> None:
    """Foydalanuvchining eng oxirgi xarajatini o'chiradi."""
    xarajat = oxirgi_xarajat(message.from_user.id)

    if not xarajat:
        await message.answer(
            "📭 O'chirish uchun xarajat topilmadi.",
            reply_markup=asosiy_menyu(),
        )
        return

    xarajat_ochir(xarajat["id"])
    await message.answer(
        f"🗑 <b>Oxirgi xarajat o'chirildi:</b>\n\n"
        f"📌 {xarajat['tavsif']} — {xarajat['summa']:,.0f} so'm",
        reply_markup=asosiy_menyu(),
        parse_mode="HTML",
    )


# ─────────────────────────────────────────────
# HANDLERLAR — YORDAM
# ─────────────────────────────────────────────

@dp.message(F.text == "❓ Yordam")
async def yordam_handler(message: Message) -> None:
    """Bot haqida yordam ma'lumotlarini ko'rsatadi."""
    matn = (
        "❓ <b>HisobchiXuzbot — Yordam</b>\n\n"
        "🔹 <b>➕ Xarajat qo'shish</b>\n"
        "   Yangi xarajat kiritasiz. Bot avtomatik keshbek kodi beradi.\n\n"
        "🔹 <b>📊 Hisobot</b>\n"
        "   So'nggi xarajatlaringiz va ularning keshbek kodlari.\n\n"
        "🔹 <b>❌ Oxirgisini o'chirish</b>\n"
        "   Eng oxirgi kiritilgan xarajatni o'chiradi.\n\n"
        "🔹 <b>Keshbek kodi haqida:</b>\n"
        "   ✅ Har bir xarajatga noyob kod beriladi.\n"
        "   ⏳ Kod 48 soat amal qiladi.\n"
        "   🔒 Kod faqat xarajat kiritilganda yaratiladi.\n\n"
        "📞 Muammo bo'lsa: @admin ga murojaat qiling."
    )
    await message.answer(matn, parse_mode="HTML", reply_markup=asosiy_menyu())


# ─────────────────────────────────────────────
# NOMA'LUM XABARLAR
# ─────────────────────────────────────────────

@dp.message()
async def notanish_xabar(message: Message, state: FSMContext) -> None:
    """FSM holati bo'lmagan noma'lum xabarlarga javob beradi."""
    current_state = await state.get_state()
    if current_state is not None:
        return  # FSM jarayonida bo'lsa, aralashmaymiz

    await message.answer(
        "🤔 Tushunmadim. Pastdagi menyudan foydalaning:",
        reply_markup=asosiy_menyu(),
    )


# ─────────────────────────────────────────────
# ASOSIY ISHGA TUSHIRISH
# ─────────────────────────────────────────────

async def main() -> None:
    """Botni ishga tushiradi."""
    db_init()
    logger.info("HisobchiXuzbot ishga tushdi ✅")
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
