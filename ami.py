import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import random
import time
import threading

# ==========================================
# 1. بيانات البوت المخصصة لك (أمين)
# ==========================================
TOKEN = "8871054387:AAF4o6YAsEo1R40WnV2DnzMQbc79hZR7YLk"
OWNER_ID = 8941616026

bot = telebot.TeleBot(TOKEN)

# ==========================================
# 2. نظام بيانات اللعبة
# ==========================================
game = {
    "active":False,
    "group_id":None,
    "creator_id": None,  # 🔒 معرف الشخص الذي بدأ اللعبة حصراً
    "phase": "waiting",  # waiting, night, day
    "round_id": 0,       # رقم الجولة لتتبع الليل والنهار بدقة
    "players": {},       # {user_id: {"name": str, "role": str, "alive": True, "soldier_shield": True, "cultified": False, "stolen_role": None}}
    "night_actions": {
        "mafia_targets": [],
        "cult_target": None,
        "doctor_target": None,
        "police_target": None,
        "spy_target": None,
        "witch_target": None,      # هدف الساحرة (المنع من القدرة)
        "thief_target": None,      # هدف اللص (سرقة الدور واستخدامه)
        "terrorist_target": None
    },
    "votes": {},         # {voter_id: target_id}
    "join_msg_id": None  # تخزين معرف رسالة الانضمام لحذفها لاحقاً
}

# قائمة الأدوار المحدثة بالكامل
ROLE_NAMES = {
    "mafia": "المافيا 🦹‍♂️",
    "spy": "الجاسوس (عين المافيا) 🕵️‍♂️",
    "witch": "الساحرـة 🧙‍♀️",
    "cultist": "الطائفي ⛪",
    "doctor": "الطبيب 💉",
    "police": "الشرطي 👮‍♂️",
    "thief": "اللص 🥷",
    "politician": "السياسي 🏛️",
    "soldier": "الجندي 🪖",
    "terrorist": "الإرهابي 💣",
    "citizen": "المواطن 🧑‍💼"
}

# دالة لعمل منشن لجميع اللاعبين الأحياء
def get_all_players_mention():
    mentions = []
    for uid, p in game["players"].items():
        if p["alive"]:
            mentions.append(f"<a href='tg://user?id={uid}'>{p['name']}</a>")
    return " ".join(mentions)

# دالة لجلب قائمة نصية بأسماء اللاعبين الأحياء حالياً
def get_living_players_text():
    living = [f"🔹 {p['name']}" for p in game["players"].values() if p["alive"]]
    if not living:
        return "لا يوجد لاعبون أحياء!"
    return "\n".join(living)

# ==========================================
# 3. الترحيب والشرح في الخاص
# ==========================================
@bot.message_handler(commands=['start'])
def send_private_welcome(message):
    if message.chat.type == 'private':
        welcome_text = (
            "أهلاً بك في بوت لعبة مافيا 42 الدرامية المعدلة!\n\n"
            "صانع ومطور البوت: أمين 👑\n\n"
            "شرح الأدوار في اللعبة:\n"
            "• المافيا: يتفقون سراً كل ليلة لاغتيال أحد السكان بدم بارد (الجاسوس معهم ويعرفهم).\n"
            "• الجاسوس: عين المافيا في الخفاء، معهم في الفريق ويفوز بفوزهم، وتصله أسماء أعضاء المافيا!\n"
            "• الساحرة: تسحر شخصاً كل ليلة لتمنعه من استخدام قدرته الليلية.\n"
            "• الطائفي: يجذب اللاعبين لطائفته سراً (ولا يستطيع تحويل المافيا أو الجاسوس لصفه).\n"
            "• الطبيب: يختار شخصاً كل ليلة لإسعافه وإنقاذه من مخالب الموت.\n"
            "• الشرطي: يحقق مع لاعب كل ليلة ليكشف هل هو مافيا أم بريء.\n"
            "• اللص: يسرق دور لاعب كل ليلة ليستخدم قدرته بدلاً عنه، وصاحب الدور المسروق يصله خبر سرقته ولن يتمكن من استخدام قدرته.\n"
            "• السياسي: شخصية نافذة، لا يمكن إعدامه أبداً في المحكمة بسبب هيبته.\n"
            "• الجندي: ينجو من الهجوم الأول للمافيا ليلاً بفضل درعه الحصين.\n"
            "• الإرهابي: إذا مت أو تم إعدامك، تفجر قنبلة وتأخذ معك خصماً للقبر!\n"
            "• المواطنون: ينشرون النقاشات في النهار ويوجهون الأصوات لطرد القتلة.\n\n"
            "كيف تلعب؟\n"
            "أضف البوت لمجموعتك، ارفعه مشرفاً (Admin)، واكتب الأمر /mafia لتبدأ اللعبة!"
        )
        bot.reply_to(message, welcome_text)

