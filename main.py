"""
HisobchiXuzbot v2.0 — Aiogram v3 + SQLite3
Yangi: Majburiy obuna, /admin to'liq panel, motivatsiyali xabarlar,
       hammaga broadcast, foydalanuvchilar ro'yxati
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
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

# ─────────────────────────────────────────────
# SOZLAMALAR
# ─────────────────────────────────────────────

API_TOKEN = "8940392800:AAF_miNknsRMJFvkKLa21dsVuYTEUpU2Ncw"
ADMIN_ID  = 8314283278
DB_PATH   = "hisobchi.db"

# Majburiy obuna kanallari/botlar
MAJBURIY_KANALLAR = [
    {"id": "@soghlomlikuz_bot",  "nom": "Soghlomlik Bot",       "havola": "https://t.me/soghlomlikuz_bot"},
    {"id": "@shzodbekcoderdev",  "nom": "Shahzodbek Coder Dev", "havola": "https://t.me/shzodbekcoderdev"},
    {"id": "@sontopxbot",        "nom": "SonTopX Bot",          "havola": "https://t.me/sontopxbot"},
    {"id": "@faylmasteruzbot",   "nom": "FaylMaster Bot",       "havola": "https://t.me/faylmasteruzbot"},
]

# Motivatsiyali xabarlar (3 kun kirmasa)
MOTIVATSIYA_XABARLARI = [
    "👋 Salom! Xarajatlaringizni kuzatishni unutmadingizmi?\n\n💰 Bugun ham xarajat kiriting va keshbek kodi oling!",
    "📊 Xarajatlaringizni nazorat qiling!\n\nHar bir xarajat uchun keshbek kodi olasiz. HisobchiXuzbot sizni kutmoqda! 🧾",
    "💡 Bilasizmi?\n\nXarajatlarni kuzatib borish oylik tejamkorligingizni oshiradi!\nHozir keling va xarajat kiriting. 💪",
    "🎯 Oylik xarajatlaringizni tahlil qiling!\n\nBot sizga so'nggi 30 ta xarajatni ko'rsatadi. Keling! 📋",
    "🔑 Keshbek kodingiz FaylMasteruzbotda ishlatilishi mumkin!\n\nXarajat kiriting → kod oling → olmos to'plang! 💎",
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# FSM HOLATLARI
# ─────────────────────────────────────────────

class XarajatState(StatesGroup):
    tavsif = State()
    summa  = State()

class AdminState(StatesGroup):
    xabar_matn     = State()   # Hammaga xabar
    balans_user_id = State()   # Foydalanuvchi ID


# ─────────────────────────────────────────────
# MA'LUMOTLAR BAZASI
# ─────────────────────────────────────────────

def db_init() -> None:
    """Ma'lumotlar bazasini yaratadi va jadvallarni sozlaydi."""
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    # Foydalanuvchilar jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            full_name     TEXT,
            oxirgi_kirish TEXT    DEFAULT (datetime('now')),
            joined_at     TEXT    DEFAULT (datetime('now'))
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


def user_register(user_id: int, username: str, full_name: str) -> bool:
    """
    Yangi foydalanuvchini bazaga qo'shadi.
    True — yangi, False — mavjud.
    """
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    mavjud = cur.fetchone()
    if not mavjud:
        cur.execute("""
            INSERT INTO users (user_id, username, full_name)
            VALUES (?, ?, ?)
        """, (user_id, username, full_name))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False


def oxirgi_kirish_yangilash(user_id: int) -> None:
    """Foydalanuvchi oxirgi kirish vaqtini yangilaydi."""
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute(
        "UPDATE users SET oxirgi_kirish = ? WHERE user_id = ?",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id)
    )
    conn.commit()
    conn.close()


def uzoq_kirmagan_userlar(kunlar: int = 3) -> list:
    """N kundan ko'p kirmaganlar ro'yxati."""
    conn    = sqlite3.connect(DB_PATH)
    cur     = conn.cursor()
    chegara = (datetime.now() - timedelta(days=kunlar)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        SELECT user_id, full_name FROM users
        WHERE oxirgi_kirish < ? OR oxirgi_kirish IS NULL
    """, (chegara,))
    rows = cur.fetchall()
    conn.close()
    return rows


def xarajat_qosh(user_id: int, tavsif: str, summa: float, cashback: str) -> None:
    """Yangi xarajatni bazaga yozadi."""
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO xarajatlar (user_id, tavsif, summa, cashback)
        VALUES (?, ?, ?, ?)
    """, (user_id, tavsif, summa, cashback))
    conn.commit()
    conn.close()


