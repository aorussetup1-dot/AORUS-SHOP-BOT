from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
import asyncio, uuid, qrcode, os

from config import BOT_TOKEN, ADMIN_ID, UPI_ID
from database import (
    get_user, update_balance,
    get_key, load_json, save_keys,
    create_pending, get_pending, delete_pending
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------------- ADMIN CHECK ----------------
def is_admin(uid: int):
    return uid == ADMIN_ID

# ---------------- TRANSACTION TRACKER ----------------
# Ensures screenshot always matches correct amount
user_last_txn = {}

# ---------------- MAIN KEYBOARD ----------------
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔑 Buy Key")],
        [KeyboardButton(text="💰 Add Funds"), KeyboardButton(text="👛 Wallet")],
        [KeyboardButton(text="📞 Support")]
    ],
    resize_keyboard=True
)

# ---------------- BUY KEY MENU ----------------
buy_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🟢 1 Day — ₹200", callback_data="buy_1")],
    [InlineKeyboardButton(text="🔵 7 Days — ₹500", callback_data="buy_7")],
    [InlineKeyboardButton(text="🔴 30 Days — ₹1400", callback_data="buy_30")]
])

PRICES = {"1": 200, "7": 500, "30": 1400}

# ---------------- ADD FUNDS MENU ----------------
funds_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="₹200", callback_data="fund_200")],
    [InlineKeyboardButton(text="₹700", callback_data="fund_700")],
    [InlineKeyboardButton(text="₹1400", callback_data="fund_1400")],
    [InlineKeyboardButton(text="➕ Custom Amount", callback_data="fund_custom")]
])

user_waiting_custom = set()

# ---------------- START ----------------
@dp.message(CommandStart())
async def start(message: types.Message):
    get_user(message.from_user.id)
    await message.answer(
        "🚀 Welcome to *AORUS OFFICIAL*\n\n"
        "🔐 Secure Wallet\n"
        "⚡ Instant Key Delivery\n"
        "💎 Trusted Premium Service\n\n"
        "Please choose an option below 👇",
        reply_markup=main_kb,
        parse_mode="Markdown"
    )

# ================= USER FEATURES =================

# ---------------- BUY KEY ----------------
@dp.message(lambda m: m.text == "🔑 Buy Key")
async def buy_key(message: types.Message):
    await message.answer(
        "🔑 *Choose Your Plan*",
        reply_markup=buy_kb,
        parse_mode="Markdown"
    )

# ---------------- BUY CALLBACK ----------------
@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery):
    uid = callback.from_user.id
    duration = callback.data.split("_")[1]
    price = PRICES[duration]

    user = get_user(uid)
    if user["balance"] < price:
        await callback.answer("❌ Insufficient wallet balance", show_alert=True)
        return

    key = get_key(duration)
    if not key:
        await callback.answer("⚠️ Stock unavailable", show_alert=True)
        return

    update_balance(uid, -price)

    await callback.message.answer(
        "✅ *Purchase Successful*\n\n"
        f"📆 Plan: {duration} Day(s)\n"
        f"🔑 Your Key:\n`{key}`\n\n"
        "⚠️ Keep this key private.",
        parse_mode="Markdown"
    )
    await callback.answer("Key delivered")

# ---------------- WALLET ----------------
@dp.message(lambda m: m.text == "👛 Wallet")
async def wallet(message: types.Message):
    user = get_user(message.from_user.id)
    await message.answer(
        f"👛 *Wallet Balance*\n\n💰 ₹{user['balance']}",
        parse_mode="Markdown"
    )

# ---------------- ADD FUNDS ----------------
@dp.message(lambda m: m.text == "💰 Add Funds")
async def add_funds(message: types.Message):
    await message.answer(
        "💳 *Add Funds*\n\nSelect an amount:",
        reply_markup=funds_kb,
        parse_mode="Markdown"
    )

# ---------------- FUND CALLBACK ----------------
@dp.callback_query(lambda c: c.data.startswith("fund_"))
async def fund_callback(c: types.CallbackQuery):
    uid = c.from_user.id

    if c.data == "fund_custom":
        user_waiting_custom.add(uid)
        await c.message.answer("✏️ Enter custom amount:")
        await c.answer()
        return

    amount = int(c.data.split("_")[1])
    await send_qr(c.message, uid, amount)
    await c.answer()

# ---------------- CUSTOM AMOUNT ----------------
@dp.message(lambda m: m.from_user.id in user_waiting_custom and m.text.isdigit())
async def custom_amount(m: types.Message):
    user_waiting_custom.remove(m.from_user.id)
    await send_qr(m, m.from_user.id, int(m.text))

