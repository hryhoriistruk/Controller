#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ПРОСТИЙ ТЕСТ КОНТРОЛЕРА БОЙЛЕРА
Без Modbus - тільки логіка
"""

import time
import threading
from datetime import datetime

class SimpleBoilerController:
    """Спрощений контролер бойлера для тестування"""
    
    def __init__(self):
        # Пороги
        self.VOLTAGE_TRIP = 400.0
        self.VOLTAGE_RESET = 380.0
        self.TEMP_TRIP = 80.0
        self.TEMP_RESET = 75.0
        
        # Стан датчиків
        self.voltage = 350.0
        self.boiler_temp = 60.0
        self.water_temp = 40.0
        self.gas_present = True
        self.vacuum_present = True
        self.oil_pressure_ok = True
        self.steam_pressure_ok = True
        self.emergency_stop = False
        
        # Виходи
        self.gas_valve = False
        self.socket1 = False
        self.socket2 = False
        self.water_pump = False
        self.oil_pump = False
        self.alarm_light = False
        
        # Команди
        self.cmd_start = False
        self.cmd_stop = False
        self.cmd_socket1 = False
        self.cmd_socket2 = False
        
        # Аварії
        self.alm_voltage_high = False
        self.alm_temp_high = False
        self.alm_no_gas = False
        self.alm_no_vacuum = False
        self.alm_oil_pressure_low = False
        self.alm_steam_pressure_bad = False
        self.alm_any_alarm = False
        
        # Стан системи
        self.system_running = False
        self.system_ready = False
        
        # Статистика
        self.stats = {
            'starts': 0,
            'stops': 0,
            'alarms': 0,
            'gas_failures': 0,
            'vacuum_failures': 0
        }
        
        # Детектори фронтів
        self.start_old = False
        self.gas_old = False
        self.vacuum_old = False
        self.alarm_old = False
        
        # Робочий потік
        self.running = False
        self.control_thread = None
        self.stop_event = threading.Event()

    def check_alarms(self):
        """Перевірка аварій"""
        old_alarm = self.alm_any_alarm
        
        # Аварія напруги
        if self.voltage >= self.VOLTAGE_TRIP:
            self.alm_voltage_high = True
        elif self.voltage < self.VOLTAGE_RESET:
            self.alm_voltage_high = False
        
        # Аварія температури
        if self.boiler_temp >= self.TEMP_TRIP:
            self.alm_temp_high = True
        elif self.boiler_temp < self.TEMP_RESET:
            self.alm_temp_high = False
        
        # Аварії по датчиках
        self.alm_no_gas = not self.gas_present
        self.alm_no_vacuum = not self.vacuum_present
        self.alm_oil_pressure_low = not self.oil_pressure_ok
        self.alm_steam_pressure_bad = not self.steam_pressure_ok
        
        # Загальна аварія
        self.alm_any_alarm = (
            self.alm_voltage_high or
            self.alm_temp_high or
            self.alm_no_gas or
            self.alm_no_vacuum or
            self.alm_oil_pressure_low or
            self.alm_steam_pressure_bad or
            self.emergency_stop
        )
        
        # Лічильник аварій
        if self.alm_any_alarm and not old_alarm:
            self.stats['alarms'] += 1
            print(f"🚨 АВАРІЯ! Код: {self.get_alarm_code()}")

    def get_alarm_code(self):
        """Код аварії"""
        if self.alm_voltage_high:
            return 1
        elif self.alm_temp_high:
            return 2
        elif self.alm_no_gas:
            return 3
        elif self.alm_no_vacuum:
            return 4
        elif self.alm_oil_pressure_low:
            return 5
        elif self.alm_steam_pressure_bad:
            return 6
        elif self.emergency_stop:
            return 7
        else:
            return 0

    def handle_start_stop(self):
        """Обробка старт/стоп"""
        # Старт
        if self.cmd_start and not self.start_old:
            if not self.system_running and not self.alm_any_alarm:
                self.system_running = True
                self.stats['starts'] += 1
                print("▶️ Систему запущено")
        
        # Стоп
        if self.cmd_stop or self.alm_any_alarm:
            if self.system_running:
                self.system_running = False
                self.stats['stops'] += 1
                print("⏹️ Систему зупинено")
        
        self.start_old = self.cmd_start

    def update_ready(self):
        """Оновлення готовності"""
        self.system_ready = (
            not self.alm_voltage_high and
            not self.alm_temp_high and
            self.gas_present and
            self.vacuum_present and
            self.oil_pressure_ok and
            self.steam_pressure_ok and
            not self.emergency_stop and
            self.system_running
        )

    def control_outputs(self):
        """Керування виходами"""
        # Газовий клапан - ПРІОРИТЕТ ВАКУУМУ!
        if self.system_ready:
            self.gas_valve = True
        else:
            self.gas_valve = False
        
        # Додатковий захист - вакуум важливіший за все!
        if not self.vacuum_present:
            self.gas_valve = False
            print("🚨 ВАКУУМ ВТРАЧЕНО! ГАЗ ЗАКРИТО!")
        
        # Розетки
        self.socket1 = self.cmd_socket1 and not self.alm_any_alarm
        self.socket2 = self.cmd_socket2 and not self.alm_any_alarm
        
        # Насоси
        self.water_pump = self.system_ready and self.water_temp > 20
        self.oil_pump = self.system_ready and self.oil_pressure_ok
        
        # Аварійна лампа
        self.alarm_light = self.alm_any_alarm

    def update_statistics(self):
        """Оновлення статистики"""
        # Відмови газу
        if not self.gas_present and self.gas_old:
            self.stats['gas_failures'] += 1
        
        # Відмови вакууму
        if not self.vacuum_present and self.vacuum_old:
            self.stats['vacuum_failures'] += 1
        
        # Оновлення детекторів
        self.gas_old = self.gas_present
        self.vacuum_old = self.vacuum_present
        self.alarm_old = self.alm_any_alarm

    def scan_cycle(self):
        """Цикл сканування"""
        self.check_alarms()
        self.handle_start_stop()
        self.update_ready()
        self.control_outputs()
        self.update_statistics()

    def control_loop(self):
        """Основний цикл"""
        print("🔄 Контролер запущено")
        
        while not self.stop_event.is_set():
            self.scan_cycle()
            time.sleep(0.1)  # 100 мс цикл
        
        print("⏹️ Контролер зупинено")

    def start(self):
        """Запуск контролера"""
        if self.running:
            return
        
        self.running = True
        self.stop_event.clear()
        
        self.control_thread = threading.Thread(target=self.control_loop, daemon=True)
        self.control_thread.start()
        
        print("🚀 Контролер запущено")

    def stop(self):
        """Зупинка контролера"""
        if not self.running:
            return
        
        self.running = False
        self.stop_event.set()
        
        if self.control_thread:
            self.control_thread.join(timeout=2)
        
        # Відключення всього
        self.gas_valve = False
        self.socket1 = False
        self.socket2 = False
        self.water_pump = False
        self.oil_pump = False
        self.alarm_light = False
        
        print("✅ Контролер зупинено")

    def set_voltage(self, volts):
        """Встановити напругу"""
        self.voltage = volts
        print(f"⚡ Напруга: {volts}В")

    def set_temperature(self, temp):
        """Встановити температуру"""
        self.boiler_temp = temp
        print(f"🌡️ Температура: {temp}°C")

    def set_gas(self, present):
        """Встановити газ"""
        self.gas_present = present
        print(f"🔥 Газ: {'Є' if present else 'НЕМАЄ'}")

    def set_vacuum(self, present):
        """Встановити вакуум"""
        self.vacuum_present = present
        print(f"🌀 Вакуум: {'Є' if present else 'НЕМАЄ'}")

    def start_system(self):
        """Старт системи"""
        self.cmd_start = True
        time.sleep(0.1)
        self.cmd_start = False

    def stop_system(self):
        """Стоп системи"""
        self.cmd_stop = True
        time.sleep(0.1)
        self.cmd_stop = False

    def print_status(self):
        """Статус системи"""
        alarm_names = {
            0: "Норма",
            1: "Висока напруга",
            2: "Висока температура",
            3: "Немає газу",
            4: "Немає вакууму",
            5: "Низький тиск масла",
            6: "Неправильний тиск пари",
            7: "Аварійний стоп"
        }
        
        print(f"\n{'='*60}")
        print(f"🔥 СТАН КОНТРОЛЕРА БОЙЛЕРА | {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'-'*60}")
        print(f"⚡ Напруга: {self.voltage:.0f}В {'⚠️' if self.alm_voltage_high else '✅'}")
        print(f"🌡️ Температура: {self.boiler_temp:.0f}°C {'⚠️' if self.alm_temp_high else '✅'}")
        print(f"🔥 Газ: {'Є' if self.gas_present else '❌'} {'⚠️' if self.alm_no_gas else ''}")
        print(f"🌀 Вакуум: {'Є' if self.vacuum_present else '❌'} {'⚠️' if self.alm_no_vacuum else ''}")
        print(f"⛽ Тиск масла: {'НОРМА' if self.oil_pressure_ok else '❌'}")
        print(f"💨 Тиск пари: {'НОРМА' if self.steam_pressure_ok else '❌'}")
        print(f"{'-'*60}")
        print(f"▶️ Система: {'ЗАПУЩЕНА' if self.system_running else 'ЗУПИНЕНА'}")
        print(f"✅ Готовність: {'ГОТОВА' if self.system_ready else 'НЕ ГОТОВА'}")
        print(f"🚨 Аварія: {alarm_names.get(self.get_alarm_code(), 'Невідома')}")
        print(f"{'-'*60}")
        print(f"🔵 Газовий клапан: {'ВІДКРИТО' if self.gas_valve else 'ЗАКРИТО'}")
        print(f"🔌 Розетка 1: {'УВІМК' if self.socket1 else 'ВИМК'}")
        print(f"🔌 Розетка 2: {'УВІМК' if self.socket2 else 'ВИМК'}")
        print(f"💧 Насос води: {'УВІМК' if self.water_pump else 'ВИМК'}")
        print(f"⛽ Насос масла: {'УВІМК' if self.oil_pump else 'ВИМК'}")
        print(f"🚨 Аварійна лампа: {'БЛИМАЄ' if self.alarm_light else 'ВИМК'}")
        print(f"{'-'*60}")
        print(f"📊 Статистика: Запусків={self.stats['starts']} | Зупинок={self.stats['stops']} | Аварій={self.stats['alarms']}")
        print(f"{'='*60}")

def interactive_test():
    """Інтерактивне тестування"""
    print("🔥 ІНТЕРАКТИВНИЙ ТЕСТ КОНТРОЛЕРА БОЙЛЕРА")
    print("="*60)
    print("\n📋 Команди:")
    print("  start      - запустити систему")
    print("  stop       - зупинити систему")
    print("  v [400]    - встановити напругу")
    print("  t [80]     - встановити температуру")
    print("  g [0/1]    - газ (0=немає, 1=є)")
    print("  vac [0/1]  - вакуум (0=немає, 1=є)")
    print("  socket1    - увімкнути розетку 1")
    print("  socket2    - увімкнути розетку 2")
    print("  status     - показати статус")
    print("  auto       - автоматичне тестування")
    print("  q          - вихід")
    print("="*60)
    
    controller = SimpleBoilerController()
    controller.start()
    
    try:
        while True:
            cmd = input("\n👉 Команда: ").strip().lower()
            
            if cmd == 'q':
                break
            elif cmd == 'start':
                controller.start_system()
            elif cmd == 'stop':
                controller.stop_system()
            elif cmd.startswith('v '):
                try:
                    volts = float(cmd.split()[1])
                    controller.set_voltage(volts)
                except:
                    print("❌ Формат: v 400")
            elif cmd.startswith('t '):
                try:
                    temp = float(cmd.split()[1])
                    controller.set_temperature(temp)
                except:
                    print("❌ Формат: t 80")
            elif cmd.startswith('g '):
                try:
                    val = int(cmd.split()[1])
                    controller.set_gas(val == 1)
                except:
                    print("❌ Формат: g 1")
            elif cmd.startswith('vac '):
                try:
                    val = int(cmd.split()[1])
                    controller.set_vacuum(val == 1)
                except:
                    print("❌ Формат: vac 1")
            elif cmd == 'socket1':
                controller.cmd_socket1 = not controller.cmd_socket1
                print(f"🔌 Розетка 1: {'УВІМК' if controller.cmd_socket1 else 'ВИМК'}")
            elif cmd == 'socket2':
                controller.cmd_socket2 = not controller.cmd_socket2
                print(f"🔌 Розетка 2: {'УВІМК' if controller.cmd_socket2 else 'ВИМК'}")
            elif cmd == 'status':
                controller.print_status()
            elif cmd == 'auto':
                run_auto_test(controller)
            elif cmd == '':
                continue
            else:
                print("❌ Невідома команда")
                
    except KeyboardInterrupt:
        print("\n⏹️ Тестування перервано")
    finally:
        controller.stop()
        print("✅ Завершено")

def run_auto_test(controller):
    """Автоматичне тестування"""
    print("\n🤖 АВТОМАТИЧНЕ ТЕСТУВАННЯ")
    print("="*50)
    
    # Тест 1: Нормальний запуск
    print("\n✅ Тест 1: Нормальний запуск")
    controller.start_system()
    time.sleep(2)
    controller.print_status()
    
    # Тест 2: Аварія напруги
    print("\n⚠️ Тест 2: Аварія напруги 420В")
    controller.set_voltage(420)
    time.sleep(2)
    controller.print_status()
    
    controller.set_voltage(360)
    time.sleep(1)
    
    # Тест 3: Аварія температури
    print("\n🔥 Тест 3: Аварія температури 85°C")
    controller.set_temperature(85)
    time.sleep(2)
    controller.print_status()
    
    controller.set_temperature(60)
    time.sleep(1)
    
    # Тест 4: Втрата вакууму (критичний!)
    print("\n🌀 Тест 4: Втрата вакууму - газ має закритися!")
    controller.set_vacuum(False)
    time.sleep(2)
    controller.print_status()
    
    controller.set_vacuum(True)
    time.sleep(1)
    
    # Тест 5: Втрата газу
    print("\n🔥 Тест 5: Втрата газу")
    controller.set_gas(False)
    time.sleep(2)
    controller.print_status()
    
    controller.set_gas(True)
    time.sleep(1)
    
    print("\n✅ Автоматичне тестування завершено")
    print("="*50)

if __name__ == "__main__":
    interactive_test()
