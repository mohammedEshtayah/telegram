from telethon import TelegramClient, events
import difflib
import os
import html
import re

#api_id = int(os.getenv('API_ID'))
#api_hash = os.getenv('API_HASH')
#phone = os.getenv('PHONE')

api_id = '24557011'
api_hash = 'a39d7a9cad2e5f14914bef052e1b2971'
phone = +970592750733


client = TelegramClient('forward_bot_session', api_id, api_hash)

target_channel = -1002584913687  # قناة My News Bot
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
]
recent_messages = []

def is_duplicate(text, threshold=0.8):
    return any(difflib.SequenceMatcher(None, text, prev).ratio() >= threshold for prev in recent_messages)

def add_to_recent(text, limit=500):
    recent_messages.append(text)
    if len(recent_messages) > limit:
        recent_messages.pop(0)
 
def clean_message_text(text: str) -> str:
    if not text:
        return ""
    
    # حذف الروابط
    text = text.replace('https://t.me/Almustashaar', '')
  
    # حذف جميع نجوم *
    text = text.replace('*', '')
 
    return text
@client.on(events.NewMessage(chats=source_channels))
async def forward_handler(event):
    try:
        chat = await event.get_chat()
        display_name = chat.title if hasattr(chat, 'title') else "قناة مجهولة"
        full_caption = f"<b> من قناة {display_name}</b>\n"
        message_text = event.message.text.strip() if event.message.text else ""
        full_caption += "\n🔁 <b><u>تنويه:</u> هذا الخبر مشابه لخبر سابق </b>❗" if is_duplicate(message_text) else ""
 
        if event.message.is_reply:
            replied_msg = await event.message.get_reply_message()
            if replied_msg and replied_msg.text:
                full_caption += f"<blockquote>🧾 <b>رد على:</b>\n{html.escape(replied_msg.text.strip())} ====></blockquote>"

        if message_text:
            full_caption += f"\n{html.escape(message_text)}"
        
        full_caption=clean_message_text(full_caption)
        if event.message.grouped_id:
            print(f"Test event.message.grouped_id{event.message.grouped_id}")
            messages = await client.get_messages(event.chat_id, limit=20)
            media_group = [msg for msg in messages if msg.grouped_id == event.message.grouped_id and msg.media]

            files = [msg.media for msg in media_group]
            await client.send_file(
                target_channel,
                file=files,
                caption=full_caption,
                parse_mode='html'
            )
        elif event.message.media:
            print(f"Test event.message.media") 
            await client.send_file(
                target_channel,
                file=event.message.media,
                caption=full_caption,
                parse_mode='html'
            )
        else:
            print(f"Test event.Text")  
            await client.send_message(
                target_channel,
                full_caption,
                parse_mode='html'
            )

        if message_text:
            add_to_recent(message_text)

        print(f"✅ نُقلت رسالة من {display_name}")

    except Exception as e:
        print(f"❌ خطأ أثناء التحويل: {e}\n{full_caption}")
async def get_target_info():
    try:
       await client.start(phone)
       print(f"📢 {dialog.name} -> ID: {dialog.id}")

       dialogs = await client.get_dialogs()
       for dialog in dialogs:
        if dialog.is_channel:
            print(f"📢 {dialog.name} -> ID: {dialog.id}")
    except Exception as e:
        print(f"❌ حصل خطأ: {e}")

async def main():
    await client.start(phone)
    print("🤖 البوت شغال، براقب القنوات...")
    await client.run_until_disconnected()

client.loop.run_until_complete(main())