# ==========================================
# 4. بدء وإيقاف اللعبة في المجموعة (مع تكرار رسالة الانضمام كل 40 ثانية)
# ==========================================
@bot.message_handler(commands=['mafia', 'بدء_مافيا'])
def start_mafia_game(message):
    global game
    if message.chat.type == 'private':
        bot.reply_to(message, "لعبة مافيا 42 تُلعب داخل المجموعات فقط! أضفني إلى مجموعة واكتب /mafia هناك.")
        return

    if game["active"]:
        bot.reply_to(message, "هناك لعبة قائمة بالفعل في هذه المجموعة!")
        return

    game = {
        "active": True,
        "group_id": message.chat.id,
        "creator_id": message.from_user.id,
        "phase": "waiting",
        "round_id": 0,
        "players": {},
        "night_actions": {
            "mafia_targets": [], "cult_target": None, "doctor_target": None,
            "police_target": None, "spy_target": None, "witch_target": None,
            "thief_target": None, "terrorist_target": None
        },
        "votes": {},
        "join_msg_id": None
    }

    send_or_update_join_message()
    threading.Thread(target=join_reminder_loop).start()

def send_or_update_join_message():
    global game
    if not game["active"] or game["phase"] != "waiting":
        return

    players_text = "\n".join([f"🔹 {p['name']}" for p in game["players"].values()]) if game["players"] else "لا يوجد لاعبون منضمون بعد..."
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("انضمام للعبة 🎮", callback_data="join_game"))
    
    bot_username = bot.get_me().username
    markup.add(InlineKeyboardButton("شرح اللعبة (في الخاص)", url=f"https://t.me/{bot_username}?start=help"))
    
    if len(game["players"]) >= 5:
        markup.add(InlineKeyboardButton("بدء اللعبة الآن 🚀", callback_data="start_game_now"))

    msg_text = (
        "🎭 <b>غرفة الانتظار - ملحمة مافيا 42!</b>\n"
        f"(تصميم وتطوير: أمين)\n\n"
        f"<b>المشاركون حتى الآن ({len(game['players'])}/5+):</b>\n{players_text}\n\n"
        "اضغط على زر الانضمام أدناه لدخول الغرفة المظلمة!"
    )

    try:
        if game["join_msg_id"]:
            bot.edit_message_text(msg_text, game["group_id"], game["join_msg_id"], reply_markup=markup, parse_mode="HTML")
        else:
            sent_msg = bot.send_message(game["group_id"], msg_text, reply_markup=markup, parse_mode="HTML")
            game["join_msg_id"] = sent_msg.message_id
    except Exception:
        try:
            sent_msg = bot.send_message(game["group_id"], msg_text, reply_markup=markup, parse_mode="HTML")
            game["join_msg_id"] = sent_msg.message_id
        except Exception:
            pass

def join_reminder_loop():
    global game
    while game["active"] and game["phase"] == "waiting":
        time.sleep(40)  # التكرار كل 40 ثانية كما طلبت
        if not game["active"] or game["phase"] != "waiting":
            break
        send_or_update_join_message()

@bot.message_handler(commands=['stop', 'ايقاف'])
def stop_mafia_game(message):
    global game
    if message.chat.type == 'private':
        return

    if not game["active"]:
        bot.reply_to(message, "لا توجد أي لعبة قائمة حالياً لإيقافها!")
        return

    game["active"] = False
    game["phase"] = "waiting"
    game["players"] = {}
    game["group_id"] = None
    game["creator_id"] = None
    game["join_msg_id"] = None
    
    bot.reply_to(message, "تم إيقاف اللعبة الحالية بنجاح!\nيمكنك بدء لعبة جديدة كتابةً عبر الأمر /mafia.")

@bot.callback_query_handler(func=lambda call: call.data in ["join_game", "start_game_now"])
def handle_registration(call):
    global game
    user_id = call.from_user.id
    name = call.from_user.first_name

    if call.data == "join_game":
        if not game["active"] or game["phase"] != "waiting":
            bot.answer_callback_query(call.id, "التسجيل مغلق حالياً!", show_alert=True)
            return

        if user_id in game["players"]:
            bot.answer_callback_query(call.id, "أنت منضم للعبة بالفعل!", show_alert=True)
            return

        game["players"][user_id] = {"name": name, "role": None, "alive": True, "soldier_shield": True, "cultified": False, "stolen_role": None}
        bot.answer_callback_query(call.id, "تم انضمامك للعبة بنجاح!")
        send_or_update_join_message()

    elif call.data == "start_game_now":
        if user_id != game["creator_id"]:
            bot.answer_callback_query(call.id, "❌ عذراً، صانع اللعبة فقط هو من يمكنه الضغط على زر البدء!", show_alert=True)
            return

        if len(game["players"]) < 5:
            bot.answer_callback_query(call.id, "يجب أن يكون عدد اللاعبين 5 على الأقل!", show_alert=True)
            return
        
        bot.answer_callback_query(call.id, "جاري توزيع الأدوار وسحب الستار وبدء اللعبة!")
        
        try:
            bot.edit_message_text(
                "🔒 <b>تم إغلاق باب التسجيل وبدء اللعبة رسمياً!</b>",
                game["group_id"],
                game["join_msg_id"],
                parse_mode="HTML"
            )
        except Exception:
            pass

        assign_roles_and_start_night()

