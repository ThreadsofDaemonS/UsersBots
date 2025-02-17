import asyncio
import random
import re
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.messages import SetTypingRequest, SendReactionRequest
from telethon.tl.types import SendMessageTypingAction, ReactionEmoji
from openai import AsyncOpenAI
from decouple import config

# ✅ OpenAI API
OPENAI_API_KEY = config("AI_API_KEY")
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ✅ ID группы и OWNER_ID
GROUP_ID = config("GROUP_ID", cast=int)
OWNER_ID = config("OWNER_ID", cast=int)

# ✅ Чат ID ботов
CHAT_ID_BOT1 = config("CHAT_ID_BOT1", cast=int)
CHAT_ID_BOT2 = config("CHAT_ID_BOT2", cast=int)

# ✅ Данные юзер-ботов
sessions = [
    {
        "phone": config("BOT1_PHONE"),
        "api_id": config("BOT1_API_ID", cast=int),
        "api_hash": config("BOT1_API_HASH"),
        "session": config("BOT1_SESSION"),
        "chat_id": CHAT_ID_BOT1
    },
    {
        "phone": config("BOT2_PHONE"),
        "api_id": config("BOT2_API_ID", cast=int),
        "api_hash": config("BOT2_API_HASH"),
        "session": config("BOT2_SESSION"),
        "chat_id": CHAT_ID_BOT2
    }
]

# ✅ Персонажи
bot_profiles = {
    CHAT_ID_BOT1: "Ты человек, который имитирует Дарта Вейдера. Говори как лорд ситхов, используя тёмную сторону силы.",
    CHAT_ID_BOT2: "Ты человек, который имитирует Люка Скайуокера. Говори как джедай, ведущий борьбу против Империи."
}

# ✅ Общая тематика
group_prompt = "Это чат о Звёздных войнах. Боты должны вести естественный диалог как люди. Писать не больше 2-ух предложений в одном сообщении."

# ✅ Определение, содержит ли сообщение вопрос
def is_question(text):
    return "?" in text

# ✅ Генерация текста через OpenAI
async def generate_message(prompt):
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"⚠ Ошибка OpenAI: {e}")
        return "Что-то пошло не так... (ошибка AI)"

# ✅ Имитация набора текста
async def send_typing_action(client, chat_id, duration=3):
    try:
        await client(SetTypingRequest(chat_id, SendMessageTypingAction()))
        await asyncio.sleep(duration)
    except Exception as e:
        print(f"⚠ Ошибка SetTypingRequest: {e}")

# ✅ Лайки (реакции) от ботов (вероятность 30%)
async def send_reaction(client, event):
    if random.random() < 0.3:
        try:
            reaction_choices = ["👍", "❤️", "🔥", "💯"]
            chosen_reaction = random.choice(reaction_choices)
            await client(SendReactionRequest(
                peer=event.chat_id,
                msg_id=event.id,
                reaction=[ReactionEmoji(emoticon=chosen_reaction)]
            ))
        except Exception as e:
            print(f"⚠ Ошибка при добавлении реакции: {e}")

# ✅ Запуск бота
async def run_bot(user, all_clients, reply_counter, dialog_started):
    client = TelegramClient(StringSession(user["session"]), user["api_id"], user["api_hash"])
    await client.start()
    print(f"✅ Бот {user['phone']} подключен!")

    bot_prompt = bot_profiles[user["chat_id"]]

    @client.on(events.NewMessage(chats=GROUP_ID))
    async def handler(event):
        if event.out:
            return  # Бот не отвечает сам себе

        sender_id = event.sender_id
        message_text = event.text.strip()

        # ✅ ПОМЕЧАЕМ СООБЩЕНИЕ КАК ПРОЧИТАННОЕ
        await client.send_read_acknowledge(event.chat_id, max_id=event.id)


        # ✅ Если пишет OWNER_ID, боты начинают беседу
        if sender_id == OWNER_ID and not dialog_started[0]:
            dialog_started[0] = True
            await send_typing_action(client, event.chat_id, duration=random.randint(10, 60))
            response_prompt = f"{group_prompt}\n{bot_prompt}\nОтветь на сообщение и начни беседу."
            message = await generate_message(response_prompt)
            await client.send_message(GROUP_ID, message)

        # ✅ Ответ на реплай пользователя, если бот ещё не отвечал на этот реплай
        if dialog_started[0] and event.is_reply and is_question(message_text):
            replied_message = await event.get_reply_message()
            replied_sender_id = replied_message.sender_id

            if replied_sender_id == user["chat_id"]:
                if replied_message.id not in reply_counter:
                    reply_counter[replied_message.id] = 1
                else:
                    return

                await asyncio.sleep(random.randint(10, 60))
                await send_typing_action(client, event.chat_id, duration=random.randint(10, 60))
                response_prompt = f"{group_prompt}\n{bot_prompt}\nОтветь на вопрос пользователя в стиле персонажа."
                message = await generate_message(response_prompt)
                await event.reply(message)

        # ✅ Если один бот написал, второй отвечает (НО НЕ САМ СЕБЕ)
        elif dialog_started[0] and sender_id in [bot["chat_id"] for bot in sessions if bot["chat_id"] != user["chat_id"]]:
            await asyncio.sleep(random.randint(10, 60))
            await send_typing_action(client, event.chat_id, duration=random.randint(10, 60))
            follow_up_prompt = f"{group_prompt}\n{bot_prompt}\nПродолжи беседу."
            follow_up_message = await generate_message(follow_up_prompt)
            await client.send_message(GROUP_ID, follow_up_message)

        # ✅ Лайк (без комментария)
        await send_reaction(client, event)

    all_clients.append(client)
    await client.run_until_disconnected()

# ✅ Запуск всех ботов
async def main():
    all_clients = []
    reply_counter = {}
    dialog_started = [False]  # Диалог начинается только после сообщения OWNER_ID
    tasks = [run_bot(user, all_clients, reply_counter, dialog_started) for user in sessions]
    await asyncio.gather(*tasks)

asyncio.run(main())
