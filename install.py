#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ІНСТАЛЯТОР ТА ТЕСТУВАЛЬНИЙ КОНТРОЛЕРА БОЙЛЕРА
Автоматична перевірка та налаштування
"""

import os
import sys
import subprocess
import time
import serial.tools.list_ports
from pathlib import Path

def check_python_version():
    """Перевірка версії Python"""
    print("🐍 Перевірка версії Python...")
    if sys.version_info >= (3, 7):
        print(f"✅ Python {sys.version.split()[0]} - OK")
        return True
    else:
        print(f"❌ Python {sys.version.split()[0]} - потрібен Python 3.7+")
        return False

def install_requirements():
    """Встановлення необхідних бібліотек"""
    print("\n📦 Встановлення бібліотек...")
    requirements = ['pymodbus', 'pyserial']
    
    for req in requirements:
        try:
            __import__(req)
            print(f"✅ {req} - вже встановлено")
        except ImportError:
            print(f"📥 Встановлення {req}...")
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', req])
                print(f"✅ {req} - встановлено")
            except subprocess.CalledProcessError:
                print(f"❌ Помилка встановлення {req}")
                return False
    return True

def find_serial_ports():
    """Пошук послідовних портів"""
    print("\n🔍 Пошук послідовних портів...")
    ports = serial.tools.list_ports.comports()
    
    if not ports:
        print("❌ Послідовні порти не знайдено")
        return []
    
    print("📡 Знайдені порти:")
    for i, port in enumerate(ports):
        print(f"  {i+1}. {port.device} - {port.description}")
    
    return [port.device for port in ports]

def test_modbus_connection(port):
    """Тестування Modbus з'єднання"""
    print(f"\n🔌 Тестування Modbus на порту {port}...")
    
    try:
        from pymodbus.client import ModbusSerialClient
        
        client = ModbusSerialClient(
            port=port,
            baudrate=9600,
            timeout=1
        )
        
        if client.connect():
            print("✅ Modbus з'єднання встановлено")
            
            # Спроба читати регістр
            try:
                result = client.read_holding_registers(0, 1, unit=1)
                if not result.isError():
                    print("✅ Читання регістрів працює")
                    client.close()
                    return True
                else:
                    print("❌ Помилка читання регістрів")
                    client.close()
                    return False
            except:
                print("⚠️ З'єднання є, але читання не вдалося")
                client.close()
                return False
        else:
            print("❌ Не вдалося підключитися до Modbus")
            return False
            
    except Exception as e:
        print(f"❌ Помилка: {e}")
        return False

