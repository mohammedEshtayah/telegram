from telethon import TelegramClient, events
import difflib
import os
import html
import re
from telethon.errors.rpcerrorlist import AuthKeyDuplicatedError
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, Chat, User, Channel
from dotenv import load_dotenv
from qa import answer_from_stored_news, split_telegram
from storage import init_db, persist_from_caption
# loading variables from .env file
load_dotenv() 
api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
phone = os.getenv('PHONE')
session_name = (os.getenv("SESSION_NAME") or "forward_bot_session_local").strip()
dic_count_group = {
}
dic_message = {
}
# لكل grouped_id: هل المنشور «تأكيد مصدر إضافي» فقط (بدون إعادة نص/ميديا كاملة)
dic_group_dup_confirm = {
}

client = TelegramClient(session_name, api_id, api_hash)

target_channel = -1002584913687  # قناة My News Bot
target_channel_Streets = -1002692513965  # قناة Streets
source_channels = [
    -1001307326930,  # المستشار احمد ابو اياد
    -1001253130437,  # فجر نيوز
    -1001807128752,  # سالم تجمعنا
    -1001200257707,  # مش هيك
    -1001672018523,  # عبري لايف
    -1001398906121,  # نابلس غير
    -1001125629973,  # رام الله مكس
    -1001966059354,  # كتيبة خليل الرحمن
    -1001634384757,  # غزة_نابلس المقاومة
    -1001700954166,  # نبض القدس
    -1001291766291,  # فلسطين الأقصى
    -1001619836256,  # الشهيد جميل العموري
    -1001014183242,  # حسن اصليح
    -1001750166587,  # كتيبة جنين
    -1001721523102,  #المحلل خ.ف: 
    -1002606693516,  #test
    -1001989491822,  # الأستاذ المترجم عزام ابو العدس
    #group
    -1001429269676,#GROUP: أحوال "الطرق وحواجز الضفةِ و القدس" -> ID: -1001429269676
    -1001267214144,#👥 GROUP: أحوال الطرق والحواجز - فلسطين -> ID: -1001267214144
    -1001325889089,#👥 GROUP: احوال طرق الشمال الى رام الله -> ID: -1001325889089 
    -591526182,#👥 BASIC GROUP: حالة طرق شمال الضفة -> ID: -591526182
    -1001756020315,#👥 GROUP: احوال الطرق وحواجز الإحتلال-> ID: -1001756020315
]
# آخر منشورات «كاملة» في كل قناة هدف: {text, target_chat_id, msg_id} — النص لإعادة عرضه عند التأكيد
recent_entries: list[dict] = []
# حد أقصى لنص «الخبر الأصلي» داخل رسالة التأكيد (حد تيليجرام ~4096)
_MAX_DUP_EMBED_CHARS = 3600


def _log(step: str, status: str, details: str = ""):
    if status == "ok":
        prefix = "✅"
    elif status == "fail":
        prefix = "❌"
    else:
        prefix = "ℹ️"
    msg = f"{prefix} [BOT] {step}"
    if details:
        msg += f" | {details}"
    print(msg)


def duplicate_match(text: str, target_chat_id: int, threshold: float = 0.8) -> dict | None:
    for entry in reversed(recent_entries):
        if entry.get("target_chat_id") != target_chat_id:
            continue
        prev = entry.get("text") or ""
        if difflib.SequenceMatcher(None, text, prev).ratio() >= threshold:
            return entry
    return None


def add_to_recent(text: str, target_chat_id: int, msg_id: int, limit: int = 500) -> None:
    if not text or msg_id is None:
        return
    recent_entries.append(
        {"text": text, "target_chat_id": target_chat_id, "msg_id": int(msg_id)}
    )
    while len(recent_entries) > limit:
        recent_entries.pop(0)


def _first_sent_message_id(result) -> int | None:
    if result is None:
        return None
    if isinstance(result, list):
        return result[0].id if result else None
    return getattr(result, "id", None)


def _group_source_text(media_group) -> str:
    for msg in media_group:
        if msg.text:
            return (msg.text or "").strip()
    return ""


def _sanitize_news_plain(s: str) -> str:
    s = (s or "").replace("*", "")
    s = s.replace("https://t.me/Almustashaar", "")
    s = s.replace("https://t.me/+tQHLyywTho82Njky", "")
    s = s.replace("#فلســـ𓂆ــــــطين_الأقصى 🇵🇸", "")
    return s.strip()