# ==========================================
# 5. توزيع الأدوار وبدء الليل الدرامي
# ==========================================
def assign_roles_and_start_night():
    global game
    if not game["active"]:
        return

    game["round_id"] += 1
    current_round = game["round_id"]

    game["phase"] = "night"
    game["night_actions"] = {
        "mafia_targets": [], "cult_target": None, "doctor_target": None,
        "police_target": None, "spy_target": None, "witch_target": None,
        "thief_target": None, "terrorist_target": None
    }
    game["votes"] = {}

    for p in game["players"].values():
        p["stolen_role"] = None

    player_ids = list(game["players"].keys())
    
    assigned_check = any(p["role"] is not None for p in game["players"].values())
    if not assigned_check:
        random.shuffle(player_ids)
        total_players = len(player_ids)

        mafia_count = 1
        if total_players >= 10:
            mafia_count = 3
        elif total_players == 9:
            mafia_count = 2

        roles_pool = ["mafia"] * mafia_count
        other_special_roles = ["spy", "witch", "cultist", "doctor", "police", "thief", "politician", "soldier", "terrorist"]
        
        remaining_slots = total_players - len(roles_pool)
        if remaining_slots > 0:
            sampled_specials = random.sample(other_special_roles, min(remaining_slots, len(other_special_roles)))
            roles_pool.extend(sampled_specials)
        
        while len(roles_pool) < total_players:
            roles_pool.append("citizen")
        
        random.shuffle(roles_pool)

        for i, uid in enumerate(player_ids):
            game["players"][uid]["role"] = roles_pool[i]
            game["players"][uid]["soldier_shield"] = True
            game["players"][uid]["cultified"] = False
            game["players"][uid]["stolen_role"] = None

    mentions = get_all_players_mention()
    bot.send_message(
        game["group_id"],
        f"🌑 <b>يسدل الستر - الليلة رقم {current_round}</b> {mentions}\n\n"
        "تنتشر غيوم الظلام فوق المدينة، وتتسلل العصابات في الزوايا المعتمة... أغلقت النوافذ ونام الجميع بحذر.\n"
        "<i>(تم إرسال المهام والأسرار الخفية لكل لاعب عبر الخاص - تصميم وتطوير: أمين)</i>\n"
        "⏳ أمامهـم 60 ثانية لاتخاذ قراراتهم المصيرية في الخفاء!",
        parse_mode="HTML"
    )

    for uid, p_data in game["players"].items():
        if not p_data["alive"]:
            continue
        
        role = p_data["role"]
        markup = InlineKeyboardMarkup()
        
        for target_id, t_data in game["players"].items():
            if t_data["alive"] and target_id != uid:
                markup.add(InlineKeyboardButton(f"👤 {t_data['name']}", callback_data=f"night_{role}_{target_id}"))

        try:
            if role == "mafia":
                partners = [p['name'] for u, p in game["players"].items() if p["role"] in ["mafia", "spy"] and u != uid and p["alive"]]
                partner_msg = f"\nشركاؤك في العصابة والجاسوس: {', '.join(partners)}" if partners else "\nأنت العضو الوحيد المتبقي في المافيا!"
                bot.send_message(uid, f"🦹‍♂️ أنت ضمن عصابة المافيا!{partner_msg}\n\nاختر فريستك التالية لتصفيتها بدم بارد الليلة:", reply_markup=markup)
            elif role == "spy":
                mafia_bosses = [p['name'] for u, p in game["players"].items() if p["role"] in ["mafia", "spy"] and u != uid and p["alive"]]
                boss_msg = f"\nأعضاء فريق المافيا والجاسوسيون معك: {', '.join(mafia_bosses)}" if mafia_bosses else "\nلا يوجد أعضاء مافيا آخرون أحياء حالياً!"
                bot.send_message(uid, f"🕵️‍♂️ أنت **الجاسوس (عين المافيا)**! تتبع فريق المافيا وتفوز بفوزهم.{boss_msg}\n\nاختر شخصاً للتجسس على دوره الحقيقي هذه الليلة:", reply_markup=markup)
            elif role == "witch":
                witch_markup = InlineKeyboardMarkup()
                for target_id, t_data in game["players"].items():
                    if t_data["alive"]:
                        witch_markup.add(InlineKeyboardButton(f"👤 {t_data['name']}", callback_data=f"night_witch_{target_id}"))
                bot.send_message(uid, "🧙‍♀️ أنت الساحرة المرعبة!\nتستطيعين كل ليلة اختيار شخص لسحره ومنعه من استخدام قدرته طوال الليل. اخترتي هدفك الليلة:", reply_markup=witch_markup)
            elif role == "cultist":
                bot.send_message(uid, "⛪ أنت الطائفي!\nاختر الشخص الذي تريد جذبه لطائفتك المظلمة هذه الليلة (يبقى بدوره لكنه يصبح تابعاً لك - تذكر: لا يمكنك تحويل المافيا أو الجاسوس):", reply_markup=markup)
            elif role == "doctor":
                doc_markup = InlineKeyboardMarkup()
                for target_id, t_data in game["players"].items():
                    if t_data["alive"]:
                        doc_markup.add(InlineKeyboardButton(f"👤 {t_data['name']}", callback_data=f"night_doctor_{target_id}"))
                bot.send_message(uid, "💉 أنت الطبيب المنقذ!\nاختر الشخص الذي ستسهر على حمايته وإسعافه من الموت الليلة:", reply_markup=doc_markup)
            elif role == "police":
                bot.send_message(uid, "👮‍♂️ أنت الشرطي السري!\nاختر مشتبهاً به لتكشف حقيقته هذه الليلة:", reply_markup=markup)
            elif role == "thief":
                bot.send_message(uid, "🪖🔍 🥷 أنت اللص المحترف!\nاختر لاعباً لسرقة دوره هذه الليلة واستخدام قدرته الخاصة بدلاً عنه:", reply_markup=markup)
            elif role == "politician":
                bot.send_message(uid, "🏛️ أنت السياسي النافذ!\nتجلس في قصرك بثقة، محصناً بهيبتك وقوتك ضد غضب المحكمة. نم قرير العين.")
            elif role == "soldier":
                bot.send_message(uid, "🪖 أنت الجندي الباسل!\nتحمل درعاً فولاذياً يحميك من رصاصة المافيا الأولى. نم بسلام واستعد للصباح.")
            elif role == "terrorist":
                bot.send_message(uid, "💣 أنت الإرهابي الخطير!\nضع قنبلتك الموقوتة واقترب من هدفك الاحتياطي؛ لو مت اليوم ستأخذه معك للجحيم:", reply_markup=markup)
            elif role == "citizen":
                bot.send_message(uid, "🧑‍💼 أنت مواطن بريء... تحاول النجاة بروحتك في مدينة لا تعرف الأمان. انتظر شروق الشمس...")
        except Exception as e:
            print(f"Error sending DM to {uid}: {e}")

    threading.Thread(target=process_night_results, args=(current_round,)).start()