def create_config_file(port):
    """Створення конфігураційного файлу"""
    print(f"\n⚙️ Створення конфігурації для порту {port}...")
    
    config_content = f'''# Конфігурація контролера бойлера
# Автоматично згенеровано інсталятором

class BoilerConfig:
    # Modbus налаштування
    MODBUS_PORT = '{port}'
    MODBUS_BAUDRATE = 9600
    MODBUS_BYTESIZE = 8
    MODBUS_PARITY = 'N'
    MODBUS_STOPBITS = 1
    MODBUS_TIMEOUT = 1.0
    MODBUS_UNIT_ID = 1
    
    # Фізичні межі
    VOLTAGE_MAX = 500.0
    TEMP_MAX = 150.0
    ADC_MAX = 4095
    
    # Аварійні пороги
    VOLTAGE_TRIP = 400.0
    VOLTAGE_RESET = 380.0
    TEMP_TRIP = 80.0
    TEMP_RESET = 75.0
    
    # Адреси Modbus (FATEK FBs-MA)
    ADDR_VOLTAGE = 0
    ADDR_BOILER_TEMP = 1
    ADDR_WATER_TEMP = 2
    ADDR_TEMP1 = 3
    ADDR_TEMP2 = 4
    ADDR_OIL_PRESSURE = 5
    ADDR_STEAM_PRESSURE = 6
    
    # Дискретні входи
    ADDR_GAS_SENSOR = 0
    ADDR_VACUUM_SENSOR = 1
    ADDR_OIL_PRESS_OK = 2
    ADDR_STEAM_PRESS_OK = 3
    ADDR_EMERGENCY_STOP = 4
    ADDR_MANUAL_MODE = 5
    
    # Виходи
    ADDR_GAS_VALVE = 0
    ADDR_SOCKET1 = 1
    ADDR_SOCKET2 = 2
    ADDR_WATER_PUMP = 3
    ADDR_OIL_PUMP = 4
    ADDR_ALARM_LIGHT = 5
    ADDR_PERMIT_RUN = 6
    ADDR_FAN_VENT = 7
    
    # Команди
    ADDR_CMD_START = 0
    ADDR_CMD_STOP = 1
    ADDR_CMD_SOCKET1 = 2
    ADDR_CMD_SOCKET2 = 3
    ADDR_CMD_RESET = 4
'''
    
    with open('config.py', 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print("✅ Конфігураційний файл config.py створено")

def create_launcher_script():
    """Створення скрипту запуску"""
    print("\n🚀 Створення скрипту запуску...")
    
    launcher_content = '''#!/bin/bash
# Скрипт запуску контролера бойлера

echo "🔥 Запуск контролера бойлера..."
echo "📊 Логи будуть записуватися в boiler_controller.log"
echo "⏹️ Натисніть Ctrl+C для зупинки"
echo ""

python3 boiler_controller_real.py
'''
    
    with open('run_boiler.sh', 'w') as f:
        f.write(launcher_content)
    
    # Зробити виконуваним
    os.chmod('run_boiler.sh', 0o755)
    print("✅ Скрипт запуску run_boiler.sh створено")

def run_emulator_test():
    """Запуск емуляції для тестування"""
    print("\n🤖 Запуск емуляції для тестування...")
    
    try:
        # Імпортуємо емулятор
        sys.path.append('.')
        from emulate_fatek import FATEK_Emulator
        import threading
        
        # Створюємо емулятор
        emulator = FATEK_Emulator()
        
        def scan_loop():
            while emulator.running:
                emulator.scan_cycle()
                time.sleep(0.1)
        
        # Запускаємо емулятор
        emulator.running = True
        scan_thread = threading.Thread(target=scan_loop, daemon=True)
        scan_thread.start()
        
        print("✅ Емулятор запущено")
        
        # Тестуємо базові функції
        emulator.start_system()
        time.sleep(4)
        
        print("\n📊 Статус емулятора:")
        emulator.print_status()
        
        # Тестуємо аварії
        print("\n⚠️ Тест аварії напруги...")
        emulator.set_voltage(420)
        time.sleep(2)
        
        emulator.set_voltage(360)
        time.sleep(1)
        emulator.reset_alarms()
        
        print("\n🌀 Тест аварії вакууму...")
        emulator.set_vacuum(False)
        time.sleep(2)
        
        emulator.set_vacuum(True)
        time.sleep(1)
        emulator.reset_alarms()
        
        print("\n📊 Фінальний статус:")
        emulator.print_status()
        
        emulator.running = False
        print("✅ Емуляція тестування завершена")
        return True
        
    except Exception as e:
        print(f"❌ Помилка емуляції: {e}")
        return False

def main():
    """Основна функція інсталятора"""
    print("🔥 ІНСТАЛЯТОР КОНТРОЛЕРА БОЙЛЕРА")
    print("="*50)
    
    # Крок 1: Перевірка Python
    if not check_python_version():
        return False
    
    # Крок 2: Встановлення бібліотек
    if not install_requirements():
        return False
    
    # Крок 3: Пошук портів
    ports = find_serial_ports()
    if not ports:
        print("\n⚠️ Порти не знайдено. Можна запустити емуляцію для тестування.")
        choice = input("Запустити емуляцію? (y/n): ").lower()
        if choice == 'y':
            return run_emulator_test()
        return False
    
    # Крок 4: Вибір порту
    print(f"\n🎯 Виберіть порт (1-{len(ports)}):")
    try:
        port_choice = int(input("Номер порту: ")) - 1
        if 0 <= port_choice < len(ports):
            selected_port = ports[port_choice]
        else:
            print("❌ Невірний номер порту")
            return False
    except ValueError:
        print("❌ Невірний ввід")
        return False
    
    # Крок 5: Тестування Modbus
    if not test_modbus_connection(selected_port):
        print("\n⚠️ Modbus не працює. Можна запустити емуляцію для тестування.")
        choice = input("Запустити емуляцію? (y/n): ").lower()
        if choice == 'y':
            return run_emulator_test()
        return False
    
    # Крок 6: Створення конфігурації
    create_config_file(selected_port)
    
    # Крок 7: Створення скрипту запуску
    create_launcher_script()
    
    # Крок 8: Тестування емуляції
    print("\n🧪 Бажаєте протестувати логіку в емуляції? (y/n):")
    choice = input("Вибір: ").lower()
    if choice == 'y':
        run_emulator_test()
    
    # Крок 9: Інструкції
    print("\n" + "="*50)
    print("✅ ІНСТАЛЯЦІЮ ЗАВЕРШЕНО!")
    print("="*50)
    print("\n📋 Далі:")
    print(f"1. Порт: {selected_port}")
    print("2. Конфігурація: config.py")
    print("3. Запуск: ./run_boiler.sh")
    print("4. Логи: boiler_controller.log")
    print("\n⚠️ ПЕРЕД ЗАПУСКОМ:")
    print("- Перевірте підключення датчиків")
    print("- Перевірте налаштування FATEK")
    print("- Протестуйте без навантажень")
    print("\n🚀 Готово до роботи!")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️ Інсталяцію перервано")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Помилка: {e}")
        sys.exit(1)
