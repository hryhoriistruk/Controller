(* ============================================
   КЕРУВАННЯ БОЙЛЕРОМ / ГАЗОВИМ ОБЛАДНАННЯМ
   Fatek FBs-MA — Structured Text (ST)
   Повна версія з усіма функціями з Python-коду
   ============================================ *)

(* --- КОНСТАНТИ --- *)
VAR CONSTANT
    (* Межі АЦП *)
    ADC_MAX             : INT := 4095;
    NAPRUGA_MAX         : INT := 500;   (* Макс. напруга, В *)
    TEMP_MAX            : INT := 150;   (* Макс. температура, °C *)

    (* Межі спрацьовування аварій *)
    NAPRUGA_AVAR_VOLT   : INT := 400;   (* Аварія напруги при 400В *)
    NAPRUGA_HYST_VOLT   : INT := 380;   (* Гістерезис: скидання при 380В *)
    TEMP_AVAR_GRAD      : INT := 80;    (* Аварія температури при 80°C *)
    TEMP_HYST_GRAD      : INT := 75;    (* Гістерезис: скидання при 75°C *)

    (* Відповідні значення АЦП для аварій *)
    NAPRUGA_AVARIA      : INT := 3276;  (* 400В → АЦП: 4095*400/500=3276 *)
    TEMP_BOILER_AVARIA  : INT := 2184;  (* 80°C → АЦП: 4095*80/150=2184 *)
END_VAR

(* --- ЗМІННІ ВХОДІВ (Inputs) --- *)
VAR
    (* Аналогові входи 0..4095 *)
    AI_NAPRUGA      AT %IW0 : INT;   (* Напруга бойлера 0-500В *)
    AI_TEMP_BOILER  AT %IW1 : INT;   (* Температура бойлера 0-150°C *)
    AI_TEMP_VODA    AT %IW2 : INT;   (* Температура води 0-150°C *)
    AI_TEMP_2       AT %IW3 : INT;   (* Додатковий датчик температури *)
    AI_TISK_MASLA   AT %IW4 : INT;   (* Тиск масла (аналоговий датчик) *)

    (* Дискретні входи *)
    X_GAZ           AT %IX0.0 : BOOL; (* Датчик газу: TRUE=є газ *)
    X_VAKUUM        AT %IX0.1 : BOOL; (* Датчик вакууму: TRUE=є вакуум *)
    X_TISK_MASLA_DI AT %IX0.2 : BOOL; (* Тиск масла дискретний: TRUE=норма *)
    X_AVARIA_EXT    AT %IX0.3 : BOOL; (* Зовнішній аварійний стоп *)

    (* Команди з HMI / оператора *)
    CMD_ROZET_1     AT %MX10.0 : BOOL; (* Команда вкл. розетки 1 *)
    CMD_ROZET_2     AT %MX10.1 : BOOL; (* Команда вкл. розетки 2 *)
    CMD_START       AT %MX10.2 : BOOL; (* Старт системи (імпульс) *)
    CMD_STOP        AT %MX10.3 : BOOL; (* Стоп системи (імпульс) *)
END_VAR

(* --- ЗМІННІ ВИХОДІВ (Outputs) --- *)
VAR
    Y_KLAPAN_GAZ    AT %QX0.0 : BOOL; (* Клапан газу: TRUE=відкрито *)
    Y_ROZET_1       AT %QX0.1 : BOOL; (* Розетка 1 *)
    Y_ROZET_2       AT %QX0.2 : BOOL; (* Розетка 2 *)
    Y_AVARIA_SIGNAL AT %QX0.3 : BOOL; (* Аварійна сигналізація *)
    Y_DOZV_ROBOTY   AT %QX0.4 : BOOL; (* Загальний дозвіл роботи *)
END_VAR

(* --- ВНУТРІШНІ МАРКЕРИ --- *)
VAR
    (* Аварії *)
    M_AVARIA_NAPRUGA    : BOOL; (* Аварія: напруга >= 400В *)
    M_AVARIA_TEMP       : BOOL; (* Аварія: температура >= 80°C *)
    M_AVARIA_VAKUUM     : BOOL; (* Аварія: пропав вакуум *)
    M_ZAGALNA_AVARIA    : BOOL; (* Будь-яка аварія *)

    (* Стан датчиків *)
    M_GAZ_IE            : BOOL; (* Газ є = 1, немає = 0 *)
    M_VAKUUM_IE         : BOOL; (* Вакуум є = 1, немає = 0 *)
    M_TISK_NORMA        : BOOL; (* Тиск масла в нормі *)

    (* Стан системи *)
    M_SYSTEM_ON         : BOOL; (* Система запущена *)
    M_SYSTEM_READY      : BOOL; (* Система готова до роботи *)

    (* Фізичні величини (для відображення на HMI) *)
    TEMP_BOILER_GRAD    : INT;  (* Температура бойлера °C *)
    TEMP_VODA_GRAD      : INT;  (* Температура води °C *)
    TEMP_2_GRAD         : INT;  (* Температура доп. датчик °C *)
    NAPRUGA_VOLT        : INT;  (* Напруга в Вольтах *)

    (* Допоміжні змінні для статистики *)
    M_START_PULSE       : BOOL; (* Детектор імпульсу старту *)
    M_STOP_PULSE        : BOOL; (* Детектор імпульсу стопу *)
    STAT_STARTS         : INT;  (* Лічильник запусків *)
    STAT_STOPS          : INT;  (* Лічильник зупинок *)
    STAT_ALARMS         : INT;  (* Лічильник аварій *)
    STAT_GAS_OFF        : INT;  (* Лічильник відключень газу *)
    STAT_VAKUUM_OFF     : INT;  (* Лічильник відключень вакууму *)

    (* Для детектора фронтів *)
    M_CMD_START_OLD     : BOOL;
    M_CMD_STOP_OLD      : BOOL;
    M_GAZ_OLD           : BOOL;
    M_VAKUUM_OLD        : BOOL;
    M_ALARM_OLD         : BOOL;