async def clean_message_text(event, target_chat_id: int) -> str:
    _log("clean_message_text", "info", "start")
    message_text = (event.message.text or "").strip()
    # تكرار عالي: تأكيد + إدراج نفس نص الخبر السابق هنا (بدون الرجوع بالمنشورات)
    if message_text:
        match = duplicate_match(message_text, target_chat_id)
        if match:
            prev = _sanitize_news_plain(match.get("text") or "")
            if len(prev) > _MAX_DUP_EMBED_CHARS:
                prev = prev[:_MAX_DUP_EMBED_CHARS].rstrip() + "\n…"
            _log("clean_message_text", "ok", "compact_duplicate_confirm")
            return (
                "🔁 <b>تأكيد من مصدر إضافي</b>\n"
                "نفس الخبر ورد سابقاً؛ هذا النص المرجعي (لا حاجة للتمرير للأعلى):\n"
                f"<blockquote>{html.escape(prev)}</blockquote>"
            )

    full_caption = ""
    if event.message.is_reply:
        replied_msg = await event.message.get_reply_message()
        if replied_msg and replied_msg.text:
            full_caption += f"<blockquote>🧾 <b>رد على:</b>\n{html.escape(replied_msg.text.strip())} ====></blockquote>"
    if message_text:
        full_caption += f"\n{html.escape(message_text)}"
    if not full_caption:
        return ""
    
    # حذف الروابط
    full_caption = full_caption.replace('https://t.me/Almustashaar', '')
    full_caption = full_caption.replace('https://t.me/+tQHLyywTho82Njky', '')
    full_caption = full_caption.replace('#فلســـ𓂆ــــــطين_الأقصى 🇵🇸', '')

    # حذف جميع نجوم *
    full_caption = full_caption.replace('*', '')
    _log("clean_message_text", "ok", f"caption_chars={len(full_caption)}")
    return full_caption

async def download_and_send_media(event, caption, files, cahnnel, archive_info=None) -> int | None:
    """archive_info: (اسم_المصدر, main|streets) لحفظ نسخة نصية لأسئلة /ask لاحقاً.
    يعيد معرف أول رسالة فُرِضَت في القناة الهدف (للربط عند التكرار)."""
    sent_msg_id: int | None = None
    try:
        _log("download_and_send_media", "info", f"target={cahnnel} files_in={len(files)}")
        temp_files = []
        for media_msg in files:
            if isinstance(media_msg.media, (MessageMediaPhoto, MessageMediaDocument)):
                temp_file = await client.download_media(media_msg.media)
                temp_files.append(temp_file)

        if temp_files:
            result = await client.send_file(
                cahnnel,
                temp_files,
                caption=caption,
                parse_mode="html",
            )
            sent_msg_id = _first_sent_message_id(result)
        else:
            result = await client.send_message(
                cahnnel,
                message=caption,
                parse_mode="html",
            )
            sent_msg_id = _first_sent_message_id(result)
        if archive_info:
            persist_from_caption(caption, archive_info[0], archive_info[1])
            _log("persist_from_caption", "ok", f"source={archive_info[0]} stream={archive_info[1]}")
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        _log("download_and_send_media", "ok", f"sent_files={len(temp_files)} msg_id={sent_msg_id}")

    except Exception as e:
        _log("download_and_send_media", "fail", str(e))
        print(f"❌ حصل خطأ أثناء تحميل أو إرسال الميديا: {e}")
    return sent_msg_id

@client.on(events.NewMessage)
async def ask_from_archive(event):
    _log("ask_from_archive", "info", "start")
    if not event.text:
        _log("ask_from_archive", "fail", "no text")
        return
    t = event.text
    m = re.match(r"^/ask(\s+|$)(.*)$", t.strip(), re.I | re.DOTALL)
    if not m:
        return
    rest = (m.group(2) or "").strip()
    me = await event.client.get_me()
    allowed_chat_ids = {me.id, target_channel, target_channel_Streets}
    if event.chat_id not in allowed_chat_ids:
        _log("ask_from_archive", "fail", f"chat_id not allowed: {event.chat_id}")
        return
    # في القنوات قد يكون sender_id هو معرف القناة نفسها، لذلك نعتمد على event.out
    # لضمان أن الأمر صدر من نفس جلسة الحساب الحالية.
    if event.chat_id != me.id and not event.out:
        _log("ask_from_archive", "fail", "message is not outgoing from this account")
        return
    if not rest:
        await event.reply(
            "استخدم هنا: /ask ثم سؤالك.\n"
            "مثال: /ask اقتصادياً: ما تفاصيل غزة في المخزن؟\n"
            "يعمل في Saved Messages أو القنوات المسموح بها."
        )
        _log("ask_from_archive", "info", "no rest")
        return
    try:
        _log("ask_from_archive", "info", "calling answer_from_stored_news")
        ans = await answer_from_stored_news(rest)
        first = True
        parts_sent = 0
        for part in split_telegram(ans, 4000):
            if not part:
                _log("ask_from_archive", "info", "no part")
                continue
            if first:
                await event.reply(part)
                _log("ask_from_archive", "info", "first part sent")
                first = False
            else:
                await event.client.send_message(event.chat_id, part)
            parts_sent += 1
        _log("ask_from_archive", "ok", f"reply_parts={parts_sent}")
    except Exception as e:
        _log("ask_from_archive", "fail", str(e))
        print(f"❌ خطأ /ask: {e}")
        await event.reply(f"تعذّر إنشاء الجواب: {e}")


