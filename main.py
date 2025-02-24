import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes # Sudah disesuaikan filters
import google.generativeai as genai
import sqlite3
import time
import re
import os
from PIL import Image
from aiohttp import web
import asyncio

# --- 1. Setup and API Keys ---

# Securely load your API keys from environment variables (recommended)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    print("Error: TELEGRAM_BOT_TOKEN atau GEMINI_API_KEY belum diatur di environment variables!")
    exit()

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash') # Using Gemini 2.0

# --- 2. Variabel Mode Bot ---
BOT_MODE = "pedas" # Mode default bot: "pedas" (roast polos)

# --- 4. Fungsi Database Setup & Create Table --- # <----- FUNGSI DATABASE SETUP BARU!
DATABASE_FILE = 'data/users.db'  # Lokasi file database

def create_database_and_table():
    """Creates the database and the users table if they don't exist."""
    conn = None  # Inisialisasi conn di luar blok try

    try:
        conn = sqlite3.connect(DATABASE_FILE) # Koneksi ke database (atau buat file kalo belum ada)
        cursor = conn.cursor()

        # Buat tabel users kalo belum ada
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                join_time TEXT,
                usage_count INTEGER DEFAULT 0,
                image_usage_count INTEGER DEFAULT 0
            )
        """)
        conn.commit() # Simpan perubahan database

        # Tambah kolom image_usage_count jika belum ada (untuk update database yang sudah ada)
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN image_usage_count INTEGER DEFAULT 0")
            conn.commit()
            print("Kolom 'image_usage_count' berhasil ditambahkan ke tabel 'users'.")
        except sqlite3.OperationalError:
            print("Kolom 'image_usage_count' sudah ada di tabel 'users'.")

        print("Database dan tabel 'users' berhasil dibuat/terhubung.") # Log success

    except sqlite3.Error as e:
        print(f"Error membuat database atau tabel: {e}") # Log error

    finally:
        if conn:
            conn.close()

def add_user_to_database(user):
    """Adds a new user to the database if they don't already exist."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Cek apakah user_id udah ada di database
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
        existing_user = cursor.fetchone()

        if existing_user:
            print(f"User ID {user.id} sudah terdaftar di database.") # Log kalo user udah ada
            return False # Balikin False, menandakan user sudah ada

        else: # Kalo user_id belum ada, tambahin user baru
            join_time = time.strftime('%Y-%m-%dT%H:%M:%S') # Format waktu join: YYYY-MM-DDTHH:MM:SS (ISO 8601)
            cursor.execute("""
                INSERT INTO users (user_id, username, join_time)
                VALUES (?, ?, ?)
            """, (user.id, user.username, join_time)) # Tambah user baru
            conn.commit()
            print(f"User baru {user.username} (ID: {user.id}) berhasil ditambahkan ke database.") # Log user baru
            return True # Balikin True, menandakan user berhasil ditambahkan

    except sqlite3.Error as e:
        print(f"Error menambahkan user ke database: {e}")
        return False # Balikin False kalo error

    finally:
        if conn:
            conn.close()

def increment_usage_count(user_id):
    """Increments the usage_count for a given user_id in the database."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Increment usage_count user
        cursor.execute("""
            UPDATE users
            SET usage_count = usage_count + 1
            WHERE user_id = ?
        """, (user_id,)) # Update usage_count berdasarkan user_id
        conn.commit()
        print(f"Usage count for User ID {user_id} berhasil diincrement.") # Log success increment
        return True # Balikin True kalo sukses increment

    except sqlite3.Error as e:
        print(f"Error increment usage count for User ID {user_id}: {e}") # Log error increment
        return False # Balikin False kalo error

    finally:
        if conn:
            conn.close()

def increment_image_usage_count(user_id):
    """Increments the image_usage_count for a given user_id in the database."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Increment image_usage_count user
        cursor.execute("""
            UPDATE users
            SET image_usage_count = image_usage_count + 1
            WHERE user_id = ?
        """, (user_id,)) # Update image_usage_count berdasarkan user_id
        conn.commit()
        print(f"Image usage count for User ID {user_id} berhasil diincrement.") # Log success increment
        return True # Balikin True kalo sukses increment

    except sqlite3.Error as e:
        print(f"Error increment image usage count for User ID {user_id}: {e}") # Log error increment
        return False # Balikin False kalo error

    finally:
        if conn:
            conn.close()