def oxirgi_xarajat(user_id: int) -> dict | None:
    """Foydalanuvchining eng oxirgi xarajatini qaytaradi."""
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, tavsif, summa, cashback, yaratilgan
        FROM xarajatlar WHERE user_id = ?
        ORDER BY id DESC LIMIT 1
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
    cur  = conn.cursor()
    cur.execute("DELETE FROM xarajatlar WHERE id = ?", (xarajat_id,))
    conn.commit()
    conn.close()


def hisobot_olish(user_id: int) -> list[dict]:
    """Foydalanuvchining so'nggi 30 ta xarajatini qaytaradi."""
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("""
        SELECT tavsif, summa, cashback, yaratilgan
        FROM xarajatlar WHERE user_id = ?
        ORDER BY id DESC LIMIT 30
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return [{"tavsif": r[0], "summa": r[1], "cashback": r[2], "yaratilgan": r[3]}
            for r in rows]


def admin_statistika() -> dict:
    """Admin uchun umumiy statistika."""
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    foydalanuvchilar = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*), COALESCE(SUM(summa), 0) FROM xarajatlar")
    row = cur.fetchone()
    jami_xarajatlar, jami_summa = row[0], row[1]

    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(summa), 0) FROM xarajatlar
        WHERE date(yaratilgan) = date('now')
    """)
    row = cur.fetchone()
    bugun_xarajatlar, bugun_summa = row[0], row[1]

    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(summa), 0) FROM xarajatlar
        WHERE date(yaratilgan) >= date('now', 'start of month')
    """)
    row = cur.fetchone()
    oy_xarajatlar, oy_summa = row[0], row[1]

    conn.close()
    return {
        "foydalanuvchilar": foydalanuvchilar,
        "jami_xarajatlar":  jami_xarajatlar,
        "jami_summa":       jami_summa,
        "bugun_xarajatlar": bugun_xarajatlar,
        "bugun_summa":      bugun_summa,
        "oy_xarajatlar":    oy_xarajatlar,
        "oy_summa":         oy_summa,
    }


def barcha_userlar() -> list:
    """Barcha user_id lar ro'yxati."""
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows


# ─────────────────────────────────────────────
# YORDAMCHI FUNKSIYALAR
# ─────────────────────────────────────────────

def cashback_kod_yarat() -> str:
    """3 qatorli noyob keshbek kodi generatsiya qiladi."""
    q1 = f"[{''.join(random.choices(string.ascii_uppercase, k=2))}{''.join(random.choices(string.digits, k=8))}]"
    q2 = f"[{''.join(random.choices(string.digits, k=8))}]"
    q3 = f"[{''.join(random.choices(string.ascii_uppercase, k=4))}]"
    return f"{q1}\n{q2}\n{q3}"


def kod_muddati_tekshir(yaratilgan_str: str) -> bool:
    """Keshbek kodi 48 soat ichida ekanligini tekshiradi."""
    try:
        yaratilgan = datetime.strptime(yaratilgan_str, "%Y-%m-%d %H:%M:%S")
        return datetime.now() - yaratilgan < timedelta(hours=48)
    except Exception:
        return False


async def obuna_tekshir(bot: Bot, user_id: int) -> list:
    """Majburiy kanallarga obuna tekshiradi. Obuna bo'lmaganlar ro'yxatini qaytaradi."""
    obuna_bolmagan = []
    for kanal in MAJBURIY_KANALLAR:
        try:
            member = await bot.get_chat_member(kanal["id"], user_id)
            if member.status in ("left", "kicked", "banned"):
                obuna_bolmagan.append(kanal)
        except Exception:
            pass
    return obuna_bolmagan


def obuna_klaviatura(obuna_bolmagan: list) -> InlineKeyboardMarkup:
    """Obuna bo'lmagan kanallar uchun tugmalar."""
    tugmalar = []
    for kanal in obuna_bolmagan:
        tugmalar.append([InlineKeyboardButton(
            text=f"✅ {kanal['nom']} ga obuna bo'lish",
            url=kanal["havola"]
        )])
    tugmalar.append([InlineKeyboardButton(
        text="🔄 Tekshirish",
        callback_data="obuna_tekshir"
    )])
    return InlineKeyboardMarkup(inline_keyboard=tugmalar)


# ─────────────────────────────────────────────
# KLAVIATURA MENYULAR
# ─────────────────────────────────────────────

