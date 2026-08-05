# -*- coding: utf-8 -*-
import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from config import BOT_TOKEN, ADMIN_ID, YONALISHLAR, JINSLAR

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# Faqat siz (ADMIN_ID) botdan foydalana olasiz
router.message.filter(F.from_user.id == ADMIN_ID)
router.callback_query.filter(F.from_user.id == ADMIN_ID)

dp.include_router(router)


# ============================================================================
# FSM holatlari
# ============================================================================

class AddStudent(StatesGroup):
    ism = State()
    yonalish = State()
    jinsi = State()


class BulkAdd(StatesGroup):
    matn = State()


class LeaveStudent(StatesGroup):
    qidiruv = State()
    turi = State()
    sabab = State()


class ReturnStudent(StatesGroup):
    qidiruv = State()


class SearchStudent(StatesGroup):
    qidiruv = State()


# ============================================================================
# Yordamchi funksiyalar
# ============================================================================

def yonalish_kb(prefix="yon"):
    kb = InlineKeyboardBuilder()
    for code, name in YONALISHLAR.items():
        kb.button(text=name, callback_data=f"{prefix}:{code}")
    kb.adjust(1)
    return kb.as_markup()


def jinsi_kb(prefix="jin"):
    kb = InlineKeyboardBuilder()
    for code, name in JINSLAR.items():
        kb.button(text=name, callback_data=f"{prefix}:{code}")
    kb.adjust(2)
    return kb.as_markup()


def students_kb(students, prefix):
    kb = InlineKeyboardBuilder()
    for s in students:
        label = f"{s['ism_familiya']} ({YONALISHLAR.get(s['yonalish'], s['yonalish'])})"
        kb.button(text=label, callback_data=f"{prefix}:{s['id']}")
    kb.adjust(1)
    return kb.as_markup()


def student_card(row, tarix):
    lines = [
        f"👤 <b>{row['ism_familiya']}</b>",
        f"Yo'nalish: {YONALISHLAR.get(row['yonalish'], row['yonalish'])}",
        f"Jinsi: {JINSLAR.get(row['jinsi'], row['jinsi'])}",
        f"Holati: {holat_belgisi(row['holati'])}",
        f"Qo'shilgan sana: {row['qoshilgan_sana']}",
    ]
    if row["holati"] in ("ketgan", "sababli"):
        kunlar = db.kun_farqi(row["qoshilgan_sana"], row["ketgan_sana"])
        lines.append(f"Ketgan sana: {row['ketgan_sana']} (jami {kunlar} kun o'qigan)")
        if row["sabab"]:
            lines.append(f"Sabab: {row['sabab']}")
    else:
        kunlar = db.kun_farqi(row["qoshilgan_sana"])
        lines.append(f"Hozirgacha: {kunlar} kundan beri o'qiyapti")

    if tarix:
        lines.append("\n<b>Tarix:</b>")
        harakat_nomi = {"qoshildi": "➕ Qo'shildi", "ketdi": "➖ Ketdi", "qaytdi": "🔁 Qaytdi"}
        for t in tarix:
            izoh = f" — {t['izoh']}" if t["izoh"] else ""
            lines.append(f"{t['sana']}: {harakat_nomi.get(t['harakat'], t['harakat'])}{izoh}")

    return "\n".join(lines)


def holat_belgisi(holati):
    return {"faol": "✅ Faol", "ketgan": "🔴 Ketgan", "sababli": "🟡 Vaqtincha ketgan"}.get(
        holati, holati
    )


# ============================================================================
# /start va umumiy
# ============================================================================

HELP_TEXT = (
    "📋 <b>O'quvchilar hisobi boti</b>\n\n"
    "/oquvchi_qoshish — bitta o'quvchi qo'shish\n"
    "/royxat_yukla — bir nechta o'quvchini birdaniga qo'shish\n"
    "/royxat — faol o'quvchilar ro'yxati\n"
    "/qidir — o'quvchini ism bo'yicha qidirish (to'liq ma'lumot)\n"
    "/ketdi — o'quvchini ketganlar ro'yxatiga qo'shish\n"
    "/qaytdi — ketgan/vaqtincha ketgan o'quvchini qaytarish\n"
    "/ketganlar — ketganlar va vaqtincha ketganlar ro'yxati\n"
    "/statistika — umumiy statistika\n"
    "/bekor — joriy amalni bekor qilish"
)


