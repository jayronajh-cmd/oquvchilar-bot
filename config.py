# -*- coding: utf-8 -*-
"""
Botni ishga tushirishdan oldin shu faylni to'ldiring (kompyuterda ishlatsangiz).
Agar Railway (yoki shunga o'xshash) orqali bulutda ishlatsangiz, TOKEN va ID ni
bu yerga yozmang — ularni platforma sozlamalarida "Environment Variables" sifatida
kiritasiz, kod ularni avtomatik o'qib oladi.
"""
import os

# @BotFather dan olingan token (Telegram'da @BotFather ga /newbot yozib oling)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "BU_YERGA_TOKENINGIZNI_YOZING")

# Sizning shaxsiy Telegram ID raqamingiz (faqat SIZ botdan foydalanishingiz uchun).
# ID ni bilish uchun Telegram'da @userinfobot ga /start yozing.
ADMIN_ID = int(os.environ.get("ADMIN_ID", "123456789"))

# Ma'lumotlar bazasi fayli (avtomatik yaratiladi, o'zgartirish shart emas)
DB_PATH = os.environ.get("DB_PATH", "oquvchilar.db")

# Yo'nalishlar (kerak bo'lsa shu yerda o'zgartirishingiz mumkin)
YONALISHLAR = {
    "ingliz": "Matematika - Ingliz tili",
    "fizika": "Matematika - Fizika",
    "ona_tili": "Matematika - Ona tili",
}

JINSLAR = {
    "ogil": "O'g'il",
    "qiz": "Qiz",
}
