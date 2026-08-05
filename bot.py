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

# Only you (ADMIN_ID) can use this bot
router.message.filter(F.from_user.id == ADMIN_ID)
router.callback_query.filter(F.from_user.id == ADMIN_ID)

dp.include_router(router)

DIVIDER = "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"

TRACK_EMOJI = {
    "ingliz": "📘",
    "fizika": "🧪",
    "ona_tili": "📖",
}


# ============================================================================
# FSM states
# ============================================================================

class AddStudent(StatesGroup):
    name = State()
    track = State()
    gender = State()


class BulkAdd(StatesGroup):
    text = State()


class LeaveStudent(StatesGroup):
    search = State()
    type_ = State()
    reason = State()


class ReturnStudent(StatesGroup):
    search = State()


class SearchStudent(StatesGroup):
    search = State()


# ============================================================================
# Keyboards
# ============================================================================

def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Add student", callback_data="menu:add")
    kb.button(text="📥 Bulk add", callback_data="menu:bulk")
    kb.button(text="📋 List", callback_data="menu:list")
    kb.button(text="🔍 Search", callback_data="menu:search")
    kb.button(text="➖ Mark left", callback_data="menu:leave")
    kb.button(text="🔁 Mark returned", callback_data="menu:return")
    kb.button(text="📤 Left students", callback_data="menu:leavers")
    kb.button(text="📊 Statistics", callback_data="menu:stats")
    kb.adjust(2)
    return kb.as_markup()


def back_to_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🏠 Main menu", callback_data="menu:home")
    return kb.as_markup()


def track_kb(prefix="trk"):
    kb = InlineKeyboardBuilder()
    for code, name in YONALISHLAR.items():
        kb.button(text=f"{TRACK_EMOJI.get(code, '')} {name}", callback_data=f"{prefix}:{code}")
    kb.adjust(1)
    return kb.as_markup()


def gender_kb(prefix="gen"):
    kb = InlineKeyboardBuilder()
    kb.button(text=f"👦 {JINSLAR['ogil']}", callback_data=f"{prefix}:ogil")
    kb.button(text=f"👧 {JINSLAR['qiz']}", callback_data=f"{prefix}:qiz")
    kb.adjust(2)
    return kb.as_markup()


def students_kb(students, prefix):
    kb = InlineKeyboardBuilder()
    for s in students:
        emoji = TRACK_EMOJI.get(s["yonalish"], "")
        gender_icon = "👦" if s["jinsi"] == "ogil" else "👧"
        kb.button(text=f"{gender_icon} {s['ism_familiya']} {emoji}", callback_data=f"{prefix}:{s['id']}")
    kb.adjust(1)
    return kb.as_markup()


# ============================================================================
# Text builders
# ============================================================================

def status_label(holati):
    return {"faol": "✅ Active", "ketgan": "🔴 Left", "sababli": "🟡 Left temporarily"}.get(
        holati, holati
    )


def student_card(row, history):
    gender_icon = "👦" if row["jinsi"] == "ogil" else "👧"
    emoji = TRACK_EMOJI.get(row["yonalish"], "")
    lines = [
        f"{gender_icon} <b>{row['ism_familiya']}</b>",
        DIVIDER,
        f"{emoji} Track: <b>{YONALISHLAR.get(row['yonalish'], row['yonalish'])}</b>",
        f"⚧ Gender: {JINSLAR.get(row['jinsi'], row['jinsi'])}",
        f"📌 Status: {status_label(row['holati'])}",
        f"📅 Joined: {row['qoshilgan_sana']}",
    ]
    if row["holati"] in ("ketgan", "sababli"):
        days = db.kun_farqi(row["qoshilgan_sana"], row["ketgan_sana"])
        lines.append(f"📅 Left: {row['ketgan_sana']}  ⏱ studied {days} days")
        if row["sabab"]:
            lines.append(f"📝 Reason: {row['sabab']}")
    else:
        days = db.kun_farqi(row["qoshilgan_sana"])
        lines.append(f"⏱ Studying for {days} days so far")

    if history:
        lines.append(DIVIDER)
        lines.append("🕘 <b>History</b>")
        action_name = {"qoshildi": "➕ Joined", "ketdi": "➖ Left", "qaytdi": "🔁 Returned"}
        for t in history:
            note = f" — {t['izoh']}" if t["izoh"] else ""
            lines.append(f"  {t['sana']} · {action_name.get(t['harakat'], t['harakat'])}{note}")

    return "\n".join(lines)


