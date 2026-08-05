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
# Chap tomondagi kod (masalan "ingliz") — bazada saqlanadi, o'zgartirmang.
# O'ng tomondagi nom — botda foydalanuvchiga ko'rinadigan matn.
YONALISHLAR = {
    "ingliz": "Math - English",
    "fizika": "Math - Physics",
    "ona_tili": "Math - Native Language",
}

JINSLAR = {
    "ogil": "Boy",
    "qiz": "Girl",
}