def get_user_account_data(user_id):
    """Retrieves user account data (username, usage_count, image_usage_count) from the database."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Ambil data user berdasarkan user_id
        cursor.execute("""
            SELECT username, usage_count, image_usage_count
            FROM users
            WHERE user_id = ?
        """, (user_id,)) # Ambil username, usage_count, image_usage_count

        user_data = cursor.fetchone() # Ambil satu baris hasil query

        if user_data:
            username, usage_count, image_usage_count = user_data # Unpack data user
            return { # Balikin data user dalam bentuk dictionary
                "username": username,
                "usage_count": usage_count,
                "image_usage_count": image_usage_count
            }
        else:
            return None # User tidak ditemukan

    except sqlite3.Error as e:
        print(f"Error mengambil data user dari database: {e}")
        return None # Error ambil data

    finally:
        if conn:
            conn.close()

# --- 5. Command Handlers ---

async def start(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user = update.effective_user

    user_added = add_user_to_database(user) # <----- PANGGIL add_user_to_database()

    # Bahasa Jaksel version of the start message - DENGAN DESKRIPSI MODE!
    await update.message.reply_markdown_v2(
        fr"""Hai {user.mention_markdown_v2()} 👋\! Gue Bot Roast Copywriting nih ceritanya\. Kirimin aja copywriting lo, nanti gue kasih *masukan membangun*\.\.\. atau mungkin gue roast aja sekalian 🔥 biar seru\.

*Mode Bot:*
Saat ini gue lagi di mode *Roast Pedas* \(default\), yang artinya gue bakal roast copywriting lo sebegala rupa tanpa ampun, fokusnya buat hiburan aja 😂\.

Kalo lo pengen masukan yang lebih *berfaedah* \(tetep di\-roast dikit sih 😜\), lo bisa ganti mode gue ke *Roast Berfaedah* dengan perintah:  `/mode_solusi`

Gue juga bisa roasting gambar/desain lo\!

Buat balik lagi ke mode awal *Roast Pedas*, pake perintah: `/mode_pedas`

Udah siap di\-roast? Kirim copywriting lo sekarang\!""",
    )

async def myaccount(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None: # <----- FUNGSI COMMAND HANDLER /MYACCOUNT BARU!
    """Sends user account information (usage stats)."""
    user = update.effective_user
    user_id = user.id

    account_data = get_user_account_data(user_id) # Ambil data akun user dari database

    if account_data:
        username = account_data["username"]
        usage_count = account_data["usage_count"]
        image_usage_count = account_data["image_usage_count"]

        myaccount_text = fr"""
👤 *Hi, {username}* 👤

📊 *Statistik Penggunaan Bot* 📊
- Roast Teks Copywriting: *{usage_count} kali*
- Roast Gambar Copywriting: *{image_usage_count} kali*

🔥 Semangat jadi korban roasting! 🔥
        """
        await update.message.reply_markdown(myaccount_text) # Kirim info akun ke user
    else:
        await update.message.reply_text("Waduh, data akun kamu nggak ketemu di database! 😫 Coba /start dulu ya, atau mungkin ada error di database.") # Error kalo data user ga ketemu

async def mode_pedas(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sets the bot mode to 'pedas' (pure roast)."""
    global BOT_MODE # Gunakan variabel global BOT_MODE
    BOT_MODE = "pedas"
    await update.message.reply_text("Oke! Mode bot sekarang di <strong>Roast Pedas</strong> 🔥 siap nyinyir abis-abisan! Kirimin copywriting lo, siap-siap di-roast tanpa ampun! 😂", parse_mode=telegram.constants.ParseMode.HTML)

