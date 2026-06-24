import os
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardRemove
from aiohttp import web

# Импортируем нашу англоязычную базу машин
from car_data import CAR_DATABASE

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("BASE_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Настройка ИИ Промпта (Образ Бати-Механика с опытом)
SYSTEM_PROMPT = (
    "You are a professional, highly experienced master car mechanic with 20 years of experience. "
    "Your goal is to help amateur car owners diagnose and fix their vehicles in a home garage context. "
    "The user will provide you with the exact car specification (Country, Brand, Model, Generation, Engine) "
    "and describe their issue. Respond in Russian, but keep technical terms, spare parts names, "
    "and fluid specs duplicated in English where necessary. Format your response beautifully: "
    "1. Potential Root Causes (Ranked from most likely to least likely). "
    "2. Step-by-Step DIY Guide on how to check/fix it safely with standard tools. "
    "3. Danger/Safety Warning (what NOT to do to avoid breaking things further)."
)

# Состояния шагов выбора машины (FSM)
class MechanicForm(StatesGroup):
    choosing_country = State()
    choosing_brand = State()
    choosing_model = State()
    choosing_generation = State()
    choosing_engine = State()
    waiting_for_problem = State()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ СБОРКИ КНОПОК ---
def get_countries_keyboard():
    builder = InlineKeyboardBuilder()
    for country in CAR_DATABASE.keys():
        builder.button(text=f"🌍 {country}", callback_data=f"country:{country}")
    builder.adjust(2)
    return builder.as_markup()

def get_brands_keyboard(country):
    builder = InlineKeyboardBuilder()
    for brand in CAR_DATABASE[country].keys():
        builder.button(text=f"🚘 {brand}", callback_data=f"brand:{brand}")
    builder.button(text="⬅️ Back", callback_data="back_to_countries")
    builder.adjust(2)
    return builder.as_markup()

def get_models_keyboard(country, brand):
    builder = InlineKeyboardBuilder()
    for model in CAR_DATABASE[country][brand].keys():
        builder.button(text=f"📦 {model}", callback_data=f"model:{model}")
    builder.button(text="⬅️ Back", callback_data=f"back_to_brands:{country}")
    builder.adjust(2)
    return builder.as_markup()

def get_generations_keyboard(country, brand, model):
    builder = InlineKeyboardBuilder()
    gens = CAR_DATABASE[country][brand][model]["Generations"]
    for gen in gens:
        builder.button(text=f"📅 {gen}", callback_data=f"gen:{gen}")
    builder.button(text="⬅️ Back", callback_data=f"back_to_models:{country}:{brand}")
    builder.adjust(1)
    return builder.as_markup()

def get_engines_keyboard(country, brand, model):
    builder = InlineKeyboardBuilder()
    engines = CAR_DATABASE[country][brand][model]["Engines"]
    for eng in engines:
        builder.button(text=f"⚙️ {eng}", callback_data=f"eng:{eng}")
    builder.button(text="⬅️ Back", callback_data=f"back_to_gens:{country}:{brand}:{model}")
    builder.adjust(1)
    return builder.as_markup()


# --- ОБРАБОТЧИКИ ХЕНДЛЕРОВ ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(MechanicForm.choosing_country)
    await message.answer(
        "Привет, бро! Я твой ИИ-Автомеханик. 🔧🚗\n"
        "Давай определимся с твоей тачкой, чтобы диагностика была точной.\n\n"
        "Выбери регион/страну производства марки:",
        reply_markup=get_countries_keyboard()
    )

@dp.callback_query(F.data.startswith("country:"), MechanicForm.choosing_country)
async def process_country(callback: types.CallbackQuery, state: FSMContext):
    country = callback.data.split(":")[1]
    await state.update_data(country=country)
    await state.set_state(MechanicForm.choosing_brand)
    
    await callback.message.edit_text(
        f"Регион: {country}\nТеперь выбери марку автомобиля (Brand):",
        reply_markup=get_brands_keyboard(country)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("brand:"), MechanicForm.choosing_brand)
async def process_brand(callback: types.CallbackQuery, state: FSMContext):
    brand = callback.data.split(":")[1]
    user_data = await state.get_data()
    country = user_data['country']
    
    await state.update_data(brand=brand)
    await state.set_state(MechanicForm.choosing_model)
    
    await callback.message.edit_text(
        f"Автомобиль: {brand} ({country})\nВыбери модель (Model):",
        reply_markup=get_models_keyboard(country, brand)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("model:"), MechanicForm.choosing_model)
async def process_model(callback: types.CallbackQuery, state: FSMContext):
    model = callback.data.split(":")[1]
    user_data = await state.get_data()
    country = user_data['country']
    brand = user_data['brand']
    
    await state.update_data(model=model)
    await state.set_state(MechanicForm.choosing_generation)
    
    await callback.message.edit_text(
        f"Машина: {brand} {model}\nВыбери поколение / годы выпуска (Generation):",
        reply_markup=get_generations_keyboard(country, brand, model)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("gen:"), MechanicForm.choosing_generation)
async def process_generation(callback: types.CallbackQuery, state: FSMContext):
    gen = callback.data.split(":")[1]
    user_data = await state.get_data()
    country = user_data['country']
    brand = user_data['brand']
    model = user_data['model']
    
    await state.update_data(generation=gen)
    await state.set_state(MechanicForm.choosing_engine)
    
    await callback.message.edit_text(
        f"Машина: {brand} {model} [{gen}]\nВыбери тип и объем двигателя (Engine):",
        reply_markup=get_engines_keyboard(country, brand, model)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("eng:"), MechanicForm.choosing_engine)
async def process_engine(callback: types.CallbackQuery, state: FSMContext):
    engine = callback.data.split(":")[1]
    user_data = await state.get_data()
    
    await state.update_data(engine=engine)
    await state.set_state(MechanicForm.waiting_for_problem)
    
    # Полный паспорт машины собран
    summary = (
        f"⚙️ **Паспорт автомобиля успешно собран!**\n"
        f"• Brand: {user_data['brand']}\n"
        f"• Model: {user_data['model']}\n"
        f"• Gen: {user_data['generation']}\n"
        f"• Engine: {engine}\n\n"
        f"А теперь, бро, опиши своими словами, что случилось? "
        f"(Например: 'Стучит спереди справа на кочках', 'Горит чек и троит движок', 'Печка дует холодным')."
    )
    
    # Удаляем inline кнопки и просим написать текст
    await callback.message.edit_text(summary, parse_mode="Markdown")
    await callback.answer()

# --- КНОПКИ НАЗАД (BACK BUTTONS LOGIC) ---
@dp.callback_query(F.data == "back_to_countries")
async def back_to_countries(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(MechanicForm.choosing_country)
    await callback.message.edit_text("Выбери регион/страну производства марки:", reply_markup=get_countries_keyboard())
    await callback.answer()

# --- ФИНАЛЬНЫЙ СБОР И ЗАПРОС К ИИ ---
@dp.message(MechanicForm.waiting_for_problem)
async def chat_with_ai_mechanic(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    problem_description = message.text
    
    status_msg = await message.answer("🛠 *Ставлю тачку на подъемник, подключаю сканер... Думаю...* ⏳", parse_mode="Markdown")
    
    # Формируем идеальный лог для ИИ
    car_info = (
        f"Vehicle Context:\n"
        f"- Brand/Make: {user_data['brand']}\n"
        f"- Model: {user_data['model']}\n"
        f"- Generation/Year: {user_data['generation']}\n"
        f"- Engine configuration: {user_data['engine']}\n"
        f"User Problem: {problem_description}"
    )
    
    # Запрос к бесплатной модели Qwen на OpenRouter
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "meta-llama/llama-3-8b-instruct:free",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": car_info}
            ],
            "temperature": 0.5
        }
        
        try:
            async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    ai_response = result['choices'][0]['message']['content']
                    await status_msg.delete()
                    await message.answer(ai_response)
                else:
                    error_text = await resp.text()
                    await status_msg.edit_text(f"❌ Ошибка автосканера (OpenRouter Error: {resp.status}). Попробуй позже.")
                    print(f"OpenRouter Error: {error_text}")
        except Exception as e:
            await status_msg.edit_text("❌ Связь с гаражом оборвалась. Проверь настройки сервера.")
            print(f"Exception: {e}")
            
    await state.clear() # Сбрасываем стейт для возможности новой диагностики

# --- WEBHOOK СЕРВЕРНАЯ СЛУЖБА ДЛЯ RENDER ---
async def handle_telegram_webhook(request):
    try:
        json_data = await request.json()
        update = types.Update(**json_data)
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"Webhook update error: {e}")
    return web.Response(text="OK")

async def handle_root(request):
    return web.Response(text="AI Mechanic is Live!")

async def on_startup(app):
    webhook_url = f"{BASE_URL}/webhook"
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(webhook_url, drop_pending_updates=True)

def main():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_post("/webhook", handle_telegram_webhook)
    app.on_startup.append(on_startup)
    
    port = int(os.getenv("PORT", 10000))
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()