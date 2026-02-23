(* ============================================
   ПРОГРАМА КОНТРОЛЕРА БОЙЛЕРА
   Для FATEK FBs-10MAR
   Structured Text (ST) - готовий до завантаження
   ============================================ *)

PROGRAM BoilerControl

(* --- КОНСТАНТИ СИСТЕМИ --- *)
VAR_CONSTANT
    ADC_MAX         : INT := 4095;          (* Максимальне значення АЦП *)
    VOLTAGE_MAX     : INT := 500;           (* Макс. напруга 500В *)
    TEMP_MAX        : INT := 150;           (* Макс. температура 150°C *)
    
    (* Аварійні пороги *)
    VOLTAGE_TRIP    : INT := 400;           (* Відключення при 400В *)
    VOLTAGE_RESET   : INT := 380;           (* Відновлення при 380В *)
    TEMP_TRIP       : INT := 80;            (* Відключення при 80°C *)
    TEMP_RESET      : INT := 75;            (* Відновлення при 75°C *)
END_VAR

(* --- ВХОДИ (INPUTS) --- *)
VAR
    (* Аналогові входи FBs-10MAR *)
    AI_BoilerVoltage    AT %IW0 : INT;      (* Напруга бойлера 0-500В *)
    AI_BoilerTemp       AT %IW1 : INT;      (* Температура бойлера 0-150°C *)
    AI_WaterTemp        AT %IW2 : INT;      (* Температура води 0-150°C *)
    AI_TempSensor1      AT %IW3 : INT;      (* Датчик температури 1 *)
    AI_TempSensor2      AT %IW4 : INT;      (* Датчик температури 2 *)
    AI_OilPressure      AT %IW5 : INT;      (* Тиск масла 0-100% *)
    AI_SteamPressure    AT %IW6 : INT;      (* Тиск пари 0-10 бар *)
    
    (* Дискретні входи *)
    DI_GasSensor        AT %IX0.0 : BOOL;    (* Датчик газу: 1=є, 0=немає *)
    DI_VacuumSensor     AT %IX0.1 : BOOL;    (* Датчик вакууму: 1=є, 0=немає *)
    DI_OilPressureOK    AT %IX0.2 : BOOL;    (* Тиск масла: 1=норма, 0=низький *)
    DI_SteamPressureOK  AT %IX0.3 : BOOL;    (* Тиск пари: 1=норма, 0=високий/низький *)
    DI_EmergencyStop    AT %IX0.4 : BOOL;    (* Аварійний стоп: 1=активний *)
    DI_ManualMode       AT %IX0.5 : BOOL;    (* Ручний режим: 1=вкл *)
    
    (* Команди з панелі оператора *)
    CMD_SystemStart      AT %MX0.0 : BOOL;    (* Старт системи *)
    CMD_SystemStop       AT %MX0.1 : BOOL;    (* Стоп системи *)
    CMD_Socket1_On       AT %MX0.2 : BOOL;    (* Вкл розетку 1 *)
    CMD_Socket2_On       AT %MX0.3 : BOOL;    (* Вкл розетку 2 *)
    CMD_ResetAlarms      AT %MX0.4 : BOOL;    (* Скидання аварій *)
END_VAR

(* --- ВИХОДИ (OUTPUTS) --- *)
VAR
    (* Керуючі виходи *)
    DO_GasValve         AT %QX0.0 : BOOL;    (* Клапан газу: 1=відкрито *)
    DO_Socket1          AT %QX0.1 : BOOL;    (* Розетка 1: 1=вкл *)
    DO_Socket2          AT %QX0.2 : BOOL;    (* Розетка 2: 1=вкл *)
    DO_WaterPump        AT %QX0.3 : BOOL;    (* Насос води: 1=вкл *)
    DO_OilPump          AT %QX0.4 : BOOL;    (* Насос масла: 1=вкл *)
    DO_AlarmLight       AT %QX0.5 : BOOL;    (* Аварійна лампа: 1=вкл *)
    DO_PermitRun        AT %QX0.6 : BOOL;    (* Дозвіл роботи: 1=дозволено *)
    DO_FanVent          AT %QX0.7 : BOOL;    (* Вентиляція: 1=вкл *)
    
    (* Індикація стану для HMI *)
    ST_SystemRunning    AT %QW0 : INT;       (* Стан системи *)
    ST_GasAvailable     AT %QW1 : INT;       (* Наявність газу: 1/0 *)
    ST_VacuumOK         AT %QW2 : INT;       (* Вакуум: 1/0 *)
    ST_AlarmCode        AT %QW3 : INT;       (* Код аварії *)
