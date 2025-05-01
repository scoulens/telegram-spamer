import asyncio
import random
import time
from telethon import TelegramClient, events
from telethon.errors import PeerFloodError, FloodWaitError, AuthRestartError
from telethon.sessions import StringSession  # Или другой тип сессии, если хотите работать с файлом
from telethon.types import User, Channel, Chat

# Импортируем telethon.errors
import telethon.errors

# Замените на свои значения
API_ID = 1234567# Ваш API ID
API_HASH = ''  # Ваш API Hash
SESSION_FILE = 'my_session.session'  # Имя файла для хранения сессии.  Может быть любым,  но должно быть расширение .session
PHONE = '+71234567890'  # Ваш номер телефона в международном формате
BOT_TOKEN = ''  # Токен вашего Telegram бота

MESSAGE = "qwerty"  # Текст сообщения для отправки
MAX_MESSAGES_PER_DAY = 50  # Максимальное количество сообщений в день
SLEEP_TIME_ON_FLOOD = 60  # Время ожидания при FloodError (в секундах)
ADMIN_ID = 123456789  # Ваш ID в Telegram.  Найдите свой ID через @userinfobot или аналогичных ботов.
SPAM_BOT_USERNAME = 'SpamBot'  # Имя пользователя SpamBot

# Глобальные переменные для управления ботом
is_running = False
target_entities = []  # Список сущностей, по которым осуществляется спам
spam_task = None  # Задача для спама
main_client = None # Main client saved
bot_client = None # Bot client saved


async def spam_message(client, entity):
    """Отправляет сообщение entity и обрабатывает возможные ошибки."""
    global MESSAGE
    try:
        await client.send_message(entity, MESSAGE)
        print(f"Сообщение отправлено: {entity.id}")
        return True  # Сообщение успешно отправлено
    except PeerFloodError as e:
        print(f"Flood error: {e}. Ожидание {SLEEP_TIME_ON_FLOOD} секунд...")
        await asyncio.sleep(SLEEP_TIME_ON_FLOOD)
        return False  # Сообщение не отправлено, нужно повторить позже
    except FloodWaitError as e:
        print(f"Flood wait error: {e}. Ожидание {e.seconds} секунд...")
        await asyncio.sleep(e.seconds)
        return False  # Сообщение не отправлено, нужно повторить позже
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")
        return False  # Сообщение не отправлено из-за другой ошибки


async def start_spam(client, target_entities):
    global is_running, spam_task
    if is_running:
        return  # Уже запущено
    is_running = True
    print("Запуск спама...")
    messages_sent = 0
    while is_running and messages_sent < MAX_MESSAGES_PER_DAY:
        if not target_entities:
            print("Нет целей для спама. Останавливаем.")
            break
        entity = random.choice(target_entities)
        success = await spam_message(client, entity)

        if success:
            messages_sent += 1
            print(f"Отправлено {messages_sent} сообщений из {MAX_MESSAGES_PER_DAY}.")

        await asyncio.sleep(random.uniform(1, 5))  # Задержка

    is_running = False
    print("Спам завершен.")
    spam_task = None  # Сбрасываем задачу


async def stop_spam(reason="Остановка спама"):
    global is_running, spam_task, main_client, bot_client
    if is_running:
        print("Остановка спама...")
        is_running = False
        if spam_task:
            spam_task.cancel()  # Отмена текущей задачи (если она существует)
            spam_task = None
        print("Спам остановлен.")
        try:
            if bot_client and ADMIN_ID: # Отправляем уведомление через бота, если он доступен
                await bot_client.send_message(ADMIN_ID, reason)
                print("Уведомление отправлено через бота.")
        except Exception as e:
            print(f"Ошибка при отправке уведомления через бота: {e}") # Print error if fails
    else:
        print("Спам не запущен.")