async def mode_solusi(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sets the bot mode to 'solusi' (roast with solutions)."""
    global BOT_MODE # Gunakan variabel global BOT_MODE
    BOT_MODE = "solusi"
    await update.message.reply_text("Sip! Mode bot ganti ke <strong>Roast Berfaedah</strong> 👍. Gue bakal tetep roast copywriting lo, tapi gue kasih juga masukan yang <strong>berfaedah</strong> dikit. Kirim copywriting lo, mari kita bedah! 😎", parse_mode=telegram.constants.ParseMode.HTML)

async def about(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None: # <----- FUNGSI COMMAND HANDLER /ABOUT BARU!
    """Sends the about message with bot description and donation link."""
    about_text = fr"""
Hai gaes! 👋 Gue adalah bot Telegram yang siap ngeroast copywriting lo sampe gosong! 🔥

Bot ini gue bikin buat hiburan semata ya, jangan baper kalo roast-nya kepedesan!

Nih kreator-nya, @navrex0 🔥

Kalo lo suka sama roast-roast yang pedas ini, dan pengen gue terus semangat ngembangin bot ini, boleh banget nih kasih dukungan ke link Trakteer gue di bawah ini 👇👇

[https://trakteer.id/ervankurniawan41/tip]

Makasih banyak ya buat supportnya! 🙏 Semoga skill copywriting lo makin mantep setelah di-roast sama gue dan rejeki lo lancar! 🔥🔥🔥
    """
    await update.message.reply_html(about_text, disable_web_page_preview=True) # <---- KIRIM PESAN /ABOUT PAKE MARKDOWNV2



# --- 4. Message Handler (Core Logic) ---

async def roast_copywriting(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Roasts the user-submitted copywriting using Gemini, based on BOT_MODE."""
    # --- Chat Action "Typing" ---
    await context.bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.constants.ChatAction.TYPING) # Kirim chat action "typing"

    user_copywriting = update.message.text

    if not user_copywriting:
        await update.message.reply_text("Eh, kirimin dulu dong teks copywriting yang mau di-roast!") # Bahasa Jaksel
        return

    # --- Kirim Pesan Awal "Diterima" ---
    initial_message = await update.message.reply_text("Copywriting lo udah gue terima nih! jangan kabur lo!") # Kirim pesan awal dan simpan object Message

    if BOT_MODE == "pedas":
        prompt = f"""
        Lo adalah seorang stand up komedi dengan pengalaman lebih dari 10 tahun. Spesialis lo adalah di roasting. Lo paling bisa kalo soal roasting. Ga cuma itu, lo juga ahli dalam copywriting sembari lo jadi stand up komedian. Nah sekarang lo ditugasin buat roasting-in hasil copywriting orang. 
        
        Lo ga perlu mikirin solusi, lo cukup kasih roasting-an sebagai hiburan. Anggep aja lo sekarang lagi di tongkrongan terus ada temen lo nunjukkin copywriting-nya!

        Lo ga usah intro, langsung kasih roasting pake bahasa sehari-hari yang gaul & friendly kayak lo gue gitu, ga usah formal.

        Nih teks copywriting-nya:
        \"{user_copywriting}\"

        lo ga perlu pake format markdown, kasih aja output lo dalam plaintext.
        """
    elif BOT_MODE == "solusi":
        prompt = f"""
        Lo adalah seorang stand up komedi dengan pengalaman lebih dari 10 tahun. Spesialis lo adalah di roasting. Lo paling bisa kalo soal roasting. Ga cuma itu, lo juga ahli dalam copywriting sembari lo jadi stand up komedian. Nah sekarang lo ditugasin buat roasting-in hasil copywriting orang. 

        Karena situasinya lo lagi ditongkrongan sama temen lu yang minta roasting-in copywriting-nya, selain ngasih roasting, lo kasih saran dan solusi juga sekalian ngebuktiin (pamer) skill lo dibidang copywriting yang udah 10 tahun itu.

        Lo ga usah intro, kasih roasting & saran pake bahasa sehari-hari yang gaul & friendly kayak lo gue gitu, ga usah formal.

        Nih teks Copywriting-nya:
        \"{user_copywriting}\"

        lo ga perlu pake format markdown, kasih aja output lo dalam plaintext.
        """
    else: # Mode tidak dikenal (fallback, jaga-jaga error)
        prompt = f"Roast copywriting ini: \"{user_copywriting}\"" # Prompt default sederhana

    # --- RETRY MECHANISM ---
    max_retries = 3 # Maksimal percobaan retry
    retry_delay = 2 # Delay antar retry (detik)
    retry_count = 0

    while retry_count < max_retries:
        retry_count += 1
        print(f"Mencoba panggil Gemini API (percobaan ke-{retry_count})... (Mode: {BOT_MODE})") # Log retry attempt

        try:
            await context.bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.constants.ChatAction.TYPING) # Kirim chat action "typing"
            # --- Edit Pesan Awal Jadi "Sabar ya..." ---
            await context.bot.edit_message_text(
                chat_id=update.message.chat_id,
                message_id=initial_message.message_id, # Gunakan message_id dari pesan awal
                text=f"Wait, bahan lo lagi digoreng master chef pake mode *{BOT_MODE}*! 🔥", # Pesan editan, info mode juga
                parse_mode=telegram.constants.ParseMode.MARKDOWN
            )

            start_time = time.time()
            await context.bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.constants.ChatAction.TYPING) # Kirim chat action "typing"
            response = model.generate_content(prompt)
            end_time = time.time()
            print(f"Waktu panggil Gemini API: {end_time - start_time:.2f} detik (Mode: {BOT_MODE})") # Tambahkan info mode di log
            gemini_roast = response.text

            if gemini_roast:
                await context.bot.delete_message(
                    chat_id=update.message.chat_id,
                    message_id=initial_message.message_id
                )
                # --- INCREMENT USAGE COUNT USER! --- # <----- TAMBAHAN PANGGIL increment_usage_count()
                increment_usage_count(update.effective_user.id) # Increment usage_count user
                await update.message.reply_text(gemini_roast)
            else:
                await update.message.reply_text("Hmm, Gemini kayaknya speechless...  copywriting lo terlalu bagus (atau terlalu parah?)! Coba kirim yang lain deh.") # Bahasa Jaksel

        except Exception as e:
            print(f"Error komunikasi sama Gemini: {e} (Mode: {BOT_MODE})") # Tambahkan info mode di log
            if retry_count < max_retries: # Kalo masih ada kesempatan retry
                await context.bot.edit_message_text( # Edit pesan awal, kasih tau lagi nyoba
                    chat_id=update.message.chat_id,
                    message_id=initial_message.message_id,
                    text=f"Waduh, mesin roasting mode *{BOT_MODE}* kayaknya lagi ngambek dikit... 😪\nGue coba sekali lagi ya... (percobaan ke-{retry_count + 1})" # Pesan editan, info retry
                )
                time.sleep(retry_delay) # Tunggu sebentar sebelum retry
                continue # Lanjut ke awal loop retry lagi

        # --- ROAST CADANGAN KALO ERROR ---
        fallback_roast = f"Waduh, mesin roasting gue lagi error berat nih! 😫\n\nTapi tenang, gue tetep kasih roast spesial buat lo:\n\n\"Hmm, copywriting lo...  unik juga ya. Lain dari yang lain.  Pokoknya... jangan semangat & jangan berkarya!\" 😉\n\nIni roast darurat mode *{BOT_MODE}* ya, lain kali gue roast beneran deh kalo otak gue udah bener. Coba lagi ya!" # Roast cadangan Bahasa Jaksel, info mode juga

        # --- Edit Pesan Awal Jadi Pesan Error (Opsional) ---
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=initial_message.message_id, # Gunakan message_id dari pesan awal
            text=f"Waduh, mesin roasting mode *{BOT_MODE}* lagi ngambek! 😭 Sabar ya, lagi diperbaiki nih...", # Pesan error editan, info mode juga
            parse_mode=telegram.constants.ParseMode.MARKDOWN_V2
        )
        await update.message.reply_text(fallback_roast)
        # --- AKHIR ROAST CADANGAN ---