@client.on(events.NewMessage(chats=source_channels))
async def forward_handler(event):
    try:
        _log("forward_handler", "info", f"chat_id={event.chat_id}")
        chat = await event.get_chat()
        if isinstance(chat, Channel):
            if chat.megagroup:
                _log("forward_handler", "info", f"type=megagroup title={chat.title}")
                await forward_handler_Streets(event,chat) 
            else:
                _log("forward_handler", "info", f"type=channel title={chat.title}")
                await forward_handler_Channel(event,chat) 
        elif isinstance(chat, Chat):
            print(f"👥 Message from BASIC GROUP: {chat.title} (ID: {chat.id})")

        elif isinstance(chat, User):
            print(f"👤 Message from PRIVATE CHAT: {chat.first_name} (ID: {chat.id})")
    except Exception as e:
        _log("forward_handler", "fail", str(e))
        print(f"❌ خطأ أثناء التحويل: {e}\n")
async def forward_handler_Channel(event,chat):    
    display_name = chat.title if hasattr(chat, 'title') else "قناة مجهولة"
    _log("forward_handler_Channel", "info", f"source={display_name}")
    src_plain = (event.message.text or "").strip()
    dup_confirm = bool(src_plain) and duplicate_match(src_plain, target_channel) is not None

    full_caption = f"<b> من قناة {display_name}</b>\n"
    full_caption += await clean_message_text(event, target_channel)
    if event.message.grouped_id:    
        messages = await client.get_messages(event.chat_id, limit=20)  
        media_group = [msg for msg in messages if msg.grouped_id == event.message.grouped_id]  
        gid = f"{event.message.grouped_id}"
        if event.message.text != "":
            dic_message[gid] = full_caption
            dic_group_dup_confirm[gid] = dup_confirm
        if gid not in dic_count_group:
            dic_count_group[gid] = 1
        else:
            dic_count_group[gid] += 1

        if dic_count_group[gid] == len(media_group):
            files = []
            for msg in media_group:
                if msg.media:
                    files.append(msg)
            cap = dic_message.get(gid, full_caption)
            dup_only = dic_group_dup_confirm.get(gid, False)
            if files:
                _log("forward_handler_Channel", "info", f"group_media_files={len(files)} dup_confirm={dup_only}")
                if dup_only:
                    await client.send_message(
                        target_channel,
                        message=cap,
                        parse_mode="html",
                    )
                    persist_from_caption(cap, display_name, "main")
                    _log("persist_from_caption", "ok", f"source={display_name} stream=main (dup_confirm)")
                else:
                    mid = await download_and_send_media(
                        event,
                        cap,
                        files,
                        target_channel,
                        archive_info=(display_name, "main"),
                    )
                    gtxt = _group_source_text(media_group)
                    if gtxt and mid:
                        add_to_recent(gtxt, target_channel, mid)

    elif event.message.media:
        _log("forward_handler_Channel", "info", "single media message")
        if dup_confirm:
            _log("forward_handler_Channel", "info", "duplicate_confirm_text_only")
            await client.send_message(
                target_channel,
                message=full_caption,
                parse_mode="html",
            )
            persist_from_caption(full_caption, display_name, "main")
            _log("persist_from_caption", "ok", f"source={display_name} stream=main (dup_confirm)")
        else:
            mid = await download_and_send_media(
                event,
                full_caption,
                [event.message],
                target_channel,
                archive_info=(display_name, "main"),
            )
            if src_plain and mid:
                add_to_recent(src_plain, target_channel, mid)
    else: 
        _log("forward_handler_Channel", "info", "text-only message")
        sent = await client.send_message(
            target_channel,
            full_caption,
            parse_mode='html'
        )
        persist_from_caption(full_caption, display_name, "main")
        _log("persist_from_caption", "ok", f"source={display_name} stream=main")
        mid = _first_sent_message_id(sent)
        if src_plain and mid and not dup_confirm:
            add_to_recent(src_plain, target_channel, mid)

    print(f"✅ نُقلت رسالة من {display_name}")