async def main():
    global target_entities, spam_task, main_client, bot_client, MESSAGE
    client = TelegramClient(SESSION_FILE, api_id=API_ID, api_hash=API_HASH, system_version='5.13.1 x64')
    main_client = client  # Сохраняем основной клиент
    bot_client = TelegramClient('bot', API_ID, API_HASH) # Создаем клиента бота

    await client.connect()
    if not await client.is_user_authorized():
        print("Авторизация требуется.")
        try:
            await client.start(phone=PHONE)
        except Exception as e:
            print(f"Ошибка при авторизации: {e}")
            return
        print("Авторизация успешна.")

    print("Успешно авторизован.")

    # Запускаем бота и ждем его запуска
    try:
        await bot_client.start(bot_token=BOT_TOKEN)
        print("Бот Telegram запущен.")
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")
        bot_client = None  # Указываем, что бот-клиент не работает

    dialogs = await client.get_dialogs()
    all_entities = [d.entity for d in dialogs]  # Получаем все диалоги

    # Регистрируем обработчики событий *после* запуска клиента бота
    @bot_client.on(events.NewMessage(pattern='/start', from_users=ADMIN_ID))
    async def start_handler(event):
        await event.reply('Бот запущен. Используйте команды для управления.')

    @bot_client.on(events.NewMessage(pattern='/help', from_users=ADMIN_ID))
    async def help_handler(event):
        help_text = """
        Команды бота:
        /start - Запуск бота
        /help - Помощь
        /contacts - Спам по контактам
        /chats - Спам по чатам (каналам, группам) и контактам (кроме ботов)
        /stop - Остановить спам
        /settext <text> - Установить текст для отправки
        """
        await event.reply(help_text)
    @bot_client.on(events.NewMessage(pattern=r'/settext (.*)', from_users=ADMIN_ID))
    async def settext_handler(event):
        global MESSAGE
        new_text = event.pattern_match.group(1)
        MESSAGE = new_text
        await event.reply(f"Текст для отправки изменен на: {MESSAGE}")

    @bot_client.on(events.NewMessage(pattern='/contacts', from_users=ADMIN_ID))
    async def contacts_handler(event):
        global target_entities, spam_task
        target_entities = [d for d in all_entities if isinstance(d, User)]
        if not target_entities:
            await event.reply("Нет контактов для спама.")
            return
        await event.reply("Начинаем спам по контактам...")
        spam_task = asyncio.create_task(start_spam(client, target_entities))  # Запускаем спам в задаче
        await event.reply(f"Спам запущен по контактам.  Для остановки: /stop")

    @bot_client.on(events.NewMessage(pattern='/chats', from_users=ADMIN_ID))
    async def chats_handler(event):
        global target_entities, spam_task
        target_entities = [
            d for d in all_entities
            if isinstance(d, (User, Channel, Chat)) and not getattr(d.entity, 'bot', False)
        ]
        if not target_entities:
            await event.reply("Нет чатов и контактов для спама.")
            return
        await event.reply("Начинаем спам по чатам (и контактам, кроме ботов)...")
        spam_task = asyncio.create_task(start_spam(client, target_entities))  # Запускаем спам в задаче
        await event.reply(f"Спам запущен по чатам и контактам (кроме ботов).  Для остановки: /stop")

    @bot_client.on(events.NewMessage(pattern='/stop', from_users=ADMIN_ID))
    async def stop_handler(event):
        await stop_spam()
        await event.reply("Спам остановлен.")

    @client.on(events.NewMessage(from_users=SPAM_BOT_USERNAME))  # Обработчик сообщений от SpamBot
    async def spam_bot_handler(event):
        message_text = f"Получено сообщение от SpamBot. Остановка спама... Текст сообщения: {event.text}"
        print(message_text)
        try:
            if bot_client and ADMIN_ID:
                await bot_client.send_message(ADMIN_ID, message_text)
                print("Уведомление отправлено через бота.")
        except Exception as e:
            print(f"Ошибка при отправке уведомления через бота: {e}")
        await stop_spam(reason=message_text) # Передаем сообщение от SpamBot в качестве причины

    # Запускаем бота и ждем отключения (основная программа)
    print("Бот Telegram запущен. Для управления используйте команды.")
    await bot_client.run_until_disconnected()
    print("Бот Telegram отключен.")

    await client.disconnect()
    print("Основной клиент отключен.")


if __name__ == "__main__":
    asyncio.run(main())