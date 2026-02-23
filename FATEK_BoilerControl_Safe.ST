(* ============================================
   ДОДАТКОВИЙ ЗАХИСТ ДЛЯ FATEK FBs-10MAR
   Розширена версія з додатковими перевірками
   ============================================ *)

PROGRAM BoilerControlSafe

(* --- ДОДАТКОВІ КОНСТАНТИ БЕЗПЕКИ --- *)
VAR_CONSTANT
    (* Межі АЦП з запасом *)
    ADC_SAFE_MIN        : INT := 100;           (* Мінімальне значення АЦП *)
    ADC_SAFE_MAX        : INT := 3900;          (* Максимальне значення АЦП *)
    
    (* Діапазони перевірки датчиків *)
    VOLTAGE_MIN_CHECK   : INT := 50;            (* Мінімальна напруга 50В *)
    VOLTAGE_MAX_CHECK   : INT := 480;           (* Максимальна напруга 480В *)
    TEMP_MIN_CHECK      : INT := -20;           (* Мінімальна температура -20°C *)
    TEMP_MAX_CHECK      : INT := 120;           (* Максимальна температура 120°C *)
    
    (* Часові затримки безпеки *)
    STARTUP_DELAY       : TIME := T#5S;         (* Затримка старту 5 секунд *)
    GAS_VALVE_DELAY     : TIME := T#2S;         (* Затримка відкриття газу 2с *)
    EMERGENCY_SHUTDOWN  : TIME := T#0.5S;       (* Аварійне відключення 0.5с *)
    
    (* Кількість циклів для стабілізації *)
    STABILIZATION_CYCLES: INT := 10;            (* 10 циклів для стабілізації *)
END_VAR

