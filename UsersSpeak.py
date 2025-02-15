import asyncio
import random
import re
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.messages import SetTypingRequest
from telethon.tl.types import SendMessageTypingAction
from openai import AsyncOpenAI
from decouple import config

# ✅ Загружаем API-ключ OpenAI
OPENAI_API_KEY = config("AI_API_KEY")
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ✅ Загружаем ID группы
GROUP_ID = config("GROUP_ID", cast=int)

# ✅ Загружаем данные ботов из .env
sessions = [
    {
        "phone": config("BOT1_PHONE"),
        "api_id": config("BOT1_API_ID", cast=int),
        "api_hash": config("BOT1_API_HASH"),
        "session": config("BOT1_SESSION")
    },
    {
        "phone": config("BOT2_PHONE"),
        "api_id": config("BOT2_API_ID", cast=int),
        "api_hash": config("BOT2_API_HASH"),
        "session": config("BOT2_SESSION")
    }
]

# ✅ Персональные промпты для каждого бота
bot_profiles = {
    config("BOT1_PHONE"): "Ты Дарт Вейдер из Звёздных войн. Говори как лорд ситхов, используя тёмную сторону силы.",
    config("BOT2_PHONE"): "Ты Люк Скайуокер из Звёздных войн. Говори как джедай, ведущий борьбу против Империи."
}

# ✅ Общая тема чата
group_prompt = "Эта группа посвящена обсуждению Звёздных войн. Участники говорят о тёмной и светлой стороне силы и о том,\
 что Люк Скайуокер сын Дарта Вейдера. Писать нужно не больше 2-ух предложений за одно сообщение.И сообщения должны быть\
без точки в конце чтобы выглядело как буд-то это пишет человек"

# ✅ Функция определения, содержит ли сообщение вопрос
def is_question(text):
    """ Проверяет, является ли сообщение вопросом """
    return bool(re.search(r"\?", text))

# ✅ Функция генерации текста через OpenAI
async def generate_message(prompt):
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"⚠ Ошибка OpenAI: {e}")
        return "Что-то пошло не так... (ошибка AI)"

async def send_typing_action(client, chat_id, duration=3):
    """ Имитация печати (typing...) перед отправкой сообщения """
    try:
        await client(SetTypingRequest(chat_id, SendMessageTypingAction()))  # Показываем "печатает..."
        await asyncio.sleep(duration)  # Ждём случайное время
    except Exception as e:
        print(f"⚠ Ошибка SetTypingRequest: {e}")

async def run_bot(user, all_clients):
    """ Запуск юзербота с учётом персонального промпта """
    client = TelegramClient(StringSession(user["session"]), user["api_id"], user["api_hash"])
    await client.start()
    print(f"✅ Бот {user['phone']} подключен!")

    bot_prompt = bot_profiles.get(user["phone"], "Ты обычный человек.")

    @client.on(events.NewMessage(chats=GROUP_ID))
    async def handler(event):
        if event.out:  # Не отвечаем на свои сообщения
            return

        sender = await event.get_sender()
        sender_phone = getattr(sender, "phone", None)
        message_text = event.text.strip()

        # ✅ Определяем, кто первый отвечает пользователю
        first_bot_phone = random.choice(list(bot_profiles.keys()))
        second_bot_phone = [phone for phone in bot_profiles.keys() if phone != first_bot_phone][0]

        if sender_phone not in bot_profiles:
            # ✅ Это сообщение от пользователя
            if user["phone"] == first_bot_phone and is_question(message_text):
                # ✅ Если сообщение — вопрос, бот отвечает
                typing_time = random.randint(5, 120)
                await send_typing_action(client, event.chat_id, duration=typing_time)

                user_prompt = f"{group_prompt}\n{bot_prompt}\nПользователь задал вопрос: \"{message_text}\". Ответь в стиле персонажа, но не обращайся к пользователю как к Люку или Дарту Вейдеру."
                message = await generate_message(user_prompt)
                await event.reply(message)

            elif user["phone"] == second_bot_phone:
                # ✅ Второй бот поддерживает беседу
                typing_time = random.randint(5, 120)
                await send_typing_action(client, event.chat_id, duration=typing_time)

                follow_up_prompt = f"{group_prompt}\n{bot_prompt}\nПродолжи беседу, развивая тему, но не отвечай напрямую пользователю."
                message = await generate_message(follow_up_prompt)
                await event.reply(message)
            return

        # ✅ Если один бот ответил, второй может поддержать диалог
        typing_time = random.randint(5, 120)
        await send_typing_action(client, event.chat_id, duration=typing_time)

        full_prompt = f"{group_prompt}\n{bot_prompt}\nКонтекст чата: {message_text}"
        message = await generate_message(full_prompt)
        await event.reply(message)

    # ✅ Случайный запуск диалога ботами
    async def start_random_dialog():
        await asyncio.sleep(random.randint(60, 300))  # Запуск случайно в течение 1-5 минут
        typing_time = random.randint(5, 120)
        await send_typing_action(client, GROUP_ID, duration=typing_time)

        initial_prompt = f"{group_prompt}\n{bot_prompt}\nНачни разговор в стиле персонажа."
        message = await generate_message(initial_prompt)
        await client.send_message(GROUP_ID, message)

    asyncio.create_task(start_random_dialog())
    all_clients.append(client)
    await client.run_until_disconnected()

async def main():
    """ Запуск всех ботов """
    all_clients = []
    tasks = [run_bot(user, all_clients) for user in sessions]
    await asyncio.gather(*tasks)

asyncio.run(main())