END_VAR

(* --- ВНУТРІШНІ МАРКЕРИ --- *)
VAR
    (* Аварійні флаги *)
    ALM_VoltageHigh     : BOOL := FALSE;     (* Аварія: висока напруга *)
    ALM_TempHigh        : BOOL := FALSE;     (* Аварія: висока температура *)
    ALM_NoGas           : BOOL := FALSE;     (* Аварія: немає газу *)
    ALM_NoVacuum        : BOOL := FALSE;     (* Аварія: немає вакууму *)
    ALM_OilPressureLow  : BOOL := FALSE;     (* Аварія: низький тиск масла *)
    ALM_SteamPressureBad: BOOL := FALSE;     (* Аварія: неправильний тиск пари *)
    ALM_Emergency       : BOOL := FALSE;     (* Аварія: аварійний стоп *)
    ALM_AnyAlarm        : BOOL := FALSE;     (* Будь-яка аварія *)
    
    (* Стан системи *)
    SYS_Enabled         : BOOL := FALSE;     (* Система дозволена *)
    SYS_Running         : BOOL := FALSE;     (* Система працює *)
    SYS_Ready           : BOOL := FALSE;     (* Система готова *)
    SYS_ManualMode      : BOOL := FALSE;     (* Ручний режим *)
    
    (* Стан датчиків *)
    SNS_GasPresent      : BOOL := FALSE;     (* Газ присутній *)
    SNS_VacuumPresent   : BOOL := FALSE;     (* Вакуум присутній *)
    SNS_OilPressureOK   : BOOL := FALSE;     (* Тиск масла норма *)
    SNS_SteamPressureOK : BOOL := FALSE;     (* Тиск пари норма *)
    
    (* Фізичні величини для відображення *)
    PHY_Voltage         : INT;               (* Напруга в Вольтах *)
    PHY_BoilerTemp      : INT;               (* Температура бойлера °C *)
    PHY_WaterTemp       : INT;               (* Температура води °C *)
    PHY_Temp1           : INT;               (* Температура датчик 1 °C *)
    PHY_Temp2           : INT;               (* Температура датчик 2 °C *)
    PHY_OilPressure     : INT;               (* Тиск масла % *)
    PHY_SteamPressure   : INT;               (* Тиск пари бар *)
    
    (* Детектори фронтів для імпульсних входів *)
    FF_StartOld         : BOOL := FALSE;
    FF_StopOld          : BOOL := FALSE;
    FF_ResetOld         : BOOL := FALSE;
    FF_GasOld           : BOOL := FALSE;
    FF_VacuumOld        : BOOL := FALSE;
    FF_AlarmOld         : BOOL := FALSE;
    
    (* Лічильники та статистика *)
    CNT_Starts          : INT := 0;
    CNT_Stops           : INT := 0;
    CNT_Alarms          : INT := 0;
    CNT_GasFailures     : INT := 0;
    CNT_VacuumFailures  : INT := 0;
    CNT_RunTime         : INT := 0;          (* Час роботи в секундах *)
    TMR_RunTimer        : TON;               (* Таймер роботи *)
    
    (* Таймери та затримки *)
    TMR_StartDelay      : TON;               (* Затримка старту 3с *)
    TMR_AlarmDelay      : TON;               (* Затримка аварії 2с *)
    TMR_ResetDelay      : TON;               (* Затримка скидання 1с *)
END_VAR