def bar(part, total, length=8):
    """Simple text progress bar: ▓▓▓▓░░░░"""
    if total == 0:
        return "░" * length
    filled = round((part / total) * length)
    return "▓" * filled + "░" * (length - filled)


def build_list_texts():
    texts = []
    for code, name in YONALISHLAR.items():
        students = db.get_list(holati="faol", yonalish=code)
        if not students:
            continue
        emoji = TRACK_EMOJI.get(code, "")
        lines = [f"{emoji} <b>{name}</b>  ({len(students)})", DIVIDER]
        for s in students:
            icon = "👦" if s["jinsi"] == "ogil" else "👧"
            lines.append(f"{icon} {s['ism_familiya']}")
        texts.append("\n".join(lines))
    if not texts:
        texts.append("📭 No active students yet.")
    return texts


def build_leavers_texts():
    texts = []
    temp_left = db.get_list(holati="sababli")
    left = db.get_list(holati="ketgan")

    if temp_left:
        parts = ["🟡 <b>Left temporarily</b>  (may return)", DIVIDER]
        for s in temp_left:
            days = db.kun_farqi(s["qoshilgan_sana"], s["ketgan_sana"])
            reason = f"\n   📝 {s['sabab']}" if s["sabab"] else ""
            parts.append(
                f"👤 <b>{s['ism_familiya']}</b>\n"
                f"   📅 {s['qoshilgan_sana']} → {s['ketgan_sana']}  ⏱ {days} days{reason}"
            )
        texts.append("\n\n".join(parts))

    if left:
        parts = ["🔴 <b>Left for good</b>", DIVIDER]
        for s in left:
            days = db.kun_farqi(s["qoshilgan_sana"], s["ketgan_sana"])
            reason = f"\n   📝 {s['sabab']}" if s["sabab"] else ""
            parts.append(
                f"👤 <b>{s['ism_familiya']}</b>\n"
                f"   📅 {s['qoshilgan_sana']} → {s['ketgan_sana']}  ⏱ {days} days{reason}"
            )
        texts.append("\n\n".join(parts))

    if not texts:
        texts.append("🎉 No one has left yet.")
    return texts


def build_stats_text():
    s = db.get_stats()
    total = s["jami_faol"]

    lines = [
        "📊 <b>OVERALL STATISTICS</b>",
        DIVIDER,
        f"✅ Total active students: <b>{total}</b>",
        "",
        f"👦 Boys: <b>{s['ogil']}</b>   {bar(s['ogil'], total)}",
        f"👧 Girls: <b>{s['qiz']}</b>   {bar(s['qiz'], total)}",
        "",
        "<b>By track:</b>",
    ]
    for code, name in YONALISHLAR.items():
        count = s["yonalish_taqsimot"].get(code, 0)
        emoji = TRACK_EMOJI.get(code, "")
        lines.append(f"{emoji} {name}: <b>{count}</b>  {bar(count, total)}")

    lines.append("")
    lines.append(DIVIDER)
    lines.append(f"🟡 Left temporarily: <b>{s['sababli_soni']}</b>")
    lines.append(f"🔴 Left for good: <b>{s['ketgan_soni']}</b>")

    return "\n".join(lines)


# ============================================================================
# /start, /menu and general
# ============================================================================

WELCOME_TEXT = (
    "👋 <b>Hello, Teacher!</b>\n\n"
    "📋 Welcome to your <b>Student Tracker Bot</b>.\n"
    "Choose an option from the menu below:"
)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(WELCOME_TEXT, parse_mode="HTML", reply_markup=main_menu_kb())


