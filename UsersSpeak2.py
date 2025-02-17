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

# ✅ Данные юзер-ботов
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

# ✅ Персонажи
bot_profiles = {
    config("BOT1_PHONE"): "Ты человек, который имитирует Дарта Вейдера. Говори как лорд ситхов, используя тёмную сторону силы.",
    config("BOT2_PHONE"): "Ты человек, который имитирует Люка Скайуокера. Говори как джедай, ведущий борьбу против Империи."
}

# ✅ Общая тематика
group_prompt = "Это чат о Звёздных войнах. Боты должны вести естественный диалог."

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

# ✅ Лайки (реакции) от ботов
async def send_reaction(client, event):
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
async def run_bot(user, all_clients):
    client = TelegramClient(StringSession(user["session"]), user["api_id"], user["api_hash"])
    await client.start()
    print(f"✅ Бот {user['phone']} подключен!")

    bot_prompt = bot_profiles[user["phone"]]

    @client.on(events.NewMessage(chats=GROUP_ID))
    async def handler(event):
        if event.out:
            return  # Бот не отвечает сам себе

        sender = await event.get_sender()
        sender_id = event.sender_id
        message_text = event.text.strip()

        # ✅ Если пишет OWNER_ID, боты начинают беседу
        if sender_id == OWNER_ID:
            first_bot, second_bot = sessions  # Чёткий порядок
            if user["phone"] == first_bot["phone"]:
                await send_typing_action(client, event.chat_id, duration=random.randint(5, 10))
                response_prompt = f"{group_prompt}\n{bot_prompt}\nОтветь на сообщение и начни беседу."
                message = await generate_message(response_prompt)
                await client.send_message(GROUP_ID, message)

                # ✅ Второй бот обязательно отвечает
                await asyncio.sleep(random.randint(10, 30))
                second_client = all_clients[1] if all_clients[0] == client else all_clients[0]
                await send_typing_action(second_client, event.chat_id, duration=random.randint(5, 10))
                follow_up_prompt = f"{group_prompt}\n{bot_profiles[second_bot['phone']]}\nПродолжи беседу."
                follow_up_message = await generate_message(follow_up_prompt)
                await second_client.send_message(GROUP_ID, follow_up_message)

        # ✅ Если один бот написал, второй отвечает
        elif sender_id in [bot["api_id"] for bot in sessions if bot["phone"] != user["phone"]]:
            await asyncio.sleep(random.randint(30, 60))
            await send_typing_action(client, event.chat_id, duration=random.randint(5, 10))
            follow_up_prompt = f"{group_prompt}\n{bot_prompt}\nПродолжи беседу."
            follow_up_message = await generate_message(follow_up_prompt)
            await client.send_message(GROUP_ID, follow_up_message)

        # ✅ Лайк + сообщение
        await send_reaction(client, event)
        await asyncio.sleep(random.randint(10, 30))  # Интервал перед ответом
        await send_typing_action(client, event.chat_id, duration=random.randint(5, 10))
        comment_prompt = f"{group_prompt}\n{bot_prompt}\nНапиши короткий комментарий в стиле персонажа."
        comment_message = await generate_message(comment_prompt)
        await client.send_message(GROUP_ID, comment_message)

    all_clients.append(client)
    await client.run_until_disconnected()

# ✅ Запуск всех ботов
async def main():
    all_clients = []
    tasks = [run_bot(user, all_clients) for user in sessions]
    await asyncio.gather(*tasks)

asyncio.run(main())