def asosiy_menyu() -> ReplyKeyboardMarkup:
    """Asosiy foydalanuvchi menyusi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Xarajat qo'shish")],
            [KeyboardButton(text="📊 Hisobot"), KeyboardButton(text="❌ Oxirgisini o'chirish")],
            [KeyboardButton(text="❓ Yordam")],
        ],
        resize_keyboard=True,
    )


def admin_menyu() -> ReplyKeyboardMarkup:
    """Admin paneli menyusi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Statistika")],
            [KeyboardButton(text="📢 Hammaga xabar"), KeyboardButton(text="👥 Foydalanuvchilar")],
            [KeyboardButton(text="🔙 Orqaga")],
        ],
        resize_keyboard=True,
    )


# ─────────────────────────────────────────────
# BOT VA DISPATCHER
# ─────────────────────────────────────────────

bot = Bot(token=API_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())


# ─────────────────────────────────────────────
# HANDLERLAR — START
# ─────────────────────────────────────────────

@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    """
    /start — majburiy obunani tekshiradi,
    keyin foydalanuvchini ro'yxatdan o'tkazadi.
    """
    u = message.from_user

    # Majburiy obuna tekshirish
    obuna_bolmagan = await obuna_tekshir(bot, u.id)
    if obuna_bolmagan:
        await message.answer(
            "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
            "Obuna bo'lgandan so'ng «🔄 Tekshirish» tugmasini bosing.",
            reply_markup=obuna_klaviatura(obuna_bolmagan),
            parse_mode="HTML"
        )
        return

    yangi = user_register(u.id, u.username or "", u.full_name or "")
    oxirgi_kirish_yangilash(u.id)

    if yangi:
        xabar = (
            f"👋 Salom, <b>{u.full_name}</b>!\n\n"
            "🧾 <b>HisobchiXuzbot</b> — xarajatlaringizni kuzatib boruvchi bot.\n\n"
            "✅ Har bir xarajat uchun keshbek kodi olasiz!\n"
            "💎 Kodni FaylMasteruzbotda ishlatib olmos to'plang!\n\n"
            "Pastdagi menyudan foydalaning:"
        )
    else:
        xabar = (
            f"👋 Qaytib keldingiz, <b>{u.full_name}</b>!\n\n"
            "Menyudan foydalaning:"
        )

    await message.answer(xabar, reply_markup=asosiy_menyu(), parse_mode="HTML")


# ─────────────────────────────────────────────
# HANDLERLAR — OBUNA CALLBACK
# ─────────────────────────────────────────────

@dp.callback_query(F.data == "obuna_tekshir")
async def obuna_tekshir_callback(callback: CallbackQuery) -> None:
    """Foydalanuvchi 'Tekshirish' tugmasini bosdi."""
    u = callback.from_user
    obuna_bolmagan = await obuna_tekshir(bot, u.id)

    if obuna_bolmagan:
        await callback.answer("❌ Hali obuna bo'lmagan kanallar bor!", show_alert=True)
        await callback.message.edit_reply_markup(
            reply_markup=obuna_klaviatura(obuna_bolmagan)
        )
        return

    # Obuna bo'ldi
    await callback.answer("✅ Rahmat! Barcha kanallarga obuna bo'ldingiz!", show_alert=True)
    yangi = user_register(u.id, u.username or "", u.full_name or "")
    oxirgi_kirish_yangilash(u.id)

    if yangi:
        xabar = (
            f"🎉 <b>Xush kelibsiz, {u.full_name}!</b>\n\n"
            "🧾 <b>HisobchiXuzbot</b> — xarajatlaringizni kuzatib boruvchi bot.\n\n"
            "✅ Har bir xarajat uchun keshbek kodi olasiz!\n"
            "Pastdagi menyudan foydalaning:"
        )
    else:
        xabar = f"👋 Qaytib keldingiz, <b>{u.full_name}</b>!"

    await callback.message.answer(xabar, reply_markup=asosiy_menyu(), parse_mode="HTML")


# ─────────────────────────────────────────────
# HANDLERLAR — ADMIN
# ─────────────────────────────────────────────

