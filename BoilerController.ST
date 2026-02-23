(* ============================================
   КОНТРОЛЕР УПРАВЛІННЯ БОЙЛЕРОМ
   FATEK FBs-MA - Structured Text (ST)
   Версія 2.0 - Оптимізований під ваші вимоги
   ============================================ *)

(* --- КОНСТАНТИ --- *)
VAR CONSTANT
    (* Діапазони АЦП *)
    ADC_MAX         : INT := 4095;
    VOLTAGE_MAX     : INT := 500;   (* Макс. напруга, В *)
    TEMP_MAX        : INT := 150;   (* Макс. температура, °C *)
    
    (* Аварійні межі *)
    VOLTAGE_ALARM   : INT := 400;   (* Аварія напруги при 400В *)
    VOLTAGE_RESET   : INT := 380;   (* Скидання при 380В *)
    TEMP_ALARM      : INT := 80;    (* Аварія температури при 80°C *)
    TEMP_RESET      : INT := 75;    (* Скидання при 75°C *)
    
    (* АЦП значення для аварій *)
    ADC_VOLTAGE_ALARM : INT := 3276; (* 400В → АЦП: 4095*400/500 *)
    ADC_TEMP_ALARM    : INT := 2184; (* 80°C → АЦП: 4095*80/150 *)
END_VAR

(* --- ВХОДИ (Inputs) --- *)
VAR
    (* Аналогові входи 0..4095 *)
    AI_VOLTAGE      AT %IW0 : INT;   (* Напруга бойлера 0-500В *)
    AI_TEMP_BOILER  AT %IW1 : INT;   (* Температура бойлера 0-150°C *)
    AI_TEMP_WATER   AT %IW2 : INT;   (* Температура води 0-150°C *)
    AI_TEMP_1       AT %IW3 : INT;   (* Датчик температури 1 *)
    AI_TEMP_2       AT %IW4 : INT;   (* Датчик температури 2 *)
    AI_OIL_PRESSURE AT %IW5 : INT;   (* Тиск масла (аналоговий) *)
    
    (* Дискретні входи *)
    X_GAS_PRESENT   AT %IX0.0 : BOOL; (* Датчик газу: TRUE=є газ *)
    X_VACUUM_OK     AT %IX0.1 : BOOL; (* Датчик вакууму: TRUE=є вакуум *)
    X_OIL_PRESS_OK  AT %IX0.2 : BOOL; (* Тиск масла: TRUE=норма *)
    X_EMERGENCY_STOP: AT %IX0.3 : BOOL; (* Аварійний стоп: TRUE=активний *)
    
    (* Команди оператора/HMI *)
    CMD_START       AT %MX10.0 : BOOL; (* Команда старт *)
    CMD_STOP        AT %MX10.1 : BOOL; (* Команда стоп *)
    CMD_SOCKET1     AT %MX10.2 : BOOL; (* Команда розетка 1 *)
    CMD_SOCKET2     AT %MX10.3 : BOOL; (* Команда розетка 2 *)
END_VAR

(* --- ВИХОДИ (Outputs) --- *)
VAR
    Y_GAS_VALVE     AT %QX0.0 : BOOL; (* Клапан газу: TRUE=відкрито *)
    Y_SOCKET1       AT %QX0.1 : BOOL; (* Розетка 1 *)
    Y_SOCKET2       AT %QX0.2 : BOOL; (* Розетка 2 *)
    Y_ALARM_LIGHT   AT %QX0.3 : BOOL; (* Аварійна лампа *)
    Y_PERMIT_RUN    AT %QX0.4 : BOOL; (* Дозвіл роботи *)
    Y_WATER_PUMP    AT %QX0.5 : BOOL; (* Насос води *)
END_VAR

(* --- ВНУТРІШНІ МАРКЕРИ --- *)
VAR
    (* Аварійні флаги *)
    M_VOLTAGE_ALARM : BOOL := FALSE; (* Аварія напруги *)
    M_TEMP_ALARM    : BOOL := FALSE; (* Аварія температури *)
    M_VACUUM_ALARM  : BOOL := FALSE; (* Аварія вакууму *)
    M_OIL_ALARM     : BOOL := FALSE; (* Аварія тиску масла *)
    M_ANY_ALARM     : BOOL := FALSE; (* Будь-яка аварія *)
    
    (* Стан системи *)
    M_SYSTEM_RUN    : BOOL := FALSE; (* Система запущена *)
    M_SYSTEM_READY  : BOOL := FALSE; (* Система готова *)
    M_GAS_AVAILABLE : BOOL := FALSE; (* Газ доступний *)
    M_VACUUM_OK     : BOOL := FALSE; (* Вакуум в нормі *)
    
    (* Фізичні величини для HMI *)
    VOLTAGE_DISPLAY : INT; (* Напруга в Вольтах *)
    TEMP_B_DISPLAY  : INT; (* Температура бойлера °C *)
    TEMP_W_DISPLAY  : INT; (* Температура води °C *)
    TEMP_1_DISPLAY  : INT; (* Температура датчик 1 °C *)
    TEMP_2_DISPLAY  : INT; (* Температура датчик 2 °C *)
    OIL_P_DISPLAY   : INT; (* Тиск масла в ум.од.*)
    
    (* Детектори фронтів *)
    M_CMD_START_OLD : BOOL := FALSE;
    M_CMD_STOP_OLD  : BOOL := FALSE;
    M_GAS_OLD       : BOOL := FALSE;
    M_VAC_OLD       : BOOL := FALSE;
    M_ALARM_OLD     : BOOL := FALSE;
    
    (* Статистика для HMI *)
    STAT_START_COUNT: INT := 0;
    STAT_ALARM_COUNT: INT := 0;
    STAT_GAS_OFF    : INT := 0;
    STAT_VAC_OFF    : INT := 0;
