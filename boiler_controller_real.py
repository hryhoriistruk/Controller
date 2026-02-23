#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
РЕАЛЬНИЙ КОНТРОЛЕР БОЙЛЕРА НА PYTHON
Для FATEK FBs-MA / Multicont через Modbus RTU
Повноцінна промислова реалізація
"""

import time
import threading
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import serial
from pymodbus.client import ModbusSerialClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder

# ============================================
# КОНФІГУРАЦІЯ СИСТЕМИ
# ============================================

class BoilerConfig:
    """Конфігурація контролера бойлера"""
    
    # Modbus налаштування
    MODBUS_PORT = '/dev/ttyUSB0'  # Змінити на ваш порт
    MODBUS_BAUDRATE = 9600
    MODBUS_BYTESIZE = 8
    MODBUS_PARITY = 'N'
    MODBUS_STOPBITS = 1
    MODBUS_TIMEOUT = 1.0
    MODBUS_UNIT_ID = 1
    
    # Фізичні межі
    VOLTAGE_MAX = 500.0      # Максимальна напруга В
    TEMP_MAX = 150.0         # Максимальна температура °C
    ADC_MAX = 4095           # Максимальне значення АЦП
    
    # Аварійні пороги
    VOLTAGE_TRIP = 400.0     # Аварія напруги В
    VOLTAGE_RESET = 380.0    # Відновлення напруги В
    TEMP_TRIP = 80.0         # Аварія температури °C
    TEMP_RESET = 75.0        # Відновлення температури °C
    
    # Адреси Modbus (для FATEK FBs-MA)
    # Входи (Read)
    ADDR_VOLTAGE = 0         # IW0 - Напруга бойлера
    ADDR_BOILER_TEMP = 1     # IW1 - Температура бойлера
    ADDR_WATER_TEMP = 2      # IW2 - Температура води
    ADDR_TEMP1 = 3           # IW3 - Температура датчик 1
    ADDR_TEMP2 = 4           # IW4 - Температура датчик 2
    ADDR_OIL_PRESSURE = 5    # IW5 - Тиск масла
    ADDR_STEAM_PRESSURE = 6  # IW6 - Тиск пари
    
    # Дискретні входи (Read Coils)
    ADDR_GAS_SENSOR = 0      # IX0.0 - Датчик газу
    ADDR_VACUUM_SENSOR = 1   # IX0.1 - Датчик вакууму
    ADDR_OIL_PRESS_OK = 2    # IX0.2 - Тиск масла OK
    ADDR_STEAM_PRESS_OK = 3  # IX0.3 - Тиск пари OK
    ADDR_EMERGENCY_STOP = 4  # IX0.4 - Аварійний стоп
    ADDR_MANUAL_MODE = 5     # IX0.5 - Ручний режим
    
    # Виходи (Write Coils)
    ADDR_GAS_VALVE = 0       # QX0.0 - Клапан газу
    ADDR_SOCKET1 = 1         # QX0.1 - Розетка 1
    ADDR_SOCKET2 = 2         # QX0.2 - Розетка 2
    ADDR_WATER_PUMP = 3      # QX0.3 - Насос води
    ADDR_OIL_PUMP = 4        # QX0.4 - Насос масла
    ADDR_ALARM_LIGHT = 5     # QX0.5 - Аварійна лампа
    ADDR_PERMIT_RUN = 6      # QX0.6 - Дозвіл роботи
    ADDR_FAN_VENT = 7        # QX0.7 - Вентиляція
    
    # Команди (Write Coils)
    ADDR_CMD_START = 0       # MX0.0 - Старт системи
    ADDR_CMD_STOP = 1        # MX0.1 - Стоп системи
    ADDR_CMD_SOCKET1 = 2     # MX0.2 - Команда розетка 1
    ADDR_CMD_SOCKET2 = 3     # MX0.3 - Команда розетка 2
    ADDR_CMD_RESET = 4       # MX0.4 - Скидання аварій

# ============================================
# ОСНОВНИЙ КЛАС КОНТРОЛЕРА
# ============================================

class BoilerController:
    """Основний клас контролера бойлера"""
    
    def __init__(self, config: BoilerConfig):
        self.config = config
        self.logger = self._setup_logging()
        
        # Modbus клієнт
        self.modbus_client = None
        
        # Стан системи
        self.running = False
        self.scan_count = 0
        self.last_scan_time = time.time()
        
        # Датчики
        self.sensors = {
            'voltage': 0.0,
            'boiler_temp': 0.0,
            'water_temp': 0.0,
            'temp1': 0.0,
            'temp2': 0.0,
            'oil_pressure': 0.0,
            'steam_pressure': 0.0,
            'gas_present': False,
            'vacuum_present': False,
            'oil_pressure_ok': False,
            'steam_pressure_ok': False,
            'emergency_stop': False,
            'manual_mode': False
        }
        
        # Виходи
        self.outputs = {
            'gas_valve': False,
            'socket1': False,
            'socket2': False,
            'water_pump': False,
            'oil_pump': False,
            'alarm_light': False,
            'permit_run': False,
            'fan_vent': False
        }
        
        # Команди
        self.commands = {
            'start': False,
            'stop': False,
            'socket1': False,
            'socket2': False,
            'reset': False
        }
        
        # Аварійні флаги
        self.alarms = {
            'voltage_high': False,
            'temp_high': False,
            'no_gas': False,
            'no_vacuum': False,
            'oil_pressure_low': False,
            'steam_pressure_bad': False,
            'emergency': False,
            'any_alarm': False
        }
        
        # Стан системи
        self.system_state = {
            'enabled': False,
            'running': False,
            'ready': False,
            'stable': False
        }
        
        # Статистика
        self.stats = {
            'starts': 0,
            'stops': 0,
            'alarms': 0,
            'gas_failures': 0,
            'vacuum_failures': 0,
            'runtime_seconds': 0,
            'last_start_time': None
        }
        
        # Таймери та затримки
        self.timers = {
            'startup_delay': 0.0,
            'gas_valve_delay': 0.0,
            'emergency_delay': 0.0,
            'watchdog': 0.0
        }
        
        # Флаги для детекторів фронтів
        self.edge_detectors = {
            'start_old': False,
            'stop_old': False,
            'gas_old': False,
            'vacuum_old': False,
            'alarm_old': False
        }
        
        # Фільтри для сигналів
        self.filters = {
            'voltage': [],
            'temperature': []
        }
        
        # Потік виконання
        self.control_thread = None
        self.stop_event = threading.Event()

    def _setup_logging(self) -> logging.Logger:
        """Налаштування логування"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('boiler_controller.log'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)

    def connect_modbus(self) -> bool:
        """Підключення до Modbus пристрою"""
        try:
            self.modbus_client = ModbusSerialClient(
                port=self.config.MODBUS_PORT,
                baudrate=self.config.MODBUS_BAUDRATE,
                bytesize=self.config.MODBUS_BYTESIZE,
                parity=self.config.MODBUS_PARITY,
                stopbits=self.config.MODBUS_STOPBITS,
                timeout=self.config.MODBUS_TIMEOUT
            )
            
            if self.modbus_client.connect():
                self.logger.info(f"✅ Підключено до Modbus на {self.config.MODBUS_PORT}")
                return True
            else:
                self.logger.error("❌ Не вдалося підключитися до Modbus")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Помилка підключення Modbus: {e}")
            return False

    def disconnect_modbus(self):
        """Відключення від Modbus"""
        if self.modbus_client:
            self.modbus_client.close()
            self.logger.info("🔌 Відключено від Modbus")

    def read_sensors(self) -> bool:
        """Читання всіх датчиків"""
        try:
            # Читання аналогових входів (Holding Registers)
            result = self.modbus_client.read_holding_registers(
                self.config.ADDR_VOLTAGE, 7, unit=self.config.MODBUS_UNIT_ID
            )
            
            if result.isError():
                self.logger.error("❌ Помилка читання аналогових входів")
                return False
            
            # Конвертація АЦП у фізичні величини
            self.sensors['voltage'] = result.registers[0] * self.config.VOLTAGE_MAX / self.config.ADC_MAX
            self.sensors['boiler_temp'] = result.registers[1] * self.config.TEMP_MAX / self.config.ADC_MAX
            self.sensors['water_temp'] = result.registers[2] * self.config.TEMP_MAX / self.config.ADC_MAX
            self.sensors['temp1'] = result.registers[3] * self.config.TEMP_MAX / self.config.ADC_MAX
            self.sensors['temp2'] = result.registers[4] * self.config.TEMP_MAX / self.config.ADC_MAX
            self.sensors['oil_pressure'] = result.registers[5] * 100.0 / self.config.ADC_MAX
            self.sensors['steam_pressure'] = result.registers[6] * 10.0 / self.config.ADC_MAX
            
            # Читання дискретних входів (Coils)
            result = self.modbus_client.read_coils(
                self.config.ADDR_GAS_SENSOR, 6, unit=self.config.MODBUS_UNIT_ID
            )
            
            if result.isError():
                self.logger.error("❌ Помилка читання дискретних входів")
                return False
            
            self.sensors['gas_present'] = result.bits[0]
            self.sensors['vacuum_present'] = result.bits[1]
            self.sensors['oil_pressure_ok'] = result.bits[2]
            self.sensors['steam_pressure_ok'] = result.bits[3]
            self.sensors['emergency_stop'] = result.bits[4]
            self.sensors['manual_mode'] = result.bits[5]
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Помилка читання датчиків: {e}")
            return False

    def write_outputs(self) -> bool:
        """Запис виходів"""
        try:
            # Формування масиву виходів
            output_bits = [
                self.outputs['gas_valve'],
                self.outputs['socket1'],
                self.outputs['socket2'],
                self.outputs['water_pump'],
                self.outputs['oil_pump'],
                self.outputs['alarm_light'],
                self.outputs['permit_run'],
                self.outputs['fan_vent']
            ]
            
            result = self.modbus_client.write_coils(
                self.config.ADDR_GAS_VALVE, output_bits, unit=self.config.MODBUS_UNIT_ID
            )
            
            if result.isError():
                self.logger.error("❌ Помилка запису виходів")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Помилка запису виходів: {e}")
            return False

    def read_commands(self) -> bool:
        """Читання команд з HMI"""
        try:
            result = self.modbus_client.read_coils(
                self.config.ADDR_CMD_START, 5, unit=self.config.MODBUS_UNIT_ID
            )
            
            if result.isError():
                self.logger.error("❌ Помилка читання команд")
                return False
            
            self.commands['start'] = result.bits[0]
            self.commands['stop'] = result.bits[1]
            self.commands['socket1'] = result.bits[2]
            self.commands['socket2'] = result.bits[3]
            self.commands['reset'] = result.bits[4]
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Помилка читання команд: {e}")
            return False

    def apply_filters(self):
        """Застосування фільтрів до сигналів"""
        # Фільтр ковзного середнього для напруги
        self.filters['voltage'].append(self.sensors['voltage'])
        if len(self.filters['voltage']) > 5:
            self.filters['voltage'].pop(0)
        
        if len(self.filters['voltage']) > 0:
            self.sensors['voltage'] = sum(self.filters['voltage']) / len(self.filters['voltage'])
        
        # Фільтр ковзного середнього для температури
        self.filters['temperature'].append(self.sensors['boiler_temp'])
        if len(self.filters['temperature']) > 5:
            self.filters['temperature'].pop(0)
        
        if len(self.filters['temperature']) > 0:
            self.sensors['boiler_temp'] = sum(self.filters['temperature']) / len(self.filters['temperature'])

    def check_alarms(self):
        """Перевірка аварійних умов"""
        old_alarm = self.alarms['any_alarm']
        
        # Аварія високої напруги
        if self.sensors['voltage'] >= self.config.VOLTAGE_TRIP:
            self.alarms['voltage_high'] = True
        elif self.sensors['voltage'] < self.config.VOLTAGE_RESET:
            self.alarms['voltage_high'] = False
        
        # Аварія високої температури
        if self.sensors['boiler_temp'] >= self.config.TEMP_TRIP:
            self.alarms['temp_high'] = True
        elif self.sensors['boiler_temp'] < self.config.TEMP_RESET:
            self.alarms['temp_high'] = False
        
        # Аварії по датчиках
        self.alarms['no_gas'] = not self.sensors['gas_present']
        self.alarms['no_vacuum'] = not self.sensors['vacuum_present']
        self.alarms['oil_pressure_low'] = not self.sensors['oil_pressure_ok']
        self.alarms['steam_pressure_bad'] = not self.sensors['steam_pressure_ok']
        self.alarms['emergency'] = self.sensors['emergency_stop']
        
        # Загальна аварія
        self.alarms['any_alarm'] = (
            self.alarms['voltage_high'] or
            self.alarms['temp_high'] or
            self.alarms['no_gas'] or
            self.alarms['no_vacuum'] or
            self.alarms['oil_pressure_low'] or
            self.alarms['steam_pressure_bad'] or
            self.alarms['emergency']
        )
        
        # Лічильник аварій
        if self.alarms['any_alarm'] and not old_alarm:
            self.stats['alarms'] += 1
            self.logger.warning(f"🚨 АВАРІЯ! Код: {self.get_alarm_code()}")

    def get_alarm_code(self) -> int:
        """Отримати код аварії"""
        if self.alarms['voltage_high']:
            return 1
        elif self.alarms['temp_high']:
            return 2
        elif self.alarms['no_gas']:
            return 3
        elif self.alarms['no_vacuum']:
            return 4
        elif self.alarms['oil_pressure_low']:
            return 5
        elif self.alarms['steam_pressure_bad']:
            return 6
        elif self.alarms['emergency']:
            return 7
        else:
            return 0

    def handle_start_stop_logic(self):
        """Обробка логіки старт/стоп"""
        current_time = time.time()
        
        # Детектор фронту старту
        if self.commands['start'] and not self.edge_detectors['start_old']:
            if not self.system_state['running'] and not self.alarms['any_alarm']:
                self.system_state['enabled'] = True
                self.timers['startup_delay'] = current_time + 3.0  # 3 секунди затримка
                self.logger.info("▶️ Команда старт отримана")
        
        # Детектор фронту стопу
        if self.commands['stop'] and not self.edge_detectors['stop_old']:
            self.system_state['enabled'] = False
            self.system_state['running'] = False
            self.logger.info("⏹️ Команда стоп отримана")
        
        # Оновлення детекторів
        self.edge_detectors['start_old'] = self.commands['start']
        self.edge_detectors['stop_old'] = self.commands['stop']
        
        # Автоматичний стоп при аварії
        if self.alarms['any_alarm']:
            self.system_state['enabled'] = False
            self.system_state['running'] = False
        
        # Запуск після затримки
        if (self.system_state['enabled'] and 
            current_time >= self.timers['startup_delay'] and 
            not self.system_state['running']):
            self.system_state['running'] = True
            self.stats['starts'] += 1
            self.stats['last_start_time'] = current_time
            self.logger.info("✅ Система запущена")

    def update_system_ready(self):
        """Оновлення стану готовності системи"""
        self.system_state['ready'] = (
            not self.alarms['voltage_high'] and
            not self.alarms['temp_high'] and
            self.sensors['gas_present'] and
            self.sensors['vacuum_present'] and
            self.sensors['oil_pressure_ok'] and
            self.sensors['steam_pressure_ok'] and
            not self.sensors['emergency_stop'] and
            self.system_state['running']
        )

    def control_gas_valve(self):
        """Керування газовим клапаном"""
        current_time = time.time()
        
        # Головна логіка
        if self.system_state['ready']:
            if current_time >= self.timers['gas_valve_delay']:
                self.outputs['gas_valve'] = True
        else:
            self.outputs['gas_valve'] = False
            self.timers['gas_valve_delay'] = current_time + 2.0  # 2 секунди затримка
        
        # ПРІОРИТЕТНИЙ ЗАХИСТ: Вакуум важливіший за все!
        if not self.sensors['vacuum_present']:
            self.outputs['gas_valve'] = False
            self.logger.warning("🚨 ВАКУУМ ВТРАЧЕНО! ГАЗ ЗАКРИТО!")

    def control_sockets(self):
        """Керування розетками"""
        self.outputs['socket1'] = self.commands['socket1'] and not self.alarms['any_alarm']
        self.outputs['socket2'] = self.commands['socket2'] and not self.alarms['any_alarm']

    def control_pumps(self):
        """Керування насосами"""
        self.outputs['water_pump'] = (
            self.system_state['ready'] and 
            self.sensors['water_temp'] > 20.0
        )
        
        self.outputs['oil_pump'] = (
            self.system_state['ready'] and 
            self.sensors['oil_pressure_ok']
        )
        
        self.outputs['fan_vent'] = self.system_state['running']

    def update_indicators(self):
        """Оновлення індикаторів"""
        self.outputs['alarm_light'] = self.alarms['any_alarm']
        self.outputs['permit_run'] = self.system_state['ready']

    def update_statistics(self):
        """Оновлення статистики"""
        # Лічильники відмов
        if not self.sensors['gas_present'] and self.edge_detectors['gas_old']:
            self.stats['gas_failures'] += 1
        
        if not self.sensors['vacuum_present'] and self.edge_detectors['vacuum_old']:
            self.stats['vacuum_failures'] += 1
        
        # Оновлення детекторів
        self.edge_detectors['gas_old'] = self.sensors['gas_present']
        self.edge_detectors['vacuum_old'] = self.sensors['vacuum_present']
        self.edge_detectors['alarm_old'] = self.alarms['any_alarm']
        
        # Час роботи
        if self.system_state['running']:
            self.stats['runtime_seconds'] += 1

    def scan_cycle(self):
        """Основний цикл сканування"""
        try:
            # Читання вхідних даних
            if not self.read_sensors():
                return
            
            if not self.read_commands():
                return
            
            # Фільтрація сигналів
            self.apply_filters()
            
            # Перевірка аварій
            self.check_alarms()
            
            # Обробка команд старт/стоп
            self.handle_start_stop_logic()
            
            # Оновлення стану готовності
            self.update_system_ready()
            
            # Керування виходами
            self.control_gas_valve()
            self.control_sockets()
            self.control_pumps()
            self.update_indicators()
            
            # Запис виходів
            self.write_outputs()
            
            # Оновлення статистики
            self.update_statistics()
            
            self.scan_count += 1
            self.last_scan_time = time.time()
            
        except Exception as e:
            self.logger.error(f"❌ Помилка в циклі сканування: {e}")

    def control_loop(self):
        """Основний цикл управління"""
        self.logger.info("🔄 Цикл управління запущено")
        
        while not self.stop_event.is_set():
            start_time = time.time()
            
            try:
                self.scan_cycle()
                
                # Логування стану кожні 100 циклів
                if self.scan_count % 100 == 0:
                    self.log_status()
                
            except Exception as e:
                self.logger.error(f"❌ Помилка в циклі управління: {e}")
            
            # Розрахунок часу циклу
            cycle_time = time.time() - start_time
            if cycle_time < 0.1:  # 100 мс мінімальний час циклу
                time.sleep(0.1 - cycle_time)
        
        self.logger.info("⏹️ Цикл управління зупинено")

    def log_status(self):
        """Логування стану системи"""
        self.logger.info(
            f"🔄 Цикл #{self.scan_count} | "
            f"⚡{self.sensors['voltage']:.1f}В | "
            f"🌡️{self.sensors['boiler_temp']:.1f}°C | "
            f"🔥{'✅' if self.sensors['gas_present'] else '❌'} | "
            f"🌀{'✅' if self.sensors['vacuum_present'] else '❌'} | "
            f"▶️{'✅' if self.system_state['running'] else '❌'} | "
            f"🔵{'✅' if self.outputs['gas_valve'] else '❌'}"
        )

    def start(self):
        """Запуск контролера"""
        if self.running:
            self.logger.warning("⚠️ Контролер вже працює")
            return
        
        if not self.connect_modbus():
            self.logger.error("❌ Не вдалося підключитися до Modbus")
            return
        
        self.running = True
        self.stop_event.clear()
        
        self.control_thread = threading.Thread(target=self.control_loop, daemon=True)
        self.control_thread.start()
        
        self.logger.info("🚀 Контролер бойлера запущено")

    def stop(self):
        """Зупинка контролера"""
        if not self.running:
            return
        
        self.running = False
        self.stop_event.set()
        
        if self.control_thread:
            self.control_thread.join(timeout=5.0)
        
        # Відключення всіх виходів
        for key in self.outputs:
            self.outputs[key] = False
        self.write_outputs()
        
        self.disconnect_modbus()
        
        self.logger.info("⏹️ Контролер бойлера зупинено")

    def get_status(self) -> Dict[str, Any]:
        """Отримати повний статус системи"""
        return {
            'scan_count': self.scan_count,
            'sensors': self.sensors.copy(),
            'outputs': self.outputs.copy(),
            'alarms': self.alarms.copy(),
            'system_state': self.system_state.copy(),
            'stats': self.stats.copy(),
            'alarm_code': self.get_alarm_code()
        }

# ============================================
# ТОЧКА ВХОДУ ПРОГРАМИ
# ============================================

def main():
    """Основна функція"""
    print("🔥 КОНТРОЛЕР БОЙЛЕРА НА PYTHON")
    print("="*50)
    
    # Створення конфігурації
    config = BoilerConfig()
    
    # Створення контролера
    controller = BoilerController(config)
    
    try:
        # Запуск контролера
        controller.start()
        
        print("✅ Контролер запущено. Натисніть Ctrl+C для зупинки.")
        print("📊 Статус можна перевірити в файлі boiler_controller.log")
        
        # Основний цикл програми
        while True:
            time.sleep(10)  # Оновлення статусу кожні 10 секунд
            
            # Можна додати додаткову логіку тут
            
    except KeyboardInterrupt:
        print("\n⏹️ Отримано сигнал зупинки")
    except Exception as e:
        print(f"❌ Помилка: {e}")
    finally:
        controller.stop()
        print("✅ Програма завершена")

if __name__ == "__main__":
    main()