async def roast_image_copywriting(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Roasts user-submitted image copywriting (IMAGE MESSAGE HANDLER) with Retry Mechanism."""
    user = update.effective_user
    photo = update.message.photo[-1]
    file_id = photo.file_id
    file = await context.bot.get_file(file_id)
    image_path = f"downloads/{file_id}.jpg"
    await file.download_to_drive(image_path)

    await context.bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.constants.ChatAction.TYPING)
    initial_message = await update.message.reply_text("Gambar copywriting lo udah gue terima nih! Bentar ya, lagi gue bedah... 🧐")

    # --- RETRY MECHANISM FOR IMAGE ROASTING ---
    max_retries_image = 3 # Maksimal percobaan retry untuk roast gambar
    retry_delay_image = 2 # Delay antar retry (detik) untuk roast gambar
    retry_count_image = 0

    formatted_roast_image = None # Inisialisasi variabel formatted_roast_image di luar loop retry
    fallback_roast_image = "Waduh, mesin roast gambar gue lagi error berat nih! 😭\n\nTapi tenang, gue tetep kasih roast spesial buat gambar lo:\n\n\"Hmm, gambar copywriting lo...  menarik juga ya.  Visualnya...  lain dari yang lain.  Pokoknya... jangan semangat & jangan berkarya!\" 😉\n\nIni roast darurat gambar ya, lain kali gue roast beneran deh kalo otak gue udah bener. Coba lagi ya!" # Roast cadangan gambar (Inisialisasi di luar loop retry)


    while retry_count_image < max_retries_image:
        retry_count_image += 1
        print(f"Mencoba panggil Gemini API OCR (percobaan ke-{retry_count_image})... (Mode: {BOT_MODE})") # Log retry attempt buat OCR gambar

        try: # --- TRY BLOCK BUAT OCR GAMBAR (DI DALAM LOOP RETRY!) ---
            # --- EKSTRAKSI TEKS DARI GAMBAR PAKE GEMINI API OCR! ---
            img = Image.open(image_path)
            vision_model = genai.GenerativeModel('gemini-2.0-flash')
            # image_prompt = "Tolong ekstrak teks yang ada di gambar ini. Kalo ada teks copywriting atau pesan marketing, sebutkan juga."
            image_prompt = "Lo itu seorang yang Graphic Designer dan Copywriter dengan pengalaman lebih dari 10 tahun. Lo juga orang yang sering nge-roasting desain dan copywriting yang aneh-aneh dengan gaya lo yang asik, friendly. Ga cuma roasting, lo juga suka ngasih edukasi ke orang-orang gimana benernya. Nah, sekarang gue mau lo roasting gambar ini dari segi visual dan copywriting-nya, straight to the point aja kayak lo lagi nongkrong santuy terus ada temen lo nunjukkin desain dan copywriting dia di gambar itu. Hasil roasting-nya langsung plaintext aja, ga usah pake format markdown"
            response = vision_model.generate_content(
                [image_prompt, img]
            )
            image_ocr_result = response.text

            if image_ocr_result:
                print(f"Hasil OCR Gemini API:\n{image_ocr_result}")

                response_roast_image = image_ocr_result
                gemini_roast_image = response_roast_image

                if gemini_roast_image:
                    formatted_roast_image = gemini_roast_image # Hasil roast Gemini (plaintext, sesuai gaya bot lo)
                    # --- INCREMENT USAGE COUNT USER! ---
                    increment_usage_count(user.id) # Tetap increment usage_count yang lama (untuk roast teks)
                    increment_image_usage_count(user.id) # <----- INCREMENT IMAGE USAGE COUNT!
                    # --- INCREMENT USAGE COUNT USER! ---
                    increment_usage_count(user.id)
                    await context.bot.delete_message(
                        chat_id=update.message.chat_id,
                        message_id=initial_message.message_id
                    )
                    await update.message.reply_text(formatted_roast_image)
                    break  # <----- BREAK LOOP RETRY KALO SUKSES ROAST GAMBAR!

                else: # Gemini gagal kasih roast gambar (response kosong, tapi bukan error API)
                    await update.message.reply_text("Waduh, Gemini kayaknya speechless ngeroast gambar copywriting lo! 🤔 Coba gambar lain deh.")
                    break # <----- BREAK LOOP RETRY, GAK PERLU RETRY KALO ROAST GEMINI KOSONG!

            else: # Gemini gagal OCR gambar (response OCR kosong, tapi bukan error API)
                await update.message.reply_text("Hmm, Gemini gagal fokus baca teks dari gambar lo. 😫 Coba gambar yang lebih jelas atau teksnya jangan terlalu kecil.")
                break # <----- BREAK LOOP RETRY, GAK PERLU RETRY KALO OCR GEMINI KOSONG!


        except Exception as e: # --- CATCH ERROR DI DALAM LOOP RETRY ---
            print(f"Error komunikasi sama Gemini OCR (percobaan ke-{retry_count_image}): {e} (Mode: {BOT_MODE})") # Log error OCR gambar (UPDATE PESAN ERROR LOG!)
            if retry_count_image < max_retries_image: # Kalo masih ada kesempatan retry
                await context.bot.edit_message_text(
                    chat_id=update.message.chat_id,
                    message_id=initial_message.message_id,
                    text=f"Waduh, mesin roast gambar mode *{BOT_MODE}* kayaknya lagi ngambek dikit... 😪\nGue coba sekali lagi ya... (percobaan ke-{retry_count_image + 1})" # Pesan editan, info retry gambar (UPDATE PESAN EDITAN!)
                )
                time.sleep(retry_delay_image) # Tunggu sebentar sebelum retry
                continue # Lanjut ke awal loop retry lagi
            else: # Kalo udah maksimal retry, keluar dari loop (kirim roast cadangan)
                print(f"Semua percobaan retry OCR gambar gagal. Kirim roast cadangan gambar (Mode: {BOT_MODE}).") # Log roast cadangan gambar
                await context.bot.edit_message_text(
                    chat_id=update.message.chat_id,
                    message_id=initial_message.message_id,
                    text="Waduh, mesin roast gambar lagi ngambek! 😭 Sabar ya, lagi diperbaiki nih..." # Pesan error editan gambar (UPDATE PESAN EDITAN ERROR!)
                )
                # fallback_roast_image udah diinisialisasi di luar loop, jadi bisa langsung dipake

        finally: # <----- FINALLY BLOCK (DI DALAM LOOP RETRY, SETELAH TRY-EXCEPT)!
            try:
                os.remove(image_path) # Hapus file gambar yang udah didownload
                print(f"File gambar {image_path} berhasil dihapus.")
            except Exception as e:
                print(f"Error menghapus file gambar {image_path}: {e}")


    # --- KIRIM GAMBAR YANG DI-ROAST + CAPTION (DI LUAR LOOP RETRY, SETELAH FINALLY BLOCK LOOP)! ---
    # PENTING: formatted_roast_image & fallback_roast_image udah diinisialisasi di luar loop, jadi pasti punya nilai (None atau string roast)
    # await update.message.reply_photo(photo=file_id, caption="Nih gambar copywriting lo abis di-roast! 🔥\n\n" + (formatted_roast_image if formatted_roast_image else fallback_roast_image)) # Kirim gambar + caption roast (pake formatted_roast_image kalo ada, fallback_roast_image kalo error)


# --- 5. Error Handler (Optional - Add for better bot stability) ---
async def error_handler(update: ContextTypes.DEFAULT_TYPE, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error in your preferred way (e.g., to a file, database, or logging service)
    print(f"Update {update} caused error {context.error}")
    # Optionally, you can send a message to the user or a developer group if critical errors occur

async def webhook_handler(request: web.Request) -> web.Response: # <---- FUNGSI WEBHOOK HANDLER BARU!
    """Set route /telegram to receive updates."""
    update = telegram.Update.de_json(data=await request.json(), bot=application.bot)
    await application.process_update(update)
    return web.Response()

# --- 6. Main Function ---
async def main() -> None:
    """Start the bot and setup database."""
    create_database_and_table() # <----- PANGGIL FUNGSI CREATE DATABASE DI MAIN()
    global application
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build() # Use Application.builder()

    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("mode_pedas", mode_pedas)) # Tambahkan handler untuk /mode pedas
    application.add_handler(CommandHandler("mode_solusi", mode_solusi)) # Tambahkan handler untuk /mode solusi
    application.add_handler(CommandHandler("tentang", about)) # <----- TAMBAH COMMAND HANDLER /ABOUT DI MAIN()
    application.add_handler(CommandHandler("info_akun", myaccount)) # <----- TAMBAH COMMAND HANDLER /MYACCOUNT DI MAIN()

    # Message Handler (for all text messages that are not commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, roast_copywriting)) # Sudah disesuaikan filters
    application.add_handler(MessageHandler(filters.PHOTO, roast_image_copywriting)) # <----- HANDLER BARU BUAT PESAN GAMBAR! (roast copywriting gambar)

    # Error Handler (optional but recommended)
    application.add_error_handler(error_handler)

    # Start the Bot
    # application.run_polling(allowed_updates=telegram.Update.ALL_TYPES) # Specify allowed_updates for clarity
    
    # --- JALANKAN BOT DENGAN WEBHOOK DI VERCEL! ---
    print("Bot berjalan dalam mode Webhook di Vercel!") # Log info webhook mode
    global app
    app = web.Application() # <----- PAKE web.Application()
    app.router.add_post("/telegram", webhook_handler) # <---- DAFTAR PATH /TELEGRAM BUAT WEBHOOK
    runner = web.AppRunner(app) # <----- PAKE web.AppRunner()
    await runner.setup() # <----- AWAIT runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port=int(os.environ.get("PORT", 8080))) # <----- PAKE web.TCPSite()
    await site.start() # <----- AWAIT site.start()
    await asyncio.Event().wait() # Keep app running


if __name__ == "__main__":
    # main()
    asyncio.run(main())