END_VAR

(* ============================================
   БЛОК 1: ПЕРЕТВОРЕННЯ АЦП → ФІЗИЧНІ ВЕЛИЧИНИ
   ============================================ *)

(* Напруга: 0-4095 = 0-500В *)
VOLTAGE_DISPLAY := AI_VOLTAGE * VOLTAGE_MAX / ADC_MAX;

(* Температури: 0-4095 = 0-150°C *)
TEMP_B_DISPLAY := AI_TEMP_BOILER * TEMP_MAX / ADC_MAX;
TEMP_W_DISPLAY := AI_TEMP_WATER * TEMP_MAX / ADC_MAX;
TEMP_1_DISPLAY := AI_TEMP_1 * TEMP_MAX / ADC_MAX;
TEMP_2_DISPLAY := AI_TEMP_2 * TEMP_MAX / ADC_MAX;

(* Тиск масла: 0-4095 = 0-100% *)
OIL_P_DISPLAY := AI_OIL_PRESSURE * 100 / ADC_MAX;

(* ============================================
   БЛОК 2: АВАРІЯ НАПРУГИ (≥400В)
   ============================================ *)
IF VOLTAGE_DISPLAY >= VOLTAGE_ALARM THEN
    M_VOLTAGE_ALARM := TRUE;
ELSE
    IF VOLTAGE_DISPLAY < VOLTAGE_RESET THEN
        M_VOLTAGE_ALARM := FALSE;
    END_IF;
END_IF;

(* ============================================
   БЛОК 3: АВАРІЯ ТЕМПЕРАТУРИ (≥80°C)
   ============================================ *)
IF TEMP_B_DISPLAY >= TEMP_ALARM THEN
    M_TEMP_ALARM := TRUE;
ELSE
    IF TEMP_B_DISPLAY < TEMP_RESET THEN
        M_TEMP_ALARM := FALSE;
    END_IF;
END_IF;

(* ============================================
   БЛОК 4: ДАТЧИК ГАЗУ
   ============================================ *)
M_GAS_AVAILABLE := X_GAS_PRESENT;

(* Лічильник відключень газу *)
IF M_GAS_AVAILABLE = FALSE AND M_GAS_OLD = TRUE THEN
    STAT_GAS_OFF := STAT_GAS_OFF + 1;
END_IF;
M_GAS_OLD := M_GAS_AVAILABLE;

(* ============================================
   БЛОК 5: ДАТЧИК ВАКУУМУ
   ============================================ *)
M_VACUUM_OK := X_VACUUM_OK;

IF M_VACUUM_OK = FALSE THEN
    M_VACUUM_ALARM := TRUE;  (* Немає вакууму = аварія *)
ELSE
    M_VACUUM_ALARM := FALSE;
END_IF;

(* Лічильник відключень вакууму *)
IF M_VACUUM_OK = FALSE AND M_VAC_OLD = TRUE THEN
    STAT_VAC_OFF := STAT_VAC_OFF + 1;
END_IF;
M_VAC_OLD := M_VACUUM_OK;

(* ============================================
   БЛОК 6: ТИСК МАСЛА
   ============================================ *)
IF X_OIL_PRESS_OK = FALSE THEN
    M_OIL_ALARM := TRUE;
ELSE
    M_OIL_ALARM := FALSE;
END_IF;

(* ============================================
   БЛОК 7: ЗАГАЛЬНА АВАРІЯ
   ============================================ *)
M_ANY_ALARM := M_VOLTAGE_ALARM 
             OR M_TEMP_ALARM 
             OR M_VACUUM_ALARM 
             OR M_OIL_ALARM 
             OR X_EMERGENCY_STOP;

(* Лічильник аварій *)
IF M_ANY_ALARM = TRUE AND M_ALARM_OLD = FALSE THEN
    STAT_ALARM_COUNT := STAT_ALARM_COUNT + 1;
END_IF;
M_ALARM_OLD := M_ANY_ALARM;

(* ============================================
   БЛОК 8: ЛОГІКА СТАРТ/СТОП
   ============================================ *)

(* Детектор фронту старту *)
IF CMD_START = TRUE AND M_CMD_START_OLD = FALSE THEN
    IF M_SYSTEM_RUN = FALSE AND M_ANY_ALARM = FALSE THEN
        M_SYSTEM_RUN := TRUE;
        STAT_START_COUNT := STAT_START_COUNT + 1;
    END_IF;