(* ============================================
   ОСНОВНА ЛОГІКА ПРОГРАМИ
   ============================================ *)

(* --- БЛОК 1: ПЕРЕТВОРЕННЯ АЦП У ФІЗИЧНІ ВЕЛИЧИНИ --- *)
PHY_Voltage := AI_BoilerVoltage * VOLTAGE_MAX / ADC_MAX;
PHY_BoilerTemp := AI_BoilerTemp * TEMP_MAX / ADC_MAX;
PHY_WaterTemp := AI_WaterTemp * TEMP_MAX / ADC_MAX;
PHY_Temp1 := AI_TempSensor1 * TEMP_MAX / ADC_MAX;
PHY_Temp2 := AI_TempSensor2 * TEMP_MAX / ADC_MAX;
PHY_OilPressure := AI_OilPressure * 100 / ADC_MAX;
PHY_SteamPressure := AI_SteamPressure * 10 / ADC_MAX;

(* --- БЛОК 2: ЧИТАННЯ ДИСКРЕТНИХ ДАТЧИКІВ --- *)
SNS_GasPresent := DI_GasSensor;          (* 1 = газ є, 0 = немає *)
SNS_VacuumPresent := DI_VacuumSensor;     (* 1 = вакуум є, 0 = немає *)
SNS_OilPressureOK := DI_OilPressureOK;    (* 1 = норма, 0 = аварія *)
SNS_SteamPressureOK := DI_SteamPressureOK; (* 1 = норма, 0 = аварія *)
SYS_ManualMode := DI_ManualMode;

(* --- БЛОК 3: АВАРІЯ ВИСОКОЇ НАПРУГИ (≥400В) --- *)
IF PHY_Voltage >= VOLTAGE_TRIP THEN
    ALM_VoltageHigh := TRUE;
ELSE
    IF PHY_Voltage < VOLTAGE_RESET THEN
        ALM_VoltageHigh := FALSE;
    END_IF;
END_IF;

(* --- БЛОК 4: АВАРІЯ ВИСОКОЇ ТЕМПЕРАТУРИ (≥80°C) --- *)
IF PHY_BoilerTemp >= TEMP_TRIP THEN
    ALM_TempHigh := TRUE;
ELSE
    IF PHY_BoilerTemp < TEMP_RESET THEN
        ALM_TempHigh := FALSE;
    END_IF;
END_IF;

(* --- БЛОК 5: АВАРІЇ ПО ДАТЧИКАХ --- *)
ALM_NoGas := NOT SNS_GasPresent;           (* Немає газу = аварія *)
ALM_NoVacuum := NOT SNS_VacuumPresent;     (* Немає вакууму = аварія *)
ALM_OilPressureLow := NOT SNS_OilPressureOK; (* Низький тиск масла = аварія *)
ALM_SteamPressureBad := NOT SNS_SteamPressureOK; (* Неправильний тиск пари = аварія *)
ALM_Emergency := DI_EmergencyStop;         (* Зовнішній аварійний стоп *)

(* --- БЛОК 6: ЗАГАЛЬНА АВАРІЯ --- *)
ALM_AnyAlarm := ALM_VoltageHigh 
              OR ALM_TempHigh 
              OR ALM_NoGas 
              OR ALM_NoVacuum 
              OR ALM_OilPressureLow 
              OR ALM_SteamPressureBad 
              OR ALM_Emergency;

(* --- БЛОК 7: ЛОГІКА СТАРТ/СТОП --- *)