@router.message(Command("menu"))
async def menu_cmd(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 <b>Main menu</b>", parse_mode="HTML", reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu:home")
async def menu_home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🏠 <b>Main menu</b>", parse_mode="HTML", reply_markup=main_menu_kb())
    await callback.answer()


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Cancelled.", reply_markup=back_to_menu_kb())


# ============================================================================
# Add one student
# ============================================================================

ADD_PROMPT = "➕ <b>New student</b>\n\nSend the student's full name:"


@router.message(Command("add_student"))
async def add_student_start(message: Message, state: FSMContext):
    await state.set_state(AddStudent.name)
    await message.answer(ADD_PROMPT, parse_mode="HTML")


@router.callback_query(F.data == "menu:add")
async def menu_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddStudent.name)
    await callback.message.edit_text(ADD_PROMPT, parse_mode="HTML")
    await callback.answer()


@router.message(AddStudent.name)
async def add_student_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddStudent.track)
    await message.answer("📚 Choose the track:", reply_markup=track_kb())


@router.callback_query(AddStudent.track, F.data.startswith("trk:"))
async def add_student_track(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":", 1)[1]
    await state.update_data(track=code)
    await state.set_state(AddStudent.gender)
    await callback.message.edit_text("⚧ Choose gender:", reply_markup=gender_kb())
    await callback.answer()


@router.callback_query(AddStudent.gender, F.data.startswith("gen:"))
async def add_student_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split(":", 1)[1]
    data = await state.get_data()
    db.add_student(data["name"], data["track"], gender)
    await state.clear()
    emoji = TRACK_EMOJI.get(data["track"], "")
    await callback.message.edit_text(
        f"✅ <b>{data['name']}</b> added!\n{emoji} {YONALISHLAR.get(data['track'], '')}",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()


# ============================================================================
# Bulk add students
# ============================================================================

BULK_FORMAT_HELP = (
    "📥 <b>Bulk add students</b>\n\n"
    "Send each student on a new line, in this format:\n\n"
    "<code>Full Name; track; gender</code>\n\n"
    "Track: <b>english</b>, <b>physics</b> or <b>native</b>\n"
    "Gender: <b>boy</b> or <b>girl</b>\n\n"
    "Example:\n"
    "<code>Ali Valiyev; english; boy\n"
    "Nodira Karimova; physics; girl\n"
    "Sardor Yusupov; native; boy</code>"
)


@router.message(Command("bulk_add"))
async def bulk_add_start(message: Message, state: FSMContext):
    await state.set_state(BulkAdd.text)
    await message.answer(BULK_FORMAT_HELP, parse_mode="HTML")


@router.callback_query(F.data == "menu:bulk")
async def menu_bulk(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BulkAdd.text)
    await callback.message.edit_text(BULK_FORMAT_HELP, parse_mode="HTML")
    await callback.answer()


@router.message(BulkAdd.text)
async def bulk_add_process(message: Message, state: FSMContext):
    lines = [l.strip() for l in message.text.splitlines() if l.strip()]
    added, errors = [], []

    for line in lines:
        parts = [p.strip() for p in line.split(";")]
        if len(parts) != 3:
            errors.append(f"«{line}» — wrong format (3 parts needed)")
            continue
        name, track_raw, gender_raw = parts
        track_raw_l = track_raw.lower()
        track_code = None
        if "english" in track_raw_l or "ingliz" in track_raw_l:
            track_code = "ingliz"
        elif "physic" in track_raw_l or "fizika" in track_raw_l:
            track_code = "fizika"
        elif "native" in track_raw_l or "ona" in track_raw_l:
            track_code = "ona_tili"

        gender_raw_l = gender_raw.lower()
        gender_code = None
        if "girl" in gender_raw_l or "female" in gender_raw_l or "qiz" in gender_raw_l:
            gender_code = "qiz"
        elif "boy" in gender_raw_l or "male" in gender_raw_l or "ogil" in gender_raw_l or "o'g" in gender_raw_l:
            gender_code = "ogil"

        if not name or not track_code or not gender_code:
            errors.append(f"«{line}» — could not detect track or gender")
            continue

        db.add_student(name, track_code, gender_code)
        added.append(name)

    await state.clear()
    result = f"✅ <b>Added: {len(added)} student(s)</b>\n{DIVIDER}\n"
    if added:
        result += "\n".join(f"• {name}" for name in added)
    if errors:
        result += "\n\n⚠️ <b>Errors:</b>\n" + "\n".join(f"• {e}" for e in errors)
    await message.answer(result, parse_mode="HTML", reply_markup=back_to_menu_kb())


# ============================================================================
# List (active students)
# ============================================================================

@router.message(Command("list"))
async def show_list(message: Message):
    texts = build_list_texts()
    for i, t in enumerate(texts):
        kb = back_to_menu_kb() if i == len(texts) - 1 else None
        await message.answer(t, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "menu:list")
async def menu_list(callback: CallbackQuery):
    await callback.answer()
    texts = build_list_texts()
    await callback.message.delete()
    for i, t in enumerate(texts):
        kb = back_to_menu_kb() if i == len(texts) - 1 else None
        await callback.message.answer(t, parse_mode="HTML", reply_markup=kb)


# ============================================================================
# Search / full info
# ============================================================================

SEARCH_PROMPT = "🔍 <b>Search</b>\n\nType the student's name:"


@router.message(Command("search"))
async def search_start(message: Message, state: FSMContext):
    await state.set_state(SearchStudent.search)
    await message.answer(SEARCH_PROMPT, parse_mode="HTML")


@router.callback_query(F.data == "menu:search")
async def menu_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SearchStudent.search)
    await callback.message.edit_text(SEARCH_PROMPT, parse_mode="HTML")
    await callback.answer()


