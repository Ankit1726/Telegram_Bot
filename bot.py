import os
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta

from dotenv import load_dotenv

from telegram import (
    Update,
    ChatPermissions,
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")


# =========================================================
# CONFIGURATION
# =========================================================
MAX_WARNINGS = 4
MUTE_MINUTES = 30

# Basic abusive words.
# Apne group ke according list expand kar sakte ho.
BAD_WORDS = {
    "badword1",
    "badword2",
    "badword3",
}

# Promotional / spam patterns
SPAM_WORDS = {
    "free money",
    "earn money",
    "click here",
    "join now",
    "limited offer",
    "investment opportunity",
}

# Suspicious URL patterns
URL_PATTERN = re.compile(r"(https?://|www\.|t\.me/)", re.IGNORECASE)


# =========================================================
# MEMORY
# =========================================================

# user_id -> warning count
warnings = defaultdict(int)

# user_id -> recent messages
user_messages = defaultdict(lambda: deque(maxlen=5))


# =========================================================
# ADMIN CHECK
# =========================================================


async def is_admin(update: Update) -> bool:

    if not update.effective_user:
        return False

    member = await update.effective_chat.get_member(update.effective_user.id)

    return member.status in (
        "administrator",
        "creator",
    )


# =========================================================
# WARNING SYSTEM
# =========================================================


async def warn_user(update: Update, reason: str):

    message = update.effective_message

    if not message:
        return

    user = message.from_user

    warnings[user.id] += 1

    count = warnings[user.id]

    if count >= MAX_WARNINGS:

        try:

            until_date = datetime.now() + timedelta(minutes=MUTE_MINUTES)

            await message.chat.restrict_member(
                user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date,
            )

            warnings[user.id] = 0

            await message.chat.send_message(
                f"🔇 {user.first_name} has been muted "
                f"for {MUTE_MINUTES} minutes.\n\n"
                f"Reason: {reason}"
            )

        except Exception as e:

            print("Mute error:", e)

            await message.chat.send_message(
                f"⚠️ {user.first_name} received "
                f"warning {count}/{MAX_WARNINGS}.\n\n"
                f"Reason: {reason}"
            )

    else:

        await message.chat.send_message(
            f"⚠️ Warning {count}/{MAX_WARNINGS}\n"
            f"👤 {user.first_name}\n"
            f"Reason: {reason}\n\n"
            "Please follow the group rules."
        )


# =========================================================
# MESSAGE MODERATION
# =========================================================


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = update.effective_message

    if not message:
        return

    user = message.from_user

    if not user:
        return

    # -----------------------------------------------------
    # Ignore admins
    # -----------------------------------------------------

    if await is_admin(update):
        return

    text = message.text or message.caption or ""

    text_lower = text.lower().strip()

    print(f"[MESSAGE] " f"{user.first_name} ({user.id}) : " f"{text[:100]}")

    # -----------------------------------------------------
    # 1. ABUSIVE LANGUAGE
    # -----------------------------------------------------

    for word in BAD_WORDS:

        if word in text_lower:

            try:
                await message.delete()
            except Exception as e:
                print("Delete error:", e)

            await warn_user(update, "Inappropriate language")

            return

    # -----------------------------------------------------
    # 2. SPAM KEYWORDS
    # -----------------------------------------------------

    for spam_word in SPAM_WORDS:

        if spam_word in text_lower:

            try:
                await message.delete()
            except Exception as e:
                print("Delete error:", e)

            await warn_user(update, "Spam/promotional content")

            return

    # -----------------------------------------------------
    # 3. SUSPICIOUS LINKS
    # -----------------------------------------------------

    if URL_PATTERN.search(text):

        try:
            await message.delete()
        except Exception as e:
            print("Delete error:", e)

        await warn_user(update, "Unapproved external link")

        return

    # -----------------------------------------------------
    # 4. REPEATED MESSAGE SPAM
    # -----------------------------------------------------

    user_messages[user.id].append(text_lower)

    recent = list(user_messages[user.id])

    if len(recent) >= 3 and len(set(recent[-3:])) == 1 and text_lower:

        try:
            await message.delete()
        except Exception as e:
            print("Delete error:", e)

        await warn_user(update, "Repeated/spam messages")

        return

    # -----------------------------------------------------
    # 5. IMAGE / MEDIA CHECK
    # -----------------------------------------------------

    if message.photo:

        print(f"[IMAGE] " f"{user.first_name} sent an image")

        # Don't automatically delete every image.
        # We will add AI/image moderation later.

        return

    # -----------------------------------------------------
    # NORMAL MESSAGE
    # -----------------------------------------------------

    print(f"[ALLOWED] {user.first_name}")


# =========================================================
# START COMMAND
# =========================================================


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "👋 Welcome to SSC Preparation Group!\n\n"
        "📚 Study\n"
        "📝 Practice\n"
        "🎯 SSC Preparation\n\n"
        "🚫 No Spam\n"
        "🚫 No Abuse\n"
        "🚫 No Unnecessary Promotion\n"
        "🤝 Respect Everyone\n\n"
        "🔥 Focus on preparation and help others."
    )


# =========================================================
# RULES COMMAND
# =========================================================


async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📜 GROUP RULES\n\n"
        "1️⃣ SSC preparation related discussion only\n"
        "2️⃣ No abusive language\n"
        "3️⃣ No spam\n"
        "4️⃣ No unnecessary promotion\n"
        "5️⃣ No repeated messages\n"
        "6️⃣ Respect other aspirants\n"
        "7️⃣ Useful study resources are welcome\n\n"
        "⚠️ Repeated violations may result in mute."
    )


# =========================================================
# NEW MEMBER
# =========================================================


async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):

    for member in update.message.new_chat_members:

        await update.message.reply_text(
            f"👋 Welcome {member.first_name}!\n\n"
            "🎯 Welcome to our SSC preparation community.\n"
            "📚 Study hard and help others.\n\n"
            "Use /rules to read group rules."
        )


# =========================================================
# MAIN
# =========================================================


def main():

    if not BOT_TOKEN:

        raise ValueError("BOT_TOKEN not found in .env")

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))

    app.add_handler(CommandHandler("rules", rules))

    # New members
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

    # Text + captions + media
    app.add_handler(MessageHandler(~filters.COMMAND, handle_message))

    print("🤖 SSC Moderation Bot started...")
    print("🛡️ Monitoring group messages...")

    app.run_polling()


if __name__ == "__main__":
    main()
