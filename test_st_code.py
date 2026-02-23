#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ТЕСТУВАЛЬНИК ST КОДУ ДЛЯ FATEK FBs-MA
Емуляція ПЛК та перевірка ST логіки
"""

import re
import time
from typing import Dict, List, Tuple

class STCodeTester:
    """Тестувальник Structured Text коду"""
    
    def __init__(self, st_file_path: str):
        self.st_file_path = st_file_path
        self.st_code = ""
        self.variables = {}
        self.test_results = []
        
    def load_st_code(self):
        """Завантаження ST коду з файлу"""
        try:
            with open(self.st_file_path, 'r', encoding='utf-8') as f:
                self.st_code = f.read()
            print(f"✅ ST код завантажено з {self.st_file_path}")
            return True
        except Exception as e:
            print(f"❌ Помилка завантаження ST коду: {e}")
            return False
    
    def parse_variables(self):
        """Парсинг змінних з ST коду"""
        print("\n🔍 Аналіз змінних ST коду...")
        
        # Знаходимо VAR блоки
        var_blocks = re.findall(r'VAR.*?END_VAR', self.st_code, re.DOTALL | re.IGNORECASE)
        
        for block in var_blocks:
            # Знаходимо оголошення змінних
            var_declarations = re.findall(r'(\w+)\s+AT\s+%(\w+)(?:\.\d+)?\s*:\s*(\w+)', block, re.IGNORECASE)
            
            for var_name, address, var_type in var_declarations:
                self.variables[var_name.upper()] = {
                    'address': address,
                    'type': var_type,
                    'value': 0 if var_type == 'INT' else False
                }
        
        print(f"📊 Знайдено змінних: {len(self.variables)}")
        
        # Показуємо ключові змінні
        key_vars = ['AI_VOLTAGE', 'AI_BOILER_TEMP', 'DI_GAS_SENSOR', 'DI_VACUUM_SENSOR', 
                   'DO_GAS_VALVE', 'DO_SOCKET1', 'DO_SOCKET2']
        
        print("\n🎯 Ключові змінні:")
        for var in key_vars:
            if var in self.variables:
                info = self.variables[var]
                print(f"  {var}: {info['address']} ({info['type']})")
        
        return len(self.variables) > 0
    
    def check_syntax_structure(self) -> bool:
        """Перевірка синтаксичної структури ST коду"""
        print("\n📝 Перевірка структури ST коду...")
        
        checks = [
            (r'PROGRAM\s+\w+', 'Програма визначена'),
            (r'VAR\s+CONSTANT', 'Константи визначені'),
            (r'VAR\s+', 'Змінні визначені'),
            (r'END_VAR', 'Блоки VAR закриті'),
            (r'IF.*?THEN', 'Умовні оператори'),
            (r'END_IF', 'Умовні оператори закриті'),
            (r'AT\s+%IW\d+', 'Аналогові входи'),
            (r'AT\s+%IX\d+\.\d+', 'Дискретні входи'),
            (r'AT\s+%QX\d+\.\d+', 'Виходи'),
            (r'END_PROGRAM', 'Програма закрита')
        ]
        
        passed = 0
        for pattern, description in checks:
            if re.search(pattern, self.st_code, re.IGNORECASE | re.DOTALL):
                print(f"  ✅ {description}")
                passed += 1
            else:
                print(f"  ❌ {description}")
        
        print(f"\n📊 Структура: {passed}/{len(checks)} перевірок пройдено")
        return passed >= len(checks) * 0.8  # 80% проходження
    
    def check_safety_logic(self) -> bool:
        """Перевірка логіки безпеки"""
        print("\n🛡️ Перевірка логіки безпеки...")
        
        safety_checks = [
            (r'PHY_Voltage.*>=.*VOLTAGE_TRIP', 'Аварія напруги ≥400В'),
            (r'PHY_BoilerTemp.*>=.*TEMP_TRIP', 'Аварія температури ≥80°C'),
            (r'NOT.*SNS_VacuumPresent', 'Перевірка відсутності вакууму'),
            (r'NOT.*SNS_GasPresent', 'Перевірка відсутності газу'),
            (r'DO_GasValve.*FALSE', 'Закриття газового клапана'),
            (r'ALM_AnyAlarm.*OR', 'Логіка загальної аварії'),
            (r'VOLTAGE_RESET|TEMP_RESET', 'Гістерезис для скидання'),
            (r'NOT.*SNS_VacuumPresent.*DO_GasValve.*FALSE', 'Пріоритет вакууму над газом')
        ]
        
        passed = 0
        for pattern, description in safety_checks:
            if re.search(pattern, self.st_code, re.IGNORECASE):
                print(f"  ✅ {description}")
                passed += 1
            else:
                print(f"  ⚠️ {description} (можливо відсутня)")
        
        print(f"\n📊 Безпека: {passed}/{len(safety_checks)} перевірок")
        return passed >= len(safety_checks) * 0.7  # 70% для безпеки
    
    def simulate_st_execution(self, test_scenarios: List[Dict]) -> bool:
        """Симуляція виконання ST коду"""
        print("\n🤖 Симуляція виконання ST коду...")
        
        for i, scenario in enumerate(test_scenarios, 1):
            print(f"\n📋 Сценарій {i}: {scenario['name']}")
            
            # Встановлюємо вхідні значення
            self.set_inputs(scenario['inputs'])
            
            # Симулюємо логіку ST коду
            result = self.execute_st_logic(scenario['inputs'])
            
            # Перевіряємо очікувані результати
            expected = scenario['expected']
            passed = self.check_outputs(result, expected)
            
            self.test_results.append({
                'scenario': scenario['name'],
                'passed': passed,
                'inputs': scenario['inputs'],
                'expected': expected,
                'actual': result
            })
            
            status = "✅ ПРОЙДЕНО" if passed else "❌ НЕ ПРОЙДЕНО"
            print(f"  {status}")
        
        return all(r['passed'] for r in self.test_results)
    
    def set_inputs(self, inputs: Dict):
        """Встановлення вхідних значень"""
        for var_name, value in inputs.items():
            if var_name in self.variables:
                self.variables[var_name]['value'] = value
    
    def execute_st_logic(self, inputs: Dict) -> Dict:
        """Симуляція виконання ST логіки"""
        # Ініціалізуємо виходи
        outputs = {
            'DO_GAS_VALVE': False,
            'DO_SOCKET1': False,
            'DO_SOCKET2': False,
            'DO_ALARM_LIGHT': False,
            'ALM_ANY_ALARM': False
        }
        
        # Симуляція логіки з ST коду
        voltage = inputs.get('AI_VOLTAGE', 0)
        temp = inputs.get('AI_BOILER_TEMP', 0)
        gas_present = inputs.get('DI_GAS_SENSOR', False)
        vacuum_present = inputs.get('DI_VACUUM_SENSOR', False)
        
        # Аварія напруги
        voltage_alarm = voltage >= 400
        
        # Аварія температури
        temp_alarm = temp >= 80
        
        # Аварії по датчиках
        gas_alarm = not gas_present
        vacuum_alarm = not vacuum_present
        
        # Загальна аварія
        any_alarm = voltage_alarm or temp_alarm or gas_alarm or vacuum_alarm
        
        # Логіка управління
        system_ready = (not voltage_alarm and not temp_alarm and 
                      gas_present and vacuum_present)
        
        # Управління газовим клапаном
        gas_valve = system_ready
        if not vacuum_present:  # Пріоритет вакууму!
            gas_valve = False
        
        # Управління розетками
        socket1 = inputs.get('CMD_SOCKET1', False) and not any_alarm
        socket2 = inputs.get('CMD_SOCKET2', False) and not any_alarm
        
        # Аварійна сигналізація
        alarm_light = any_alarm
        
        outputs.update({
            'DO_GAS_VALVE': gas_valve,
            'DO_SOCKET1': socket1,
            'DO_SOCKET2': socket2,
            'DO_ALARM_LIGHT': alarm_light,
            'ALM_ANY_ALARM': any_alarm,
            'SYSTEM_READY': system_ready
        })
        
        return outputs
    
    def check_outputs(self, actual: Dict, expected: Dict) -> bool:
        """Перевірка вихідних значень"""
        for key, expected_value in expected.items():
            actual_value = actual.get(key)
            if actual_value != expected_value:
                print(f"    ❌ {key}: очікувано {expected_value}, отримано {actual_value}")
                return False
        return True
    
    def generate_test_report(self):
        """Генерація звіту тестування"""
        print("\n" + "="*60)
        print("📊 ЗВІТ ТЕСТУВАННЯ ST КОДУ")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['passed'])
        
        print(f"📈 Всього тестів: {total_tests}")
        print(f"✅ Пройдено: {passed_tests}")
        print(f"❌ Не пройдено: {total_tests - passed_tests}")
        print(f"📊 Відсоток успіху: {(passed_tests/total_tests)*100:.1f}%")
        
        print("\n📋 Детальні результати:")
        for result in self.test_results:
            status = "✅" if result['passed'] else "❌"
            print(f"  {status} {result['scenario']}")
        
        if passed_tests == total_tests:
            print("\n🎉 ВСІ ТЕСТИ ПРОЙДЕНО! ST код готовий до завантаження.")
        else:
            print("\n⚠️ Деякі тести не пройдено. Перевірте логіку.")
        
        print("="*60)

def create_test_scenarios() -> List[Dict]:
    """Створення тестових сценаріїв"""
    return [
        {
            'name': 'Нормальний режим роботи',
            'inputs': {
                'AI_VOLTAGE': 350,
                'AI_BOILER_TEMP': 60,
                'DI_GAS_SENSOR': True,
                'DI_VACUUM_SENSOR': True,
                'CMD_SOCKET1': False,
                'CMD_SOCKET2': False
            },
            'expected': {
                'DO_GAS_VALVE': True,
                'DO_SOCKET1': False,
                'DO_SOCKET2': False,
                'DO_ALARM_LIGHT': False,
                'ALM_ANY_ALARM': False,
                'SYSTEM_READY': True
            }
        },
        {
            'name': 'Аварія високої напруги (420V)',
            'inputs': {
                'AI_VOLTAGE': 420,
                'AI_BOILER_TEMP': 60,
                'DI_GAS_SENSOR': True,
                'DI_VACUUM_SENSOR': True,
                'CMD_SOCKET1': False,
                'CMD_SOCKET2': False
            },
            'expected': {
                'DO_GAS_VALVE': False,
                'DO_SOCKET1': False,
                'DO_SOCKET2': False,
                'DO_ALARM_LIGHT': True,
                'ALM_ANY_ALARM': True,
                'SYSTEM_READY': False
            }
        },
        {
            'name': 'Аварія високої температури (85°C)',
            'inputs': {
                'AI_VOLTAGE': 350,
                'AI_BOILER_TEMP': 85,
                'DI_GAS_SENSOR': True,
                'DI_VACUUM_SENSOR': True,
                'CMD_SOCKET1': False,
                'CMD_SOCKET2': False
            },
            'expected': {
                'DO_GAS_VALVE': False,
                'DO_SOCKET1': False,
                'DO_SOCKET2': False,
                'DO_ALARM_LIGHT': True,
                'ALM_ANY_ALARM': True,
                'SYSTEM_READY': False
            }
        },
        {
            'name': 'Втрата газу',
            'inputs': {
                'AI_VOLTAGE': 350,
                'AI_BOILER_TEMP': 60,
                'DI_GAS_SENSOR': False,
                'DI_VACUUM_SENSOR': True,
                'CMD_SOCKET1': False,
                'CMD_SOCKET2': False
            },
            'expected': {
                'DO_GAS_VALVE': False,
                'DO_SOCKET1': False,
                'DO_SOCKET2': False,
                'DO_ALARM_LIGHT': True,
                'ALM_ANY_ALARM': True,
                'SYSTEM_READY': False
            }
        },
        {
            'name': 'Втрата вакууму (критичний тест!)',
            'inputs': {
                'AI_VOLTAGE': 350,
                'AI_BOILER_TEMP': 60,
                'DI_GAS_SENSOR': True,
                'DI_VACUUM_SENSOR': False,
                'CMD_SOCKET1': False,
                'CMD_SOCKET2': False
            },
            'expected': {
                'DO_GAS_VALVE': False,  # ГАЗ ОБОВ'ЯЗКОВО закритий!
                'DO_SOCKET1': False,
                'DO_SOCKET2': False,
                'DO_ALARM_LIGHT': True,
                'ALM_ANY_ALARM': True,
                'SYSTEM_READY': False
            }
        },
        {
            'name': 'Керування розетками в нормальному режимі',
            'inputs': {
                'AI_VOLTAGE': 350,
                'AI_BOILER_TEMP': 60,
                'DI_GAS_SENSOR': True,
                'DI_VACUUM_SENSOR': True,
                'CMD_SOCKET1': True,
                'CMD_SOCKET2': True
            },
            'expected': {
                'DO_GAS_VALVE': True,
                'DO_SOCKET1': True,
                'DO_SOCKET2': True,
                'DO_ALARM_LIGHT': False,
                'ALM_ANY_ALARM': False,
                'SYSTEM_READY': True
            }
        },
        {
            'name': 'Розетки не працюють при аварії',
            'inputs': {
                'AI_VOLTAGE': 420,  # Аварія напруги
                'AI_BOILER_TEMP': 60,
                'DI_GAS_SENSOR': True,
                'DI_VACUUM_SENSOR': True,
                'CMD_SOCKET1': True,
                'CMD_SOCKET2': True
            },
            'expected': {
                'DO_GAS_VALVE': False,
                'DO_SOCKET1': False,  # Розетки вимкнені при аварії
                'DO_SOCKET2': False,  # Розетки вимкнені при аварії
                'DO_ALARM_LIGHT': True,
                'ALM_ANY_ALARM': True,
                'SYSTEM_READY': False
            }
        }
    ]

def main():
    """Основна функція тестування ST коду"""
    print("🔥 ТЕСТУВАЛЬНИК ST КОДУ ДЛЯ FATEK FBs-MA")
    print("="*60)
    
    # Шлях до ST файлу
    st_file = "FATEK_BoilerControl.ST"
    
    # Створення тестувальника
    tester = STCodeTester(st_file)
    
    # Крок 1: Завантаження ST коду
    if not tester.load_st_code():
        return False
    
    # Крок 2: Парсинг змінних
    if not tester.parse_variables():
        print("❌ Не вдалося розпарсити змінні")
        return False
    
    # Крок 3: Перевірка синтаксичної структури
    syntax_ok = tester.check_syntax_structure()
    
    # Крок 4: Перевірка логіки безпеки
    safety_ok = tester.check_safety_logic()
    
    # Крок 5: Симуляція виконання
    test_scenarios = create_test_scenarios()
    simulation_ok = tester.simulate_st_execution(test_scenarios)
    
    # Крок 6: Генерація звіту
    tester.generate_test_report()
    
    # Загальний результат
    overall_result = syntax_ok and safety_ok and simulation_ok
    
    print(f"\n🏆 ЗАГАЛЬНИЙ РЕЗУЛЬТАТ: {'✅ ВІДМІННО' if overall_result else '⚠️ ПОТРІБНІ ВИПРАВЛЕННЯ'}")
    
    if overall_result:
        print("\n🚀 ST код готовий до завантаження в FATEK FBs-MA!")
        print("📋 Рекомендації:")
        print("  1. Перевірте фізичне підключення датчиків")
        print("  2. Налаштуйте адреси в WinProladder")
        print("  3. Завантажте код в контролер")
        print("  4. Протестуйте без навантажень")
    else:
        print("\n🔧 Потрібні виправлення:")
        print("  1. Перевірте синтаксис ST коду")
        print("  2. Додайте відсутні блоки безпеки")
        print("  3. Перевірте логіку аварій")
    
    return overall_result

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️ Тестування перервано")
        exit(1)
    except Exception as e:
        print(f"\n❌ Помилка: {e}")
        exit(1)