@router.message(SearchStudent.search)
async def search_process(message: Message, state: FSMContext):
    await state.clear()
    results = db.search_students(message.text.strip())
    if not results:
        await message.answer("😕 No one found.", reply_markup=back_to_menu_kb())
        return
    if len(results) == 1:
        row, history = db.get_student(results[0]["id"])
        await message.answer(student_card(row, history), parse_mode="HTML", reply_markup=back_to_menu_kb())
    else:
        await message.answer(
            f"🔍 {len(results)} results found, choose one:",
            reply_markup=students_kb(results, "info"),
        )


@router.callback_query(F.data.startswith("info:"))
async def search_select(callback: CallbackQuery):
    student_id = int(callback.data.split(":", 1)[1])
    row, history = db.get_student(student_id)
    await callback.message.edit_text(
        student_card(row, history), parse_mode="HTML", reply_markup=back_to_menu_kb()
    )
    await callback.answer()


# ============================================================================
# Mark left (permanent or temporary)
# ============================================================================

LEAVE_PROMPT = "➖ <b>Student left</b>\n\nType the name of the student who left:"


@router.message(Command("leave"))
async def leave_start(message: Message, state: FSMContext):
    await state.set_state(LeaveStudent.search)
    await message.answer(LEAVE_PROMPT, parse_mode="HTML")


@router.callback_query(F.data == "menu:leave")
async def menu_leave(callback: CallbackQuery, state: FSMContext):
    await state.set_state(LeaveStudent.search)
    await callback.message.edit_text(LEAVE_PROMPT, parse_mode="HTML")
    await callback.answer()


@router.message(LeaveStudent.search)
async def leave_search(message: Message, state: FSMContext):
    results = db.search_students(message.text.strip(), holatlar=["faol"])
    if not results:
        await message.answer(
            "😕 No match among active students. Try again or /cancel.",
        )
        return
    await state.update_data(candidates={str(s["id"]): s["ism_familiya"] for s in results})
    await message.answer("Which student?", reply_markup=students_kb(results, "leave_pick"))


