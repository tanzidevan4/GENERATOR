# -*- coding: utf-8 -*-
import telebot
import random
import requests
import re
from datetime import datetime
import time
import traceback
import threading

# --- Configuration ---
# আপনার টেলিগ্রাম বট টোকেনটি এখানে যোগ করুন
TELEGRAM_TOKEN = '8335359553:AAELrv53ilDiS6vxU3O4b6hy_6vP8KjiXO0'
if TELEGRAM_TOKEN == 'YOUR_TELEGRAM_BOT_TOKEN':
    print("ত্রুটি: অনুগ্রহ করে main.py ফাইলে আপনার টেলিগ্রাম বট টোকেন যোগ করুন।")
    exit()

BINLIST_API_URL = "https://lookup.binlist.net/"

# বার্তার মোছার সময় সেকেন্ডে নির্ধারণ করুন
DELETION_DELAY_SECONDS = 30

# In-Memory Storage for Started Users
started_users = set()

# --- Telebot Initialization ---
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# --- সমস্ত Helper Functions (অপরিবর্তিত) ---
def calculate_luhn(number_str):
    if not number_str or not number_str.isdigit(): return 0
    digits = [int(d) for d in number_str]; checksum = 0; is_second = False
    for digit in reversed(digits):
        if is_second: doubled = digit * 2; checksum += doubled // 10 + doubled % 10
        else: checksum += digit
        is_second = not is_second
    return (10 - (checksum % 10)) % 10

def is_luhn_valid(card_number_str):
    if not card_number_str or not card_number_str.isdigit(): return False
    n_digits = len(card_number_str); n_sum = 0; is_second = False
    for i in range(n_digits - 1, -1, -1):
        d = int(card_number_str[i])
        if is_second == True: d = d * 2
        n_sum += d // 10; n_sum += d % 10
        is_second = not is_second
    return (n_sum % 10 == 0)

def get_card_brand(card_number):
    if not card_number or not isinstance(card_number, str): return "Unknown"
    num_str = card_number.strip(); length = len(num_str)
    if length < 6: return "Unknown"
    try:
        prefix6 = int(num_str[:6])
        if num_str.startswith(('34', '37')): return "American Express"
        elif 51 <= int(num_str[:2]) <= 55: return "Mastercard"
        elif 222100 <= prefix6 <= 272099: return "Mastercard"
        elif num_str.startswith('4'): return "Visa"
        elif num_str.startswith('6011'): return "Discover"
        elif num_str.startswith('65'): return "Discover"
        elif 644 <= int(num_str[:3]) <= 649: return "Discover"
        elif 352800 <= prefix6 <= 358999: return "JCB"
        elif num_str.startswith(('300','301','302','303','304','305')): return "Diners Club"
        elif num_str.startswith(('36', '38', '39')): return "Diners Club"
    except (ValueError, IndexError): return "Unknown"
    return "Unknown"

def generate_expiry_date(year_input, month_input):
    month_input = 'x' if month_input.lower() == 'rnd' else month_input
    year_input = 'x' if year_input.lower() == 'rnd' else year_input
    month = random.randint(1, 12); year = datetime.now().year + random.randint(2, 6)
    if month_input.isdigit(): m = int(month_input); month = m if 1 <= m <= 12 else month
    if year_input.isdigit():
        y = int(year_input)
        if y > 99: full_y = y
        else: current_yy = datetime.now().year % 100; full_y = 2000 + y if y < (current_yy + 10) else 1900 + y
        current_full_year = datetime.now().year
        if full_y > current_full_year: year = full_y
        elif full_y == current_full_year: year = full_y if month >= datetime.now().month else current_full_year + random.randint(1, 5)
    return f"{month:02d}/{year % 100:02d}"

def generate_cvv(cvv_input, bin_prefix):
    cvv_input = 'x' if cvv_input.lower() in ['rnd', 'xxx'] else cvv_input
    if not bin_prefix or not isinstance(bin_prefix, str): is_amex = False
    else: is_amex = bin_prefix.startswith(('34', '37'))
    required_length = 4 if is_amex else 3; cvv = None
    if cvv_input.isdigit() and len(cvv_input) == required_length: cvv = cvv_input
    if cvv is None: cvv = f"{random.randint(0, 9999):04d}" if required_length == 4 else f"{random.randint(0, 999):03d}"
    return cvv

def get_bin_info(bin_number):
    if not bin_number or not bin_number.isdigit() or len(bin_number) < 6: return {"error": "Invalid BIN format/length."}
    headers = {'Accept-Version': '3'}; url = f"{BINLIST_API_URL}{bin_number}"
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200: return {"success": True, "data": response.json()}
        elif response.status_code == 404: return {"error": "BIN not found."}
        elif response.status_code == 429: return {"error": "Rate limit exceeded."}
        else: return {"error": f"API error ({response.status_code})."}
    except requests.exceptions.Timeout: return {"error": "API timed out."}
    except requests.exceptions.RequestException: return {"error": "Network error."}
    except Exception as e: print(traceback.format_exc()); return {"error": "Unexpected lookup error."}