(* Детектор фронту команди старт *)
IF CMD_SystemStart AND NOT FF_StartOld THEN
    IF NOT SYS_Running AND NOT ALM_AnyAlarm THEN
        SYS_Enabled := TRUE;
        TMR_StartDelay(IN := TRUE, PT := T#3S); (* Затримка старту 3 секунди *)
    END_IF;
END_IF;
FF_StartOld := CMD_SystemStart;

(* Детектор фронту команди стоп *)
IF CMD_SystemStop AND NOT FF_StopOld THEN
    SYS_Enabled := FALSE;
    SYS_Running := FALSE;
END_IF;
FF_StopOld := CMD_SystemStop;

(* Автоматичний стоп при будь-якій аварії - НЕГАЙНО! *)
IF ALM_AnyAlarm THEN
    SYS_Enabled := FALSE;
    SYS_Running := FALSE;
END_IF;

(* Запуск після затримки *)
IF TMR_StartDelay.Q THEN
    SYS_Running := TRUE;
    TMR_StartDelay(IN := FALSE);
    CNT_Starts := CNT_Starts + 1;
END_IF;

(* --- БЛОК 8: ГОТОВНІСТЬ СИСТЕМИ --- *)
SYS_Ready := NOT ALM_VoltageHigh
           AND NOT ALM_TempHigh
           AND SNS_GasPresent
           AND SNS_VacuumPresent
           AND SNS_OilPressureOK
           AND SNS_SteamPressureOK
           AND NOT ALM_Emergency
           AND SYS_Running;

(* --- БЛОК 9: КЕРУВАННЯ КЛАПАНОМ ГАЗУ --- *)
(* ГОЛОВНЕ ПРАВИЛО: Газ відкритий тільки якщо ВСІ умови виконані *)
IF SYS_Ready THEN
    DO_GasValve := TRUE;    (* Відкрити клапан газу *)
ELSE
    DO_GasValve := FALSE;   (* ЗАКРИТИ клапан газу *)
END_IF;

(* ДОДАТКОВИЙ ЗАХИСТ: Якщо немає вакууму - ОБОВ'ЯЗКОВО закрити газ *)
IF NOT SNS_VacuumPresent THEN
    DO_GasValve := FALSE;
END_IF;

(* --- БЛОК 10: КЕРУВАННЯ РОЗЕТКАМИ --- *)
(* Розетки працюють тільки якщо немає аварій *)
DO_Socket1 := CMD_Socket1_On AND NOT ALM_AnyAlarm;
DO_Socket2 := CMD_Socket2_On AND NOT ALM_AnyAlarm;

(* --- БЛОК 11: КЕРУВАННЯ НАСОСАМИ --- *)
(* Насос води: працює якщо система готова і є температура води *)
DO_WaterPump := SYS_Ready AND PHY_WaterTemp > 20;

(* Насос масла: працює якщо система готова і тиск в нормі *)
DO_OilPump := SYS_Ready AND SNS_OilPressureOK;

(* Вентиляція: працює коли система працює *)
DO_FanVent := SYS_Running;

(* --- БЛОК 12: СИГНАЛІЗАЦІЯ ТА ІНДИКАЦІЯ --- *)
DO_AlarmLight := ALM_AnyAlarm;              (* Аварійна лампа *)
DO_PermitRun := SYS_Ready;                 (* Дозвіл роботи *)

(* Вивід стану для HMI *)
ST_SystemRunning := INT#1 IF SYS_Running ELSE INT#0;
ST_GasAvailable := INT#1 IF SNS_GasPresent ELSE INT#0;
ST_VacuumOK := INT#1 IF SNS_VacuumPresent ELSE INT#0;

(* Коди аварій для HMI *)
IF ALM_VoltageHigh THEN ST_AlarmCode := 1;
ELSIF ALM_TempHigh THEN ST_AlarmCode := 2;
ELSIF ALM_NoGas THEN ST_AlarmCode := 3;
ELSIF ALM_NoVacuum THEN ST_AlarmCode := 4;
ELSIF ALM_OilPressureLow THEN ST_AlarmCode := 5;
ELSIF ALM_SteamPressureBad THEN ST_AlarmCode := 6;
ELSIF ALM_Emergency THEN ST_AlarmCode := 7;
ELSE ST_AlarmCode := 0;
END_IF;

(* --- БЛОК 13: СТАТИСТИКА ТА ЛІЧИЛЬНИКИ --- *)

(* Лічильник аварій по передньому фронту *)
IF ALM_AnyAlarm AND NOT FF_AlarmOld THEN
    CNT_Alarms := CNT_Alarms + 1;
END_IF;
FF_AlarmOld := ALM_AnyAlarm;

(* Лічильник відмов газу *)
IF NOT SNS_GasPresent AND FF_GasOld THEN
    CNT_GasFailures := CNT_GasFailures + 1;
END_IF;
FF_GasOld := SNS_GasPresent;

(* Лічильник відмов вакууму *)
IF NOT SNS_VacuumPresent AND FF_VacuumOld THEN
    CNT_VacuumFailures := CNT_VacuumFailures + 1;
END_IF;
FF_VacuumOld := SNS_VacuumPresent;

(* Лічильник зупинок *)
IF (CMD_SystemStop AND NOT FF_StopOld) OR (ALM_AnyAlarm AND NOT FF_AlarmOld) THEN
    IF SYS_Running THEN
        CNT_Stops := CNT_Stops + 1;
    END_IF;
END_IF;

(* Таймер роботи системи *)
TMR_RunTimer(IN := SYS_Running, PT := T#1S);
IF TMR_RunTimer.Q THEN
    CNT_RunTime := CNT_RunTime + 1;
    TMR_RunTimer(IN := FALSE);
    TMR_RunTimer(IN := TRUE);
END_IF;

(* --- БЛОК 14: СКИДАННЯ АВАРІЙ --- *)
IF CMD_ResetAlarms AND NOT FF_ResetOld THEN
    TMR_ResetDelay(IN := TRUE, PT := T#1S);
END_IF;
FF_ResetOld := CMD_ResetAlarms;

IF TMR_ResetDelay.Q THEN
    (* Скидаємо тільки ті аварії, які можна скинути вручну *)
    IF NOT ALM_VoltageHigh AND NOT ALM_TempHigh AND NOT ALM_Emergency THEN
        ALM_NoGas := FALSE;
        ALM_NoVacuum := FALSE;
        ALM_OilPressureLow := FALSE;
        ALM_SteamPressureBad := FALSE;
    END_IF;
    TMR_ResetDelay(IN := FALSE);
END_IF;

(* ============================================
   ЕКСПОРТ ДАНИХ ДЛЯ HMI (REGISTRI)
   ============================================ *)
(* Аналогові дані для відображення *)
(*
MW0  = PHY_Voltage        (* Напруга бойлера В *)
MW1  = PHY_BoilerTemp     (* Температура бойлера °C *)
MW2  = PHY_WaterTemp      (* Температура води °C *)
MW3  = PHY_Temp1          (* Температура датчик 1 °C *)
MW4  = PHY_Temp2          (* Температура датчик 2 °C *)
MW5  = PHY_OilPressure    (* Тиск масла % *)
MW6  = PHY_SteamPressure  (* Тиск пари бар *)

MW10 = CNT_Starts         (* Кількість запусків *)
MW11 = CNT_Stops          (* Кількість зупинок *)
MW12 = CNT_Alarms         (* Кількість аварій *)
MW13 = CNT_GasFailures    (* Відмов газу *)
MW14 = CNT_VacuumFailures (* Відмов вакууму *)
MW15 = CNT_RunTime        (* Час роботи секунд *)

MX20 = SYS_Running         (* Система працює *)
MX21 = SYS_Ready          (* Система готова *)
MX22 = SNS_GasPresent     (* Газ присутній *)
MX23 = SNS_VacuumPresent  (* Вакуум присутній *)
MX24 = ALM_VoltageHigh    (* Аварія напруги *)
MX25 = ALM_TempHigh       (* Аварія температури *)
MX26 = ALM_NoGas          (* Аварія газу *)
MX27 = ALM_NoVacuum       (* Аварія вакууму *)
MX28 = ALM_OilPressureLow (* Аварія тиску масла *)
MX29 = ALM_SteamPressureBad(* Аварія тиску пари *)
MX30 = ALM_Emergency      (* Аварійний стоп *)
MX31 = ALM_AnyAlarm       (* Будь-яка аварія *)
*)

END_PROGRAM
