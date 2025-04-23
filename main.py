from telethon import TelegramClient, events
import difflib

api_id = 24557011 
api_hash = 'a39d7a9cad2e5f14914bef052e1b2971'  
phone = '+970592750733'   

client = TelegramClient('forward_bot_session', api_id, api_hash)

#target_channel = -2584913687  
target_channel = 'https://t.me/+Cw6daBtlDx8xNDcy'
source_channels = [
    'P_S_PI',
    'azzamaddas',
    'Almustashaar',
    'fajernews',
    'salemvillage1',
    'meshheek',
    'rueib_alkian',
    'EabriLive',
    'Nablusgheer',
    'hpress',
    'ramallahmix1',
    'KhalilRahmanBrigades',
]
recent_messages = []

def are_similar(text1, text2, threshold=0.7):
    ratio = difflib.SequenceMatcher(None, text1, text2).ratio()
    return ratio >= threshold

@client.on(events.NewMessage(chats=source_channels))
async def handler(event):
    try:
        chat = await event.get_chat()
        display_name = chat.title if hasattr(chat, 'title') else "قناة مجهولة"

        caption = f"📰 من قناة {display_name}" 
        if event.message.text and not event.message.media:
            current_text = event.message.text.strip()

            # تحقق من التشابه مع آخر 1000 خبر
            is_duplicate = any(are_similar(current_text, prev) for prev in recent_messages)

            repeated_note = ""
            if is_duplicate:
                repeated_note = "\n🔁 <b><u>تنويه:</u></b> <i>هذا الخبر مشابه لخبر سابق</i> ❗"

            msg_to_send = f"{caption}{repeated_note}\n\n{current_text}"
            await client.send_message(target_channel, msg_to_send, parse_mode='html')

            # أضف الرسالة الجديدة للقائمة
            recent_messages.append(current_text)
            if len(recent_messages) > 1000:
                recent_messages.pop(0)

        # رسائل ميديا
        elif event.message.media:
            current_text = event.message.text.strip() if event.message.text else ""
            is_duplicate = any(are_similar(current_text, prev) for prev in recent_messages)

            repeated_note = ""
            if is_duplicate:
                repeated_note = "\n🔁 <b><u>تنويه:</u></b> <i>هذا الخبر مشابه لخبر سابق</i> ❗"

            full_caption = f"{caption}{repeated_note}"
            if current_text:
                full_caption += f"\n\n{current_text}"

            await client.send_file(
                target_channel,
                file=event.message.media,
                caption=full_caption,
                parse_mode='html'
            )

            # أضف النص للقائمة في حال وجد
            if current_text:
                recent_messages.append(current_text)
                if len(recent_messages) > 1000:
                    recent_messages.pop(0)
            
        print(f"✅ نُقلت رسالة من {display_name}")

    except Exception as e:
        print(f'❌ خطأ أثناء التحويل: {e}')

async def main():
    await client.start(phone)
    print("🤖 البوت شغال، براقب القنوات...")
    await client.run_until_disconnected()

client.loop.run_until_complete(main())
