from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
import logging
import requests
import asyncio
from datetime import datetime
import matplotlib.pyplot as plt
from io import BytesIO
import numpy as np

# Логирование
logging.basicConfig(level=logging.INFO)

API_TOKEN = ""
WEATHER_API_KEY = ""
WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/forecast"

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

#Определение состояний(лонг памох)
class WeatherStates(StatesGroup):
    waiting_for_start_point = State()
    waiting_for_end_point = State()
    waiting_for_stops = State()
    waiting_for_interval = State()

# Ф-я получения погоды на несколько дней
async def get_weather(city, days):
    try:
        params = {
            'q': city,
            'appid': WEATHER_API_KEY,
            'units': 'metric',
            'lang': 'ru',
            'cnt': days * 8  #8 измирений в день (каждые 3 часа)
        }
        response = requests.get(WEATHER_API_URL, params=params)
        data = response.json()
        
        if response.status_code == 200:
            forecasts = []
            temps = []
            dates = []
            
            for item in data['list']:
                dt = datetime.fromtimestamp(item['dt'])
                temp = item['main']['temp']
                humidity = item['main']['humidity']
                wind = item['wind']['speed']
                description = item['weather'][0]['description']
                
                if dt.hour == 12 or len(forecasts) == 0:
                    forecasts.append({
                        'date': dt.strftime('%d.%m.%Y %H:%M'),
                        'temp': temp,
                        'humidity': humidity,
                        'wind': wind,
                        'description': description
                    })
                
                temps.append(temp)
                dates.append(dt)
            
            return forecasts, dates, temps
        else:
            return None, None, None
    except Exception as e:
        logging.error(f"Ошибка получения погоды: {e}")
        return None, None, None



def get_interval_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 день", callback_data="interval_1"),
            InlineKeyboardButton(text="3 дня", callback_data="interval_3")
        ],
        [
            InlineKeyboardButton(text="5 дней", callback_data="interval_5")
        ]
    ])
    return keyboard

@dp.message(F.text == '/start')
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот прогноза погоды для путешественников.\n"
        "🌤 Я помогу узнать погоду на вашем маршруте.\n"
        "Используйте /weather для начала работы или /help для справки."
    )


@dp.message(F.text == '/weather')
async def cmd_weather(message: types.Message, state: FSMContext):
    await state.set_state(WeatherStates.waiting_for_start_point)
    await message.answer("Введите начальную точку маршрута:")

@dp.message(WeatherStates.waiting_for_start_point)
async def process_start_point(message: types.Message, state: FSMContext):
    await state.update_data(start_point=message.text)
    await state.set_state(WeatherStates.waiting_for_end_point)
    await message.answer("Теперь введите конечную точку маршрута:")

@dp.message(WeatherStates.waiting_for_end_point)
async def process_end_point(message: types.Message, state: FSMContext):
    await state.update_data(end_point=message.text)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да", callback_data="add_stops"),
            InlineKeyboardButton(text="Нет", callback_data="no_stops")
        ]
    ])
    



@dp.message(WeatherStates.waiting_for_stops)
async def process_stops(message: types.Message, state: FSMContext):
    stops = [stop.strip() for stop in message.text.split(',')]
    await state.update_data(stops=stops)
    await message.answer("Выберите интервал прогноза:", reply_markup=get_interval_keyboard())

@dp.callback_query(F.data.startswith("interval_"))
async def process_interval(callback: types.CallbackQuery, state: FSMContext):
    interval = int(callback.data.split("_")[1])
    data = await state.get_data()
    
    route_points = [data['start_point']]
    if 'stops' in data:
        route_points.extend(data['stops'])
    route_points.append(data['end_point'])
    
    await callback.message.answer(f"⏳ Собираю прогноз погоды для вашего маршрута на {interval} {'день' if interval == 1 else 'дня' if interval < 5 else 'дней'}...")
    
    for point in route_points:
        forecasts, dates, temps = await get_weather(point, interval)
        if forecasts and dates and temps:
            #Отправляем текстовый прогноз
            forecast_text = f"📍 Прогноз погоды для {point} на {interval} {'день' if interval == 1 else 'дня' if interval < 5 else 'дней'}:\n\n"
            for forecast in forecasts:
                forecast_text += (
                    f"📅 {forecast['date']}:\n"
                    f"🌡 Температура: {forecast['temp']}°C\n"
                    f"💧 Влажность: {forecast['humidity']}%\n"
                    f"💨 Ветер: {forecast['wind']} м/с\n"
                    f"☁️ {forecast['description'].capitalize()}\n\n"
                )
            await callback.message.answer(forecast_text)

    
    await callback.message.answer("🏁 Прогноз погоды для всего маршрута собран!")
    await state.clear()
    await callback.answer()

#Обработчик иных сообщений
@dp.message()
async def handle_unknown_message(message: types.Message):
    await message.answer('Извините, я не понял ваш запрос. Пожалуйста, напишите /start и следуйте инструкциям')
    
if __name__ == '__main__':
    try:
        asyncio.run(dp.start_polling(bot))
    except Exception as e:
        logging.error(f'Ошибка при запуске бота: {e}')