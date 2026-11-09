# YouTube Telegram Bot

A Telegram bot that downloads a YouTube video at a selected quality and sends it
back to the chat.

## Setup

1. Create a Telegram bot with [BotFather](https://t.me/BotFather) and copy its
   token.
2. Create and activate a Python virtual environment:

   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:

   ```sh
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project directory:

   ```dotenv
   BOT_TOKEN=your_telegram_bot_token
   ```

5. Start the bot:

   ```sh
   python bot.py
   ```

Keep `.env` private; it is excluded from Git.
