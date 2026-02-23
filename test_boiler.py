#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Емуляція роботи контролера FATEK FBs-MA з ST кодом
Тестування програми BoilerController.ST
"""

import time
import threading
import random
from datetime import datetime

class PLCEmulator:
    """Емуляція ПЛК FATEK FBs-MA"""
    
    def __init__(self):
        # Ініціалізація входів/виходів
        self.reset_io()
        
        # Стан системи
        self.running = False
        self.scan_count = 0
        
    def reset_io(self):
        """Скидання всіх входів/виходів"""
        # Аналогові входи (IW)
        self.AI_VOLTAGE = 2500      # ~305V
        self.AI_TEMP_BOILER = 1500  # ~55°C
        self.AI_TEMP_WATER = 1000   # ~37°C
        self.AI_TEMP_1 = 1200       # ~44°C
        self.AI_TEMP_2 = 1100       # ~40°C
        self.AI_OIL_PRESSURE = 3000 # ~73%
        
        # Дискретні входи (IX)
        self.X_GAS_PRESENT = True
        self.X_VACUUM_OK = True
        self.X_OIL_PRESS_OK = True
        self.X_EMERGENCY_STOP = False
        
        # Команди (MX)
        self.CMD_START = False
        self.CMD_STOP = False
        self.CMD_SOCKET1 = False
        self.CMD_SOCKET2 = False
        
        # Виходи (QX)
        self.Y_GAS_VALVE = False
        self.Y_SOCKET1 = False
        self.Y_SOCKET2 = False
        self.Y_ALARM_LIGHT = False
        self.Y_PERMIT_RUN = False
        self.Y_WATER_PUMP = False
        
        # Внутрішні маркери
        self.M_VOLTAGE_ALARM = False
        self.M_TEMP_ALARM = False
        self.M_VACUUM_ALARM = False
        self.M_OIL_ALARM = False
        self.M_ANY_ALARM = False
        self.M_SYSTEM_RUN = False
        self.M_SYSTEM_READY = False
        self.M_GAS_AVAILABLE = False
        self.M_VACUUM_OK = False
        
        # Фізичні величини
        self.VOLTAGE_DISPLAY = 0
        self.TEMP_B_DISPLAY = 0
        self.TEMP_W_DISPLAY = 0
        self.TEMP_1_DISPLAY = 0
        self.TEMP_2_DISPLAY = 0
        self.OIL_P_DISPLAY = 0
        
        # Статистика
        self.STAT_START_COUNT = 0
        self.STAT_ALARM_COUNT = 0
        self.STAT_GAS_OFF = 0
        self.STAT_VAC_OFF = 0
        
        # Детектори фронтів
        self.M_CMD_START_OLD = False
        self.M_CMD_STOP_OLD = False
        self.M_GAS_OLD = False
        self.M_VAC_OLD = False
        self.M_ALARM_OLD = False
        
        # Константи
        self.ADC_MAX = 4095
        self.VOLTAGE_MAX = 500
        self.TEMP_MAX = 150
        self.VOLTAGE_ALARM = 400
        self.VOLTAGE_RESET = 380
        self.TEMP_ALARM = 80
        self.TEMP_RESET = 75

    def scan_cycle(self):
        """Один цикл сканування ПЛК"""
        
        # БЛОК 1: Перетворення АЦП → фізичні величини
        self.VOLTAGE_DISPLAY = self.AI_VOLTAGE * self.VOLTAGE_MAX // self.ADC_MAX
        self.TEMP_B_DISPLAY = self.AI_TEMP_BOILER * self.TEMP_MAX // self.ADC_MAX
        self.TEMP_W_DISPLAY = self.AI_TEMP_WATER * self.TEMP_MAX // self.ADC_MAX
        self.TEMP_1_DISPLAY = self.AI_TEMP_1 * self.TEMP_MAX // self.ADC_MAX
        self.TEMP_2_DISPLAY = self.AI_TEMP_2 * self.TEMP_MAX // self.ADC_MAX
        self.OIL_P_DISPLAY = self.AI_OIL_PRESSURE * 100 // self.ADC_MAX
        
        # БЛОК 2: Аварія напруги
        if self.VOLTAGE_DISPLAY >= self.VOLTAGE_ALARM:
            self.M_VOLTAGE_ALARM = True
        elif self.VOLTAGE_DISPLAY < self.VOLTAGE_RESET:
            self.M_VOLTAGE_ALARM = False
            
        # БЛОК 3: Аварія температури
        if self.TEMP_B_DISPLAY >= self.TEMP_ALARM:
            self.M_TEMP_ALARM = True
        elif self.TEMP_B_DISPLAY < self.TEMP_RESET:
            self.M_TEMP_ALARM = False
            
        # БЛОК 4: Датчик газу
        self.M_GAS_AVAILABLE = self.X_GAS_PRESENT
        if self.M_GAS_AVAILABLE == False and self.M_GAS_OLD == True:
            self.STAT_GAS_OFF += 1
        self.M_GAS_OLD = self.M_GAS_AVAILABLE
        
        # БЛОК 5: Датчик вакууму
        self.M_VACUUM_OK = self.X_VACUUM_OK
        if self.M_VACUUM_OK == False:
            self.M_VACUUM_ALARM = True
        else:
            self.M_VACUUM_ALARM = False
            
        if self.M_VACUUM_OK == False and self.M_VAC_OLD == True:
            self.STAT_VAC_OFF += 1
        self.M_VAC_OLD = self.M_VACUUM_OK
        
        # БЛОК 6: Тиск масла
        self.M_OIL_ALARM = not self.X_OIL_PRESS_OK
        
        # БЛОК 7: Загальна аварія
        old_alarm = self.M_ANY_ALARM
        self.M_ANY_ALARM = (self.M_VOLTAGE_ALARM or self.M_TEMP_ALARM or 
                           self.M_VACUUM_ALARM or self.M_OIL_ALARM or 
                           self.X_EMERGENCY_STOP)
        
        if self.M_ANY_ALARM == True and self.M_ALARM_OLD == False:
            self.STAT_ALARM_COUNT += 1
        self.M_ALARM_OLD = self.M_ANY_ALARM
        
        # БЛОК 8: Логіка старт/стоп
        if self.CMD_START == True and self.M_CMD_START_OLD == False:
            if self.M_SYSTEM_RUN == False and self.M_ANY_ALARM == False:
                self.M_SYSTEM_RUN = True
                self.STAT_START_COUNT += 1
        self.M_CMD_START_OLD = self.CMD_START
        
        if self.CMD_STOP == True and self.M_CMD_STOP_OLD == False:
            self.M_SYSTEM_RUN = False
        self.M_CMD_STOP_OLD = self.CMD_STOP
        
        if self.M_ANY_ALARM == True:
            self.M_SYSTEM_RUN = False
            
        # БЛОК 9: Готовність системи
        self.M_SYSTEM_READY = (not self.M_VOLTAGE_ALARM and 
                              not self.M_TEMP_ALARM and 
                              self.M_GAS_AVAILABLE and 
                              self.M_VACUUM_OK and 
                              not self.M_OIL_ALARM and 
                              not self.X_EMERGENCY_STOP and 
                              self.M_SYSTEM_RUN)
        
        # БЛОК 10: Керування клапаном газу
        if self.M_SYSTEM_READY:
            self.Y_GAS_VALVE = True
        else:
            self.Y_GAS_VALVE = False
            
        if self.M_VACUUM_OK == False:
            self.Y_GAS_VALVE = False
            
        # БЛОК 11: Керування розетками
        self.Y_SOCKET1 = (self.CMD_SOCKET1 == True and self.M_ANY_ALARM == False)
        self.Y_SOCKET2 = (self.CMD_SOCKET2 == True and self.M_ANY_ALARM == False)
        
        # БЛОК 12: Насос води
        self.Y_WATER_PUMP = (self.M_SYSTEM_READY and self.TEMP_W_DISPLAY > 20)
        
        # БЛОК 13: Аварійна сигналізація
        self.Y_ALARM_LIGHT = self.M_ANY_ALARM
        
        # БЛОК 14: Дозвіл роботи
        self.Y_PERMIT_RUN = self.M_SYSTEM_READY
        
        self.scan_count += 1

    def print_status(self):
        """Виведення стану системи"""
        print(f"\n{'='*60}")
        print(f"🔥 СТАН КОНТРОЛЕРА БОЙЛЕРА (цикл #{self.scan_count})")
        print(f"⏰ Час: {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'-'*60}")
        print(f"⚡ Напруга: {self.VOLTAGE_DISPLAY:3d}В {'⚠️' if self.M_VOLTAGE_ALARM else '✅'}")
        print(f"🌡️  Темп. бойлера: {self.TEMP_B_DISPLAY:2d}°C {'⚠️' if self.M_TEMP_ALARM else '✅'}")
        print(f"💧 Темп. води: {self.TEMP_W_DISPLAY:2d}°C")
        print(f"🔥 Газ: {'Є' if self.M_GAS_AVAILABLE else '❌'}")
        print(f"🌀 Вакуум: {'Є' if self.M_VACUUM_OK else '❌'} {'⚠️' if self.M_VACUUM_ALARM else ''}")
        print(f"⛽ Тиск масла: {'НОРМА' if not self.M_OIL_ALARM else '⚠️'}")
        print(f"{'-'*60}")
        print(f"▶️  Система: {'ЗАПУЩЕНА' if self.M_SYSTEM_RUN else 'ЗУПИНЕНА'}")
        print(f"✅ Готовність: {'ГОТОВА' if self.M_SYSTEM_READY else 'НЕ ГОТОВА'}")
        print(f"🚨 Загальна аварія: {'ТАК' if self.M_ANY_ALARM else 'НІ'}")
        print(f"{'-'*60}")
        print(f"🔵 Клапан газу: {'ВІДКРИТО' if self.Y_GAS_VALVE else 'ЗАКРИТО'}")
        print(f"🔌 Розетка 1: {'УВІМК' if self.Y_SOCKET1 else 'ВИМК'}")
        print(f"🔌 Розетка 2: {'УВІМК' if self.Y_SOCKET2 else 'ВИМК'}")
        print(f"💧 Насос води: {'УВІМК' if self.Y_WATER_PUMP else 'ВИМК'}")
        print(f"🚨 Сигнал аварії: {'АКТИВНИЙ' if self.Y_ALARM_LIGHT else 'НЕАКТИВНИЙ'}")
        print(f"🔑 Дозвіл роботи: {'АКТИВНИЙ' if self.Y_PERMIT_RUN else 'НЕАКТИВНИЙ'}")
        print(f"{'='*60}")

    def start_system(self):
        """Запуск системи"""
        self.CMD_START = True
        time.sleep(0.1)
        self.CMD_START = False
        print("▶️ Команда старт відправлена")

    def stop_system(self):
        """Зупинка системи"""
        self.CMD_STOP = True
        time.sleep(0.1)
        self.CMD_STOP = False
        print("⏹️ Команда стоп відправлена")

    def set_voltage(self, volts):
        """Встановити напругу"""
        self.AI_VOLTAGE = volts * self.ADC_MAX // self.VOLTAGE_MAX
        print(f"⚡ Напругу встановлено: {volts}В")

    def set_temperature(self, temp):
        """Встановити температуру бойлера"""
        self.AI_TEMP_BOILER = temp * self.ADC_MAX // self.TEMP_MAX
        print(f"🌡️ Температуру встановлено: {temp}°C")

    def set_gas(self, present):
        """Встановити наявність газу"""
        self.X_GAS_PRESENT = present
        print(f"🔥 Газ: {'Є' if present else 'НЕМАЄ'}")

    def set_vacuum(self, ok):
        """Встановити стан вакууму"""
        self.X_VACUUM_OK = ok
        print(f"🌀 Вакуум: {'Є' if ok else 'НЕМАЄ'}")

def test_controller():
    """Тестування контролера"""
    print("🔥 ТЕСТУВАННЯ КОНТРОЛЕРА БОЙЛЕРА (ST код)")
    print("="*60)
    
    plc = PLCEmulator()
    
    try:
        # Запускаємо сканування
        def scan_loop():
            while plc.running:
                plc.scan_cycle()
                time.sleep(0.1)
        
        scan_thread = threading.Thread(target=scan_loop, daemon=True)
        plc.running = True
        scan_thread.start()
        
        # Тест 1: Нормальний запуск
        print("\n📋 Тест 1: Нормальний запуск системи")
        plc.print_status()
        time.sleep(1)
        
        plc.start_system()
        time.sleep(2)
        plc.print_status()
        
        # Тест 2: Перевищення напруги
        print("\n⚠️ Тест 2: Перевищення напруги до 420В")
        plc.set_voltage(420)
        time.sleep(3)
        plc.print_status()
        
        # Відновлення напруги
        print("\n↩️ Відновлення напруги до 360В")
        plc.set_voltage(360)
        time.sleep(1)
        plc.start_system()  # Перезапуск
        time.sleep(2)
        plc.print_status()
        
        # Тест 3: Перевищення температури
        print("\n🔥 Тест 3: Перевищення температури до 85°C")
        plc.set_temperature(85)
        time.sleep(3)
        plc.print_status()
        
        # Відновлення температури
        print("\n❄️ Відновлення температури до 60°C")
        plc.set_temperature(60)
        time.sleep(1)
        plc.start_system()  # Перезапуск
        time.sleep(2)
        plc.print_status()
        
        # Тест 4: Втрата вакууму
        print("\n🌀 Тест 4: Втрата вакууму")
        plc.set_vacuum(False)
        time.sleep(3)
        plc.print_status()
        
        # Відновлення вакууму
        print("\n✅ Відновлення вакууму")
        plc.set_vacuum(True)
        time.sleep(1)
        plc.start_system()  # Перезапуск
        time.sleep(2)
        plc.print_status()
        
        # Тест 5: Керування розетками
        print("\n🔌 Тест 5: Керування розетками")
        plc.CMD_SOCKET1 = True
        time.sleep(1)
        plc.CMD_SOCKET2 = True
        time.sleep(2)
        plc.print_status()
        
        plc.CMD_SOCKET1 = False
        plc.CMD_SOCKET2 = False
        time.sleep(1)
        
        # Статистика
        print(f"\n📊 СТАТИСТИКА РОБОТИ")
        print(f"Кількість запусків: {plc.STAT_START_COUNT}")
        print(f"Кількість аварій: {plc.STAT_ALARM_COUNT}")
        print(f"Відключень газу: {plc.STAT_GAS_OFF}")
        print(f"Відключень вакууму: {plc.STAT_VAC_OFF}")
        
    except KeyboardInterrupt:
        print("\n⏹️ Тестування перервано")
    finally:
        plc.running = False
        print("\n✅ Тестування завершено")

if __name__ == "__main__":
    test_controller()