@router.callback_query(F.data.startswith("leave_pick:"))
async def leave_pick(callback: CallbackQuery, state: FSMContext):
    student_id = callback.data.split(":", 1)[1]
    await state.update_data(student_id=student_id)
    kb = InlineKeyboardBuilder()
    kb.button(text="🔴 Left for good", callback_data="leave_type:permanent")
    kb.button(text="🟡 Temporary (with reason)", callback_data="leave_type:temporary")
    kb.adjust(1)
    await state.set_state(LeaveStudent.type_)
    await callback.message.edit_text("How did they leave?", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(LeaveStudent.type_, F.data.startswith("leave_type:"))
async def leave_type(callback: CallbackQuery, state: FSMContext):
    leave_kind = callback.data.split(":", 1)[1]  # "permanent" or "temporary"
    await state.update_data(leave_kind=leave_kind)
    await state.set_state(LeaveStudent.reason)
    await callback.message.edit_text("📝 Type the reason (or send «no» if none):")
    await callback.answer()


@router.message(LeaveStudent.reason)
async def leave_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    reason = message.text.strip()
    if reason.lower() in ("no", "none", "-", "yo'q", "yoq"):
        reason = None
    turi = "butunlay" if data["leave_kind"] == "permanent" else "vaqtincha"
    db.mark_left(int(data["student_id"]), turi, reason)
    name = data["candidates"].get(data["student_id"], "Student")
    await state.clear()
    if data["leave_kind"] == "permanent":
        label, icon = "left for good", "🔴"
    else:
        label, icon = "left temporarily", "🟡"
    await message.answer(
        f"{icon} <b>{name}</b> marked as {label}.",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )


# ============================================================================
# Mark returned
# ============================================================================

RETURN_PROMPT = "🔁 <b>Student returned</b>\n\nType the name of the student who came back:"


@router.message(Command("return"))
async def return_start(message: Message, state: FSMContext):
    await state.set_state(ReturnStudent.search)
    await message.answer(RETURN_PROMPT, parse_mode="HTML")


@router.callback_query(F.data == "menu:return")
async def menu_return(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ReturnStudent.search)
    await callback.message.edit_text(RETURN_PROMPT, parse_mode="HTML")
    await callback.answer()


@router.message(ReturnStudent.search)
async def return_search(message: Message, state: FSMContext):
    results = db.search_students(message.text.strip(), holatlar=["ketgan", "sababli"])
    await state.clear()
    if not results:
        await message.answer("😕 No match among students who left.", reply_markup=back_to_menu_kb())
        return
    await message.answer("Who is returning?", reply_markup=students_kb(results, "return_pick"))


@router.callback_query(F.data.startswith("return_pick:"))
async def return_pick(callback: CallbackQuery):
    student_id = int(callback.data.split(":", 1)[1])
    row, _ = db.get_student(student_id)
    db.mark_returned(student_id)
    await callback.message.edit_text(
        f"🔁 <b>{row['ism_familiya']}</b> is back!",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb(),
    )
    await callback.answer()


# ============================================================================
# Left students list
# ============================================================================

@router.message(Command("leavers"))
async def leavers_list(message: Message):
    texts = build_leavers_texts()
    for i, t in enumerate(texts):
        kb = back_to_menu_kb() if i == len(texts) - 1 else None
        await message.answer(t, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "menu:leavers")
async def menu_leavers(callback: CallbackQuery):
    await callback.answer()
    texts = build_leavers_texts()
    await callback.message.delete()
    for i, t in enumerate(texts):
        kb = back_to_menu_kb() if i == len(texts) - 1 else None
        await callback.message.answer(t, parse_mode="HTML", reply_markup=kb)


# ============================================================================
# Statistics
# ============================================================================

@router.message(Command("stats"))
async def stats(message: Message):
    await message.answer(build_stats_text(), parse_mode="HTML", reply_markup=back_to_menu_kb())


@router.callback_query(F.data == "menu:stats")
async def menu_stats(callback: CallbackQuery):
    await callback.message.edit_text(
        build_stats_text(), parse_mode="HTML", reply_markup=back_to_menu_kb()
    )
    await callback.answer()


# ============================================================================
# Startup
# ============================================================================

async def main():
    db.init_db()
    print("Bot started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