@dp.message(Command("admin"))
async def admin_panel(message: Message) -> None:
    """
    /admin — to'liq admin paneli.
    Bot ma'lumotlari + statistika + buyruqlar + foydalanuvchilar.
    """
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizda bu buyruq uchun ruxsat yo'q.")
        return

    stat     = admin_statistika()
    bot_info = await bot.get_me()

    # 1-xabar: Bot ma'lumotlari + statistika
    await message.answer(
        "🔐 <b>ADMIN PANELI</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 <b>BOT MA'LUMOTLARI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📛 Nomi: <b>{bot_info.full_name}</b>\n"
        f"🔗 Username: @{bot_info.username}\n"
        f"🆔 Bot ID: <code>{bot_info.id}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📊 <b>STATISTIKA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Jami foydalanuvchilar: <b>{stat['foydalanuvchilar']}</b>\n"
        f"📋 Jami xarajatlar: <b>{stat['jami_xarajatlar']}</b>\n"
        f"💰 Jami summa: <b>{stat['jami_summa']:,.0f} so'm</b>\n\n"
        f"📅 Bugungi xarajatlar: <b>{stat['bugun_xarajatlar']}</b>\n"
        f"💵 Bugungi summa: <b>{stat['bugun_summa']:,.0f} so'm</b>\n\n"
        f"📆 Oylik xarajatlar: <b>{stat['oy_xarajatlar']}</b>\n"
        f"💴 Oylik summa: <b>{stat['oy_summa']:,.0f} so'm</b>",
        reply_markup=admin_menyu(),
        parse_mode="HTML"
    )

    # 2-xabar: Admin buyruqlari
    await message.answer(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ <b>ADMIN BUYRUQLARI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📊 <b>Statistika</b>\n"
        "   └ Bot umumiy statistikasini ko'rsatadi\n\n"
        "📢 <b>Hammaga xabar</b>\n"
        "   └ Barcha foydalanuvchilarga broadcast\n"
        "   └ Xabar yozing → hammaga ketadi\n\n"
        "👥 <b>Foydalanuvchilar</b>\n"
        "   └ Barcha foydalanuvchilar ro'yxati\n"
        "   └ ID, ism, username, qo'shilgan sana\n\n"
        "🔙 <b>Orqaga</b>\n"
        "   └ Asosiy menyuga qaytish",
        parse_mode="HTML"
    )

    # 3-xabar: Barcha foydalanuvchilar
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("""
        SELECT u.user_id, u.full_name, u.username,
               COUNT(x.id) as xarajat_soni,
               COALESCE(SUM(x.summa), 0) as jami_summa,
               u.joined_at
        FROM users u
        LEFT JOIN xarajatlar x ON x.user_id = u.user_id
        GROUP BY u.user_id
        ORDER BY jami_summa DESC
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await message.answer("📭 Hozircha foydalanuvchi yo'q.")
        return

    await message.answer(
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>BARCHA FOYDALANUVCHILAR ({len(rows)} ta)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML"
    )

    for i in range(0, len(rows), 10):
        qism     = rows[i:i+10]
        qatorlar = [f"📋 <b>{i+1}-{i+len(qism)}:</b>\n"]
        for uid, full_name, username, xarajat_soni, jami, joined in qism:
            uname = f"@{username}" if username else "username yo'q"
            sana  = joined[:10] if joined else "—"
            qatorlar.append(
                f"👤 <b>{full_name}</b>\n"
                f"   🆔 <code>{uid}</code>\n"
                f"   📱 {uname}\n"
                f"   📋 {xarajat_soni} ta xarajat | 💰 {jami:,.0f} so'm\n"
                f"   📅 {sana}"
            )
        await message.answer("\n\n".join(qatorlar), parse_mode="HTML")
        await asyncio.sleep(0.3)


# ─────────────────────────────────────────────
# HANDLERLAR — ADMIN MENYUSI
# ─────────────────────────────────────────────

@dp.message(F.text == "📊 Statistika")
async def admin_stat_handler(message: Message) -> None:
    """Admin statistikasini ko'rsatadi."""
    if message.from_user.id != ADMIN_ID:
        return
    stat = admin_statistika()
    await message.answer(
        "📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{stat['foydalanuvchilar']}</b>\n"
        f"📋 Jami xarajatlar: <b>{stat['jami_xarajatlar']}</b>\n"
        f"💰 Jami summa: <b>{stat['jami_summa']:,.0f} so'm</b>\n\n"
        f"📅 Bugun: <b>{stat['bugun_xarajatlar']}</b> ta — <b>{stat['bugun_summa']:,.0f} so'm</b>\n"
        f"📆 Bu oy: <b>{stat['oy_xarajatlar']}</b> ta — <b>{stat['oy_summa']:,.0f} so'm</b>",
        parse_mode="HTML"
    )


@dp.message(F.text == "📢 Hammaga xabar")
async def admin_xabar_boshlash(message: Message, state: FSMContext) -> None:
    """Barcha foydalanuvchilarga xabar yuborish."""
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminState.xabar_matn)
    await message.answer("📢 Xabar matnini kiriting:", reply_markup=ReplyKeyboardRemove())