async def forward_handler_Streets(event,chat):
    display_name = chat.title if hasattr(chat, 'title') else "قناة مجهولة"
    _log("forward_handler_Streets", "info", f"source={display_name}")
    src_plain = (event.message.text or "").strip()
    dup_confirm = bool(src_plain) and duplicate_match(src_plain, target_channel_Streets) is not None

    full_caption = f"<b> من قناة {display_name}</b>\n"
    full_caption += await clean_message_text(event, target_channel_Streets)
    if event.message.grouped_id: 
        #print(f"Test event.message.grouped_id")     
        messages = await client.get_messages(event.chat_id, limit=20)  
        media_group = [msg for msg in messages if msg.grouped_id == event.message.grouped_id]   
        gid = f"{event.message.grouped_id}"
        if event.message.text != "":
            dic_message[gid] = full_caption
            dic_group_dup_confirm[gid] = dup_confirm
        if gid not in dic_count_group:
            dic_count_group[gid] = 1
        else:
            dic_count_group[gid] += 1
        if dic_count_group[gid] <= 1:
            files = []
            for msg in media_group:
                if msg.media:
                    files.append(msg)
            cap = dic_message.get(gid, full_caption)
            dup_only = dic_group_dup_confirm.get(gid, False)
            if files:
                _log("forward_handler_Streets", "info", f"group_media_files={len(files)} dup_confirm={dup_only}")
                if dup_only:
                    await client.send_message(
                        target_channel_Streets,
                        message=cap,
                        parse_mode="html",
                    )
                    persist_from_caption(cap, display_name, "streets")
                    _log("persist_from_caption", "ok", f"source={display_name} stream=streets (dup_confirm)")
                else:
                    mid = await download_and_send_media(
                        event,
                        cap,
                        files,
                        target_channel_Streets,
                        archive_info=(display_name, "streets"),
                    )
                    gtxt = _group_source_text(media_group)
                    if gtxt and mid:
                        add_to_recent(gtxt, target_channel_Streets, mid)

    elif event.message.media:
        _log("forward_handler_Streets", "info", "single media message")
        if dup_confirm:
            _log("forward_handler_Streets", "info", "duplicate_confirm_text_only")
            await client.send_message(
                target_channel_Streets,
                message=full_caption,
                parse_mode="html",
            )
            persist_from_caption(full_caption, display_name, "streets")
            _log("persist_from_caption", "ok", f"source={display_name} stream=streets (dup_confirm)")
        else:
            mid = await download_and_send_media(
                event,
                full_caption,
                [event.message],
                target_channel_Streets,
                archive_info=(display_name, "streets"),
            )
            if src_plain and mid:
                add_to_recent(src_plain, target_channel_Streets, mid)
    else:
        _log("forward_handler_Streets", "info", "text-only message")
        sent = await client.send_message(
            target_channel_Streets,
            full_caption,
            parse_mode='html'
        )
        persist_from_caption(full_caption, display_name, "streets")
        _log("persist_from_caption", "ok", f"source={display_name} stream=streets")
        mid = _first_sent_message_id(sent)
        if src_plain and mid and not dup_confirm:
            add_to_recent(src_plain, target_channel_Streets, mid)

    print(f"✅ نُقلت رسالة من {display_name}")


async def get_target_info():
    try: 
       dialogs = await client.get_dialogs()
       for dialog in dialogs:
        if dialog.is_channel:
            print(f"📢 {dialog.name} -> ID: {dialog.id}")
        if isinstance(dialog.entity, Channel):
            if dialog.entity.megagroup:
                print(f"📢 Message from SUPERGROUP: {dialog.title} (ID: {dialog.id})")
            else:
                print(f"👥 Message from BASIC Channel: {dialog.title} (ID: {dialog.id})")

        elif isinstance(dialog, Chat):
            print(f"👥 Message from BASIC GROUP: {dialog.title} (ID: {dialog.id})")

        elif isinstance(dialog, User):
            print(f"👤 Message from PRIVATE CHAT: {dialog.first_name} (ID: {dialog.id})")
        
    except Exception as e:
        print(f"❌ حصل خطأ: {e}")

async def main():  
    _log("main", "info", f"starting client session={session_name}")
    try:
        await client.start(phone)
    except AuthKeyDuplicatedError:
        _log("main", "fail", "session key duplicated across multiple IPs")
        print(
            "❌ جلسة Telethon الحالية أصبحت غير صالحة (AuthKeyDuplicatedError).\n"
            "الحل:\n"
            "1) غيّر SESSION_NAME في .env إلى اسم جديد (مثال: forward_bot_session_oracle).\n"
            "2) شغّل البوت من جديد وسجّل دخول Telegram مرة واحدة.\n"
            "3) لا تستخدم نفس ملف session على جهازين مختلفين بنفس الوقت."
        )
        return
    _log("main", "ok", "client started")
    init_db()
    _log("main", "ok", "database initialized")
    await get_target_info()
    print("🤖 البوت شغال، براقب القنوات...")
    _log("main", "ok", "run_until_disconnected")
    await client.run_until_disconnected()


client.loop.run_until_complete(main())