END_VAR

(* ============================================
   БЛОК 1: ПЕРЕРАХУНОК АЦП → РЕАЛЬНІ ОДИНИЦІ
   Формула: РЕАЛ = АЦП * MAX_ЗНАЧЕННЯ / 4095
   ============================================ *)

(* Напруга: 0-4095 = 0-500В *)
NAPRUGA_VOLT    := AI_NAPRUGA * 500 / 4095;

(* Температури: 0-4095 = 0-150°C *)
TEMP_BOILER_GRAD := AI_TEMP_BOILER * 150 / 4095;
TEMP_VODA_GRAD   := AI_TEMP_VODA * 150 / 4095;
TEMP_2_GRAD      := AI_TEMP_2 * 150 / 4095;

(* ============================================
   БЛОК 2: АВАРІЯ ПО НАПРУЗІ БОЙЛЕРА
   З гістерезисом: ввімкнення при 400В, вимкнення при 380В
   ============================================ *)
IF NAPRUGA_VOLT >= NAPRUGA_AVAR_VOLT THEN
    M_AVARIA_NAPRUGA := TRUE;
ELSE
    IF NAPRUGA_VOLT < NAPRUGA_HYST_VOLT THEN
        M_AVARIA_NAPRUGA := FALSE;
    END_IF;
END_IF;

(* ============================================
   БЛОК 3: АВАРІЯ ПО ТЕМПЕРАТУРІ БОЙЛЕРА
   З гістерезисом: ввімкнення при 80°C, вимкнення при 75°C
   ============================================ *)
IF TEMP_BOILER_GRAD >= TEMP_AVAR_GRAD THEN
    M_AVARIA_TEMP := TRUE;
ELSE
    IF TEMP_BOILER_GRAD < TEMP_HYST_GRAD THEN
        M_AVARIA_TEMP := FALSE;
    END_IF;
END_IF;

(* ============================================
   БЛОК 4: ДАТЧИК ГАЗУ
   X_GAZ = TRUE (замкнутий) → газ є (M_GAZ_IE = 1)
   X_GAZ = FALSE (розімкнутий) → газу немає (M_GAZ_IE = 0)
   ============================================ *)
M_GAZ_IE := X_GAZ;

(* Лічильник відключень газу *)
IF M_GAZ_IE = FALSE AND M_GAZ_OLD = TRUE THEN
    STAT_GAS_OFF := STAT_GAS_OFF + 1;
END_IF;
M_GAZ_OLD := M_GAZ_IE;

(* ============================================
   БЛОК 5: ДАТЧИК ВАКУУМУ
   X_VAKUUM = TRUE (замкнутий) → вакуум є
   X_VAKUUM = FALSE (розімкнутий) → вакууму немає → АВАРІЯ
   ============================================ *)
M_VAKUUM_IE := X_VAKUUM;

IF NOT M_VAKUUM_IE THEN
    M_AVARIA_VAKUUM := TRUE;  (* Пропав вакуум — аварія *)
ELSE
    M_AVARIA_VAKUUM := FALSE; (* Вакуум є — норма *)
END_IF;

(* Лічильник відключень вакууму *)
IF M_VAKUUM_IE = FALSE AND M_VAKUUM_OLD = TRUE THEN
    STAT_VAKUUM_OFF := STAT_VAKUUM_OFF + 1;
END_IF;
M_VAKUUM_OLD := M_VAKUUM_IE;

(* ============================================
   БЛОК 6: ТИСК МАСЛА
   X_TISK_MASLA_DI = TRUE → тиск норма
   ============================================ *)
M_TISK_NORMA := X_TISK_MASLA_DI;

(* ============================================
   БЛОК 7: ЗАГАЛЬНА АВАРІЯ
   Будь-яка з умов → загальна аварія
   ============================================ *)
M_ZAGALNA_AVARIA := M_AVARIA_NAPRUGA
                 OR M_AVARIA_TEMP
                 OR M_AVARIA_VAKUUM
                 OR NOT M_TISK_NORMA
                 OR X_AVARIA_EXT;

