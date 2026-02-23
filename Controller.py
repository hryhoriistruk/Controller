#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================
КЕРУВАННЯ БОЙЛЕРОМ / ГАЗОВИМ ОБЛАДНАННЯМ
Python-емуляція логіки контролера FATEK FBs-MA
Повністю готовий до запуску код
============================================
"""

import time
import threading
import random
from datetime import datetime
from typing import Dict, Any, Optional

# ============================================
# КОНСТАНТИ
# ============================================
ADC_MAX = 4095
NAPRUGA_MAX = 500      # Вольт (макс. діапазон)
TEMP_MAX = 150         # °C (макс. діапазон)

# Межі спрацьовування аварій
NAPRUGA_AVAR_VOLT = 400    # Аварія напруги при 400В
NAPRUGA_HYST_VOLT = 380    # Гістерезис: скидання при 380В
TEMP_AVAR_GRAD = 80        # Аварія температури при 80°C
TEMP_HYST_GRAD = 75        # Гістерезис: скидання при 75°C

# Інтервал оновлення (секунди) - емуляція часу скану PLC
SCAN_INTERVAL = 0.1        # 100 мс

# ============================================
# КЛАСИ ДЛЯ ЕМУЛЯЦІЇ ВХОДІВ/ВИХОДІВ
# ============================================

class AnalogInput:
    """Емуляція аналогового входу 0..4095"""
    def __init__(self, name: str, initial_value: int = 0):
        self.name = name
        self._value = max(0, min(ADC_MAX, initial_value))
        self._lock = threading.Lock()

    @property
    def value(self) -> int:
        with self._lock:
            return self._value

    @value.setter
    def value(self, new_value: int):
        with self._lock:
            self._value = max(0, min(ADC_MAX, new_value))

    def read(self) -> int:
        """Читання значення (сумісність з PLC-стилем)"""
        return self.value

    def set_value(self, value: int):
        """Встановлення значення (для тестування)"""
        self.value = value

    def adc_to_physical(self, max_physical: int) -> int:
        """Перерахунок АЦП у фізичну величину"""
        return self.value * max_physical // ADC_MAX


class DigitalInput:
    """Емуляція дискретного входу (True/False)"""
    def __init__(self, name: str, initial_state: bool = False):
        self.name = name
        self._state = initial_state
        self._lock = threading.Lock()

    @property
    def state(self) -> bool:
        with self._lock:
            return self._state

    @state.setter
    def state(self, new_state: bool):
        with self._lock:
            self._state = new_state

    def read(self) -> bool:
        """Читання стану"""
        return self.state

    def set_state(self, state: bool):
        """Встановлення стану (для тестування)"""
        self.state = state


class DigitalOutput:
    """Емуляція дискретного виходу (True/False)"""
    def __init__(self, name: str, initial_state: bool = False):
        self.name = name
        self._state = initial_state
        self._lock = threading.Lock()

    @property
    def state(self) -> bool:
        with self._lock:
            return self._state

    @state.setter
    def state(self, new_state: bool):
        with self._lock:
            self._state = new_state

    def write(self, state: bool):
        """Запис стану"""
        self.state = state

    def read(self) -> bool:
        """Читання стану"""
        return self.state


# ============================================
# ОСНОВНИЙ КЛАС КОНТРОЛЕРА
# ============================================

class BoilerController:
    """
    Головний клас контролера керування бойлером
    Повна емуляція логіки FATEK FBs-MA
    """

    def __init__(self):
        # ============================================
        # ІНІЦІАЛІЗАЦІЯ ВХОДІВ
        # ============================================

        # Аналогові входи (емуляція AT %IW0..%IW4)
        self.AI_NAPRUGA = AnalogInput("Напруга бойлера", 2000)      # AI0
        self.AI_TEMP_BOILER = AnalogInput("Температура бойлера", 1500)  # AI1
        self.AI_TEMP_VODA = AnalogInput("Температура води", 1000)   # AI2
        self.AI_TEMP_2 = AnalogInput("Додаткова температура", 800)  # AI3
        self.AI_TISK_MASLA = AnalogInput("Тиск масла", 2000)        # AI4

        # Дискретні входи (емуляція AT %IX0.0..%IX0.3)
        self.X_GAZ = DigitalInput("Газ", True)           # X0: Датчик газу
        self.X_VAKUUM = DigitalInput("Вакуум", True)     # X1: Датчик вакууму
        self.X_TISK_MASLA_DI = DigitalInput("Тиск масла DI", True)  # X2: Тиск масла дискретний
        self.X_AVARIA_EXT = DigitalInput("Аварія зовнішня", False)  # X3: Зовнішній стоп

        # Команди з HMI (емуляція AT %MX10.0..%MX10.3)
        self.CMD_ROZET_1 = DigitalInput("Команда розетка 1", False)  # MX10.0
        self.CMD_ROZET_2 = DigitalInput("Команда розетка 2", False)  # MX10.1
        self.CMD_START = DigitalInput("Старт", False)                # MX10.2
        self.CMD_STOP = DigitalInput("Стоп", False)                  # MX10.3

        # ============================================
        # ІНІЦІАЛІЗАЦІЯ ВИХОДІВ
        # ============================================

        # Дискретні виходи (емуляція AT %QX0.0..%QX0.4)
        self.Y_KLAPAN_GAZ = DigitalOutput("Клапан газу", False)     # Y0
        self.Y_ROZET_1 = DigitalOutput("Розетка 1", False)          # Y1
        self.Y_ROZET_2 = DigitalOutput("Розетка 2", False)          # Y2
        self.Y_AVARIA_SIGNAL = DigitalOutput("Сигнал аварії", False)  # Y3
        self.Y_DOZV_ROBOTY = DigitalOutput("Дозвіл роботи", False)  # Y4

        # ============================================
        # ВНУТРІШНІ МАРКЕРИ
        # ============================================

        self.M_AVARIA_NAPRUGA = False    # Аварія напруги
        self.M_AVARIA_TEMP = False       # Аварія температури
        self.M_GAZ_IE = False             # Газ є
        self.M_VAKUUM_IE = False          # Вакуум є
        self.M_TISK_NORMA = False         # Тиск масла в нормі
        self.M_AVARIA_VAKUUM = False      # Аварія вакууму
        self.M_SYSTEM_READY = False       # Система готова
        self.M_ZAGALNA_AVARIA = False     # Загальна аварія
        self.M_SYSTEM_ON = False          # Система запущена

        # Фізичні величини (для відображення)
        self.NAPRUGA_VOLT = 0              # Напруга у Вольтах
        self.TEMP_BOILER_GRAD = 0          # Температура бойлера °C
        self.TEMP_VODA_GRAD = 0            # Температура води °C
        self.TEMP_2_GRAD = 0                # Додаткова температура °C

        # Лічильник циклів
        self.scan_count = 0

        # Статистика
        self.stats = {
            'starts': 0,
            'stops': 0,
            'alarms': 0,
            'gas_off_count': 0,
            'vakuum_off_count': 0
        }

        # Флаг роботи
        self.running = False
        self.scan_thread = None

    # ============================================
    # БЛОК 1: ПЕРЕРАХУНОК АЦП → РЕАЛЬНІ ОДИНИЦІ
    # ============================================
    def _update_physical_values(self):
        """Оновлення фізичних величин з АЦП"""
        self.NAPRUGA_VOLT = self.AI_NAPRUGA.adc_to_physical(NAPRUGA_MAX)
        self.TEMP_BOILER_GRAD = self.AI_TEMP_BOILER.adc_to_physical(TEMP_MAX)
        self.TEMP_VODA_GRAD = self.AI_TEMP_VODA.adc_to_physical(TEMP_MAX)
        self.TEMP_2_GRAD = self.AI_TEMP_2.adc_to_physical(TEMP_MAX)

    # ============================================
    # БЛОК 2: АВАРІЯ ПО НАПРУЗІ
    # ============================================
    def _check_voltage_alarm(self):
        """Перевірка аварії по напрузі з гістерезисом"""
        if self.NAPRUGA_VOLT >= NAPRUGA_AVAR_VOLT:
            if not self.M_AVARIA_NAPRUGA:
                print(f"⚠️ АВАРІЯ: Напруга {self.NAPRUGA_VOLT}В перевищила {NAPRUGA_AVAR_VOLT}В")
            self.M_AVARIA_NAPRUGA = True
        else:
            if self.NAPRUGA_VOLT < NAPRUGA_HYST_VOLT and self.M_AVARIA_NAPRUGA:
                print(f"✅ Напруга {self.NAPRUGA_VOLT}В повернулася в норму")
                self.M_AVARIA_NAPRUGA = False

    # ============================================
    # БЛОК 3: АВАРІЯ ПО ТЕМПЕРАТУРІ
    # ============================================
    def _check_temperature_alarm(self):
        """Перевірка аварії по температурі з гістерезисом"""
        if self.TEMP_BOILER_GRAD >= TEMP_AVAR_GRAD:
            if not self.M_AVARIA_TEMP:
                print(f"⚠️ АВАРІЯ: Температура {self.TEMP_BOILER_GRAD}°C перевищила {TEMP_AVAR_GRAD}°C")
            self.M_AVARIA_TEMP = True
        else:
            if self.TEMP_BOILER_GRAD < TEMP_HYST_GRAD and self.M_AVARIA_TEMP:
                print(f"✅ Температура {self.TEMP_BOILER_GRAD}°C повернулася в норму")
                self.M_AVARIA_TEMP = False

    # ============================================
    # БЛОК 4: ДАТЧИКИ ГАЗУ ТА ВАКУУМУ
    # ============================================
    def _check_gas_and_vakuum(self):
        """Перевірка датчиків газу та вакууму"""
        # Датчик газу
        old_gaz = self.M_GAZ_IE
        self.M_GAZ_IE = self.X_GAZ.read()
        if old_gaz != self.M_GAZ_IE:
            print(f"{'✅' if self.M_GAZ_IE else '❌'} Газ: {'Є' if self.M_GAZ_IE else 'НЕМАЄ'}")
            if not self.M_GAZ_IE:
                self.stats['gas_off_count'] += 1

        # Датчик вакууму
        old_vakuum = self.M_VAKUUM_IE
        self.M_VAKUUM_IE = self.X_VAKUUM.read()
        if old_vakuum != self.M_VAKUUM_IE:
            print(f"{'✅' if self.M_VAKUUM_IE else '❌'} Вакуум: {'Є' if self.M_VAKUUM_IE else 'НЕМАЄ'}")
            if not self.M_VAKUUM_IE:
                self.stats['vakuum_off_count'] += 1
                self.M_AVARIA_VAKUUM = True
            else:
                self.M_AVARIA_VAKUUM = False

    # ============================================
    # БЛОК 5: ТИСК МАСЛА
    # ============================================
    def _check_oil_pressure(self):
        """Перевірка тиску масла"""
        old_tisk = self.M_TISK_NORMA
        self.M_TISK_NORMA = self.X_TISK_MASLA_DI.read()
        if old_tisk != self.M_TISK_NORMA:
            print(f"{'✅' if self.M_TISK_NORMA else '❌'} Тиск масла: {'НОРМА' if self.M_TISK_NORMA else 'АВАРІЯ'}")

    # ============================================
    # БЛОК 6: ЗАГАЛЬНА АВАРІЯ
    # ============================================
    def _update_general_alarm(self):
        """Оновлення стану загальної аварії"""
        old_alarm = self.M_ZAGALNA_AVARIA
        self.M_ZAGALNA_AVARIA = (
                self.M_AVARIA_NAPRUGA or
                self.M_AVARIA_TEMP or
                self.M_AVARIA_VAKUUM or
                not self.M_TISK_NORMA or
                self.X_AVARIA_EXT.read()
        )

        if old_alarm != self.M_ZAGALNA_AVARIA:
            if self.M_ZAGALNA_AVARIA:
                print("🚨 ЗАГАЛЬНА АВАРІЯ АКТИВОВАНА!")
                self.stats['alarms'] += 1
            else:
                print("✅ Загальна аварія скинута")

    # ============================================
    # БЛОК 7: ЛОГІКА СТАРТ/СТОП
    # ============================================
    def _handle_start_stop(self):
        """Обробка команд старт/стоп"""
        # Старт системи
        if self.CMD_START.read() and not self.M_SYSTEM_ON and not self.M_ZAGALNA_AVARIA:
            self.M_SYSTEM_ON = True
            print("▶️ СИСТЕМА ЗАПУЩЕНА")
            self.stats['starts'] += 1

        # Стоп системи
        if self.CMD_STOP.read() or self.M_ZAGALNA_AVARIA:
            if self.M_SYSTEM_ON:
                self.M_SYSTEM_ON = False
                print("⏹️ СИСТЕМА ЗУПИНЕНА")
                self.stats['stops'] += 1

    # ============================================
    # БЛОК 8: ГОТОВНІСТЬ СИСТЕМИ
    # ============================================
    def _update_system_ready(self):
        """Оновлення стану готовності системи"""
        old_ready = self.M_SYSTEM_READY
        self.M_SYSTEM_READY = (
                not self.M_AVARIA_NAPRUGA and
                not self.M_AVARIA_TEMP and
                self.M_GAZ_IE and
                self.M_VAKUUM_IE and
                self.M_TISK_NORMA and
                not self.X_AVARIA_EXT.read() and
                self.M_SYSTEM_ON
        )

        if old_ready != self.M_SYSTEM_READY:
            print(f"{'✅' if self.M_SYSTEM_READY else '⏸️'} Система {'ГОТОВА' if self.M_SYSTEM_READY else 'НЕ ГОТОВА'}")

    # ============================================
    # БЛОК 9: КЕРУВАННЯ КЛАПАНОМ ГАЗУ
    # ============================================
    def _control_gas_valve(self):
        """Керування клапаном газу"""
        should_open = self.M_SYSTEM_READY

        # Додаткова гарантія безпеки
        if not self.M_VAKUUM_IE:
            should_open = False

        old_state = self.Y_KLAPAN_GAZ.read()
        self.Y_KLAPAN_GAZ.write(should_open)

        if old_state != should_open:
            print(f"{'🔵' if should_open else '⚫'} Клапан газу: {'ВІДКРИТО' if should_open else 'ЗАКРИТО'}")

    # ============================================
    # БЛОК 10: КЕРУВАННЯ РОЗЕТКАМИ
    # ============================================
    def _control_sockets(self):
        """Керування розетками"""
        # Розетка 1
        old_rozet1 = self.Y_ROZET_1.read()
        new_rozet1 = self.CMD_ROZET_1.read() and not self.M_ZAGALNA_AVARIA
        self.Y_ROZET_1.write(new_rozet1)

        if old_rozet1 != new_rozet1:
            print(f"{'🔌' if new_rozet1 else '⭕'} Розетка 1: {'УВІМК' if new_rozet1 else 'ВИМК'}")

        # Розетка 2
        old_rozet2 = self.Y_ROZET_2.read()
        new_rozet2 = self.CMD_ROZET_2.read() and not self.M_ZAGALNA_AVARIA
        self.Y_ROZET_2.write(new_rozet2)

        if old_rozet2 != new_rozet2:
            print(f"{'🔌' if new_rozet2 else '⭕'} Розетка 2: {'УВІМК' if new_rozet2 else 'ВИМК'}")

    # ============================================
    # БЛОК 11: АВАРІЙНА СИГНАЛІЗАЦІЯ
    # ============================================
    def _control_alarm_signal(self):
        """Керування аварійною сигналізацією"""
        self.Y_AVARIA_SIGNAL.write(self.M_ZAGALNA_AVARIA)

    # ============================================
    # БЛОК 12: ЗАГАЛЬНИЙ ДОЗВІЛ РОБОТИ
    # ============================================
    def _control_operation_permit(self):
        """Керування загальним дозволом роботи"""
        self.Y_DOZV_ROBOTY.write(self.M_SYSTEM_READY)

    # ============================================
    # ГОЛОВНИЙ ЦИКЛ СКАНУВАННЯ
    # ============================================
    def scan_cycle(self):
        """
        Один цикл виконання програми (емуляція скану PLC)
        Викликається періодично з інтервалом SCAN_INTERVAL
        """
        # 1. Оновлення фізичних величин
        self._update_physical_values()

        # 2. Перевірка аварій
        self._check_voltage_alarm()
        self._check_temperature_alarm()

        # 3. Перевірка датчиків
        self._check_gas_and_vakuum()
        self._check_oil_pressure()

        # 4. Оновлення стану аварій
        self._update_general_alarm()

        # 5. Обробка команд старт/стоп
        self._handle_start_stop()

        # 6. Оновлення готовності
        self._update_system_ready()

        # 7. Керування виконавчими механізмами
        self._control_gas_valve()
        self._control_sockets()
        self._control_alarm_signal()
        self._control_operation_permit()

        # 8. Збільшення лічильника
        self.scan_count += 1

    # ============================================
    # ЗАПУСК ЦИКЛІЧНОГО СКАНУВАННЯ
    # ============================================
    def start(self):
        """Запуск циклічного сканування в окремому потоці"""
        if self.running:
            print("⚠️ Контролер вже працює")
            return

        self.running = True
        self.scan_thread = threading.Thread(target=self._run_scan_loop, daemon=True)
        self.scan_thread.start()
        print("🚀 Контролер запущено (цикл сканування активний)")

    def _run_scan_loop(self):
        """Внутрішній цикл сканування"""
        while self.running:
            self.scan_cycle()
            time.sleep(SCAN_INTERVAL)

    def stop(self):
        """Зупинка контролера"""
        self.running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=1.0)
        print("⏹️ Контролер зупинено")

    # ============================================
    # ВІДОБРАЖЕННЯ СТАНУ
    # ============================================
    def print_status(self):
        """Виведення поточного стану системи"""
        print("\n" + "="*60)
        print(f"📊 СТАН СИСТЕМИ (цикл #{self.scan_count})")
        print(f"⏱️  Час: {datetime.now().strftime('%H:%M:%S')}")
        print("-"*60)
        print(f"⚡ Напруга:          {self.NAPRUGA_VOLT:4d} В")
        print(f"🌡️  Темп. бойлера:   {self.TEMP_BOILER_GRAD:3d}°C")
        print(f"💧 Темп. води:       {self.TEMP_VODA_GRAD:3d}°C")
        print(f"🌡️  Темп. додаткова: {self.TEMP_2_GRAD:3d}°C")
        print("-"*60)
        print(f"🔥 Газ:               {'Є' if self.M_GAZ_IE else 'НЕМАЄ'}")
        print(f"🌀 Вакуум:            {'Є' if self.M_VAKUUM_IE else 'НЕМАЄ'}")
        print(f"⛽ Тиск масла:        {'НОРМА' if self.M_TISK_NORMA else 'АВАРІЯ'}")
        print("-"*60)
        print(f"⚠️  Аварія напруги:   {'ТАК' if self.M_AVARIA_NAPRUGA else 'НІ'}")
        print(f"⚠️  Аварія температури: {'ТАК' if self.M_AVARIA_TEMP else 'НІ'}")
        print(f"⚠️  Аварія вакууму:   {'ТАК' if self.M_AVARIA_VAKUUM else 'НІ'}")
        print(f"🚨 Загальна аварія:   {'ТАК' if self.M_ZAGALNA_AVARIA else 'НІ'}")
        print("-"*60)
        print(f"▶️  Система запущена: {'ТАК' if self.M_SYSTEM_ON else 'НІ'}")
        print(f"✅ Готовність:        {'ТАК' if self.M_SYSTEM_READY else 'НІ'}")
        print("-"*60)
        print(f"🔵 Клапан газу:       {'ВІДКРИТО' if self.Y_KLAPAN_GAZ.read() else 'ЗАКРИТО'}")
        print(f"🔌 Розетка 1:         {'УВІМК' if self.Y_ROZET_1.read() else 'ВИМК'}")
        print(f"🔌 Розетка 2:         {'УВІМК' if self.Y_ROZET_2.read() else 'ВИМК'}")
        print(f"🚨 Сигнал аварії:     {'АКТИВНИЙ' if self.Y_AVARIA_SIGNAL.read() else 'НЕАКТИВНИЙ'}")
        print(f"🔑 Дозвіл роботи:     {'АКТИВНИЙ' if self.Y_DOZV_ROBOTY.read() else 'НЕАКТИВНИЙ'}")
        print("="*60)

    def print_stats(self):
        """Виведення статистики роботи"""
        print("\n" + "="*60)
        print("📈 СТАТИСТИКА РОБОТИ")
        print("-"*60)
        print(f"🔄 Всього циклів:      {self.scan_count}")
        print(f"▶️  Запусків системи:   {self.stats['starts']}")
        print(f"⏹️  Зупинок системи:    {self.stats['stops']}")
        print(f"🚨 Аварій:              {self.stats['alarms']}")
        print(f"🔥 Відключень газу:     {self.stats['gas_off_count']}")
        print(f"🌀 Відключень вакууму:  {self.stats['vakuum_off_count']}")
        print("="*60)

    # ============================================
    # МЕТОДИ ДЛЯ ТЕСТУВАННЯ
    # ============================================
    def simulate_sensor_changes(self):
        """Імітація зміни показників датчиків (для тестування)"""
        # Змінюємо напругу
        self.AI_NAPRUGA.set_value(random.randint(2000, 3800))

        # Змінюємо температуру
        self.AI_TEMP_BOILER.set_value(random.randint(1000, 2500))

        # Випадкове зникнення газу (рідко)
        if random.random() < 0.05:  # 5% шанс
            self.X_GAZ.set_state(False)
        else:
            self.X_GAZ.set_state(True)

        # Випадкове зникнення вакууму (рідко)
        if random.random() < 0.03:  # 3% шанс
            self.X_VAKUUM.set_state(False)
        else:
            self.X_VAKUUM.set_state(True)

    def set_voltage(self, volts: int):
        """Встановлення напруги (для тестування)"""
        adc_value = volts * ADC_MAX // NAPRUGA_MAX
        self.AI_NAPRUGA.set_value(adc_value)
        print(f"⚡ Встановлено напругу: {volts} В")

    def set_temperature(self, temp: int):
        """Встановлення температури бойлера (для тестування)"""
        adc_value = temp * ADC_MAX // TEMP_MAX
        self.AI_TEMP_BOILER.set_value(adc_value)
        print(f"🌡️  Встановлено температуру: {temp}°C")

    def set_gas(self, present: bool):
        """Встановлення наявності газу"""
        self.X_GAZ.set_state(present)
        print(f"🔥 Газ: {'Є' if present else 'НЕМАЄ'}")

    def set_vakuum(self, present: bool):
        """Встановлення наявності вакууму"""
        self.X_VAKUUM.set_state(present)
        print(f"🌀 Вакуум: {'Є' if present else 'НЕМАЄ'}")

    def set_oil_pressure(self, normal: bool):
        """Встановлення тиску масла"""
        self.X_TISK_MASLA_DI.set_state(normal)
        print(f"⛽ Тиск масла: {'НОРМА' if normal else 'АВАРІЯ'}")

    def start_system(self):
        """Команда старт системи"""
        self.CMD_START.set_state(True)
        # Скидаємо через невеликий час (емуляція імпульсу)
        threading.Timer(0.2, lambda: self.CMD_START.set_state(False)).start()

    def stop_system(self):
        """Команда стоп системи"""
        self.CMD_STOP.set_state(True)
        threading.Timer(0.2, lambda: self.CMD_STOP.set_state(False)).start()

    def socket1_on(self):
        """Увімкнути розетку 1"""
        self.CMD_ROZET_1.set_state(True)
        print("🔌 Команда: увімкнути розетку 1")

    def socket1_off(self):
        """Вимкнути розетку 1"""
        self.CMD_ROZET_1.set_state(False)
        print("🔌 Команда: вимкнути розетку 1")

    def socket2_on(self):
        """Увімкнути розетку 2"""
        self.CMD_ROZET_2.set_state(True)
        print("🔌 Команда: увімкнути розетку 2")

    def socket2_off(self):
        """Вимкнути розетку 2"""
        self.CMD_ROZET_2.set_state(False)
        print("🔌 Команда: вимкнути розетку 2")


# ============================================
# ПРИКЛАД ВИКОРИСТАННЯ (ТЕСТОВА ПРОГРАМА)
# ============================================

def demo_mode():
    """Демонстраційний режим роботи"""
    print("="*60)
    print("🔥 ДЕМОНСТРАЦІЙНИЙ РЕЖИМ КОНТРОЛЕРА БОЙЛЕРА")
    print("="*60)
    print("\n📋 Команди для тестування:")
    print("  s - запустити систему")
    print("  t - зупинити систему")
    print("  v [напруга] - встановити напругу (напр. v 420)")
    print("  tmp [температура] - встановити температуру (напр. tmp 85)")
    print("  g [0/1] - газ (0 - немає, 1 - є)")
    print("  vak [0/1] - вакуум (0 - немає, 1 - є)")
    print("  o [0/1] - тиск масла (0 - аварія, 1 - норма)")
    print("  1on - розетка 1 увімк")
    print("  1off - розетка 1 вимк")
    print("  2on - розетка 2 увімк")
    print("  2off - розетка 2 вимк")
    print("  sim - імітувати випадкові зміни датчиків")
    print("  status - показати стан")
    print("  stats - показати статистику")
    print("  q - вихід")
    print("="*60)

    # Створюємо контролер
    ctrl = BoilerController()

    # Запускаємо цикл сканування
    ctrl.start()

    try:
        while True:
            cmd = input("\n👉 Команда: ").strip().lower()

            if cmd == 'q':
                break
            elif cmd == 's':
                ctrl.start_system()
            elif cmd == 't':
                ctrl.stop_system()
            elif cmd.startswith('v '):
                try:
                    volts = int(cmd.split()[1])
                    ctrl.set_voltage(volts)
                except:
                    print("❌ Невірний формат. Використовуйте: v 400")
            elif cmd.startswith('tmp '):
                try:
                    temp = int(cmd.split()[1])
                    ctrl.set_temperature(temp)
                except:
                    print("❌ Невірний формат. Використовуйте: tmp 80")
            elif cmd.startswith('g '):
                try:
                    val = int(cmd.split()[1])
                    ctrl.set_gas(val == 1)
                except:
                    print("❌ Невірний формат. Використовуйте: g 1")
            elif cmd.startswith('vak '):
                try:
                    val = int(cmd.split()[1])
                    ctrl.set_vakuum(val == 1)
                except:
                    print("❌ Невірний формат. Використовуйте: vak 1")
            elif cmd.startswith('o '):
                try:
                    val = int(cmd.split()[1])
                    ctrl.set_oil_pressure(val == 1)
                except:
                    print("❌ Невірний формат. Використовуйте: o 1")
            elif cmd == '1on':
                ctrl.socket1_on()
            elif cmd == '1off':
                ctrl.socket1_off()
            elif cmd == '2on':
                ctrl.socket2_on()
            elif cmd == '2off':
                ctrl.socket2_off()
            elif cmd == 'sim':
                ctrl.simulate_sensor_changes()
            elif cmd == 'status':
                ctrl.print_status()
            elif cmd == 'stats':
                ctrl.print_stats()
            elif cmd == '':
                continue
            else:
                print("❌ Невідома команда")

    except KeyboardInterrupt:
        print("\n\n👋 Завершення роботи...")
    finally:
        ctrl.stop()
        print("✅ Програма завершена")


def simple_auto_mode():
    """Простий автоматичний режим для тестування"""
    print("="*60)
    print("🤖 АВТОМАТИЧНИЙ РЕЖИМ ТЕСТУВАННЯ")
    print("="*60)

    ctrl = BoilerController()
    ctrl.start()

    try:
        # Запускаємо систему
        print("\n▶️ Запуск системи...")
        ctrl.start_system()
        time.sleep(2)

        # Тест 1: Нормальна робота
        print("\n✅ Тест 1: Нормальна робота")
        for i in range(5):
            ctrl.print_status()
            time.sleep(1)

        # Тест 2: Перевищення напруги
        print("\n⚠️ Тест 2: Перевищення напруги до 420В")
        ctrl.set_voltage(420)
        time.sleep(3)
        ctrl.print_status()

        # Повернення напруги
        print("\n↩️ Повернення напруги до 360В")
        ctrl.set_voltage(360)
        time.sleep(3)
        ctrl.print_status()

        # Тест 3: Втрата вакууму
        print("\n⚠️ Тест 3: Втрата вакууму")
        ctrl.set_vakuum(False)
        time.sleep(3)
        ctrl.print_status()

        # Відновлення вакууму
        print("\n↩️ Відновлення вакууму")
        ctrl.set_vakuum(True)
        ctrl.start_system()  # Потрібно перезапустити
        time.sleep(3)
        ctrl.print_status()

        # Тест 4: Керування розетками
        print("\n🔌 Тест 4: Керування розетками")
        ctrl.socket1_on()
        time.sleep(2)
        ctrl.socket2_on()
        time.sleep(2)
        ctrl.print_status()
        time.sleep(2)
        ctrl.socket1_off()
        ctrl.socket2_off()

        # Статистика
        time.sleep(1)
        ctrl.print_stats()

    except KeyboardInterrupt:
        pass
    finally:
        ctrl.stop()
        print("\n✅ Тестування завершено")


# ============================================
# ТОЧКА ВХОДУ
# ============================================

if __name__ == "__main__":
    print("🔥 КОНТРОЛЕР КЕРУВАННЯ БОЙЛЕРОМ (Python-емуляція FATEK FBs-MA)")
    print("="*60)
    print("Виберіть режим роботи:")
    print("1. Демонстраційний режим (інтерактивний)")
    print("2. Автоматичне тестування")
    print("3. Запустити в фоновому режимі (без інтерфейсу)")

    choice = input("\nВаш вибір (1/2/3): ").strip()

    if choice == '1':
        demo_mode()
    elif choice == '2':
        simple_auto_mode()
    elif choice == '3':
        print("\n🔄 Запуск контролера в фоновому режимі...")
        ctrl = BoilerController()
        ctrl.start()
        print("✅ Контролер працює. Натисніть Ctrl+C для зупинки.")
        try:
            while True:
                ctrl.print_status()
                time.sleep(5)
        except KeyboardInterrupt:
            ctrl.stop()
            print("✅ Контролер зупинено")
    else:
        print("❌ Невірний вибір")