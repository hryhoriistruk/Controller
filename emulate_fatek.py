#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ЕМУЛЯТОР FATEK FBs-10MAR ДЛЯ ТЕСТУВАННЯ ПРОГРАМИ БОЙЛЕРА
Повна емуляція логіки з FATEK_BoilerControl.ST
"""

import time
import threading
import random
from datetime import datetime

class FATEK_Emulator:
    """Емуляція FATEK FBs-10MAR контролера"""
    
    def __init__(self):
        self.reset_all()
        self.running = False
        self.scan_count = 0
        
    def reset_all(self):
        """Скидання всіх змінних"""
        
        # --- Аналогові входи (IW) ---
        self.AI_BoilerVoltage = 2500      # ~305V
        self.AI_BoilerTemp = 1500         # ~55°C  
        self.AI_WaterTemp = 1000          # ~37°C
        self.AI_TempSensor1 = 1200        # ~44°C
        self.AI_TempSensor2 = 1100        # ~40°C
        self.AI_OilPressure = 3000        # ~73%
        self.AI_SteamPressure = 2000      # ~4.9 бар
        
        # --- Дискретні входи (IX) ---
        self.DI_GasSensor = True          # 1=є газ
        self.DI_VacuumSensor = True       # 1=є вакуум
        self.DI_OilPressureOK = True      # 1=норма
        self.DI_SteamPressureOK = True    # 1=норма
        self.DI_EmergencyStop = False     # 1=аварійний стоп
        self.DI_ManualMode = False        # 1=ручний режим
        
        # --- Команди (MX) ---
        self.CMD_SystemStart = False
        self.CMD_SystemStop = False
        self.CMD_Socket1_On = False
        self.CMD_Socket2_On = False
        self.CMD_ResetAlarms = False
        
        # --- Виходи (QX) ---
        self.DO_GasValve = False
        self.DO_Socket1 = False
        self.DO_Socket2 = False
        self.DO_WaterPump = False
        self.DO_OilPump = False
        self.DO_AlarmLight = False
        self.DO_PermitRun = False
        self.DO_FanVent = False
        
        # --- Індикація (QW) ---
        self.ST_SystemRunning = 0
        self.ST_GasAvailable = 0
        self.ST_VacuumOK = 0
        self.ST_AlarmCode = 0
        
        # --- Аварійні флаги ---
        self.ALM_VoltageHigh = False
        self.ALM_TempHigh = False
        self.ALM_NoGas = False
        self.ALM_NoVacuum = False
        self.ALM_OilPressureLow = False
        self.ALM_SteamPressureBad = False
        self.ALM_Emergency = False
        self.ALM_AnyAlarm = False
        
        # --- Стан системи ---
        self.SYS_Enabled = False
        self.SYS_Running = False
        self.SYS_Ready = False
        self.SYS_ManualMode = False
        
        # --- Стан датчиків ---
        self.SNS_GasPresent = False
        self.SNS_VacuumPresent = False
        self.SNS_OilPressureOK = False
        self.SNS_SteamPressureOK = False
        
        # --- Фізичні величини ---
        self.PHY_Voltage = 0
        self.PHY_BoilerTemp = 0
        self.PHY_WaterTemp = 0
        self.PHY_Temp1 = 0
        self.PHY_Temp2 = 0
        self.PHY_OilPressure = 0
        self.PHY_SteamPressure = 0
        
        # --- Детектори фронтів ---
        self.FF_StartOld = False
        self.FF_StopOld = False
        self.FF_ResetOld = False
        self.FF_GasOld = False
        self.FF_VacuumOld = False
        self.FF_AlarmOld = False
        
        # --- Лічильники ---
        self.CNT_Starts = 0
        self.CNT_Stops = 0
        self.CNT_Alarms = 0
        self.CNT_GasFailures = 0
        self.CNT_VacuumFailures = 0
        self.CNT_RunTime = 0
        
        # --- Таймери ---
        self.TMR_StartDelay = {'IN': False, 'Q': False, 'ET': 0, 'PT': 3000}  # 3с
        self.TMR_AlarmDelay = {'IN': False, 'Q': False, 'ET': 0, 'PT': 2000}  # 2с
        self.TMR_ResetDelay = {'IN': False, 'Q': False, 'ET': 0, 'PT': 1000}  # 1с
        self.TMR_RunTimer = {'IN': False, 'Q': False, 'ET': 0, 'PT': 1000}    # 1с
        
        # --- Константи ---
        self.ADC_MAX = 4095
        self.VOLTAGE_MAX = 500
        self.TEMP_MAX = 150
        self.VOLTAGE_TRIP = 400
        self.VOLTAGE_RESET = 380
        self.TEMP_TRIP = 80
        self.TEMP_RESET = 75

    def timer_update(self, timer, dt):
        """Оновлення таймера TON"""
        if timer['IN']:
            timer['ET'] += dt
            if timer['ET'] >= timer['PT']:
                timer['Q'] = True
        else:
            timer['ET'] = 0
            timer['Q'] = False

    def scan_cycle(self):
        """Один цикл сканування FATEK контролера"""
        dt = 100  # 100мс час скану
        
        # --- БЛОК 1: Перетворення АЦП ---
        self.PHY_Voltage = self.AI_BoilerVoltage * self.VOLTAGE_MAX // self.ADC_MAX
        self.PHY_BoilerTemp = self.AI_BoilerTemp * self.TEMP_MAX // self.ADC_MAX
        self.PHY_WaterTemp = self.AI_WaterTemp * self.TEMP_MAX // self.ADC_MAX
        self.PHY_Temp1 = self.AI_TempSensor1 * self.TEMP_MAX // self.ADC_MAX
        self.PHY_Temp2 = self.AI_TempSensor2 * self.TEMP_MAX // self.ADC_MAX
        self.PHY_OilPressure = self.AI_OilPressure * 100 // self.ADC_MAX
        self.PHY_SteamPressure = self.AI_SteamPressure * 10 // self.ADC_MAX
        
        # --- БЛОК 2: Читання дискретних датчиків ---
        self.SNS_GasPresent = self.DI_GasSensor
        self.SNS_VacuumPresent = self.DI_VacuumSensor
        self.SNS_OilPressureOK = self.DI_OilPressureOK
        self.SNS_SteamPressureOK = self.DI_SteamPressureOK
        self.SYS_ManualMode = self.DI_ManualMode
        
        # --- БЛОК 3: Аварія високої напруги ---
        if self.PHY_Voltage >= self.VOLTAGE_TRIP:
            self.ALM_VoltageHigh = True
        elif self.PHY_Voltage < self.VOLTAGE_RESET:
            self.ALM_VoltageHigh = False
            
        # --- БЛОК 4: Аварія високої температури ---
        if self.PHY_BoilerTemp >= self.TEMP_TRIP:
            self.ALM_TempHigh = True
        elif self.PHY_BoilerTemp < self.TEMP_RESET:
            self.ALM_TempHigh = False
            
        # --- БЛОК 5: Аварії по датчиках ---
        self.ALM_NoGas = not self.SNS_GasPresent
        self.ALM_NoVacuum = not self.SNS_VacuumPresent
        self.ALM_OilPressureLow = not self.SNS_OilPressureOK
        self.ALM_SteamPressureBad = not self.SNS_SteamPressureOK
        self.ALM_Emergency = self.DI_EmergencyStop
        
        # --- БЛОК 6: Загальна аварія ---
        old_alarm = self.ALM_AnyAlarm
        self.ALM_AnyAlarm = (self.ALM_VoltageHigh or self.ALM_TempHigh or 
                           self.ALM_NoGas or self.ALM_NoVacuum or 
                           self.ALM_OilPressureLow or self.ALM_SteamPressureBad or 
                           self.ALM_Emergency)
        
        # --- БЛОК 7: Логіка старт/стоп ---
        if self.CMD_SystemStart and not self.FF_StartOld:
            if not self.SYS_Running and not self.ALM_AnyAlarm:
                self.SYS_Enabled = True
                self.TMR_StartDelay['IN'] = True
        self.FF_StartOld = self.CMD_SystemStart
        
        if self.CMD_SystemStop and not self.FF_StopOld:
            self.SYS_Enabled = False
            self.SYS_Running = False
        self.FF_StopOld = self.CMD_SystemStop
        
        if self.ALM_AnyAlarm:
            self.SYS_Enabled = False
            self.SYS_Running = False
            
        # Запуск після затримки
        if self.TMR_StartDelay['Q']:
            self.SYS_Running = True
            self.TMR_StartDelay['IN'] = False
            self.CNT_Starts += 1
            
        # --- БЛОК 8: Готовність системи ---
        self.SYS_Ready = (not self.ALM_VoltageHigh and not self.ALM_TempHigh and
                        self.SNS_GasPresent and self.SNS_VacuumPresent and
                        self.SNS_OilPressureOK and self.SNS_SteamPressureOK and
                        not self.ALM_Emergency and self.SYS_Running)
        
        # --- БЛОК 9: Керування клапаном газу ---
        if self.SYS_Ready:
            self.DO_GasValve = True
        else:
            self.DO_GasValve = False
            
        # Додатковий захист - якщо немає вакууму
        if not self.SNS_VacuumPresent:
            self.DO_GasValve = False
            
        # --- БЛОК 10: Керування розетками ---
        self.DO_Socket1 = self.CMD_Socket1_On and not self.ALM_AnyAlarm
        self.DO_Socket2 = self.CMD_Socket2_On and not self.ALM_AnyAlarm
        
        # --- БЛОК 11: Керування насосами ---
        self.DO_WaterPump = self.SYS_Ready and self.PHY_WaterTemp > 20
        self.DO_OilPump = self.SYS_Ready and self.SNS_OilPressureOK
        self.DO_FanVent = self.SYS_Running
        
        # --- БЛОК 12: Сигналізація та індикація ---
        self.DO_AlarmLight = self.ALM_AnyAlarm
        self.DO_PermitRun = self.SYS_Ready
        
        self.ST_SystemRunning = 1 if self.SYS_Running else 0
        self.ST_GasAvailable = 1 if self.SNS_GasPresent else 0
        self.ST_VacuumOK = 1 if self.SNS_VacuumPresent else 0
        
        # Коди аварій
        if self.ALM_VoltageHigh: self.ST_AlarmCode = 1
        elif self.ALM_TempHigh: self.ST_AlarmCode = 2
        elif self.ALM_NoGas: self.ST_AlarmCode = 3
        elif self.ALM_NoVacuum: self.ST_AlarmCode = 4
        elif self.ALM_OilPressureLow: self.ST_AlarmCode = 5
        elif self.ALM_SteamPressureBad: self.ST_AlarmCode = 6
        elif self.ALM_Emergency: self.ST_AlarmCode = 7
        else: self.ST_AlarmCode = 0
        
        # --- БЛОК 13: Статистика ---
        if self.ALM_AnyAlarm and not self.FF_AlarmOld:
            self.CNT_Alarms += 1
        self.FF_AlarmOld = self.ALM_AnyAlarm
        
        if not self.SNS_GasPresent and self.FF_GasOld:
            self.CNT_GasFailures += 1
        self.FF_GasOld = self.SNS_GasPresent
        
        if not self.SNS_VacuumPresent and self.FF_VacuumOld:
            self.CNT_VacuumFailures += 1
        self.FF_VacuumOld = self.SNS_VacuumPresent
        
        if (self.CMD_SystemStop and not self.FF_StopOld) or (self.ALM_AnyAlarm and not old_alarm):
            if self.SYS_Running:
                self.CNT_Stops += 1
                
        # Таймер роботи
        self.TMR_RunTimer['IN'] = self.SYS_Running
        if self.TMR_RunTimer['Q']:
            self.CNT_RunTime += 1
            self.TMR_RunTimer['IN'] = False
            self.TMR_RunTimer['IN'] = True
            
        # --- БЛОК 14: Скидання аварій ---
        if self.CMD_ResetAlarms and not self.FF_ResetOld:
            self.TMR_ResetDelay['IN'] = True
        self.FF_ResetOld = self.CMD_ResetAlarms
        
        if self.TMR_ResetDelay['Q']:
            if not self.ALM_VoltageHigh and not self.ALM_TempHigh and not self.ALM_Emergency:
                self.ALM_NoGas = False
                self.ALM_NoVacuum = False
                self.ALM_OilPressureLow = False
                self.ALM_SteamPressureBad = False
            self.TMR_ResetDelay['IN'] = False
            
        # Оновлення таймерів
        self.timer_update(self.TMR_StartDelay, dt)
        self.timer_update(self.TMR_AlarmDelay, dt)
        self.timer_update(self.TMR_ResetDelay, dt)
        self.timer_update(self.TMR_RunTimer, dt)
        
        self.scan_count += 1

    def print_status(self):
        """Виведення стану системи"""
        alarm_names = {
            0: "Норма",
            1: "Висока напруга (≥400В)",
            2: "Висока температура (≥80°C)",
            3: "Немає газу",
            4: "Немає вакууму",
            5: "Низький тиск масла",
            6: "Неправильний тиск пари",
            7: "Аварійний стоп"
        }
        
        print(f"\n{'='*70}")
        print(f"🔥 EMULATOR FATEK FBs-10MAR - КОНТРОЛЕР БОЙЛЕРА")
        print(f"🔄 Цикл сканування: #{self.scan_count} | ⏰ {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'-'*70}")
        
        print(f"📊 ВХІДНІ ПАРАМЕТРИ:")
        print(f"   ⚡ Напруга бойлера: {self.PHY_Voltage:3d}В {'⚠️' if self.ALM_VoltageHigh else '✅'}")
        print(f"   🌡️  Температура бойлера: {self.PHY_BoilerTemp:2d}°C {'⚠️' if self.ALM_TempHigh else '✅'}")
        print(f"   💧 Температура води: {self.PHY_WaterTemp:2d}°C")
        print(f"   🔥 Газ: {'Є' if self.SNS_GasPresent else '❌'} {'⚠️' if self.ALM_NoGas else ''}")
        print(f"   🌀 Вакуум: {'Є' if self.SNS_VacuumPresent else '❌'} {'⚠️' if self.ALM_NoVacuum else ''}")
        print(f"   ⛽ Тиск масла: {'НОРМА' if self.SNS_OilPressureOK else '❌'} {'⚠️' if self.ALM_OilPressureLow else ''}")
        print(f"   💨 Тиск пари: {'НОРМА' if self.SNS_SteamPressureOK else '❌'} {'⚠️' if self.ALM_SteamPressureBad else ''}")
        
        print(f"\n🎛️ СТАН СИСТЕМИ:")
        print(f"   ▶️  Система: {'ЗАПУЩЕНА' if self.SYS_Running else 'ЗУПИНЕНА'}")
        print(f"   ✅ Готовність: {'ГОТОВА' if self.SYS_Ready else 'НЕ ГОТОВА'}")
        print(f"   🚨 Загальна аварія: {'ТАК' if self.ALM_AnyAlarm else 'НІ'}")
        print(f"   📱 Код аварії: {self.ST_AlarmCode} - {alarm_names.get(self.ST_AlarmCode, 'Невідомий')}")
        
        print(f"\n🔌 ВИХОДИ:")
        print(f"   🔵 Клапан газу: {'ВІДКРИТО' if self.DO_GasValve else 'ЗАКРИТО'}")
        print(f"   🔌 Розетка 1: {'УВІМК' if self.DO_Socket1 else 'ВИМК'}")
        print(f"   🔌 Розетка 2: {'УВІМК' if self.DO_Socket2 else 'ВИМК'}")
        print(f"   💧 Насос води: {'УВІМК' if self.DO_WaterPump else 'ВИМК'}")
        print(f"   ⛽ Насос масла: {'УВІМК' if self.DO_OilPump else 'ВИМК'}")
        print(f"   🌪️ Вентиляція: {'УВІМК' if self.DO_FanVent else 'ВИМК'}")
        print(f"   🚨 Аварійна лампа: {'БЛИМАЄ' if self.DO_AlarmLight else 'ВИМК'}")
        print(f"   🔑 Дозвіл роботи: {'АКТИВНИЙ' if self.DO_PermitRun else 'НЕАКТИВНИЙ'}")
        
        print(f"\n📈 СТАТИСТИКА:")
        print(f"   🔄 Запусків: {self.CNT_Starts} | ⏹️ Зупинок: {self.CNT_Stops}")
        print(f"   🚨 Аварій: {self.CNT_Alarms} | 🔥 Відмов газу: {self.CNT_GasFailures}")
        print(f"   🌀 Відмов вакууму: {self.CNT_VacuumFailures} | ⏱️ Час роботи: {self.CNT_RunTime}с")
        print(f"{'='*70}")

    def start_system(self):
        """Команда старт системи"""
        self.CMD_SystemStart = True
        time.sleep(0.1)
        self.CMD_SystemStart = False
        print("▶️ Команда СТАРТ відправлена")

    def stop_system(self):
        """Команда стоп системи"""
        self.CMD_SystemStop = True
        time.sleep(0.1)
        self.CMD_SystemStop = False
        print("⏹️ Команда СТОП відправлена")

    def reset_alarms(self):
        """Скидання аварій"""
        self.CMD_ResetAlarms = True
        time.sleep(0.1)
        self.CMD_ResetAlarms = False
        print("🔄 Команда СКИДАННЯ АВАРІЙ відправлена")

    def set_voltage(self, volts):
        """Встановити напругу"""
        self.AI_BoilerVoltage = volts * self.ADC_MAX // self.VOLTAGE_MAX
        print(f"⚡ Напругу встановлено: {volts}В")

    def set_temperature(self, temp):
        """Встановити температуру бойлера"""
        self.AI_BoilerTemp = temp * self.ADC_MAX // self.TEMP_MAX
        print(f"🌡️ Температуру встановлено: {temp}°C")

    def set_gas(self, present):
        """Встановити наявність газу"""
        self.DI_GasSensor = present
        print(f"🔥 Газ: {'Є' if present else 'НЕМАЄ'}")

    def set_vacuum(self, present):
        """Встановити наявність вакууму"""
        self.DI_VacuumSensor = present
        print(f"🌀 Вакуум: {'Є' if present else 'НЕМАЄ'}")

    def set_oil_pressure(self, ok):
        """Встановити тиск масла"""
        self.DI_OilPressureOK = ok
        print(f"⛽ Тиск масла: {'НОРМА' if ok else 'НИЗЬКИЙ'}")

    def emergency_stop(self):
        """Аварійний стоп"""
        self.DI_EmergencyStop = True
        print("🚨 АВАРІЙНИЙ СТОП АКТИВОВАНО!")

    def reset_emergency(self):
        """Скидання аварійного стопу"""
        self.DI_EmergencyStop = False
        print("✅ Аварійний стоп скинуто")

def interactive_test():
    """Інтерактивне тестування"""
    print("🔥 ІНТЕРАКТИВНЕ ТЕСТУВАННЯ FATEK FBs-10MAR")
    print("="*70)
    print("\n📋 КОМАНДИ:")
    print("  start      - запустити систему")
    print("  stop       - зупинити систему") 
    print("  reset      - скинути аварії")
    print("  v [400]    - встановити напругу (напр. v 420)")
    print("  t [80]     - встановити температуру (напр. t 85)")
    print("  g [0/1]    - газ (0=немає, 1=є)")
    print("  vac [0/1]  - вакуум (0=немає, 1=є)")
    print("  oil [0/1]  - тиск масла (0=низький, 1=норма)")
    print("  emergency  - аварійний стоп")
    print("  clear      - скидання аварійного стопу")
    print("  socket1    - увімкнути розетку 1")
    print("  socket2    - увімкнути розетку 2")
    print("  status     - показати статус")
    print("  auto       - автоматичне тестування")
    print("  q          - вихід")
    print("="*70)
    
    plc = FATEK_Emulator()
    
    def scan_loop():
        while plc.running:
            plc.scan_cycle()
            time.sleep(0.1)
    
    scan_thread = threading.Thread(target=scan_loop, daemon=True)
    plc.running = True
    scan_thread.start()
    
    try:
        while True:
            cmd = input("\n👉 Команда: ").strip().lower()
            
            if cmd == 'q':
                break
            elif cmd == 'start':
                plc.start_system()
            elif cmd == 'stop':
                plc.stop_system()
            elif cmd == 'reset':
                plc.reset_alarms()
            elif cmd.startswith('v '):
                try:
                    volts = int(cmd.split()[1])
                    plc.set_voltage(volts)
                except:
                    print("❌ Формат: v 400")
            elif cmd.startswith('t '):
                try:
                    temp = int(cmd.split()[1])
                    plc.set_temperature(temp)
                except:
                    print("❌ Формат: t 80")
            elif cmd.startswith('g '):
                try:
                    val = int(cmd.split()[1])
                    plc.set_gas(val == 1)
                except:
                    print("❌ Формат: g 1")
            elif cmd.startswith('vac '):
                try:
                    val = int(cmd.split()[1])
                    plc.set_vacuum(val == 1)
                except:
                    print("❌ Формат: vac 1")
            elif cmd.startswith('oil '):
                try:
                    val = int(cmd.split()[1])
                    plc.set_oil_pressure(val == 1)
                except:
                    print("❌ Формат: oil 1")
            elif cmd == 'emergency':
                plc.emergency_stop()
            elif cmd == 'clear':
                plc.reset_emergency()
            elif cmd == 'socket1':
                plc.CMD_Socket1_On = not plc.CMD_Socket1_On
                print(f"🔌 Розетка 1: {'УВІМК' if plc.CMD_Socket1_On else 'ВИМК'}")
            elif cmd == 'socket2':
                plc.CMD_Socket2_On = not plc.CMD_Socket2_On
                print(f"🔌 Розетка 2: {'УВІМК' if plc.CMD_Socket2_On else 'ВИМК'}")
            elif cmd == 'status':
                plc.print_status()
            elif cmd == 'auto':
                run_auto_test(plc)
            elif cmd == '':
                continue
            else:
                print("❌ Невідома команда")
                
    except KeyboardInterrupt:
        print("\n⏹️ Тестування перервано")
    finally:
        plc.running = False
        print("✅ Емуляцію зупинено")

def run_auto_test(plc):
    """Автоматичне тестування"""
    print("\n🤖 ЗАПУСК АВТОМАТИЧНОГО ТЕСТУВАННЯ")
    print("="*50)
    
    # Тест 1: Нормальний запуск
    print("\n✅ ТЕСТ 1: Нормальний запуск системи")
    plc.print_status()
    time.sleep(1)
    
    plc.start_system()
    time.sleep(4)  # Чекаємо 3с затримку старту
    plc.print_status()
    
    # Тест 2: Перевищення напруги
    print("\n⚠️ ТЕСТ 2: Перевищення напруги до 420В")
    plc.set_voltage(420)
    time.sleep(3)
    plc.print_status()
    
    # Відновлення напруги
    print("\n↩️ Відновлення напруги до 360В")
    plc.set_voltage(360)
    time.sleep(1)
    plc.reset_alarms()
    time.sleep(1)
    plc.start_system()
    time.sleep(4)
    plc.print_status()
    
    # Тест 3: Перевищення температури
    print("\n🔥 ТЕСТ 3: Перевищення температури до 85°C")
    plc.set_temperature(85)
    time.sleep(3)
    plc.print_status()
    
    # Відновлення температури
    print("\n❄️ Відновлення температури до 60°C")
    plc.set_temperature(60)
    time.sleep(1)
    plc.reset_alarms()
    time.sleep(1)
    plc.start_system()
    time.sleep(4)
    plc.print_status()
    
    # Тест 4: Втрата вакууму (критичний тест!)
    print("\n🌀 ТЕСТ 4: Втрата вакууму - газ має закритися НЕГАЙНО!")
    plc.set_vacuum(False)
    time.sleep(3)
    plc.print_status()
    
    # Відновлення вакууму
    print("\n✅ Відновлення вакууму")
    plc.set_vacuum(True)
    time.sleep(1)
    plc.reset_alarms()
    time.sleep(1)
    plc.start_system()
    time.sleep(4)
    plc.print_status()
    
    # Тест 5: Втрата газу
    print("\n🔥 ТЕСТ 5: Втрата газу")
    plc.set_gas(False)
    time.sleep(3)
    plc.print_status()
    
    # Відновлення газу
    print("\n✅ Відновлення газу")
    plc.set_gas(True)
    time.sleep(1)
    plc.reset_alarms()
    time.sleep(1)
    plc.start_system()
    time.sleep(4)
    plc.print_status()
    
    # Тест 6: Керування розетками
    print("\n🔌 ТЕСТ 6: Керування розетками")
    plc.CMD_Socket1_On = True
    time.sleep(2)
    plc.CMD_Socket2_On = True
    time.sleep(2)
    plc.print_status()
    
    plc.CMD_Socket1_On = False
    plc.CMD_Socket2_On = False
    time.sleep(1)
    
    # Тест 7: Аварійний стоп
    print("\n🚨 ТЕСТ 7: Аварійний стоп")
    plc.emergency_stop()
    time.sleep(3)
    plc.print_status()
    
    # Відновлення
    print("\n✅ Відновлення після аварійного стопу")
    plc.reset_emergency()
    plc.reset_alarms()
    time.sleep(2)
    
    # Фінальна статистика
    print(f"\n📊 ФІНАЛЬНА СТАТИСТИКА:")
    print(f"   Запусків: {plc.CNT_Starts}")
    print(f"   Зупинок: {plc.CNT_Stops}")
    print(f"   Аварій: {plc.CNT_Alarms}")
    print(f"   Відмов газу: {plc.CNT_GasFailures}")
    print(f"   Відмов вакууму: {plc.CNT_VacuumFailures}")
    print(f"   Час роботи: {plc.CNT_RunTime}с")
    
    print("\n✅ АВТОМАТИЧНЕ ТЕСТУВАННЯ ЗАВЕРШЕНО")
    print("="*50)

if __name__ == "__main__":
    interactive_test()