(* Лічильник аварій (по передньому фронту) *)
IF M_ZAGALNA_AVARIA = TRUE AND M_ALARM_OLD = FALSE THEN
    STAT_ALARMS := STAT_ALARMS + 1;
END_IF;
M_ALARM_OLD := M_ZAGALNA_AVARIA;

(* ============================================
   БЛОК 8: ЛОГІКА СТАРТ/СТОП
   Детектори імпульсів та керування станом системи
   ============================================ *)

(* Детектор переднього фронту для СТАРТ *)
M_START_PULSE := CMD_START AND NOT M_CMD_START_OLD;
M_CMD_START_OLD := CMD_START;

(* Детектор переднього фронту для СТОП *)
M_STOP_PULSE := CMD_STOP AND NOT M_CMD_STOP_OLD;
M_CMD_STOP_OLD := CMD_STOP;

(* Старт системи *)
IF M_START_PULSE AND NOT M_SYSTEM_ON AND NOT M_ZAGALNA_AVARIA THEN
    M_SYSTEM_ON := TRUE;
    STAT_STARTS := STAT_STARTS + 1;
END_IF;

(* Стоп системи *)
IF M_STOP_PULSE OR M_ZAGALNA_AVARIA THEN
    IF M_SYSTEM_ON THEN
        M_SYSTEM_ON := FALSE;
        STAT_STOPS := STAT_STOPS + 1;
    END_IF;
END_IF;

(* ============================================
   БЛОК 9: ГОТОВНІСТЬ СИСТЕМИ ДО РОБОТИ
   Всі умови мають бути виконані
   ============================================ *)
M_SYSTEM_READY := NOT M_AVARIA_NAPRUGA   (* Напруга норма *)
              AND NOT M_AVARIA_TEMP       (* Температура норма *)
              AND M_GAZ_IE                (* Газ є *)
              AND M_VAKUUM_IE             (* Вакуум є *)
              AND M_TISK_NORMA            (* Тиск масла норма *)
              AND NOT X_AVARIA_EXT        (* Немає зовнішньої аварії *)
              AND M_SYSTEM_ON;            (* Система запущена *)

(* ============================================
   БЛОК 10: КЕРУВАННЯ КЛАПАНОМ ГАЗУ (Y0)
   Відкрити тільки якщо ВСІ умови виконані
   Додаткова гарантія: без вакууму газ закрито
   ============================================ *)
IF M_SYSTEM_READY THEN
    Y_KLAPAN_GAZ := TRUE;   (* Відкрити клапан газу *)
ELSE
    Y_KLAPAN_GAZ := FALSE;  (* ЗАЧИНИТИ клапан газу *)
END_IF;

(* Додаткова гарантія: якщо немає вакууму — ОБОВ'ЯЗКОВО закрити газ *)
IF NOT M_VAKUUM_IE THEN
    Y_KLAPAN_GAZ := FALSE;
END_IF;

(* ============================================
   БЛОК 11: КЕРУВАННЯ РОЗЕТКАМИ
   Вмикаються командою з контролера/HMI
   але тільки якщо немає загальної аварії
   ============================================ *)

(* Розетка 1 *)
IF CMD_ROZET_1 AND NOT M_ZAGALNA_AVARIA THEN
    Y_ROZET_1 := TRUE;
ELSE
    Y_ROZET_1 := FALSE;
END_IF;

(* Розетка 2 *)
IF CMD_ROZET_2 AND NOT M_ZAGALNA_AVARIA THEN
    Y_ROZET_2 := TRUE;
ELSE
    Y_ROZET_2 := FALSE;
END_IF;

(* ============================================
   БЛОК 12: АВАРІЙНА СИГНАЛІЗАЦІЯ
   ============================================ *)
Y_AVARIA_SIGNAL := M_ZAGALNA_AVARIA;

(* ============================================
   БЛОК 13: ЗАГАЛЬНИЙ ДОЗВІЛ РОБОТИ
   ============================================ *)
Y_DOZV_ROBOTY := M_SYSTEM_READY;

(* ============================================
   БЛОК 14: СТАТИСТИКА ДЛЯ HMI
   Виведення на HMI дисплей
   ============================================ *)

(* Маркери для відображення на HMI *)
(*
   MW0  = NAPRUGA_VOLT      (відображати в Вольтах)
   MW1  = TEMP_BOILER_GRAD  (відображати в °C)
   MW2  = TEMP_VODA_GRAD    (відображати в °C)
   MW3  = TEMP_2_GRAD       (відображати в °C)
   MW10 = STAT_STARTS       (кількість запусків)
   MW11 = STAT_STOPS        (кількість зупинок)
   MW12 = STAT_ALARMS       (кількість аварій)
   MW13 = STAT_GAS_OFF      (скільки разів відключався газ)
   MW14 = STAT_VAKUUM_OFF   (скільки разів пропадав вакуум)
*)