"""
Echorouk Editorial OS — Seed Users Script
=======================================
Seeds the database with Echorouk Online journalist accounts.
Passwords are hashed with bcrypt before storage.

Usage:
    python -m scripts.seed_users

⚠️  WARNING: This file contains initial passwords.
    - All users MUST change their passwords on first login.
    - This file should be in .gitignore for production.
    - For development/staging only.
"""

print("SEED SCRIPT STARTED...")
import asyncio
import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import async_session, init_db
from app.core.security import hash_password
from app.models.user import User, UserRole, Department


# ══════════════════════════════════════════════
#  قائمة صحفيي موقع الشروق أونلاين
# ══════════════════════════════════════════════

JOURNALISTS = [
    # ── المدير ──
    {
        "full_name_ar": "بهاء الدين بورزق",
        "username": "bourezgb",
        "password": "password123",
        "role": UserRole.director,
        "departments": [Department.MANAGEMENT],
        "specialization": "المدير العام",
    },

    # ── القسم الوطني والدولي ──
    {
        "full_name_ar": "سهام حواس",
        "username": "s.hawas",
        "password": "Shro0uq2025@Hw",
        "role": UserRole.journalist,
        "departments": [Department.NATIONAL, Department.INTERNATIONAL],
        "specialization": "وطني + دولي",
    },
    {
        "full_name_ar": "إيمان بوخاتم",
        "username": "i.boukhatem",
        "password": "Watani2025@Bk",
        "role": UserRole.journalist,
        "departments": [Department.NATIONAL],
        "specialization": "وطني",
    },
    {
        "full_name_ar": "محمد عبد المؤمن",
        "username": "m.abdelmoumin",
        "password": "News2025@Am",
        "role": UserRole.editor_chief,
        "departments": [Department.NATIONAL],
        "specialization": "رئيس تحرير + وطني",
    },
    {
        "full_name_ar": "مجيد صراح",
        "username": "m.sarrah",
        "password": "Daw1i2025@Sr",
        "role": UserRole.journalist,
        "departments": [Department.NATIONAL, Department.INTERNATIONAL],
        "specialization": "وطني + دولي",
    },

    # ── القسم الاقتصادي ──
    {
        "full_name_ar": "محمد فاسي",
        "username": "m.fassi",
        "password": "Econ0my2025@Fs",
        "role": UserRole.journalist,
        "departments": [Department.ECONOMY],
        "specialization": "اقتصاد",
    },
    {
        "full_name_ar": "عادل فداد",
        "username": "a.faddad",
        "password": "Iqtisad2025@Fd",
        "role": UserRole.journalist,
        "departments": [Department.ECONOMY],
        "specialization": "اقتصاد",
    },

    # ── القسم الرياضي ──
    {
        "full_name_ar": "عمر سلامي",
        "username": "o.salami",
        "password": "Sport2025@Sl",
        "role": UserRole.journalist,
        "departments": [Department.SPORTS],
        "specialization": "رياضة",
    },
    {
        "full_name_ar": "علي بهولي",
        "username": "a.behouli",
        "password": "Riyada2025@Bh",
        "role": UserRole.journalist,
        "departments": [Department.SPORTS],
        "specialization": "رياضة",
    },

    # ── القسم الفرنسي ──
    {
        "full_name_ar": "رشال حمدي",
        "username": "r.hamdi",
        "password": "French2025@Hm",
        "role": UserRole.journalist,
        "departments": [Department.FRENCH],
        "specialization": "القسم الفرنسي",
    },

    # ── السوشيال ميديا ──
    {
        "full_name_ar": "خديجة عليواش",
        "username": "k.aliwach",
        "password": "Social2025@Aw",
        "role": UserRole.social_media,
        "departments": [Department.SOCIAL_MEDIA],
        "specialization": "سوشيال ميديا",
    },
    {
        "full_name_ar": "أيمن سحنون",
        "username": "a.sahnoun",
        "password": "Media2025@Sh",
        "role": UserRole.social_media,
        "departments": [Department.SOCIAL_MEDIA],
        "specialization": "سوشيال ميديا",
    },

    # ── مادة الجريدة ──
    {
        "full_name_ar": "محمد شوية",
        "username": "m.chouia",
        "password": "Paper2025@Ch",
        "role": UserRole.print_editor,
        "departments": [Department.PRINT],
        "specialization": "مادة الجريدة",
    },
    {
        "full_name_ar": "نصر الدين مرازقة",
        "username": "n.merazga",
        "password": "Print2025@Mz",
        "role": UserRole.print_editor,
        "departments": [Department.PRINT],
        "specialization": "مادة الجريدة",
    },

    # ── رئيسة التحرير + منوعات ──
    {
        "full_name_ar": "نادية شريف",
        "username": "n.cherif",
        "password": "Vari3ty2025@Ch",
        "role": UserRole.editor_chief,
        "departments": [Department.INTERNATIONAL, Department.VARIETY],
        "specialization": "رئيسة تحرير + دولي + منوعات",
    },

    # ── جواهر ──
    {
        "full_name_ar": "سمية سعادة",
        "username": "s.saada",
        "password": "Jawah1r2025@Sa",
        "role": UserRole.journalist,
        "departments": [Department.JEWELRY],
        "specialization": "جواهر",
    },
]


async def seed_users():
    """Seed the database with Echorouk journalists."""
    await init_db()

    async with async_session() as session:
        added = 0
        skipped = 0

        for journalist in JOURNALISTS:
            # Check if user already exists
            from sqlalchemy import select
            result = await session.execute(
                select(User).where(User.username == journalist["username"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"  ⏭️  {journalist['full_name_ar']} ({journalist['username']}) — موجود مسبقاً")
                skipped += 1
                continue

            # Create user with hashed password
            print(f"Hashing password for {journalist['username']}: {journalist['password']} (len={len(journalist['password'])})")
            print(f"DEBUG: Role value: {journalist['role'].value} (type: {type(journalist['role'].value)})")
            user = User(
                full_name_ar=journalist["full_name_ar"],
                username=journalist["username"],
                hashed_password=hash_password(journalist["password"][:50]),
                role=journalist["role"].value,
                departments=[d.value for d in journalist["departments"]],
                specialization=journalist.get("specialization"),
                is_active=True,
            )
            session.add(user)
            print(f"  ✅ {journalist['full_name_ar']} ({journalist['username']}) — تمت الإضافة")
            added += 1

        await session.commit()

    print(f"\n{'='*50}")
    print(f"📊 النتيجة: {added} مستخدم جديد | {skipped} موجود مسبقاً")
    print(f"👥 الإجمالي: {len(JOURNALISTS)} صحفي")
    print(f"{'='*50}")


if __name__ == "__main__":
    print("=" * 50)
    print("🏗️  بذر قاعدة البيانات — صحفيو الشروق أونلاين")
    print("=" * 50)
    asyncio.run(seed_users())