# ---------------- SEND QR ----------------
async def send_qr(message, user_id, amount):
    txn_id = uuid.uuid4().hex[:10]
    user_last_txn[user_id] = txn_id

    upi_link = f"upi://pay?pa={UPI_ID}&am={amount}&cu=INR&tn=AORUS-{txn_id}"
    img = qrcode.make(upi_link)

    qr_path = f"qr_{txn_id}.png"
    img.save(qr_path)

    create_pending(txn_id, user_id, amount)

    await message.answer_photo(
        FSInputFile(qr_path),
        caption=(
            f"💳 UPI Payment Request\n\n"
            f"💰 Amount: ₹{amount}\n"
            f"🏦 UPI ID: {UPI_ID}\n"
            f"🆔 Transaction ID: {txn_id}\n\n"
            "📸 Complete payment and send screenshot here."
        )
    )
    os.remove(qr_path)

# ---------------- RECEIVE SCREENSHOT ----------------
@dp.message(lambda m: m.photo)
async def receive_screenshot(m: types.Message):
    uid = m.from_user.id

    if uid not in user_last_txn:
        await m.answer("❌ No active payment request found.\nPlease use Add Funds again.")
        return

    txn_id = user_last_txn[uid]
    data = get_pending(txn_id)

    if not data:
        await m.answer("❌ Payment request expired.\nPlease try again.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Approve", callback_data=f"approve_{txn_id}"),
            InlineKeyboardButton(text="❌ Reject", callback_data=f"reject_{txn_id}")
        ]
    ])

    await bot.send_photo(
        ADMIN_ID,
        m.photo[-1].file_id,
        caption=(
            "💰 PAYMENT VERIFICATION\n\n"
            f"User ID: {data['user_id']}\n"
            f"Amount: ₹{data['amount']}\n"
            f"Txn ID: {txn_id}"
        ),
        reply_markup=kb
    )

    del user_last_txn[uid]
    await m.answer("⏳ Screenshot sent. Waiting for admin approval.")

# ---------------- ADMIN APPROVE / REJECT ----------------
@dp.callback_query(lambda c: c.data.startswith(("approve_", "reject_")))
async def admin_action(c: types.CallbackQuery):
    if not is_admin(c.from_user.id):
        return

    action, txn_id = c.data.split("_")
    data = get_pending(txn_id)

    if not data:
        await c.answer("Already processed", show_alert=True)
        return

    uid = data["user_id"]
    amt = data["amount"]

    if action == "approve":
        update_balance(uid, amt)
        await bot.send_message(uid, f"✅ ₹{amt} credited to your wallet.")
        await c.message.edit_caption("✅ PAYMENT APPROVED", reply_markup=None)
    else:
        await bot.send_message(uid, "❌ Payment rejected. Contact support.")
        await c.message.edit_caption("❌ PAYMENT REJECTED", reply_markup=None)

    delete_pending(txn_id)
    await c.answer("Done")

# ================= ADMIN COMMANDS =================

@dp.message(lambda m: m.text.startswith("/addkey"))
async def admin_add_key(m: types.Message):
    if not is_admin(m.from_user.id):
        return
    try:
        _, days, key = m.text.split(maxsplit=2)
        keys = load_json("keys.json")
        keys[days].append(key)
        save_keys(keys)
        await m.answer("✅ Key added successfully")
    except:
        await m.answer("Usage: /addkey 1 KEY")

@dp.message(lambda m: m.text == "/stock")
async def admin_stock(m: types.Message):
    if not is_admin(m.from_user.id):
        return
    keys = load_json("keys.json")
    msg = "📦 KEY STOCK\n\n"
    for d, k in keys.items():
        msg += f"{d} DAY → {len(k)} keys\n"
    await m.answer(msg)

@dp.message(lambda m: m.text.startswith("/addbalance"))
async def admin_add_balance(m: types.Message):
    if not is_admin(m.from_user.id):
        return
    try:
        _, uid, amt = m.text.split()
        update_balance(int(uid), int(amt))
        await m.answer("✅ Balance updated")
        await bot.send_message(int(uid), f"💰 ₹{amt} added by admin")
    except:
        await m.answer("Usage: /addbalance USER_ID AMOUNT")

@dp.message(lambda m: m.text.startswith("/userinfo"))
async def admin_userinfo(m: types.Message):
    if not is_admin(m.from_user.id):
        return
    try:
        _, uid = m.text.split()
        user = get_user(int(uid))
        await m.answer(f"User ID: {uid}\nBalance: ₹{user['balance']}")
    except:
        await m.answer("Usage: /userinfo USER_ID")

@dp.message(lambda m: m.text.startswith("/broadcast"))
async def admin_broadcast(m: types.Message):
    if not is_admin(m.from_user.id):
        return
    msg = m.text.replace("/broadcast", "").strip()
    users = load_json("users.json")
    sent = 0
    for uid in users:
        try:
            await bot.send_message(int(uid), f"📢 ANNOUNCEMENT\n\n{msg}")
            sent += 1
        except:
            pass
    await m.answer(f"Broadcast sent to {sent} users")

# ---------------- SUPPORT ----------------
@dp.message(lambda m: m.text == "📞 Support")
async def support(message: types.Message):
    await message.answer("📞 Support\n\nPlease contact admin for assistance.")

# ---------------- RUN ----------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