(* --- ДОДАТКОВІ МАРКЕРИ БЕЗПЕКИ --- *)
VAR
    (* Перевірка датчиків *)
    SNS_VoltageOK       : BOOL := TRUE;         (* Напруга в межах норми *)
    SNS_TemperatureOK   : BOOL := TRUE;         (* Температура в межах норми *)
    SNS_ADC_OK          : BOOL := TRUE;         (* АЦП працює нормально *)
    SNS_CommunicationOK : BOOL := TRUE;         (* Зв'язок з датчиками є *)
    
    (* Стани безпеки *)
    SAF_SystemStable    : BOOL := FALSE;        (* Система стабілізована *)
    SAF_StartupMode      : BOOL := TRUE;         (* Режим старту *)
    SAF_EmergencyMode   : BOOL := FALSE;        (* Аварійний режим *)
    SAF_ManualOverride  : BOOL := FALSE;        (* Ручне перевизначення *)
    
    (* Лічильники безпеки *)
    SAF_CycleCounter    : INT := 0;             (* Лічильник циклів *)
    SAF_ErrorCounter    : INT := 0;             (* Лічильник помилок *)
    SAF_LastErrorTime   : TIME := T#0S;         (* Час останньої помилки *)
    
    (* Детектори помилок *)
    ERR_ADC_Failure     : BOOL := FALSE;        (* Відмова АЦП *)
    ERR_SensorRange     : BOOL := FALSE;        (* Датчик поза діапазоном *)
    ERR_CommTimeout     : BOOL := FALSE;        (* Тайм-аут зв'язку *)
    ERR_PowerSupply     : BOOL := FALSE;        (* Проблема живлення *)
    
    (* Таймери безпеки *)
    TMR_SafetyStartup   : TON;                  (* Таймер безпечного старту *)
    TMR_GasValveSafety  : TON;                  (* Таймер безпеки газового клапана *)
    TMR_EmergencyDelay  : TON;                  (* Таймер аварійної затримки *)
    TMR_Watchdog        : TON;                  (* Ватчдог системи *)
    
    (* Буфери для фільтрації *)
    FILTER_Voltage      : ARRAY[0..4] OF INT;   (* Фільтр напруги *)
    FILTER_Temperature  : ARRAY[0..4] OF INT;   (* Фільтр температури *)
    FILTER_Index        : INT := 0;             (* Індекс фільтра *)
END_VAR

(* ============================================
   БЛОК БЕЗПЕКИ: ПЕРЕВІРКА АЦП ВХОДІВ
   ============================================ *)

(* Перевірка АЦП на вихід за межі *)
IF (AI_BoilerVoltage < ADC_SAFE_MIN OR AI_BoilerVoltage > ADC_SAFE_MAX) OR
   (AI_BoilerTemp < ADC_SAFE_MIN OR AI_BoilerTemp > ADC_SAFE_MAX) OR
   (AI_WaterTemp < ADC_SAFE_MIN OR AI_WaterTemp > ADC_SAFE_MAX) THEN
    ERR_ADC_Failure := TRUE;
    SAF_ErrorCounter := SAF_ErrorCounter + 1;
ELSE
    ERR_ADC_Failure := FALSE;
END_IF;

(* Перевірка фізичних величин на адекватність *)
IF (PHY_Voltage < VOLTAGE_MIN_CHECK OR PHY_Voltage > VOLTAGE_MAX_CHECK) OR
   (PHY_BoilerTemp < TEMP_MIN_CHECK OR PHY_BoilerTemp > TEMP_MAX_CHECK) THEN
    ERR_SensorRange := TRUE;
    SAF_ErrorCounter := SAF_ErrorCounter + 1;
ELSE
    ERR_SensorRange := FALSE;
END_IF;

(* ============================================
   БЛОК БЕЗПЕКИ: ФІЛЬТРАЦІЯ СИГНАЛІВ
   ============================================ *)

(* Кільцевий буфер для фільтрації напруги *)
FILTER_Voltage[FILTER_Index] := AI_BoilerVoltage;
FILTER_Temperature[FILTER_Index] := AI_BoilerTemp;

(* Обчислення середнього значення *)
VAR
    i : INT;
    sum_voltage : INT := 0;
    sum_temp : INT := 0;
END_VAR

FOR i := 0 TO 4 DO
    sum_voltage := sum_voltage + FILTER_Voltage[i];
    sum_temp := sum_temp + FILTER_Temperature[i];
END_FOR;

(* Використовуємо відфільтровані значення *)
PHY_Voltage := (sum_voltage / 5) * VOLTAGE_MAX / ADC_MAX;
PHY_BoilerTemp := (sum_temp / 5) * TEMP_MAX / ADC_MAX;

(* Оновлення індексу фільтра *)
FILTER_Index := (FILTER_Index + 1) MOD 5;

(* ============================================
   БЛОК БЕЗПЕКИ: СТАБІЛІЗАЦІЯ СИСТЕМИ
   ============================================ *)

(* Лічильник циклів для стабілізації *)
IF SAF_CycleCounter < STABILIZATION_CYCLES THEN
    SAF_CycleCounter := SAF_CycleCounter + 1;
    SAF_SystemStable := FALSE;
    SAF_StartupMode := TRUE;
ELSE
    SAF_SystemStable := TRUE;
    SAF_StartupMode := FALSE;
END_IF;

(* Таймер безпечного старту *)
TMR_SafetyStartup(IN := SAF_StartupMode, PT := STARTUP_DELAY);

(* ============================================
   БЛОК БЕЗПЕКИ: УМОВИ РОБОТИ
   ============================================ *)

(* Загальні умови безпеки *)
SNS_VoltageOK := NOT ERR_ADC_Failure AND NOT ERR_SensorRange;
SNS_TemperatureOK := NOT ERR_SensorRange;
SNS_ADC_OK := NOT ERR_ADC_Failure;
SNS_CommunicationOK := TRUE; (* Для майбутнього розширення *)

(* ============================================
   БЛОК БЕЗПЕКИ: МОДИФІКОВАНА ЛОГІКА УПРАВЛІННЯ
   ============================================ *)

(* Посилені умови готовності системи *)
SYS_Ready := SAF_SystemStable                    (* Система стабільна *)
           AND SNS_VoltageOK                      (* Напруга норма *)
           AND SNS_TemperatureOK                  (* Температура норма *)
           AND SNS_ADC_OK                         (* АЦП працює *)
           AND NOT ERR_ADC_Failure                (* Немає помилок АЦП *)
           AND NOT ERR_SensorRange                (* Датчики в діапазоні *)
           AND NOT SAF_EmergencyMode              (* Не аварійний режим *)
           AND SNS_GasPresent                      (* Газ є *)
           AND SNS_VacuumPresent                   (* Вакуум є *)
           AND SNS_OilPressureOK                   (* Тиск масла норма *)
           AND SNS_SteamPressureOK                 (* Тиск пари норма *)
           AND NOT ALM_Emergency                   (* Немає зовнішньої аварії *)
           AND SYS_Running                         (* Система запущена *)
           AND SAF_ErrorCounter < 10;              (* Забагато помилок? *)

(* ============================================
   БЛОК БЕЗПЕКИ: КЕРУВАННЯ ГАЗОВИМ КЛАПАНОМ
   ============================================ *)

(* Додатковий таймер безпеки для газового клапана *)
IF SYS_Ready THEN
    TMR_GasValveSafety(IN := TRUE, PT := GAS_VALVE_DELAY);
ELSE
    TMR_GasValveSafety(IN := FALSE);
END_IF;

(* Відкриття газу тільки після всіх перевірок + затримка *)
DO_GasValve := SYS_Ready AND TMR_GasValveSafety.Q AND NOT SAF_StartupMode;

(* ПРИОРИТЕТНИЙ ЗАХИСТ: Вакуум важливіший за все! *)
IF NOT SNS_VacuumPresent THEN
    DO_GasValve := FALSE;
    SAF_EmergencyMode := TRUE;
END_IF;

(* ============================================
   БЛОК БЕЗПЕКИ: АВАРІЙНІ ВИХОДИ
   ============================================ *)

(* Аварійне відключення при критичних помилках *)
IF ERR_ADC_Failure OR ERR_SensorRange OR SAF_ErrorCounter >= 10 THEN
    SAF_EmergencyMode := TRUE;
    TMR_EmergencyDelay(IN := TRUE, PT := EMERGENCY_SHUTDOWN);
END_IF;

(* Примусове відключення всього при аварії *)
IF SAF_EmergencyMode OR TMR_EmergencyDelay.Q THEN
    DO_GasValve := FALSE;
    DO_Socket1 := FALSE;
    DO_Socket2 := FALSE;
    DO_WaterPump := FALSE;
    DO_OilPump := FALSE;
    DO_FanVent := FALSE;
    SYS_Running := FALSE;
END_IF;

(* ============================================
   БЛОК БЕЗПЕКИ: WATCHDOG ТА ДІАГНОСТИКА
   ============================================ *)

(* Watchdog таймер - має перезавантажуватись кожен цикл *)
TMR_Watchdog(IN := TRUE, PT := T#1S);

(* Якщо watchdog не спрацьовує - є проблема з циклом сканування *)
IF NOT TMR_Watchdog.Q THEN
    ERR_CommTimeout := TRUE;
    SAF_ErrorCounter := SAF_ErrorCounter + 1;
END_IF;

(* Скидання watchdog на кожному циклі *)
TMR_Watchdog(IN := FALSE);
TMR_Watchdog(IN := TRUE);

(* ============================================
   БЛОК БЕЗПЕКИ: ІНДИКАЦІЯ ПОМИЛОК
   ============================================ *)

(* Розширена індикація кодів помилок *)
IF ERR_ADC_Failure THEN ST_AlarmCode := 10;
ELSIF ERR_SensorRange THEN ST_AlarmCode := 11;
ELSIF ERR_CommTimeout THEN ST_AlarmCode := 12;
ELSIF ERR_PowerSupply THEN ST_AlarmCode := 13;
ELSIF SAF_EmergencyMode THEN ST_AlarmCode := 99;
ELSE
    (* Оригінальні коди аварій *)
    IF ALM_VoltageHigh THEN ST_AlarmCode := 1;
    ELSIF ALM_TempHigh THEN ST_AlarmCode := 2;
    ELSIF ALM_NoGas THEN ST_AlarmCode := 3;
    ELSIF ALM_NoVacuum THEN ST_AlarmCode := 4;
    ELSIF ALM_OilPressureLow THEN ST_AlarmCode := 5;
    ELSIF ALM_SteamPressureBad THEN ST_AlarmCode := 6;
    ELSIF ALM_Emergency THEN ST_AlarmCode := 7;
    ELSE ST_AlarmCode := 0;
    END_IF;
END_IF;

(* ============================================
   БЛОК БЕЗПЕКИ: ЛОГІКУВАННЯ ПОМИЛОК
   ============================================ *)

(* Реєстрація часу помилки *)
IF ERR_ADC_Failure OR ERR_SensorRange OR ERR_CommTimeout THEN
    SAF_LastErrorTime := CURRENT_TIME;
END_IF;

(* Автоматичне скидання помилок після 5 хвилин *)
IF (CURRENT_TIME - SAF_LastErrorTime) > T#5M THEN
    ERR_ADC_Failure := FALSE;
    ERR_SensorRange := FALSE;
    ERR_CommTimeout := FALSE;
    SAF_EmergencyMode := FALSE;
    SAF_ErrorCounter := 0;
END_IF;

END_PROGRAM