@router.message(CommandStart())
async def start(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML")


@router.message(Command("bekor"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi.")


# ============================================================================
# Bitta o'quvchi qo'shish
# ============================================================================

@router.message(Command("oquvchi_qoshish"))
async def add_student_start(message: Message, state: FSMContext):
    await state.set_state(AddStudent.ism)
    await message.answer("O'quvchining ism va familiyasini yuboring:")


@router.message(AddStudent.ism)
async def add_student_ism(message: Message, state: FSMContext):
    await state.update_data(ism=message.text.strip())
    await state.set_state(AddStudent.yonalish)
    await message.answer("Yo'nalishni tanlang:", reply_markup=yonalish_kb())


@router.callback_query(AddStudent.yonalish, F.data.startswith("yon:"))
async def add_student_yonalish(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":", 1)[1]
    await state.update_data(yonalish=code)
    await state.set_state(AddStudent.jinsi)
    await callback.message.edit_text("Jinsini tanlang:", reply_markup=jinsi_kb())
    await callback.answer()


@router.callback_query(AddStudent.jinsi, F.data.startswith("jin:"))
async def add_student_jinsi(callback: CallbackQuery, state: FSMContext):
    jinsi = callback.data.split(":", 1)[1]
    data = await state.get_data()
    db.add_student(data["ism"], data["yonalish"], jinsi)
    await state.clear()
    await callback.message.edit_text(f"✅ <b>{data['ism']}</b> qo'shildi!", parse_mode="HTML")
    await callback.answer()


# ============================================================================
# Ko'plab o'quvchini birdaniga qo'shish
# ============================================================================

BULK_FORMAT_HELP = (
    "Har bir o'quvchini yangi qatordan, quyidagi formatda yuboring:\n\n"
    "<code>Ism Familiya; yonalish; jinsi</code>\n\n"
    "Yo'nalish uchun: <b>ingliz</b>, <b>fizika</b> yoki <b>ona_tili</b>\n"
    "Jinsi uchun: <b>ogil</b> yoki <b>qiz</b>\n\n"
    "Misol:\n"
    "<code>Aliyev Vali; ingliz; ogil\n"
    "Karimova Nodira; fizika; qiz\n"
    "Yusupov Sardor; ona_tili; ogil</code>"
)


@router.message(Command("royxat_yukla"))
async def bulk_add_start(message: Message, state: FSMContext):
    await state.set_state(BulkAdd.matn)
    await message.answer(BULK_FORMAT_HELP, parse_mode="HTML")


@router.message(BulkAdd.matn)
async def bulk_add_process(message: Message, state: FSMContext):
    lines = [l.strip() for l in message.text.splitlines() if l.strip()]
    qoshildi, xato = [], []

    for line in lines:
        parts = [p.strip() for p in line.split(";")]
        if len(parts) != 3:
            xato.append(f"«{line}» — format noto'g'ri (3 qism kerak)")
            continue
        ism, yon_raw, jin_raw = parts
        yon_code = None
        for code in YONALISHLAR:
            if code in yon_raw.lower() or yon_raw.lower() in code:
                yon_code = code
                break
        jin_code = None
        if "qiz" in jin_raw.lower():
            jin_code = "qiz"
        elif "ogil" in jin_raw.lower() or "o'g" in jin_raw.lower() or "ug'il" in jin_raw.lower():
            jin_code = "ogil"

        if not ism or not yon_code or not jin_code:
            xato.append(f"«{line}» — yo'nalish yoki jinsi aniqlanmadi")
            continue

        db.add_student(ism, yon_code, jin_code)
        qoshildi.append(ism)

    await state.clear()
    natija = f"✅ Qo'shildi: {len(qoshildi)} ta o'quvchi\n"
    if qoshildi:
        natija += "\n".join(f"• {ism}" for ism in qoshildi)
    if xato:
        natija += "\n\n⚠️ Xatoliklar:\n" + "\n".join(f"• {x}" for x in xato)
    await message.answer(natija)


# ============================================================================
# Ro'yxat (faol o'quvchilar)
# ============================================================================

@router.message(Command("royxat"))
async def show_list(message: Message):
    for code, name in YONALISHLAR.items():
        students = db.get_list(holati="faol", yonalish=code)
        if not students:
            continue
        lines = [f"<b>{name}</b> ({len(students)} ta):"]
        for s in students:
            belgi = "👦" if s["jinsi"] == "ogil" else "👧"
            lines.append(f"{belgi} {s['ism_familiya']}")
        await message.answer("\n".join(lines), parse_mode="HTML")

    jami = db.get_list(holati="faol")
    if not jami:
        await message.answer("Hozircha faol o'quvchilar yo'q.")


# ============================================================================
# Qidirish / to'liq ma'lumot
# ============================================================================

@router.message(Command("qidir"))
async def search_start(message: Message, state: FSMContext):
    await state.set_state(SearchStudent.qidiruv)
    await message.answer("Ism yoki familiyani yozing:")


@router.message(SearchStudent.qidiruv)
async def search_process(message: Message, state: FSMContext):
    await state.clear()
    results = db.search_students(message.text.strip())
    if not results:
        await message.answer("Hech kim topilmadi.")
        return
    if len(results) == 1:
        row, tarix = db.get_student(results[0]["id"])
        await message.answer(student_card(row, tarix), parse_mode="HTML")
    else:
        await message.answer(
            f"{len(results)} ta natija topildi, birini tanlang:",
            reply_markup=students_kb(results, "info"),
        )


@router.callback_query(F.data.startswith("info:"))
async def search_select(callback: CallbackQuery):
    student_id = int(callback.data.split(":", 1)[1])
    row, tarix = db.get_student(student_id)
    await callback.message.edit_text(student_card(row, tarix), parse_mode="HTML")
    await callback.answer()


# ============================================================================
# Ketdi (butunlay yoki vaqtincha)
# ============================================================================

@router.message(Command("ketdi"))
async def leave_start(message: Message, state: FSMContext):
    await state.set_state(LeaveStudent.qidiruv)
    await message.answer("Kim ketganini ism/familiya bilan yozing:")


@router.message(LeaveStudent.qidiruv)
async def leave_search(message: Message, state: FSMContext):
    results = db.search_students(message.text.strip(), holatlar=["faol"])
    if not results:
        await message.answer("Faol o'quvchilar orasida topilmadi. Qaytadan urinib ko'ring yoki /bekor.")
        return
    await state.update_data(candidates={str(s["id"]): s["ism_familiya"] for s in results})
    await message.answer("Kimni tanlaysiz?", reply_markup=students_kb(results, "ketdi_tanlash"))


@router.callback_query(F.data.startswith("ketdi_tanlash:"))
async def leave_pick(callback: CallbackQuery, state: FSMContext):
    student_id = callback.data.split(":", 1)[1]
    await state.update_data(student_id=student_id)
    kb = InlineKeyboardBuilder()
    kb.button(text="🔴 Butunlay ketdi", callback_data="ketdi_turi:butunlay")
    kb.button(text="🟡 Vaqtincha (sababli)", callback_data="ketdi_turi:vaqtincha")
    kb.adjust(1)
    await state.set_state(LeaveStudent.turi)
    await callback.message.edit_text("Qanday ketdi?", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(LeaveStudent.turi, F.data.startswith("ketdi_turi:"))
async def leave_turi(callback: CallbackQuery, state: FSMContext):
    turi = callback.data.split(":", 1)[1]
    await state.update_data(turi=turi)
    await state.set_state(LeaveStudent.sabab)
    await callback.message.edit_text(
        "Sababini yozing (bo'lmasa «yo'q» deb yozing):"
    )
    await callback.answer()


@router.message(LeaveStudent.sabab)
async def leave_sabab(message: Message, state: FSMContext):
    data = await state.get_data()
    sabab = message.text.strip()
    if sabab.lower() in ("yo'q", "yoq", "-"):
        sabab = None
    db.mark_left(int(data["student_id"]), data["turi"], sabab)
    ism = data["candidates"].get(data["student_id"], "O'quvchi")
    await state.clear()
    turi_matn = "butunlay ketdi" if data["turi"] == "butunlay" else "vaqtincha (sababli) ketdi"
    await message.answer(f"✅ <b>{ism}</b> {turi_matn} deb belgilandi.", parse_mode="HTML")


# ============================================================================
# Qaytdi
# ============================================================================

@router.message(Command("qaytdi"))
async def return_start(message: Message, state: FSMContext):
    await state.set_state(ReturnStudent.qidiruv)
    await message.answer("Kim qaytganini ism/familiya bilan yozing:")


@router.message(ReturnStudent.qidiruv)
async def return_search(message: Message, state: FSMContext):
    results = db.search_students(message.text.strip(), holatlar=["ketgan", "sababli"])
    await state.clear()
    if not results:
        await message.answer("Ketganlar orasida topilmadi.")
        return
    await message.answer("Kimni qaytaramiz?", reply_markup=students_kb(results, "qaytdi_tanlash"))


@router.callback_query(F.data.startswith("qaytdi_tanlash:"))
async def return_pick(callback: CallbackQuery):
    student_id = int(callback.data.split(":", 1)[1])
    row, _ = db.get_student(student_id)
    db.mark_returned(student_id)
    await callback.message.edit_text(f"🔁 <b>{row['ism_familiya']}</b> qaytib keldi!", parse_mode="HTML")
    await callback.answer()


# ============================================================================
# Ketganlar ro'yxati
# ============================================================================

@router.message(Command("ketganlar"))
async def leavers_list(message: Message):
    ketgan = db.get_list(holati="ketgan")
    sababli = db.get_list(holati="sababli")

    if sababli:
        lines = ["🟡 <b>Vaqtincha ketganlar (qaytishi mumkin):</b>"]
        for s in sababli:
            kunlar = db.kun_farqi(s["qoshilgan_sana"], s["ketgan_sana"])
            sabab = f" — {s['sabab']}" if s["sabab"] else ""
            lines.append(f"• {s['ism_familiya']}: {s['qoshilgan_sana']} → {s['ketgan_sana']} ({kunlar} kun o'qigan){sabab}")
        await message.answer("\n".join(lines), parse_mode="HTML")

    if ketgan:
        lines = ["🔴 <b>Butunlay ketganlar:</b>"]
        for s in ketgan:
            kunlar = db.kun_farqi(s["qoshilgan_sana"], s["ketgan_sana"])
            sabab = f" — {s['sabab']}" if s["sabab"] else ""
            lines.append(f"• {s['ism_familiya']}: {s['qoshilgan_sana']} → {s['ketgan_sana']} ({kunlar} kun o'qigan){sabab}")
        await message.answer("\n".join(lines), parse_mode="HTML")

    if not sababli and not ketgan:
        await message.answer("Hozircha hech kim ketmagan. 🎉")


# ============================================================================
# Statistika
# ============================================================================

@router.message(Command("statistika"))
async def stats(message: Message):
    s = db.get_stats()
    lines = [
        "📊 <b>Umumiy statistika</b>\n",
        f"✅ Jami faol o'quvchilar: <b>{s['jami_faol']}</b>",
        f"👦 O'g'il: {s['ogil']}   👧 Qiz: {s['qiz']}\n",
        "<b>Yo'nalishlar bo'yicha:</b>",
    ]
    for code, name in YONALISHLAR.items():
        soni = s["yonalish_taqsimot"].get(code, 0)
        lines.append(f"• {name}: {soni} ta")

    lines.append("")
    lines.append(f"🟡 Vaqtincha ketganlar: {s['sababli_soni']}")
    lines.append(f"🔴 Butunlay ketganlar: {s['ketgan_soni']}")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ============================================================================
# Ishga tushirish
# ============================================================================

async def main():
    db.init_db()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