def generate_card_number(bin_pattern):
    if not bin_pattern: return None
    final_card_number = None; bin_prefix = ""; digits_only_pattern = ""
    for char in bin_pattern:
        if char.isdigit(): bin_prefix += char; digits_only_pattern += char
        elif char.lower() == 'x': bin_prefix += random.choice('0123456789')
        else: return None
    if not digits_only_pattern or len(digits_only_pattern) < 6: return None
    prefix_start = bin_prefix[:6] if len(bin_prefix) >= 6 else bin_prefix
    length = 15 if prefix_start.startswith(('34', '37')) else 16
    current_length = len(bin_prefix); pattern_len = len(bin_pattern); partial_card = None
    if pattern_len > length: return None
    elif pattern_len == length:
        if 'x' not in bin_pattern.lower(): final_card_number = bin_prefix
        else: partial_card = bin_prefix[:length - 1]
    else:
        num_random_digits_to_add = length - current_length - 1
        if num_random_digits_to_add < 0: num_random_digits_to_add = 0
        random_part = ''.join(random.choice('0123456789') for _ in range(num_random_digits_to_add))
        partial_card = bin_prefix + random_part
    if partial_card is not None and final_card_number is None:
        if not partial_card: return None
        check_digit = calculate_luhn(partial_card)
        final_card_number = partial_card + str(check_digit)
    if final_card_number and is_luhn_valid(final_card_number): return final_card_number
    else: return None

# --- Message Deletion Scheduler ---
def schedule_message_deletion(chat_id, message_id, delay_seconds):
    def delete_worker():
        time.sleep(delay_seconds)
        try:
            bot.delete_message(chat_id, message_id)
        except Exception as e:
            print(f"বার্তা মুছতে ব্যর্থ: {e}")
    thread = threading.Thread(target=delete_worker)
    thread.start()

# --- Telebot Command Handlers ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        user_id = message.from_user.id
        start_message = "Welcome to THE CC UX Bot ⚡\nFor See Commands use /help"
        if user_id in started_users:
            sent_message = bot.send_message(message.chat.id, start_message)
            schedule_message_deletion(message.chat.id, sent_message.message_id, DELETION_DELAY_SECONDS)
            schedule_message_deletion(message.chat.id, message.message_id, DELETION_DELAY_SECONDS)
        else:
            started_users.add(user_id)
            bot.send_message(message.chat.id, start_message)
    except Exception as e:
        print(f"Start command error: {e}")

@bot.message_handler(commands=['help'])
def handle_help(message):
    try:
        help_text = ["For Generating CC from BIN Use `/gen` or `.gen` With the BIN", "Example `/gen 123456`", "", "For Checking BIN Details Use `/bin` or `.bin`", "Example `/bin 123456`"]
        help_message_content = "\n".join(help_text)
        sent_message = bot.send_message(message.chat.id, help_message_content, parse_mode='Markdown')
        schedule_message_deletion(message.chat.id, sent_message.message_id, DELETION_DELAY_SECONDS)
        schedule_message_deletion(message.chat.id, message.message_id, DELETION_DELAY_SECONDS)
    except Exception as e:
        print(f"Help command error: {e}")