@dp.message(AdminState.xabar_matn)
async def admin_xabar_yuborish(message: Message, state: FSMContext) -> None:
    """Xabarni barcha foydalanuvchilarga yuboradi."""
    matn    = message.text.strip()
    await state.clear()
    userlar = barcha_userlar()
    yuborildi = 0
    for uid in userlar:
        try:
            await bot.send_message(uid, f"📢 <b>Admin xabari:</b>\n\n{matn}", parse_mode="HTML")
            yuborildi += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await message.answer(
        f"✅ Yuborildi: <b>{yuborildi}/{len(userlar)}</b> foydalanuvchi",
        reply_markup=admin_menyu(),
        parse_mode="HTML"
    )


@dp.message(F.text == "👥 Foydalanuvchilar")
async def admin_foydalanuvchilar(message: Message) -> None:
    """Barcha foydalanuvchilar ro'yxatini ko'rsatadi."""
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute("""
        SELECT u.user_id, u.full_name, u.username,
               COUNT(x.id) as xarajat_soni,
               COALESCE(SUM(x.summa), 0) as jami_summa,
               u.joined_at
        FROM users u
        LEFT JOIN xarajatlar x ON x.user_id = u.user_id
        GROUP BY u.user_id
        ORDER BY u.joined_at DESC
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await message.answer("📭 Hozircha foydalanuvchi yo'q.")
        return

    await message.answer(
        f"👥 <b>Jami: {len(rows)} ta foydalanuvchi</b>",
        parse_mode="HTML"
    )

    for i in range(0, len(rows), 10):
        qism     = rows[i:i+10]
        qatorlar = []
        for uid, full_name, username, xarajat_soni, jami, joined in qism:
            uname = f"@{username}" if username else "—"
            sana  = joined[:10] if joined else "—"
            qatorlar.append(
                f"👤 <b>{full_name}</b>\n"
                f"   🆔 <code>{uid}</code>\n"
                f"   📱 {uname}\n"
                f"   📋 {xarajat_soni} ta | 💰 {jami:,.0f} so'm\n"
                f"   📅 {sana}"
            )
        await message.answer("\n\n".join(qatorlar), parse_mode="HTML")
        await asyncio.sleep(0.3)


@dp.message(F.text == "🔙 Orqaga")
async def admin_orqaga(message: Message) -> None:
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("✅ Asosiy menyu", reply_markup=asosiy_menyu())


# ─────────────────────────────────────────────
# HANDLERLAR — XARAJAT QO'SHISH (FSM)
# ─────────────────────────────────────────────

@dp.message(F.text == "➕ Xarajat qo'shish")
async def xarajat_boshlash(message: Message, state: FSMContext) -> None:
    """Xarajat qo'shish jarayonini boshlaydi."""
    # Obunani tekshirish
    obuna_bolmagan = await obuna_tekshir(bot, message.from_user.id)
    if obuna_bolmagan:
        await message.answer(
            "⚠️ Avval barcha kanallarga obuna bo'ling!",
            reply_markup=obuna_klaviatura(obuna_bolmagan)
        )
        return

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
    va keshbek kodini generatsiya qilib chiqaradi.
    """
    try:
        summa = float(message.text.strip().replace(" ", "").replace(",", "."))
        if summa <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Iltimos, to'g'ri raqam kiriting (masalan: 50000):")
        return

    data    = await state.get_data()
    tavsif  = data["tavsif"]
    cashback = cashback_kod_yarat()

    xarajat_qosh(message.from_user.id, tavsif, summa, cashback)
    oxirgi_kirish_yangilash(message.from_user.id)
    await state.clear()

    await message.answer(
        "✅ <b>Xarajat qo'shildi!</b>\n\n"
        f"📌 Tavsif: <b>{tavsif}</b>\n"
        f"💸 Summa: <b>{summa:,.0f} so'm</b>\n\n"
        "🎁 <b>Sizning keshbek kodingiz (48 soat amal qiladi):</b>\n\n"
        f"<code>{cashback}</code>\n\n"
        "💡 Bu kodni <b>FaylMasteruzbotda</b> ishlatib olmos to'plang!\n"
        "⚠️ Kodni saqlab qo'ying!",
        reply_markup=asosiy_menyu(),
        parse_mode="HTML"
    )


# ─────────────────────────────────────────────
# HANDLERLAR — HISOBOT
# ─────────────────────────────────────────────

@dp.message(F.text == "📊 Hisobot")
async def hisobot_handler(message: Message) -> None:
    """Foydalanuvchining so'nggi xarajatlarini chiqaradi."""
    # Obuna tekshirish
    obuna_bolmagan = await obuna_tekshir(bot, message.from_user.id)
    if obuna_bolmagan:
        await message.answer(
            "⚠️ Avval barcha kanallarga obuna bo'ling!",
            reply_markup=obuna_klaviatura(obuna_bolmagan)
        )
        return

    xarajatlar = hisobot_olish(message.from_user.id)
    oxirgi_kirish_yangilash(message.from_user.id)

    if not xarajatlar:
        await message.answer(
            "📭 Hozircha xarajatlaringiz yo'q.\n➕ Xarajat qo'shish tugmasini bosing!",
            reply_markup=asosiy_menyu(),
        )
        return

    jami     = sum(x["summa"] for x in xarajatlar)
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
    """Bot haqida batafsil yordam."""
    await message.answer(
        "❓ <b>HisobchiXuzbot — To'liq qo'llanma</b>\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
        "➕ <b>XARAJAT QO'SHISH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ «➕ Xarajat qo'shish» tugmasini bosing\n"
        "2️⃣ Xarajat tavsifini kiriting (masalan: Oziq-ovqat)\n"
        "3️⃣ Summani so'mda kiriting (masalan: 50000)\n"
        "4️⃣ Bot avtomatik <b>keshbek kodi</b> beradi\n"
        "⚠️ Kodni saqlab qo'ying — 48 soat amal qiladi!\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔑 <b>KESHBEK KODI NIMA?</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Har bir xarajat kiritganda noyob kod beriladi\n"
        "💎 Bu kodni <b>FaylMasteruzbotda</b> ishlatib olmos to'plang\n"
        "⏳ Kod faqat <b>48 soat</b> amal qiladi\n"
        "🔒 Kod bir marta ishlatilishi mumkin\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
        "📊 <b>HISOBOT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "• So'nggi 30 ta xarajatni ko'rsatadi\n"
        "• Har bir xarajatning keshbek kodi holati\n"
        "• Jami xarajat summasi\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
        "❌ <b>OXIRGISINI O'CHIRISH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "• Eng oxirgi kiritilgan xarajatni o'chiradi\n"
        "• Xato kiritgan bo'lsangiz ishlating\n\n"

        "📞 Muammo bo'lsa admin bilan bog'laning.",
        parse_mode="HTML",
        reply_markup=asosiy_menyu()
    )


# ─────────────────────────────────────────────
# NOMA'LUM XABARLAR
# ─────────────────────────────────────────────

@dp.message()
async def notanish_xabar(message: Message, state: FSMContext) -> None:
    """FSM holati bo'lmagan noma'lum xabarlarga javob beradi."""
    current_state = await state.get_state()
    if current_state is not None:
        return
    await message.answer(
        "🤔 Tushunmadim. Pastdagi menyudan foydalaning:",
        reply_markup=asosiy_menyu(),
    )


# ─────────────────────────────────────────────
# MOTIVATSIYA SCHEDULER
# ─────────────────────────────────────────────

async def motivatsiya_yuborish() -> None:
    """
    Har 6 soatda bir marta tekshiradi:
    3 kun kirmagan foydalanuvchilarga motivatsiyali xabar yuboradi.
    """
    while True:
        try:
            await asyncio.sleep(6 * 3600)
            uzoq_kirmagan = uzoq_kirmagan_userlar(kunlar=3)
            if not uzoq_kirmagan:
                continue
            logger.info(f"Motivatsiya: {len(uzoq_kirmagan)} ta foydalanuvchiga xabar")
            for user_id, full_name in uzoq_kirmagan:
                xabar = random.choice(MOTIVATSIYA_XABARLARI)
                try:
                    await bot.send_message(
                        user_id,
                        f"💌 <b>Salom, {full_name}!</b>\n\n{xabar}",
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(0.1)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Motivatsiya xatosi: {e}")
            await asyncio.sleep(60)


# ─────────────────────────────────────────────
# ASOSIY ISHGA TUSHIRISH
# ─────────────────────────────────────────────

async def main() -> None:
    """Botni ishga tushiradi."""
    db_init()
    logger.info("HisobchiXuzbot v2.0 ishga tushdi ✅")
    asyncio.create_task(motivatsiya_yuborish())
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