# ==========================================
# 6. معالجة تفاعلات الليل الدرامية
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("night_"))
def handle_night_buttons(call):
    global game
    if game["phase"] != "night":
        bot.answer_callback_query(call.id, "لقد انتهى وقت الظلام وسطع النور!", show_alert=True)
        return

    user_id = call.from_user.id
    
    if game["night_actions"]["witch_target"] == user_id:
        bot.answer_callback_query(call.id, "❌ أنت مسحور من الساحرة ولا يمكنك استخدام قدرتك الليلة!", show_alert=True)
        try:
            bot.send_message(user_id, "🔮 لقد ألق تعويذة سحرية عليك من قِبل **الساحرة** هذا المساء! شلت قواك تماماً ولم تستطع تنفيذ مهاراتك.")
        except Exception:
            pass
        return

    parts = call.data.split("_")
    role = parts[1]
    target_id = int(parts[2])
    
    if target_id not in game["players"] or not game["players"][target_id]["alive"]:
        bot.answer_callback_query(call.id, "هذا الهدف غير متاح أو فارق الحياة!", show_alert=True)
        return

    target_name = game["players"][target_id]["name"]

    # فحص دور اللص المسروق إن وجد
    effective_role = role
    if role == "thief":
        stolen_target_role = game["players"][target_id]["role"]
        game["players"][user_id]["stolen_role"] = stolen_target_role
        effective_role = stolen_target_role
        
        # إعلام الشخص الذي سرقته بأنه تم سرقته ولن تستطيع استخدام قدرته هاته الليلة
        try:
            bot.send_message(
                target_id,
                "🥷 <b>تسلل اللص إلى جيبك في منتصف الليل!</b>\n"
                "لقد تمت سرقة دورك وقدرتك الخاصة هاته الليلة، ولن تتمكن من استخدامها الآن!"
            )
        except Exception:
            pass

    if effective_role == "mafia":
        if target_id not in game["night_actions"]["mafia_targets"]:
            game["night_actions"]["mafia_targets"].append(target_id)
        bot.answer_callback_query(call.id, f"تم تحديد الضحية: {target_name}")
        try:
            bot.edit_message_text(f"🎯 لقد صوّبت سلاحك نحو: <b>{target_name}</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        except Exception:
            pass
    elif effective_role == "spy":
        game["night_actions"]["spy_target"] = target_id
        actual_role = ROLE_NAMES[game["players"][target_id]["role"]]
        bot.answer_callback_query(call.id, "تم كشف الدور!")
        try:
            bot.edit_message_text(f"🕵️‍♂️ بوصفك جاسوساً، راقبت {target_name} وعرفت أن دوره الحقيقي هو: <b>{actual_role}</b> (أخبر عصابة المافيا بذلك!)", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        except Exception:
            pass
    elif effective_role == "witch":
        game["night_actions"]["witch_target"] = target_id
        bot.answer_callback_query(call.id, f"تم سحر اللاعب {target_name} بنجاح!")
        try:
            bot.edit_message_text(f"🧙‍♀️ ألقيت تعويذتك المظلمة وشللت قدرة اللاعب: <b>{target_name}</b> هذه الليلة!", call.message.chat.id, call.message.message_id, parse_mode="HTML")
            bot.send_message(target_id, "⚠️ لقد استيقظت اليوم وتشعر بثقل غريب وسحر يمنعك من استخدام أي قدرة خاصة طوال هذه الليلة!")
        except Exception:
            pass
    elif effective_role == "cultist":
        game["night_actions"]["cult_target"] = target_id
        target_role = game["players"][target_id]["role"]
        # الطائفي لا يستطيع تحويل المافيا أو الجاسوس لصفه
        if target_role in ["mafia", "spy"]:
            bot.answer_callback_query(call.id, "فشل التحويل: الهدف ليس من المواطنين!", show_alert=True)
            try:
                bot.edit_message_text(f"⛪ فشلت محاولة جذب <b>{target_name}</b> لطائفتك.. لأن هذا الشخص ينتمي للمافيا أو الجاسوسية ولا يمكن ضمه!", call.message.chat.id, call.message.message_id, parse_mode="HTML")
            except Exception:
                pass
            game["night_actions"]["cult_target"] = None
        else:
            bot.answer_callback_query(call.id, f"تمت محاولة جذب {target_name} لطائفتك!")
            try:
                bot.edit_message_text(f"⛪ زرعت أفكار طائفتك في عقل: <b>{target_name}</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
            except Exception:
                pass
    elif effective_role == "doctor":
        game["night_actions"]["doctor_target"] = target_id
        bot.answer_callback_query(call.id, f"أنت تحرس {target_name}!")
        try:
            bot.edit_message_text(f"💉 أقمت درعاً طبياً حول المريض: <b>{target_name}</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        except Exception:
            pass
    elif effective_role == "police":
        game["night_actions"]["police_target"] = target_id
        target_role = game["players"][target_id]["role"]
        is_mafia_side = target_role in ["mafia", "spy"]
        res = "ينتمي لعصابة المافيا والجاسوسية! ⚠️" if is_mafia_side else "بريء ولا شائبة عليه. ✅"
        bot.answer_callback_query(call.id, "اكتشفت الحقيقة!")
        try:
            bot.edit_message_text(f"🔍 تقرير الشرطة عن {target_name}: إنه {res}", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        except Exception:
            pass
    elif effective_role == "thief":
        # إذا سرق اللص لصاً آخر
        bot.answer_callback_query(call.id, f"لقد سرقت دور {target_name} ({ROLE_NAMES.get(game['players'][target_id]['role'], 'مواطن')})!")
        try:
            bot.edit_message_text(f"🥷 نجحت في سرقة دور اللاعب <b>{target_name}</b> وهو: <b>{ROLE_NAMES.get(game['players'][target_id]['role'], 'مواطن')}</b> واستخدمته ليلتك!", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        except Exception:
            pass
    elif role == "terrorist":
        game["night_actions"]["terrorist_target"] = target_id
        bot.answer_callback_query(call.id, f"ربطت قنبلتك بـ {target_name}!")
        try:
            bot.edit_message_text(f"💣 وضعت صاعق التفجير الفوري ليكون هدفك عند الموت: <b>{target_name}</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        except Exception:
            pass

# ==========================================
# 7. نتائج الليل ودراما الشروق
# ==========================================
def process_night_results(target_round):
    time.sleep(60)
    global game
    if not game["active"] or game["round_id"] != target_round or game["phase"] != "night":
        return

    try:
        game["phase"] = "day"
        game["votes"] = {}
        mafia_targets = game["night_actions"]["mafia_targets"]
        doctor_target = game["night_actions"]["doctor_target"]
        cult_target = game["night_actions"]["cult_target"]

        killed_user = None
        soldier_survived = False
        doctor_saved = False

        # معالجة تحويل الطائفي
        if cult_target and game["players"][cult_target]["alive"]:
            target_role = game["players"][cult_target]["role"]
            if target_role not in ["mafia", "spy", "cultist"]:
                game["players"][cult_target]["cultified"] = True
                try:
                    bot.send_message(
                        cult_target,
                        "⛪ <b>تسللت أفكار الطائفي المظلمة إلى عقلك في وضح الظلام!</b>\n"
                        "لقد أصبحت <b>تابعاً للطائفة</b> رسمياً، ولكنك <b>تحتفظ بدورك وقدرتك بالكامل</b>.. وستفوز مع الطائفي إذا نجحوا بالهيمنة!"
                    )
                except Exception:
                    pass

        if mafia_targets:
            target_to_kill = mafia_targets[0]
            
            if target_to_kill == doctor_target:
                doctor_saved = True
                killed_user = None
            elif game["players"][target_to_kill]["role"] == "soldier" and game["players"][target_to_kill]["soldier_shield"]:
                game["players"][target_to_kill]["soldier_shield"] = False
                soldier_survived = True
                killed_user = None
            else:
                killed_user = target_to_kill
                game["players"][killed_user]["alive"] = False

        mentions = get_all_players_mention()
        msg = f"🌅 <b>تتكسر عتمة الليل - اشراقة النهار للجولة رقم {target_round}</b> {mentions}\n\n"
        
        if doctor_saved:
            msg += f"💉 <b>بطولة معطف الأبيض!</b> تسللت المافيا في الظلام وهاجمت اللاعب <b>{game['players'][doctor_target]['name']}</b>، لكن معجزة الطبيب تدخلت في آخر ثانية وقامت بإسعافه وإنقاذه من موت محتم! لا توجد خسائر بشرية بسبب الطبيب الليلة! ✨\n\n"
        elif soldier_survived:
            msg += "🛡️ <b>صوت انفجار رصاصة واختراق درع!</b> هجمت المافيا بوحشية على الجندي الباسل، لكن درعه الفولاذي تصدى للهجمة الأولى وخرج سالمًا يفض الشباك! لم يمت أحد الليلة بفضل درع الجندي! 🪖\n\n"
        elif killed_user:
            victim_name = game["players"][killed_user]["name"]
            victim_role_key = game["players"][killed_user]["role"]
            victim_role_name = ROLE_NAMES[victim_role_key]
            
            msg += f"⚰️ <b>فاجعة صباحية دامية!</b> عثر السكان على جثة اللاعب <b>{victim_name}</b> هامدة وسط الدماء بعد أن بطشت به المافيا بلا رحمة في وضح الليل...\n"
            msg += f"📌 <b>كشف الهوية:</b> لقد تبين بعد فحص جثته أن دوره الحقيقي كان: <b>{victim_role_name}</b>!\n\n"
            
            if victim_role_key == "terrorist":
                t_target = game["night_actions"]["terrorist_target"]
                if t_target and game["players"][t_target]["alive"]:
                    game["players"][t_target]["alive"] = False
                    t_name = game["players"][t_target]["name"]
                    t_role_name = ROLE_NAMES[game["players"][t_target]["role"]]
                    msg += f"💥 <b>جحيم الموت المفاجئ!</b> لحظة أن لفظ الإرهابي (<b>{victim_name}</b>) أنفاسه الأخيرة، ضغط على زر التفجير الأخير ليأخذ معه إلى القبر اللاعب <b>{t_name}</b>!\n"
                    msg += f"📌 <b>سقوط مزدوج:</b> لقد كان دور المرافق المنفجر معكوساً كـ: <b>{t_role_name}</b>!\n\n"
        else:
            msg += "🕊️ هبت نسائم الصباح بسلام تام، لم يسمع أي صوت رصاص ولم يسقط أي ضحية في هذه الليلة الهادئة.\n\n"

        living_list_text = get_living_players_text()
        msg += f"📋 <b>قائمة الناجين الأحياء حالياً:</b>\n{living_list_text}\n\n"

        if check_game_over():
            return

        msg += "⚖️ <b>ساعات النقاش والمحاكمة قد بدأت!</b>\nفندوا الآراء واكشفوا الخونة بينكم، ثم اضغطوا أسفله للتصويت على إعدام المشتبه به (أمامكم 120 ثانية):\n"
        
        markup = InlineKeyboardMarkup()
        for uid, p in game["players"].items():
            if p["alive"]:
                markup.add(InlineKeyboardButton(f"⚖️ إعدام {p['name']}", callback_data=f"vote_{uid}"))

        bot.send_message(game["group_id"], msg, reply_markup=markup, parse_mode="HTML")

        threading.Thread(target=process_day_timer, args=(target_round,)).start()
    except Exception as e:
        print(f"Error in process_night_results: {e}")

# ==========================================
# 8. التصويت الدرامي ومحكمة النهار
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("vote_"))
def handle_voting(call):
    global game
    if game["phase"] != "day":
        bot.answer_callback_query(call.id, "محكمة النهار مغلقة الآن!", show_alert=True)
        return

    voter_id = call.from_user.id
    if voter_id not in game["players"] or not game["players"][voter_id]["alive"]:
        bot.answer_callback_query(call.id, "الأموات لا حق لهم في التصويت والمحاكم!", show_alert=True)
        return

    if voter_id in game["votes"]:
        bot.answer_callback_query(call.id, "❌ لقد ألقيت صوتك بالفعل في هذه الجولة، لا يمكن التراجع!", show_alert=True)
        return

    target_id = int(call.data.split("_")[1])
    
    if target_id not in game["players"] or not game["players"][target_id]["alive"]:
        bot.answer_callback_query(call.id, "هذا الشخص ليس ضمن الأحياء حالياً!", show_alert=True)
        return

    game["votes"][voter_id] = target_id
    
    voter_name = game["players"][voter_id]["name"]
    target_name = game["players"][target_id]["name"]
    
    bot.answer_callback_query(call.id, f"✅ تم تثبيت صوتك ضد المشنقة لـ {target_name}!")
    bot.send_message(game["group_id"], f"🗳️ صوّت المواطن <b>{voter_name}</b> بطلب الإعدام ضد المشتبه به <b>{target_name}</b>!", parse_mode="HTML")

def process_day_timer(target_round):
    time.sleep(120)
    global game
    if not game["active"] or game["round_id"] != target_round or game["phase"] != "day":
        return
    count_and_execute_vote(target_round)

def count_and_execute_vote(target_round):
    global game
    if not game["active"] or game["round_id"] != target_round:
        return

    if not game["votes"]:
        bot.send_message(game["group_id"], "⏳ انقضى وقت المحاكمة الطويل ولم يجرؤ أحد على التصويت!\nلم يُعدم أحد اليوم وغرق الجميع في الشكوك، وسيعود الليل مجدداً...")
    else:
        vote_counts = {}
        for target in game["votes"].values():
            vote_counts[target] = vote_counts.get(target, 0) + 1

        max_votes = max(vote_counts.values())
        top_targets = [t for t, count in vote_counts.items() if count == max_votes]

        if len(top_targets) > 1:
            tied_names = [game["players"][t]["name"] for t in top_targets]
            bot.send_message(
                game["group_id"],
                f"⚖️ <b>تعادل وانقسام في أصوات المحكمة!</b>\n"
                f"تساوى المشتبه بهم ({', '.join(tied_names)}) بـ ({max_votes} أصوات).\n"
                f"ونظراً لعدم وجود إجماع، تُرفع جلسة المحاكمة ولن يُعدم أحد اليوم!",
                parse_mode="HTML"
            )
        else:
            most_voted = top_targets[0]
            executed_name = game["players"][most_voted]["name"]
            executed_role_key = game["players"][most_voted]["role"]
            executed_role_name = ROLE_NAMES[executed_role_key]

            summary_text = f"📊 <b>قرار منصة المحاكم الشعبية:</b>\n لقد حصد المتهم <b>{executed_name}</b> الحصة الأكبر من أصوات الإعدام بـ ({max_votes} أصوات).\n\n"

            if executed_role_key == "politician":
                summary_text += f"🏛️ صعد السياسي <b>{executed_name}</b> إلى منصة المشنقة بثبات، وما إن همّ الجلاد بتنفيذ الحكم حتى رفع يده بهيبة طاغية ورفض الخضوع للقانون! صاح بصوت عالي: <b>'لا يمكن لأحد إعدام السياسي لقوتي ونفوذي المطلق!'</b>\n✨ نجا السياسي من حبل المشنقة وعاد لقصرسالماً معافى!"
            else:
                game["players"][most_voted]["alive"] = False
                summary_text += f"⚖️ <b>تم تنفيذ حكم الإعدام بحق: {executed_name}!</b>\n"
                summary_text += f"📌 <b>كشف حقيقي لدوره:</b> لقد سقط قناع الضحية ليتضح أنه كان: <b>{executed_role_name}</b>!"

                if executed_role_key == "terrorist":
                    t_target = game["night_actions"]["terrorist_target"]
                    if t_target and game["players"][t_target]["alive"]:
                        game["players"][t_target]["alive"] = False
                        t_name = game["players"][t_target]["name"]
                        t_role_name = ROLE_NAMES[game["players"][t_target]["role"]]
                        summary_text += f"\n\n💣 <b>انفجار هائل وسط الساحة العامة!</b> لم يرض الإرهابي (<b>{executed_name}</b>) بالرحيل وحده، فضغط على زر التفجير اليدوي ليأخذ معه فوراً إلى القبر اللاعب <b>{t_name}</b>!\n"
                        summary_text += f"📌 <b>ضحية الانفجار البريء:</b> كان دور الشخص المرافق الذي أخذ معه هو: <b>{t_role_name}</b>!"

            living_list_text = get_living_players_text()
            summary_text += f"\n\n📋 <b>قائمة الناجين الأحياء حالياً:</b>\n{living_list_text}"
            bot.send_message(game["group_id"], summary_text, parse_mode="HTML")

    game["votes"] = {}
    
    if not check_game_over():
        bot.send_message(game["group_id"], "🔄 تغرب شمس النهار الدامية تدريجياً... ولينزل الليل من جديد...")
        time.sleep(5)
        assign_roles_and_start_night()

# ==========================================
# 9. نهاية اللعبة وكشف الفائزين والأدوار الكاملة
# ==========================================
def check_game_over():
    global game
    mafia_list = [p for p in game["players"].values() if p["role"] in ["mafia", "spy"]]
    cult_team = [p for p in game["players"].values() if p["role"] == "cultist" or p.get("cultified", False)]
    
    mafia_alive = sum(1 for p in mafia_list if p["alive"])
    cult_alive = sum(1 for p in cult_team if p["alive"])
    others_alive = sum(1 for p in game["players"].values() if p["alive"] and p["role"] not in ["mafia", "spy", "cultist"] and not p.get("cultified", False))

    winner_team = None
    win_reason = ""

    if mafia_alive == 0 and cult_alive == 0:
        winner_team = "المواطنون والعدالة الأبدية 🏆"
        win_reason = "تم تطهير المدينة بالكامل من جرائم العصابات والمخربين وعاد السلام الشامل."
    elif mafia_alive > 0 and mafia_alive >= (others_alive + cult_alive):
        winner_team = "عصابة المافيا الدموية 🦹‍♂️"
        win_reason = "فرضت المافيا وجاسوسها سيطرتهما المطلقة وتساوى عددهم أو زاد عن البقية!"
    elif cult_alive > 0 and cult_alive >= (others_alive + mafia_alive):
        winner_team = "فريق الطائفيين الظلاميين ⛪"
        win_reason = "هيمن الطائفي وتابعه على عقول أغلبية السكان وزاد عددهم عن بقية الأحياء!"

    if winner_team:
        winners_names = []
        if "المواطنون" in winner_team:
            winners_names = [p["name"] for p in game["players"].values() if p["role"] not in ["mafia", "spy", "cultist"] and not p.get("cultified", False)]
        elif "المافيا" in winner_team:
            winners_names = [p["name"] for p in mafia_list]
        elif "الطائفيين" in winner_team:
            winners_names = [f"{p['name']} ({ROLE_NAMES[p['role']]})" for p in cult_team]

        all_roles_reveal = "\n".join([f"🔹 {p['name']} ⟵ <b>{ROLE_NAMES[p['role']]}</b>" + (" (تابع للطائفة ⛪)" if p.get("cultified", False) else "") for p in game["players"].values()])

        end_message = (
            f"🏁 <b>سدل الستار وانتهت الملحمة بفوز: {winner_team}</b>\n\n"
            f"📌 <b>قصة النصر:</b> {win_reason}\n"
            f"👑 <b>الأبطال الفائزون:</b> {', '.join(winners_names) if winners_names else 'لا يوجد ناجون'}\n\n"
            f"📋 <b>كشف الأوراق والأدوار الكاملة لجميع المشاركين:</b>\n{all_roles_reveal}\n\n"
            f"<i>(تصميم وإخراج اللعبة: أمين)</i>"
        )

        bot.send_message(game["group_id"], end_message, parse_mode="HTML")
        game["active"] = False
        game["creator_id"] = None
        game["join_msg_id"] = None
        return True

    return False

# ==========================================
# 10. تشغيل البوت
# ==========================================
if __name__ == "__main__":
    print("--------------------------------------------------")
    print("جاري تشغيل بوت مافيا 42 الدرامي (إخراج: أمين) بنجاح...")
    print("--------------------------------------------------")
    bot.infinity_polling(skip_pending=True, timeout=90)