@bot.message_handler(regexp=r"^[./]gen")
def handle_gen(message):
    try:
        raw_text = message.text.strip()
        command_len = 4 if raw_text.startswith('.gen') else 5
        
        # খালি কমান্ডের জন্য বার্তা
        if len(raw_text.split()) == 1:
            bot.reply_to(message, "Please send BIN to Generate CC\nExample `/gen 123456`")
            return

        processing_message = bot.send_message(message.chat.id, "Prossesing You Request ☑️")
        time.sleep(3)
        
        args_str = raw_text[command_len:].strip()
        bin_pattern = ""
        param_parts = []
        first_sep_index = -1
        
        for i, char in enumerate(args_str):
            if char in [' ', '|', '/']:
                potential_bin = args_str[:i].strip()
                if potential_bin and all(c.isdigit() or c.lower() == 'x' for c in potential_bin):
                    digit_part = ''.join(filter(str.isdigit, potential_bin))
                    if len(digit_part) >= 6:
                        first_sep_index = i
                        break
        
        if first_sep_index != -1:
            bin_pattern = args_str[:first_sep_index].strip()
            remaining_args = args_str[first_sep_index:].strip()
            remaining_args = remaining_args.replace('|', ' ').replace('/', ' ')
            param_parts = [part for part in remaining_args.split(' ') if part]
        else:
            potential_bin = args_str.strip()
            if potential_bin and all(c.isdigit() or c.lower() == 'x' for c in potential_bin):
                digit_part = ''.join(filter(str.isdigit, potential_bin))
                if len(digit_part) >= 6:
                    bin_pattern = potential_bin
                else:
                    bin_pattern = None
            else:
                bin_pattern = None

        final_message = ""
        if not bin_pattern:
            final_message = "❌ Invalid command format or BIN pattern (min 6 digits, only digits/x)."
        elif len(bin_pattern) > 19:
            final_message = "❌ BIN pattern is too long."
        else:
            month_input = param_parts[0] if len(param_parts) > 0 else 'x'
            year_input = param_parts[1] if len(param_parts) > 1 else 'x'
            cvv_input = param_parts[2] if len(param_parts) > 2 else 'x'
            
            generated_cards = []
            amount_to_generate = 10
            display_bin = bin_pattern
            brand_name = "Unknown"
            attempts = 0
            max_attempts = 500
            
            while len(generated_cards) < amount_to_generate and attempts < max_attempts:
                attempts += 1
                card_number = generate_card_number(bin_pattern)
                if card_number:
                    if not generated_cards or brand_name == "Unknown":
                        brand_name = get_card_brand(card_number)
                    
                    concrete_bin_prefix = card_number[:6]
                    expiry_str = generate_expiry_date(year_input, month_input)
                    cvv = generate_cvv(cvv_input, concrete_bin_prefix)
                    
                    try:
                        month_str, year_str = expiry_str.split('/')
                        card_data_str = f"`{card_number}|{month_str}|{year_str}|{cvv}`"
                        if card_data_str not in generated_cards:
                            generated_cards.append(card_data_str)
                    except ValueError:
                        print(f"Warning: Could not parse expiry date '{expiry_str}' for card.")

            if len(generated_cards) == amount_to_generate:
                output_lines = ["CC Generated Successfully ✅", f"Bin Pattern: `{display_bin}`", f"Amount: {len(generated_cards)}", f"Brand: {brand_name}", ""]
                output_lines.extend(generated_cards)
                output_lines.extend(["", "BOT BY U-235 ⚡"])
                final_message = "\n".join(output_lines)
            else:
                final_message = f"❌ Failed to generate {amount_to_generate} valid cards after {max_attempts} attempts."
        
        bot.edit_message_text(final_message, message.chat.id, processing_message.message_id, parse_mode='Markdown')

    except Exception as e:
        print(f"Gen command error: {e}")
        traceback.print_exc()
        bot.reply_to(message, "An error occurred while processing your request.")

@bot.message_handler(regexp=r"^[./]bin")
def handle_bin(message):
    try:
        raw_text = message.text.strip()
        command_len = 4 if raw_text.startswith('.bin') else 5
        
        # খালি কমান্ডের জন্য বার্তা
        if len(raw_text.split()) == 1:
            bot.reply_to(message, "Please send BIN for Check BIN Details\nExample `/bin 123456`")
            return
            
        processing_message = bot.send_message(message.chat.id, "Checking BIN... ⏳")
        time.sleep(5)
        
        args_str = raw_text[command_len:].strip()
        potential_bin_pattern = ""
        bin_digits = ""
        
        for char in args_str:
            if char.isdigit() or char.lower() == 'x':
                potential_bin_pattern += char
            else:
                break
        
        if potential_bin_pattern:
            bin_digits = ''.join(filter(str.isdigit, potential_bin_pattern))

        final_message = ""
        if len(bin_digits) < 6:
            final_message = f"❌ Invalid BIN: '{potential_bin_pattern}'. Needs 6+ digits."
        else:
            lookup_bin = bin_digits[:8]
            original_input_bin_display = potential_bin_pattern
            bin_info_result = get_bin_info(lookup_bin)

            if bin_info_result.get("success"):
                data = bin_info_result.get("data", {})
                scheme = data.get("scheme", "N/A").upper()
                card_type = data.get("type", "N/A").upper()
                level = data.get("brand", "N/A")
                country_data = data.get("country", {})
                country_name = country_data.get("name", "N/A")
                country_emoji = str(country_data.get("emoji", ""))
                country_code = country_data.get("alpha2", "")
                currency = country_data.get("currency", "N/A")
                bank_data = data.get("bank", {})
                bank_name = bank_data.get("name", "N/A")

                output_lines = [f"Bin: `{original_input_bin_display}`", "", f"Brand: {scheme}", f"Type: {card_type}", f"Level: {level}", f"Country: {country_name} {country_emoji} {country_code}", f"Currency: {currency}", f"Bank: {bank_name}", "", "BOT BY U-235 ⚡"]
                final_message = "\n".join(output_lines)
            else:
                final_message = f"❌ {bin_info_result.get('error', 'Unknown lookup error.')}"
        
        bot.edit_message_text(final_message, message.chat.id, processing_message.message_id, parse_mode='Markdown')

    except Exception as e:
        print(f"Bin command error: {e}")
        traceback.print_exc()
        bot.reply_to(message, "An error occurred while processing your request.")

# --- Main Block ---
if __name__ == '__main__':
    print("বট চালু হচ্ছে...")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"বট চালাতে গিয়ে মারাত্মক ত্রুটি: {e}")
        traceback.print_exc()