END_IF;
M_CMD_START_OLD := CMD_START;

(* Детектор фронту стопу *)
IF CMD_STOP = TRUE AND M_CMD_STOP_OLD = FALSE THEN
    M_SYSTEM_RUN := FALSE;
END_IF;
M_CMD_STOP_OLD := CMD_STOP;

(* Автоматичний стоп при аварії *)
IF M_ANY_ALARM = TRUE THEN
    M_SYSTEM_RUN := FALSE;
END_IF;

(* ============================================
   БЛОК 9: ГОТОВНІСТЬ СИСТЕМИ
   ============================================ *)
M_SYSTEM_READY := NOT M_VOLTAGE_ALARM      (* Напруга норма *)
                AND NOT M_TEMP_ALARM        (* Температура норма *)
                AND M_GAS_AVAILABLE          (* Газ є *)
                AND M_VACUUM_OK              (* Вакуум є *)
                AND NOT M_OIL_ALARM           (* Тиск масла норма *)
                AND NOT X_EMERGENCY_STOP      (* Немає аварійного стопу *)
                AND M_SYSTEM_RUN;             (* Система запущена *)

(* ============================================
   БЛОК 10: КЕРУВАННЯ КЛАПАНОМ ГАЗУ
   ============================================ *)
(* Головна логіка: газ відкритий тільки якщо ВСІ умови виконані *)
IF M_SYSTEM_READY THEN
    Y_GAS_VALVE := TRUE;   (* Відкрити клапан газу *)
ELSE
    Y_GAS_VALVE := FALSE;  (* Закрити клапан газу *)
END_IF;

(* Додатковий захист: якщо немає вакууму - ОБОВ'ЯЗКОВО закрити газ *)
IF M_VACUUM_OK = FALSE THEN
    Y_GAS_VALVE := FALSE;
END_IF;

(* ============================================
   БЛОК 11: КЕРУВАННЯ РОЗЕТКАМИ
   ============================================ *)

(* Розетка 1 - вмикається командою, але не при аварії *)
IF CMD_SOCKET1 = TRUE AND M_ANY_ALARM = FALSE THEN
    Y_SOCKET1 := TRUE;
ELSE
    Y_SOCKET1 := FALSE;
END_IF;

(* Розетка 2 - вмикається командою, але не при аварії *)
IF CMD_SOCKET2 = TRUE AND M_ANY_ALARM = FALSE THEN
    Y_SOCKET2 := TRUE;
ELSE
    Y_SOCKET2 := FALSE;
END_IF;

(* ============================================
   БЛОК 12: КЕРУВАННЯ НАСОСОМ ВОДИ
   ============================================ *)
(* Насос води працює якщо система готова і є температура води *)
IF M_SYSTEM_READY AND TEMP_W_DISPLAY > 20 THEN
    Y_WATER_PUMP := TRUE;
ELSE
    Y_WATER_PUMP := FALSE;
END_IF;

(* ============================================
   БЛОК 13: АВАРІЙНА СИГНАЛІЗАЦІЯ
   ============================================ *)
Y_ALARM_LIGHT := M_ANY_ALARM;

(* ============================================
   БЛОК 14: ЗАГАЛЬНИЙ ДОЗВІЛ РОБОТИ
   ============================================ *)
Y_PERMIT_RUN := M_SYSTEM_READY;

(* ============================================
   БЛОК 15: ЕКСПОРТ ДАНИХ ДЛЯ HMI
   ============================================ *)
(* Ці маркери можна використовувати для відображення на HMI дисплей *)
(*
MW0  = VOLTAGE_DISPLAY    (* Напруга в Вольтах *)
MW1  = TEMP_B_DISPLAY     (* Температура бойлера °C *)
MW2  = TEMP_W_DISPLAY     (* Температура води °C *)
MW3  = TEMP_1_DISPLAY     (* Температура датчик 1 °C *)
MW4  = TEMP_2_DISPLAY     (* Температура датчик 2 °C *)
MW5  = OIL_P_DISPLAY      (* Тиск масла % *)

MW10 = STAT_START_COUNT   (* Кількість запусків *)
MW11 = STAT_ALARM_COUNT   (* Кількість аварій *)
MW12 = STAT_GAS_OFF       (* Відключень газу *)
MW13 = STAT_VAC_OFF       (* Відключень вакууму *)

MX20 = M_SYSTEM_RUN       (* Система запущена *)
MX21 = M_SYSTEM_READY     (* Система готова *)
MX22 = M_GAS_AVAILABLE    (* Газ доступний *)
MX23 = M_VACUUM_OK        (* Вакуум в нормі *)
MX24 = M_VOLTAGE_ALARM    (* Аварія напруги *)
MX25 = M_TEMP_ALARM       (* Аварія температури *)
MX26 = M_VACUUM_ALARM     (* Аварія вакууму *)
MX27 = M_OIL_ALARM        (* Аварія тиску масла *)
MX28 = M_ANY_ALARM        (* Загальна аварія *)
*)
