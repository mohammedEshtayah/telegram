from telethon import TelegramClient, events
import difflib
import os
import html
import re
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument,Chat, User , Channel 
from dotenv import load_dotenv, dotenv_values 
# loading variables from .env file
load_dotenv() 
api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')
phone = os.getenv('PHONE')
dic_count_group = {
}
dic_message = {
}
#api_id = '24557011'
#api_hash = 'a39d7a9cad2e5f14914bef052e1b2971'
#phone = +970592750733


client = TelegramClient('forward_bot_session', api_id, api_hash)

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
recent_messages = []

def is_duplicate(text, threshold=0.8):
    return any(difflib.SequenceMatcher(None, text, prev).ratio() >= threshold for prev in recent_messages)

def add_to_recent(text, limit=500):
    recent_messages.append(text)
    if len(recent_messages) > limit:
        recent_messages.pop(0)
 
async def clean_message_text(event) -> str:

    message_text = event.message.text.strip() if event.message.text else ""
    full_caption = "\n🔁 <b><u>تنويه:</u> هذا الخبر مشابه لخبر سابق </b>❗\n" if is_duplicate(message_text) else ""
    
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
 
    return full_caption

async def download_and_send_media(event,caption ,files,cahnnel):
    try:
        temp_files = [] 
        for media_msg in files: 
            if isinstance(media_msg.media, (MessageMediaPhoto, MessageMediaDocument)):
                temp_file = await client.download_media(media_msg.media)
                temp_files.append(temp_file)
            
        if temp_files:
            await client.send_file(
            cahnnel,
            temp_files,
            caption=caption,
            parse_mode='html'
          )
        else:
         # Send just the caption as a text message
            await client.send_message(
            cahnnel,
            message=caption,
             parse_mode='html'
        )
        # حذف الملفات المؤقتة
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    except Exception as e:
        print(f"❌ حصل خطأ أثناء تحميل أو إرسال الميديا: {e}")

@client.on(events.NewMessage(chats=source_channels))
async def forward_handler(event):
    try:
        chat = await event.get_chat()
        if isinstance(chat, Channel):
            if chat.megagroup:
                await forward_handler_Streets(event,chat) 
            else:
                await forward_handler_Channel(event,chat) 
        elif isinstance(chat, Chat):
            print(f"👥 Message from BASIC GROUP: {chat.title} (ID: {chat.id})")

        elif isinstance(chat, User):
            print(f"👤 Message from PRIVATE CHAT: {chat.first_name} (ID: {chat.id})")
    except Exception as e:
        print(f"❌ خطأ أثناء التحويل: {e}\n")
async def forward_handler_Channel(event,chat):    
    display_name = chat.title if hasattr(chat, 'title') else "قناة مجهولة"
    full_caption = f"<b> من قناة {display_name}</b>\n"
    full_caption += await clean_message_text(event)
    if event.message.grouped_id:    
        messages = await client.get_messages(event.chat_id, limit=20)  
        media_group = [msg for msg in messages if msg.grouped_id == event.message.grouped_id]  
        if event.message.text != '': 
            dic_message[f"{event.message.grouped_id}"] = full_caption
        if f"{event.message.grouped_id}" not in dic_count_group:
            dic_count_group[f"{event.message.grouped_id}"] = 1
        else: 
            dic_count_group[f"{event.message.grouped_id}"] += 1  

        if  dic_count_group[f"{event.message.grouped_id}"] == len(media_group):
            files = []
            for msg in media_group:
                if msg.media:
                    files.append(msg)    
            if files:
                await download_and_send_media(event, dic_message[f"{event.message.grouped_id}"], files,target_channel)
            
    elif event.message.media: 
        await download_and_send_media(event, full_caption, [event.message],target_channel)
    else: 
        await client.send_message(
            target_channel,
            full_caption,
            parse_mode='html'
        )
    
    if event.message.text:
        add_to_recent(event.message.text.strip())    
    print(f"✅ نُقلت رسالة من {display_name}")
async def forward_handler_Streets(event,chat):    
    full_caption = "" 
    display_name = chat.title if hasattr(chat, 'title') else "قناة مجهولة"
    full_caption = f"<b> من قناة {display_name}</b>\n"
    full_caption = await clean_message_text(event) 
    if event.message.grouped_id: 
        #print(f"Test event.message.grouped_id")     
        messages = await client.get_messages(event.chat_id, limit=20)  
        media_group = [msg for msg in messages if msg.grouped_id == event.message.grouped_id]   
        if event.message.text != '': 
            dic_message[f"{event.message.grouped_id}"] = full_caption 
        if f"{event.message.grouped_id}" not in dic_count_group:
            dic_count_group[f"{event.message.grouped_id}"] = 1
        else: 
            dic_count_group[f"{event.message.grouped_id}"] += 1    
        if  dic_count_group[f"{event.message.grouped_id}"] <= 1:
            files = []
            for msg in media_group:
                if msg.media:
                    files.append(msg)    
            if files:
                await download_and_send_media(event, dic_message[f"{event.message.grouped_id}"], files,target_channel_Streets)
            
    elif event.message.media: 
        await download_and_send_media(event, full_caption, [event.message],target_channel_Streets)
    else:
        await client.send_message(
            target_channel_Streets,
            full_caption,
            parse_mode='html'
        )
    
    if event.message.text: 
        add_to_recent(event.message.text.strip())    
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
    await client.start(phone)
    await get_target_info()
    print("🤖 البوت شغال، براقب القنوات...")
    await client.run_until_disconnected()


client.loop.run_until_complete(main())
