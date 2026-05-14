import os
import json
import time
import urllib.parse
import urllib.request


BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:

    raise RuntimeError("Не задан BOT_TOKEN в Railway Variables")

if not ADMIN_ID:

    raise RuntimeError("Не задан ADMIN_ID в Railway Variables")

ADMIN_ID = int(ADMIN_ID)

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"



user_states = {}
user_data = {}

# Защита от двойных нажатий на inline-кнопки.
# Иногда пользователь нажимает кнопку два раза подряд или Telegram присылает
# два callback-события почти одновременно — из-за этого бот повторяет один и тот же вопрос.
processed_callback_ids = set()
last_callback_by_user = {}
CALLBACK_DEBOUNCE_SECONDS = 1.2

# =========================================================
# MLSport bot — подбор инвентаря по ассортименту MLSport
# =========================================================
# Исправлено:
# - уровень игрока теперь главный фильтр;
# - МС / ФНТР 1000+ не получает Allplay, Vega Intro, Flextra, Primorac-сборки и т.п.;
# - убраны кнопки «быстрее / контрольнее / дешевле», потому что они ломали выдачу;
# - бот не обещает наличие/цену, а передаёт менеджеру контекст подбора.


def P(name, category, levels, styles, goals, sides, budgets, speed, spin, control, difficulty, short, best_for, compare, role=None, family=None):
    return {
        "name": name,
        "category": category,
        "levels": levels,
        "styles": styles,
        "goals": goals,
        "sides": sides,
        "budgets": budgets,
        "speed": speed,
        "spin": spin,
        "control": control,
        "difficulty": difficulty,
        "short": short,
        "best_for": best_for,
        "compare": compare,
        "role": role,
        "family": family or name.split()[0],
    }


PRODUCTS = [
    # =========================
    # РАКЕТКИ / СБОРКИ
    # =========================
    P("Double Fish J5", "racket", ["beginner"], ["stable", "universal"], ["first_racket", "control", "less_errors"], ["both"], ["low"], 4, 4, 9, 1, "готовая учебная ракетка для самого простого старта", "детям, новичкам и редкой игре", "проще сборной ракетки; не для спортивного роста", "value", "Double Fish"),
    P("Double Fish J7", "racket", ["beginner"], ["stable", "universal"], ["first_racket", "control", "less_errors"], ["both"], ["low"], 5, 5, 8, 2, "готовая ракетка чуть активнее J5", "новичкам, которым нужен недорогой старт", "быстрее J5, но проще полноценной сборки", "value", "Double Fish"),
    P("Ракетка сборная 729", "racket", ["beginner", "club"], ["stable", "universal"], ["first_racket", "control", "less_errors"], ["both"], ["low", "middle"], 6, 6, 8, 3, "доступная сборная ракетка для перехода от готовых ракеток", "любителям до 200 ФНТР", "лучше простой готовой ракетки; проще индивидуальной сборки", "value", "729"),
    P("Xiom Allround FL + Xiom Vega Intro / Vega Europe", "racket", ["beginner", "club"], ["stable", "block", "universal"], ["first_racket", "control", "less_errors", "receive"], ["both"], ["middle"], 6, 7, 9, 3, "первая нормальная сборка через контроль", "новичкам и любителям, которым важно начать с управляемого инвентаря", "контрольнее атакующих оснований; логичнее готовой ракетки для обучения", "control", "Xiom"),
    P("Donic Appelgren Allplay FL + Vega Europe / Vega Intro", "racket", ["beginner", "club"], ["stable", "universal", "block"], ["first_racket", "control", "less_errors", "receive"], ["both"], ["middle"], 6, 7, 10, 3, "мягкая контрольная сборка для стабильности", "новичкам, детям и любителям до 200 ФНТР", "спокойнее Korbel и Offensive S; не для КМС/МС", "control", "Donic"),
    P("Xiom Offensive S FL + Vega Pro / Vega Europe DF", "racket", ["club", "regular"], ["topspin", "universal", "attack"], ["level_up", "spin", "control", "forehand"], ["both"], ["middle", "high"], 8, 8, 8, 5, "универсальная атакующая сборка без экстремальной скорости", "игрокам 200–500 ФНТР для роста в топспине", "быстрее Allround; контрольнее быстрых карбонов", "balanced", "Xiom"),
    P("Butterfly Zoran Primorac + Rozena / Glayzer 09C", "racket", ["club", "regular"], ["stable", "topspin", "universal"], ["control", "spin", "level_up", "less_errors"], ["both"], ["high", "premium"], 7, 8, 9, 5, "универсальная Butterfly-сборка с контролем", "любителям и регулярным игрокам, которым не нужен резкий карбон", "контрольнее Korbel; не вариант для МС как основная сборка", "balanced", "Butterfly"),
    P("Butterfly Petr Korbel + Tenergy 05 / Tenergy 80 FX", "racket", ["regular", "advanced"], ["topspin", "universal", "attack"], ["spin", "forehand", "backhand", "level_up"], ["both"], ["premium"], 8, 9, 8, 6, "классическая деревянная Butterfly-сборка для топспина", "регулярно тренирующимся и продвинутым игрокам", "мягче и понятнее ALC/ZLC; спортивнее Xiom Offensive S", "premium", "Butterfly"),
    P("Stiga Clipper CR FL + Donic BluFire M2 / Acuda S2", "racket", ["regular", "advanced", "strong"], ["fast", "attack", "block"], ["speed", "forehand", "block", "level_up"], ["both"], ["high"], 9, 8, 7, 7, "семислойная сборка для темпа, блока и давления", "игрокам 500–1000 ФНТР, которым нужен плотный удар", "быстрее Korbel; понятнее и дешевле топовых Butterfly-композитов", "power", "Stiga"),
    P("DHS Hurricane Long 3 + Xiom Omega 7 China / Vega Europe", "racket", ["regular", "advanced", "strong"], ["topspin", "power_loop", "universal"], ["spin", "forehand", "receive", "level_up"], ["both"], ["high"], 8, 10, 7, 7, "сборка через китайскую логику форхенда и контроль слева", "игрокам, которые работают рукой и хотят больше вращения первым ходом", "больше удержания; меньше лёгкой катапульты", "balanced", "DHS"),
    P("Butterfly Innerforce Layer ALC + Dignics 09C / Dignics 80", "racket", ["advanced", "strong", "master"], ["topspin", "universal", "attack", "stable"], ["spin", "receive", "forehand", "backhand", "level_up", "control"], ["both"], ["premium"], 9, 10, 7, 8, "профессиональная сборка через вращение, приём и контролируемую мощность", "сильным игрокам и МС, которым нужен карбон с удержанием мяча", "контрольнее внешнего ZLC/Super ZLC; мощнее дерева", "premium", "Butterfly"),
    P("Butterfly Freitas ALC + Tenergy 05 / Tenergy 19", "racket", ["advanced", "strong", "master"], ["topspin", "attack", "universal"], ["spin", "forehand", "level_up", "speed"], ["both"], ["premium"], 9, 9, 7, 8, "ALC-сборка для вариативной атаки через вращение", "продвинутым и сильным игрокам, которым нужна скорость без максимальной резкости", "прямее Innerforce ALC; мягче по требованиям, чем Super ZLC", "premium", "Butterfly"),
    P("Butterfly Harimoto Tomokazu ALC + Dignics 05 / Dignics 80", "racket", ["strong", "master"], ["topspin", "attack", "power_loop", "stable"], ["speed", "spin", "forehand", "backhand", "level_up"], ["both"], ["premium"], 10, 10, 6, 9, "сильная профессиональная сборка для мощного топспина", "игрокам уровня КМС/МС, которые сами контролируют быстрый инвентарь", "быстрее дерева; требовательнее к ногам и технике", "power", "Butterfly"),
    P("Butterfly Viscaria Super ALC + ZYRE 03 / Dignics 80", "racket", ["master"], ["attack", "fast", "power_loop"], ["speed", "spin", "forehand", "level_up"], ["both"], ["premium"], 10, 10, 5, 10, "экстремально мощная премиальная сборка для максимального потолка атаки", "мастерскому уровню, где игрок уверенно управляет очень быстрым инвентарём", "самый требовательный вариант; не как первый карбон", "power", "Butterfly"),

    # =========================
    # НАКЛАДКИ
    # =========================
    P("Butterfly Flextra", "rubbers", ["beginner"], ["stable", "universal"], ["first_racket", "control", "less_errors"], ["fh", "bh", "both"], ["middle"], 4, 4, 10, 2, "очень спокойная учебная накладка", "детям и новичкам для постановки техники", "медленнее Vega Intro; максимум контроля", "control", "Butterfly"),
    P("Xiom Vega Intro", "rubbers", ["beginner", "club"], ["stable", "universal"], ["first_racket", "control", "less_errors"], ["fh", "bh", "both"], ["middle"], 6, 7, 9, 3, "понятная первая накладка для сборной ракетки", "новичкам и любителям, которым нужна управляемость", "проще Vega Europe; хороший старт", "control", "Xiom"),
    P("Xiom Vega Europe", "rubbers", ["beginner", "club"], ["stable", "universal", "block"], ["control", "less_errors", "backhand"], ["bh", "both"], ["middle"], 7, 8, 9, 4, "мягкая контрольная накладка", "бэкхенду, любителям и стабильной игре", "мягче Vega Pro; безопаснее быстрых тензоров", "control", "Xiom"),
    P("Xiom Vega Europe DF", "rubbers", ["beginner", "club"], ["stable", "universal", "block"], ["control", "less_errors", "backhand"], ["bh", "both"], ["middle"], 7, 8, 9, 4, "мягкая версия Vega Europe с упором на контроль", "игрокам, которым нужен комфортный бэкхенд", "похожа на Vega Europe, но ощущается ещё дружелюбнее", "control", "Xiom"),
    P("Xiom Vega Japan", "rubbers", ["club", "regular"], ["topspin", "attack", "universal"], ["spin", "level_up", "control"], ["fh", "bh", "both"], ["middle", "high"], 8, 8, 8, 5, "универсальная Vega с более живым отскоком", "любителям и регулярным игрокам для атаки без перегруза", "быстрее Vega Europe; контрольнее Omega VII", "balanced", "Xiom"),
    P("Xiom Vega Korea", "rubbers", ["club", "regular"], ["attack", "fast", "universal"], ["level_up", "spin", "speed"], ["fh", "bh", "both"], ["middle", "high"], 8, 8, 8, 5, "современная универсальная Vega с атакующим характером", "игрокам, которым нужна атака и немного больше динамики", "спортивнее Vega Intro; проще Omega VII", "balanced", "Xiom"),
    P("Xiom Vega Pro", "rubbers", ["club", "regular", "advanced"], ["attack", "fast", "topspin"], ["speed", "spin", "forehand"], ["fh", "both"], ["middle", "high"], 9, 9, 7, 7, "жёсткая и быстрая накладка для атаки", "форхенду и активному топспину", "быстрее Vega Europe; доступнее премиум Butterfly", "power", "Xiom"),
    P("Xiom Omega VII Euro", "rubbers", ["club", "regular", "advanced"], ["topspin", "attack"], ["spin", "level_up", "backhand"], ["bh", "both"], ["high"], 9, 9, 7, 7, "более мягкая Omega для топспина и дуги", "игрокам, которым нужна скорость без чрезмерной жёсткости", "контрольнее Omega Asia; мощнее Vega Japan", "balanced", "Xiom"),
    P("Xiom Omega VII Asia", "rubbers", ["regular", "advanced", "strong"], ["attack", "fast"], ["speed", "forehand", "level_up"], ["fh", "both"], ["high"], 10, 9, 6, 8, "быстрая жёсткая накладка для давления", "сильным игрокам, которым нужна скорость и прямота", "мощнее Vega Pro; требовательнее к технике", "power", "Xiom"),
    P("Xiom Omega VII Tour", "rubbers", ["regular", "advanced", "strong", "master"], ["power_loop", "topspin", "attack"], ["speed", "spin", "forehand"], ["fh", "both"], ["high", "premium"], 10, 10, 6, 9, "топовая атакующая Omega для мощного топспина", "сильным атакующим игрокам и МС как альтернатива Butterfly", "выше потолок, чем у Vega Pro; сложнее в контроле", "power", "Xiom"),
    P("Xiom Omega 7 China Guang", "rubbers", ["regular", "advanced", "strong", "master"], ["short_game", "topspin", "attack"], ["spin", "receive", "forehand"], ["fh"], ["high"], 8, 10, 8, 8, "цепкая китайская логика для подачи и первого топса", "форхенду с активной рукой и работой корпусом", "больше вращения и контроля короткой игры; меньше лёгкой катапульты", "balanced", "Xiom"),
    P("Xiom Jekyll&Hyde V 47.5", "rubbers", ["regular", "advanced", "strong"], ["topspin", "attack"], ["speed", "spin", "level_up"], ["fh", "both"], ["premium"], 9, 9, 7, 8, "современная атакующая накладка с яркой динамикой", "игрокам, которым нужна мощь и современный топспин", "быстрее классических Vega; требует уверенной техники", "power", "Xiom"),

    P("Donic Acuda S2", "rubbers", ["club", "regular"], ["universal", "topspin"], ["control", "spin", "level_up"], ["fh", "bh", "both"], ["middle", "high"], 8, 8, 8, 5, "сбалансированная накладка Donic для роста", "любителям и регулярным игрокам, которым нужен баланс", "контрольнее Bluestorm/Bluestar; хороший массовый вариант", "balanced", "Donic"),
    P("Donic Acuda S3", "rubbers", ["beginner", "club"], ["stable", "universal"], ["control", "less_errors", "backhand"], ["bh", "both"], ["middle"], 7, 8, 9, 4, "мягкая Acuda для стабильности", "бэкхенду и игрокам, которым нужна мягкость", "мягче Acuda S2; проще атакующих Bluestorm", "control", "Donic"),
    P("Donic BluFire M3", "rubbers", ["club", "regular"], ["stable", "universal", "topspin"], ["control", "backhand", "spin"], ["bh", "both"], ["high"], 8, 8, 8, 5, "мягкая BluFire для контроля и топспина", "бэкхенду и умеренной атаке", "мягче M2; быстрее Acuda S3", "balanced", "Donic"),
    P("Donic BluFire M2", "rubbers", ["club", "regular", "advanced"], ["topspin", "attack"], ["spin", "speed", "level_up"], ["fh", "bh", "both"], ["high"], 9, 9, 7, 7, "популярная атакующая накладка с балансом", "регулярным игрокам для вращения и скорости", "универсальнее M1; мощнее Acuda S2", "power", "Donic"),
    P("Donic BluFire M1", "rubbers", ["regular", "advanced", "strong"], ["attack", "fast"], ["speed", "forehand", "level_up"], ["fh", "both"], ["high"], 10, 9, 6, 8, "жёсткая быстрая накладка для атаки", "активному форхенду и давлению", "мощнее M2; требовательнее к технике", "power", "Donic"),
    P("Donic Bluestorm Z3", "rubbers", ["club", "regular"], ["stable", "universal", "topspin"], ["control", "backhand", "less_errors"], ["bh", "both"], ["high"], 8, 8, 8, 5, "мягкая Bluestorm для бэкхенда и контроля", "любителям, которым нужна динамика без перегруза", "мягче Z2; стабильнее на блоке", "balanced", "Donic"),
    P("Donic Bluestorm Z2", "rubbers", ["club", "regular", "advanced"], ["topspin", "attack"], ["spin", "speed", "level_up"], ["fh", "bh", "both"], ["high"], 9, 9, 7, 7, "сбалансированная Bluestorm для атаки", "игрокам, которым нужна мощь без максимальной жёсткости", "контрольнее Z1; мощнее Acuda S2", "power", "Donic"),
    P("Donic Bluestorm Z1", "rubbers", ["regular", "advanced", "strong"], ["attack", "fast"], ["speed", "forehand"], ["fh", "both"], ["high"], 10, 9, 6, 8, "быстрая тензорная накладка для давления", "форхенду и игрокам у стола", "быстрее Z2/Z3; требует техники", "power", "Donic"),
    P("Donic Bluestar A1", "rubbers", ["advanced", "strong", "master"], ["power_loop", "topspin", "attack"], ["speed", "spin", "forehand"], ["fh", "both"], ["premium"], 10, 10, 5, 9, "жёсткая профессиональная накладка Donic", "сильному форхенду и мощной атаке", "мощнее большинства Bluestorm; сложнее в контроле", "power", "Donic"),
    P("Donic Bluestar A2", "rubbers", ["regular", "advanced", "strong"], ["topspin", "attack"], ["spin", "speed", "level_up"], ["fh", "both"], ["premium"], 9, 10, 6, 8, "чуть мягче и доступнее по контролю, чем A1", "продвинутым игрокам для сильного вращения", "контрольнее A1; мощнее BluFire M2", "power", "Donic"),
    P("Donic Bluestorm Pro", "rubbers", ["advanced", "strong", "master"], ["attack", "fast"], ["speed", "forehand", "level_up"], ["fh", "both"], ["premium"], 10, 9, 6, 9, "профессиональная версия Bluestorm для скорости", "сильным игрокам с активной атакой", "выше потолок, чем Z1/Z2; требовательнее", "premium", "Donic"),
    P("Donic Bluestorm Pro AM", "rubbers", ["regular", "advanced", "strong"], ["topspin", "attack"], ["spin", "backhand", "level_up"], ["bh", "both"], ["premium"], 9, 9, 7, 8, "профессиональная Bluestorm с более мягкой логикой", "игрокам, которым нужна премиальная атака с контролем", "контрольнее Pro; всё равно не для новичка", "premium", "Donic"),
    P("Donic BluGrip C1", "rubbers", ["regular", "advanced", "strong", "master"], ["short_game", "topspin", "attack"], ["spin", "receive", "forehand"], ["fh", "both"], ["premium"], 9, 10, 7, 8, "цепкая гибридная накладка Donic", "игрокам, которым нужны вращение и первый ход", "больше зацепа, чем Bluestorm; меньше лёгкой катапульты", "premium", "Donic"),

    P("Tibhar Evolution EL-P", "rubbers", ["club", "regular"], ["universal", "topspin"], ["control", "backhand", "level_up"], ["bh", "both"], ["high"], 8, 8, 8, 6, "сбалансированная Evolution для атаки и контроля", "тем, кому MX-P слишком резкая", "мягче MX-P; мощнее контрольных накладок", "balanced", "Tibhar"),
    P("Tibhar Evolution EL-S", "rubbers", ["club", "regular"], ["topspin", "attack"], ["spin", "control", "level_up"], ["fh", "bh", "both"], ["high"], 8, 9, 8, 6, "накладка для вращения с контролем", "игрокам, которым нужен зацеп без максимальной скорости", "контрольнее MX-S; спортивнее EL-P по вращению", "balanced", "Tibhar"),
    P("Tibhar Evolution FX-P", "rubbers", ["beginner", "club"], ["stable", "universal", "block"], ["control", "backhand", "less_errors"], ["bh", "both"], ["high"], 8, 8, 8, 5, "мягкая динамичная Evolution", "бэкхенду, блоку и стабильной атаке", "мягче EL-P; комфортнее для любителя", "balanced", "Tibhar"),
    P("Tibhar Evolution FX-S", "rubbers", ["beginner", "club"], ["topspin", "attack", "stable"], ["spin", "control", "backhand"], ["bh", "both"], ["high"], 7, 9, 8, 5, "мягкая накладка с акцентом на вращение", "игрокам, которые хотят зацеп и контроль", "мягче EL-S; проще на бэкхенде", "balanced", "Tibhar"),
    P("Tibhar Evolution MX-P", "rubbers", ["regular", "advanced", "strong"], ["attack", "fast"], ["speed", "forehand", "level_up"], ["fh", "both"], ["high"], 10, 9, 6, 8, "мощная накладка для скорости и давления", "агрессивным игрокам, которым не хватает темпа", "быстрее EL-P; менее контрольная", "power", "Tibhar"),
    P("Tibhar Evolution MX-P 50", "rubbers", ["advanced", "strong", "master"], ["power_loop", "topspin", "attack"], ["speed", "spin", "forehand"], ["fh"], ["high", "premium"], 10, 10, 5, 9, "жёсткая версия MX-P для сильной атаки", "физически сильным игрокам и форхенду", "мощнее MX-P; требует точной техники", "power", "Tibhar"),
    P("Tibhar Evolution MX-S", "rubbers", ["regular", "advanced", "strong"], ["topspin", "attack"], ["spin", "forehand", "receive"], ["fh", "both"], ["high"], 9, 10, 6, 8, "накладка для максимального вращения в серии Evolution", "игрокам, которые сами создают дугу и вращение", "цепче MX-P, но не такая лёгкая в скорости", "power", "Tibhar"),
    P("Tibhar Hybrid K1 European", "rubbers", ["club", "regular"], ["short_game", "topspin", "attack"], ["spin", "receive", "forehand"], ["fh", "both"], ["high"], 8, 9, 8, 7, "гибрид Tibhar с хорошим зацепом", "игрокам, которым нужна подача, приём и первый топс", "спокойнее Hybrid K3; доступная гибридная логика", "balanced", "Tibhar"),

    P("STIGA DNA Platinum S", "rubbers", ["beginner", "club"], ["stable", "universal", "topspin"], ["control", "backhand", "spin"], ["bh", "both"], ["high"], 8, 8, 8, 5, "мягкая DNA Platinum для контроля и дуги", "бэкхенду и стабильному топспину", "мягче M/H; проще для любителя", "balanced", "STIGA"),
    P("STIGA DNA Platinum M", "rubbers", ["club", "regular", "advanced"], ["topspin", "attack"], ["spin", "speed", "level_up"], ["fh", "bh", "both"], ["high"], 9, 9, 7, 7, "средняя версия DNA Platinum для атаки", "регулярным игрокам для скорости и вращения", "баланс между S и H", "power", "STIGA"),
    P("STIGA DNA Platinum H", "rubbers", ["regular", "advanced", "strong"], ["attack", "fast"], ["speed", "forehand", "level_up"], ["fh", "both"], ["high"], 10, 9, 6, 8, "жёсткая DNA Platinum для давления", "активному форхенду и атаке", "мощнее M; требовательнее в короткой игре", "power", "STIGA"),
    P("STIGA Hybrid XH", "rubbers", ["regular", "advanced", "strong", "master"], ["short_game", "topspin", "attack"], ["spin", "receive", "forehand"], ["fh"], ["high"], 9, 10, 7, 8, "жёсткая гибридная STIGA для вращения", "форхенду с активной рукой", "цепче обычных тензоров; меньше простоты на пассиве", "power", "STIGA"),
    P("JOOLA Dynaryz ZGR", "rubbers", ["regular", "advanced", "strong", "master"], ["short_game", "topspin", "attack"], ["spin", "receive", "forehand"], ["fh", "both"], ["premium"], 9, 10, 7, 8, "гибрид JOOLA для вращения и первого хода", "игрокам, которым нужна цепкость и тяжёлый мяч", "ближе к гибридной логике, чем к мягким тензорам", "premium", "JOOLA"),
    P("JOOLA Tronix CMD", "rubbers", ["club", "regular"], ["universal", "topspin"], ["control", "backhand", "level_up"], ["bh", "both"], ["high"], 8, 8, 8, 6, "универсальная JOOLA для контроля и атаки", "игрокам, которым нужен сбалансированный вариант", "контрольнее Tronix ZGR; проще гибридов", "balanced", "JOOLA"),
    P("JOOLA Tronix ZGR", "rubbers", ["regular", "advanced", "strong"], ["short_game", "topspin", "attack"], ["spin", "receive", "forehand"], ["fh", "both"], ["premium"], 9, 10, 7, 8, "цепкая JOOLA для вращения и давления", "форхенду, подачам и первому топсу", "более гибридная и требовательная, чем CMD", "premium", "JOOLA"),
    P("VICTAS VS-401", "rubbers", ["club", "regular"], ["defense", "stable"], ["control", "receive", "less_errors"], ["bh", "both"], ["high"], 6, 9, 9, 6, "контрольная накладка для подрезки и вращения", "защитникам и универсалам через контроль", "медленнее атакующих тензоров; сильнее в подрезке", "control", "VICTAS"),

    P("Butterfly Aibiss", "rubbers", ["club", "regular"], ["short_game", "topspin", "attack"], ["spin", "receive", "control"], ["fh", "both"], ["high"], 7, 9, 8, 7, "цепкая накладка Butterfly для контроля вращения", "игрокам, которым важны подача, приём и первый ход", "спокойнее Dignics 09C; больше контроля, меньше катапульты", "balanced", "Butterfly"),
    P("Butterfly Glayzer", "rubbers", ["club", "regular"], ["topspin", "attack", "universal"], ["spin", "control", "level_up"], ["fh", "bh", "both"], ["high"], 8, 8, 8, 6, "современная Butterfly для стабильного топспина", "игрокам, которым нужна Butterfly-логика дешевле Tenergy/Dignics", "спортивнее Rozena; спокойнее Tenergy", "balanced", "Butterfly"),
    P("Butterfly Glayzer 09C", "rubbers", ["club", "regular", "advanced"], ["short_game", "topspin", "attack"], ["spin", "receive", "control"], ["fh", "both"], ["high"], 8, 9, 8, 6, "доступная гибридная Butterfly с зацепом", "игрокам, которым нужны вращение, подача и приём", "проще Dignics 09C; цепче обычного Glayzer", "balanced", "Butterfly"),
    P("Butterfly Tenergy 05", "rubbers", ["regular", "advanced", "strong", "master"], ["power_loop", "topspin", "attack", "stable"], ["spin", "forehand", "level_up"], ["fh", "both"], ["premium"], 10, 10, 6, 8, "классическая топовая накладка для мощного топспина", "сильному форхенду и атаке через вращение", "резче Glayzer; классичнее Dignics 05", "premium", "Butterfly"),
    P("Butterfly Tenergy 05 FX", "rubbers", ["club", "regular", "advanced"], ["topspin", "attack", "stable"], ["control", "spin", "backhand"], ["bh", "both"], ["premium"], 8, 9, 8, 6, "мягкая Tenergy для контроля и дуги", "бэкхенду и тем, кому обычная Tenergy 05 жёсткая", "премиальнее Rozena/Glayzer; мягче Tenergy 05", "premium", "Butterfly"),
    P("Butterfly Tenergy 05 Hard", "rubbers", ["advanced", "strong", "master"], ["power_loop", "topspin", "attack"], ["speed", "spin", "forehand"], ["fh"], ["premium"], 10, 10, 5, 9, "жёсткая Tenergy для тяжёлого форхенда", "физически сильным игрокам с активной работой рукой", "мощнее обычной 05; заметно требовательнее", "premium", "Butterfly"),
    P("Butterfly Tenergy 19", "rubbers", ["regular", "advanced", "strong", "master"], ["topspin", "attack", "universal"], ["spin", "control", "level_up"], ["fh", "bh", "both"], ["premium"], 9, 9, 7, 8, "Tenergy с хорошим удержанием мяча", "игрокам, которым нужна вариативная дуга и стабильный топспин", "гибче по ощущению, чем 05; не такая прямая, как 64", "premium", "Butterfly"),
    P("Butterfly Tenergy 25", "rubbers", ["regular", "advanced", "strong"], ["block", "fast"], ["block", "speed", "forehand"], ["fh", "both"], ["premium"], 9, 9, 6, 8, "накладка для игры ближе к столу и короткой дуги", "игрокам, которые давят у стола блоком и контратакой", "более специфичная, чем Tenergy 05/80", "premium", "Butterfly"),
    P("Butterfly Tenergy 80 FX", "rubbers", ["club", "regular", "advanced"], ["topspin", "attack", "universal"], ["control", "backhand", "spin"], ["bh", "both"], ["premium"], 8, 9, 8, 6, "мягкая универсальная Tenergy для обеих сторон", "бэкхенду и универсальной игре", "мягче Tenergy 80; стабильнее для контроля", "premium", "Butterfly"),
    P("Butterfly Dignics 05", "rubbers", ["advanced", "strong", "master"], ["power_loop", "topspin", "attack", "stable"], ["speed", "spin", "forehand", "level_up"], ["fh", "both"], ["premium"], 10, 10, 6, 9, "топовая накладка для современной атаки и высокого качества мяча", "очень сильным игрокам, КМС и МС", "мощнее Tenergy 05; требовательнее Glayzer и большинства тензоров", "premium", "Butterfly"),
    P("Butterfly Dignics 09C", "rubbers", ["regular", "advanced", "strong", "master"], ["short_game", "topspin", "attack", "stable"], ["spin", "receive", "forehand", "control"], ["fh", "both"], ["premium"], 9, 10, 8, 8, "премиальный гибрид для подачи, приёма и первого топса", "сильным игрокам и МС, играющим через вращение и короткую игру", "контрольнее Dignics 05; динамичнее липких китайских вариантов", "premium", "Butterfly"),
    P("Butterfly Dignics 64", "rubbers", ["advanced", "strong", "master"], ["fast", "attack"], ["speed", "level_up"], ["fh", "bh", "both"], ["premium"], 10, 8, 6, 9, "очень быстрая Dignics для прямой скорости", "игрокам, которым важны темп и быстрый розыгрыш", "быстрее по траектории, но менее вращательная, чем Dignics 05/09C", "premium", "Butterfly"),
    P("Butterfly Dignics 80", "rubbers", ["regular", "advanced", "strong", "master"], ["universal", "topspin", "attack", "stable"], ["speed", "backhand", "spin", "level_up"], ["bh", "both"], ["premium"], 9, 9, 7, 8, "универсальная Dignics между скоростью и контролем", "сильному бэкхенду и универсальной атаке", "спокойнее Dignics 05; мощнее Rozena/Glayzer", "premium", "Butterfly"),
    P("Butterfly ZYRE 03", "rubbers", ["master"], ["power_loop", "topspin", "attack"], ["speed", "spin", "forehand", "level_up"], ["fh", "both"], ["premium"], 10, 10, 5, 10, "самая мощная премиальная накладка Butterfly в базе", "мастерскому уровню и очень сильной атаке", "выше потолок, чем Dignics; не вариант для контроля новичка", "premium", "Butterfly"),

    # =========================
    # ОСНОВАНИЯ
    # =========================
    P("Xiom Allround FL", "blade", ["beginner", "club"], ["stable", "universal"], ["control", "first_racket", "less_errors"], ["both"], ["middle"], 5, 7, 10, 2, "простое контрольное основание для обучения", "новичкам и любителям до 200 ФНТР", "самое безопасное начало; медленнее Offensive S", "control", "Xiom"),
    P("DONIC Appelgren Allplay FL", "blade", ["beginner", "club"], ["stable", "universal", "block"], ["control", "first_racket", "less_errors"], ["both"], ["middle"], 5, 7, 10, 2, "классическое allround-основание для контроля", "новичкам, детям и стабильной игре", "похоже по задаче на Xiom Allround; мягкое и понятное", "control", "Donic"),
    P("Neottec Mark ALL FL", "blade", ["beginner", "club"], ["stable", "universal"], ["control", "first_racket", "less_errors"], ["both"], ["low", "middle"], 5, 7, 10, 2, "доступное контрольное основание", "тем, кому нужен бюджетный вход в сборку", "дешевле Butterfly; больше про контроль, чем скорость", "value", "Neottec"),
    P("Neottec Mark FL", "blade", ["beginner", "club"], ["stable", "universal"], ["control", "level_up"], ["both"], ["low", "middle"], 6, 7, 9, 3, "бюджетное универсальное основание", "любителям для первой сборки", "чуть активнее Mark ALL; не перегружает скоростью", "value", "Neottec"),
    P("Yinhe Galaxy N-11s FL", "blade", ["beginner", "club"], ["stable", "universal"], ["first_racket", "control", "level_up"], ["both"], ["low", "middle"], 6, 7, 9, 3, "доступное основание для первой сборки", "новичкам и любителям, которым нужен бюджетный вариант", "лучше готовой ракетки; проще дорогих Butterfly", "value", "Yinhe"),
    P("Butterfly Timo Boll TJ FL", "blade", ["beginner", "club"], ["stable", "universal"], ["first_racket", "control"], ["both"], ["high"], 5, 7, 10, 2, "детское/юниорское основание для обучения", "детям и подросткам для правильного старта", "спокойное и безопасное; не про взрослую скорость", "control", "Butterfly"),
    P("Butterfly Zoran Primorac FL/ST", "blade", ["club", "regular"], ["stable", "topspin", "universal"], ["control", "level_up", "less_errors"], ["both"], ["high"], 7, 8, 9, 4, "универсальное деревянное основание Butterfly", "любителям и регулярным игрокам для баланса", "контрольнее Korbel; качественнее бюджетных ALL", "balanced", "Butterfly"),
    P("Butterfly Maze Advance FL", "blade", ["club", "regular"], ["stable", "universal", "attack"], ["control", "level_up"], ["both"], ["high"], 7, 8, 8, 4, "лёгкое allround/offensive основание", "игрокам, которым нужен баланс атаки и контроля", "активнее Primorac; проще карбона", "balanced", "Butterfly"),
    P("Nittaku Latika FL", "blade", ["club", "regular"], ["stable", "topspin", "universal"], ["control", "spin", "level_up"], ["both"], ["high"], 7, 8, 8, 4, "универсальное дерево Nittaku для роста", "любителям и регулярным игрокам, которым нужна управляемость", "альтернатива Primorac/Offensive S с приятным чувством", "balanced", "Nittaku"),
    P("Xiom Offensive S FL", "blade", ["club", "regular"], ["topspin", "attack", "universal"], ["speed", "level_up", "forehand"], ["both"], ["middle", "high"], 7, 8, 8, 4, "универсальное offensive-основание без перегруза", "первому апгрейду после allround", "быстрее Xiom Allround; контрольнее карбона", "balanced", "Xiom"),
    P("DHS Power G2/G3", "blade", ["club", "regular"], ["stable", "attack", "universal"], ["control", "level_up", "speed"], ["both"], ["middle"], 7, 8, 8, 4, "доступное основание DHS для роста", "любителям, которым нужен бюджетный апгрейд", "активнее чистого ALL; проще Hurricane Long 3", "value", "DHS"),
    P("Butterfly Hadraw 5 FL", "blade", ["regular", "advanced"], ["topspin", "attack", "universal"], ["spin", "forehand", "level_up"], ["both"], ["premium"], 8, 9, 8, 6, "5-слойное атакующее дерево Butterfly", "техничным игрокам для топспина и чувства мяча", "деревяннее и мягче ALC/ZLC; быстрее Primorac", "premium", "Butterfly"),
    P("Butterfly Petr Korbel FL/ST", "blade", ["regular", "advanced"], ["topspin", "attack", "universal"], ["spin", "forehand", "level_up"], ["both"], ["high", "premium"], 8, 9, 8, 6, "классическое атакующее дерево с отличным чувством", "регулярным игрокам, которые хотят атаковать без резкого карбона", "быстрее Primorac; контрольнее ZLC/ALC", "balanced", "Butterfly"),
    P("Butterfly Korbel SK7 FL", "blade", ["regular", "advanced", "strong"], ["fast", "attack", "block"], ["speed", "block", "forehand"], ["both"], ["premium"], 9, 8, 7, 7, "семислойное дерево для плотной атаки", "игрокам у стола, которым нужны темп и блок", "быстрее обычного Korbel; понятнее карбона", "power", "Butterfly"),
    P("Nittaku Tenor FL", "blade", ["regular", "advanced"], ["topspin", "universal"], ["spin", "control", "level_up"], ["both"], ["premium"], 8, 9, 8, 6, "премиальное деревянное основание Nittaku", "техничным игрокам, которым важны касание и дуга", "тоньше по ощущениям, чем обычные OFF-деревяшки", "premium", "Nittaku"),
    P("XIOM Solo FL", "blade", ["regular", "advanced"], ["attack", "topspin"], ["speed", "forehand", "level_up"], ["both"], ["high"], 8, 8, 7, 5, "атакующее деревянное основание Xiom", "игрокам, которым нужна скорость без композита", "мощнее Offensive S; проще Stradivarius", "power", "Xiom"),
    P("Xiom Stradivarius OFF FL", "blade", ["advanced", "strong"], ["attack", "fast", "topspin"], ["speed", "forehand", "level_up"], ["both"], ["premium"], 9, 8, 7, 7, "карбоновое OFF-основание Xiom для атаки", "продвинутым игрокам, которым нужен быстрый темп", "быстрее дерева; дешевле части топовых Butterfly", "power", "Xiom"),
    P("Stiga Clipper CR FL", "blade", ["regular", "advanced", "strong"], ["fast", "attack", "block"], ["speed", "forehand", "block"], ["both"], ["high"], 9, 8, 7, 7, "семислойное дерево для давления у стола", "игрокам, которым нужен плотный удар и блок", "быстрее Korbel; контрольнее большинства карбонов", "power", "Stiga"),
    P("Yasaka Falck Carbon FL", "blade", ["advanced", "strong"], ["attack", "topspin", "fast"], ["speed", "forehand", "level_up"], ["both"], ["premium"], 9, 8, 7, 7, "карбоновое основание Yasaka для атаки", "продвинутым игрокам для темпа и форхенда", "быстрее дерева; не такой экстремум, как Super ZLC", "premium", "Yasaka"),
    P("DHS Hurricane Long 3 FL", "blade", ["regular", "advanced", "strong"], ["topspin", "power_loop"], ["spin", "forehand", "level_up"], ["both"], ["high"], 8, 9, 7, 7, "основание DHS для игры через топспин", "игрокам, которые вкладываются в мяч рукой", "больше удержания, чем у прямого карбона; хорошо под липкие/гибридные накладки", "balanced", "DHS"),
    P("Butterfly Balsa Carbo X5 22", "blade", ["club", "regular"], ["stable", "block", "attack"], ["control", "block", "less_errors"], ["both"], ["premium"], 8, 7, 8, 5, "лёгкое карбоновое основание с бальзой", "игрокам, которым нужна лёгкость и блок", "легче классических OFF; специфичное ощущение", "balanced", "Butterfly"),
    P("Butterfly Outerforce CAF FL", "blade", ["club", "regular"], ["stable", "topspin", "universal"], ["control", "level_up"], ["both"], ["premium"], 8, 8, 8, 5, "первый спецматериал без резкости ALC", "игрокам, которые хотят перейти от дерева к композиту", "проще ALC/ZLC; логичный мостик от дерева", "premium", "Butterfly"),
    P("Butterfly Outerforce ALC FL", "blade", ["regular", "advanced", "strong"], ["topspin", "attack", "universal"], ["spin", "level_up", "speed"], ["both"], ["premium"], 9, 9, 7, 7, "внешний ALC для современной атаки", "игрокам, которым нужна скорость и стабильность", "быстрее CAF; проще Super ZLC", "premium", "Butterfly"),
    P("Butterfly Innerforce Layer ALC FL", "blade", ["regular", "advanced", "strong", "master"], ["topspin", "universal", "attack", "stable"], ["control", "spin", "level_up"], ["both"], ["premium"], 9, 9, 7, 7, "внутренний ALC с удержанием мяча", "тем, кому нужна атака без резкого внешнего карбона", "контрольнее внешних ZLC/Super ZLC; мощнее дерева", "premium", "Butterfly"),
    P("Butterfly Freitas ALC FL", "blade", ["advanced", "strong", "master"], ["topspin", "attack", "universal"], ["spin", "forehand", "level_up"], ["both"], ["premium"], 9, 9, 7, 7, "ALC-основание для вариативной атаки", "продвинутым и сильным игрокам, которым нужен баланс мощности и чувства", "альтернатива Innerforce/Outerforce с другим балансом", "premium", "Butterfly"),
    P("Butterfly Harimoto Tomokazu ALC FL", "blade", ["advanced", "strong", "master"], ["topspin", "attack"], ["spin", "forehand", "level_up"], ["both"], ["premium"], 9, 9, 7, 8, "ALC-основание под топспиновую атаку", "сильным игрокам с активным вращением", "мощнее дерева; требует уверенной техники", "premium", "Butterfly"),
    P("Butterfly Timo Boll ZLF FL", "blade", ["regular", "advanced"], ["topspin", "universal"], ["control", "spin", "level_up"], ["both"], ["premium"], 8, 9, 8, 6, "композит ZLF с мягким чувством", "игрокам, которым важнее дуга и контроль, чем максимальная скорость", "контрольнее ALC/ZLC; мягче по ощущению", "premium", "Butterfly"),
    P("Butterfly Apolonia ZLC", "blade", ["advanced", "strong", "master"], ["topspin", "attack", "universal"], ["speed", "spin", "level_up"], ["both"], ["premium"], 9, 9, 7, 8, "премиальное ZLC-основание для атаки", "сильным игрокам, которым нужна мощь и упругость", "быстрее ALC по ощущению; сложнее дерева", "premium", "Butterfly"),
    P("Butterfly Franziska Innerforce ZLC FL", "blade", ["advanced", "strong", "master"], ["topspin", "attack"], ["spin", "speed", "level_up"], ["both"], ["premium"], 9, 9, 7, 8, "внутренний ZLC с удержанием и мощностью", "игрокам, которым нужен топовый композит не максимально резкий", "контрольнее внешних Super ZLC; мощнее Innerforce ALC", "premium", "Butterfly"),
    P("Butterfly Mizutani Jun ZLC FL", "blade", ["strong", "master"], ["attack", "fast", "topspin"], ["speed", "forehand", "level_up"], ["both"], ["premium"], 10, 9, 6, 9, "быстрое ZLC-основание для сильной атаки", "сильным игрокам, которым нужна высокая скорость", "резче Innerforce; не для первого карбона", "power", "Butterfly"),
    P("Butterfly Zhang Jike ZLC FL", "blade", ["strong", "master"], ["attack", "fast", "topspin"], ["speed", "forehand", "level_up"], ["both"], ["premium"], 10, 9, 6, 9, "профессиональное ZLC-основание для атаки", "сильным игрокам, умеющим контролировать скорость", "быстрее дерева; требовательнее ALC-вариантов", "power", "Butterfly"),
    P("Butterfly Fan Zhendong ZLC FL", "blade", ["strong", "master"], ["attack", "fast", "power_loop"], ["speed", "forehand", "level_up"], ["both"], ["premium"], 10, 9, 6, 9, "топовое ZLC-основание для мощной атаки", "сильным игрокам с хорошей техникой", "мощнее ALC; контроль ниже, чем у дерева", "power", "Butterfly"),
    P("Butterfly Lin Yun-Ju Super ZLC FL", "blade", ["strong", "master"], ["attack", "fast", "topspin"], ["speed", "spin", "level_up"], ["both"], ["premium"], 10, 9, 6, 10, "быстрое Super ZLC с высоким потолком", "мастерским игрокам для темпа и давления", "экстремальнее ALC/ZLC; очень требовательно", "power", "Butterfly"),
    P("Butterfly Fan Zhendong Super ZLC FL", "blade", ["master"], ["attack", "fast", "power_loop"], ["speed", "forehand", "level_up"], ["both"], ["premium"], 10, 9, 5, 10, "экстремально быстрое Super ZLC", "мастерскому уровню и максимальной атаке", "не вариант для любителя; требует техники и ног", "power", "Butterfly"),
    P("Butterfly Harimoto Innerforce Super ZLC FL", "blade", ["strong", "master"], ["topspin", "attack"], ["spin", "speed", "level_up"], ["both"], ["premium"], 10, 10, 6, 10, "топовый внутренний Super ZLC", "сильным игрокам, которым нужна мощь с удержанием", "мягче по логике, чем внешний Super ZLC, но всё равно очень сложный", "power", "Butterfly"),
    P("Butterfly Viscaria Super ALC FL", "blade", ["master"], ["attack", "fast", "power_loop"], ["speed", "forehand", "level_up"], ["both"], ["premium"], 10, 9, 5, 10, "экстремально быстрая версия ALC", "мастерскому уровню и агрессивной атаке", "намного требовательнее обычных ALC; не для первого карбона", "power", "Butterfly"),
    P("Butterfly Primorac Carbon Japan FL", "blade", ["strong", "master"], ["attack", "fast"], ["speed", "forehand", "level_up"], ["both"], ["premium"], 10, 8, 5, 10, "очень быстрое классическое карбоновое основание", "сильным игрокам, которые любят прямую скорость", "быстрее большинства деревяшек и ALC; контроль сложнее", "power", "Butterfly"),
    P("Butterfly Diode Pro FL/ST", "blade", ["regular", "advanced", "strong"], ["defense", "pips_defense"], ["control", "receive", "less_errors"], ["both"], ["premium"], 5, 8, 10, 6, "защитное основание для подрезки и шипов", "защитникам и комбинированной игре", "медленнее атакующих оснований; создано для контроля", "control", "Butterfly"),

    # =========================
    # ШИПЫ / АНТИСПИН
    # =========================
    P("Andro Blowfish", "pips", ["regular", "advanced"], ["short_pips", "pips_block"], ["speed", "block", "disrupt"], ["fh", "bh"], ["high"], 8, 5, 7, 7, "короткие шипы для быстрой плоской игры", "игрокам у стола, которым нужна скорость и блок", "быстрее длинных шипов; меньше вращения, чем гладкая накладка", "power", "Andro"),
    P("Butterfly Challenger Attack", "pips", ["club", "regular"], ["short_pips", "pips_block"], ["speed", "block", "control"], ["fh", "bh"], ["high"], 7, 5, 8, 6, "контрольные короткие шипы для атаки", "тем, кто хочет попробовать короткие шипы без экстремума", "спокойнее Killer и более резких коротких шипов", "balanced", "Butterfly"),
    P("Dr.Neubauer Killer", "pips", ["regular", "advanced", "strong"], ["short_pips", "pips_disrupt"], ["disrupt", "block", "speed"], ["bh"], ["premium"], 8, 4, 6, 8, "короткие шипы с выраженным мешающим эффектом", "игрокам, которые хотят ломать ритм соперника у стола", "агрессивнее обычных коротких шипов; требует привыкания", "power", "Dr.Neubauer"),
    P("Butterfly Feint Long III", "pips", ["regular", "advanced"], ["pips_defense", "pips_disrupt"], ["control", "disrupt", "less_errors"], ["bh"], ["high"], 4, 4, 8, 6, "длинные шипы для вариативной защиты", "защитникам, которым нужна стабильность и смена вращения", "контрольнее Grass D.TecS; больше про защиту", "balanced", "Butterfly"),
    P("Tibhar Grass D.TecS", "pips", ["regular", "advanced", "strong"], ["pips_block", "pips_disrupt"], ["disrupt", "block", "less_errors"], ["bh"], ["high"], 6, 4, 7, 8, "длинные шипы с сильным мешающим эффектом", "игрокам у стола, которые хотят ломать темп соперника", "сложнее Feint Long III; сильнее мешающий эффект", "power", "Tibhar"),
    P("VICTAS Curl P4V", "pips", ["regular", "advanced"], ["pips_defense"], ["control", "less_errors", "receive"], ["bh"], ["high"], 4, 4, 9, 6, "длинные шипы для стабильной подрезки", "защитникам и игрокам от контроля", "контрольнее Grass D.TecS; меньше хаоса", "control", "VICTAS"),
    P("Yasaka AntiPower", "pips", ["club", "regular", "advanced"], ["anti"], ["receive", "less_errors", "disrupt"], ["bh"], ["middle", "high"], 3, 2, 9, 7, "антиспин для приёма и разрушения темпа", "тем, кому сложно справляться с вращением", "проще на приёме; ограничивает собственную атаку", "control", "Yasaka"),

    # =========================
    # ОБУВЬ
    # =========================
    P("Butterfly Lezoline Levalis", "shoes", ["advanced", "strong", "master"], ["stable", "attack", "topspin"], ["support", "control"], ["both"], ["premium"], 8, 0, 9, 2, "флагманская обувь Butterfly с поддержкой и амортизацией", "сильным игрокам и тем, кто много тренируется", "больше поддержки, чем лёгкие модели; нужно подбирать размер", "premium", "Butterfly"),
    P("Butterfly Lezoline Rifones", "shoes", ["regular", "advanced", "strong"], ["stable", "attack", "topspin"], ["support", "control"], ["both"], ["premium"], 8, 0, 9, 2, "специализированная обувь Butterfly с хорошей поддержкой", "регулярным тренировкам и турнирам", "стабильнее лёгких моделей; важно примерять посадку", "premium", "Butterfly"),
    P("Butterfly Lezoline Vilata", "shoes", ["club", "regular", "advanced"], ["fast", "attack", "topspin"], ["lightness", "speed"], ["both"], ["high", "premium"], 8, 0, 8, 2, "лёгкая обувь для быстрых перемещений и широкой стопы", "игрокам, которым важны скорость и комфорт", "легче и свободнее по посадке, чем многие узкие модели", "balanced", "Butterfly"),
    P("Butterfly Lezoline Zero", "shoes", ["club", "regular"], ["fast", "stable"], ["lightness", "control"], ["both"], ["high"], 7, 0, 8, 2, "лёгкая модель Butterfly для тренировок", "любителям и регулярным игрокам", "проще Levalis/Rifones; хороший вариант при подходящем размере", "balanced", "Butterfly"),

    # =========================
    # АКСЕССУАРЫ / УХОД
    # =========================
    P("Butterfly Rubber Wiper / хлопковая губка Pro", "accessories", ["beginner", "club", "regular", "advanced", "strong", "master"], ["stable", "topspin", "attack", "block"], ["care"], ["both"], ["low", "middle"], 0, 0, 10, 1, "губка для ухода за накладками", "любому игроку после тренировок", "лучше, чем протирать накладку чем попало", "value", "Care"),
    P("Butterfly Combi Cleaner / Rubber Cleaner / Refresh Foam", "accessories", ["beginner", "club", "regular", "advanced", "strong", "master"], ["stable", "topspin", "attack", "block"], ["care"], ["both"], ["middle"], 0, 0, 10, 1, "очиститель для накладок из ассортимента MLSport", "игрокам с гладкими, тензорными и премиальными накладками", "помогает дольше сохранять сцепление", "value", "Care"),
    P("Защитная плёнка Butterfly для накладок", "accessories", ["beginner", "club", "regular", "advanced", "strong", "master"], ["topspin", "attack", "universal"], ["care"], ["both"], ["low", "middle"], 0, 0, 10, 1, "защита поверхности накладок от пыли", "особенно для липких и цепких накладок", "полезна с Dignics 09C, Aibiss, гибридами и дорогими тензорами", "value", "Care"),
    P("Клей Butterfly Free Chack / DHS №15 / NEOTTEC Neofix", "accessories", ["beginner", "club", "regular", "advanced", "strong", "master"], ["stable", "topspin", "attack"], ["care"], ["both"], ["middle", "high"], 0, 0, 8, 1, "клей для сборки ракетки", "тем, кто покупает основание и накладки отдельно", "нужен для полноценной сборки; менеджер поможет выбрать объём", "balanced", "Glue"),
    P("Чехол Butterfly / NEOTEC / DOUBLE FISH / JOOLA", "accessories", ["beginner", "club", "regular", "advanced", "strong", "master"], ["stable", "topspin", "attack", "block"], ["care"], ["both"], ["low", "middle", "high"], 0, 0, 10, 1, "защита ракетки при переноске", "любому игроку, особенно с дорогой сборкой", "жёсткий лучше защищает; двойной удобен для двух ракеток", "balanced", "Case"),
    P("Торцевая лента Butterfly", "accessories", ["beginner", "club", "regular", "advanced", "strong", "master"], ["stable", "topspin", "attack"], ["care"], ["both"], ["low"], 0, 0, 8, 1, "защита края основания и накладок", "тем, кто хочет защитить сборку от ударов о стол", "дешёвая защита для дорогой ракетки", "value", "Care"),
    P("Мячи DHS 3*** DJ40+ WTT ITTF 6 шт", "accessories", ["beginner", "club", "regular", "advanced", "strong", "master"], ["stable", "topspin", "attack", "block"], ["training"], ["both"], ["middle", "high"], 0, 0, 9, 1, "качественные матчевые мячи 3 звезды", "играм, турнирам и тренировкам с нормальным отскоком", "лучше для матчей, чем дешёвые тренировочные мячи", "balanced", "Balls"),
    P("Мячи Double Fish V40+ WTT 6 шт", "accessories", ["beginner", "club", "regular", "advanced", "strong", "master"], ["stable", "topspin", "attack", "block"], ["training"], ["both"], ["middle", "high"], 0, 0, 9, 1, "матчевые мячи Double Fish WTT", "играм и тренировкам, где нужен стабильный отскок", "альтернатива DHS 3***", "balanced", "Balls"),
    P("Мячи DHS D40+ 120 шт / DOUBLE FISH V40+ 100 шт", "accessories", ["beginner", "club", "regular", "advanced", "strong", "master"], ["stable", "topspin", "attack", "block"], ["training"], ["both"], ["middle"], 0, 0, 8, 1, "большая упаковка для тренировок", "тренерам, клубам и отработке подачи/корзины", "выгоднее для объёма; для матчей лучше 3***", "value", "Balls"),
    P("Корзина для сбора мячей DONIC", "accessories", ["club", "regular", "advanced", "strong", "master"], ["stable", "topspin", "attack"], ["training"], ["both"], ["high"], 0, 0, 8, 1, "корзина для большого количества мячей", "тренерам и игрокам, которые отрабатывают упражнения сериями", "логична вместе с упаковкой 100/120 тренировочных мячей", "balanced", "Training"),
    P("Сетка DHS P104 / Double Fish XW-923", "accessories", ["beginner", "club", "regular", "advanced", "strong", "master"], ["stable", "topspin", "attack"], ["training"], ["both"], ["middle"], 0, 0, 8, 1, "сетка для стола из ассортимента MLSport", "домашним тренировкам, клубам и залам", "выбор зависит от крепления и задачи", "value", "Net"),
    P("Рюкзак / сумка Butterfly", "accessories", ["beginner", "club", "regular", "advanced", "strong", "master"], ["stable", "topspin", "attack"], ["care"], ["both"], ["high", "premium"], 0, 0, 8, 1, "сумка или рюкзак для формы и инвентаря", "игрокам, которые ходят на тренировки и турниры", "удобнее, чем носить всё отдельно; менеджер уточнит модель", "balanced", "Bag"),
]

# СПРАВОЧНИКИ
LEVEL_MAP = {
    "lvl_beginner": "beginner",
    "lvl_club": "club",
    "lvl_regular": "regular",
    "lvl_advanced": "advanced",
    "lvl_strong": "strong",
    "lvl_master": "master",
    "lvl_child": "beginner",
}

LEVEL_TEXT = {
    "beginner": "Новичок / любитель · ФНТР до 200",
    "club": "Клубный уровень · ФНТР до 200",
    "regular": "Играю регулярно · ФНТР 200–500",
    "advanced": "Продвинутый уровень · ФНТР 500–800",
    "strong": "Сильный игрок / КМС · ФНТР 800–1000",
    "master": "МС · ФНТР 1000+",
}

STYLE_MAP = {
    "style_stable": "stable",
    "style_topspin": "topspin",
    "style_attack": "attack",
    "style_fast": "fast",
    "style_block": "block",
    "style_power_loop": "power_loop",
    "style_defense": "defense",
    "style_universal": "universal",
    "style_unknown": "stable",
}

STYLE_TEXT = {
    "stable": "Стабильная игра",
    "topspin": "Топспины и вращение",
    "attack": "Атака",
    "fast": "Быстрая игра у стола",
    "block": "Блок и контратака",
    "power_loop": "Мощный первый топс",
    "defense": "Защита / подрезка",
    "universal": "Универсальная игра",
}

PIPS_STYLE_MAP = {
    "pips_block": "pips_block",
    "pips_defense": "pips_defense",
    "pips_disrupt": "pips_disrupt",
    "short_pips": "short_pips",
    "anti": "anti",
    "pips_unknown": "pips_block",
}

PIPS_STYLE_TEXT = {
    "pips_block": "Длинные шипы / блок у стола",
    "pips_defense": "Длинные шипы / защита",
    "pips_disrupt": "Шипы с мешающим эффектом",
    "short_pips": "Короткие шипы / атака",
    "anti": "Антиспин",
}

GOAL_MAP = {
    "goal_first": "first_racket",
    "goal_control": "control",
    "goal_less_errors": "less_errors",
    "goal_spin": "spin",
    "goal_speed": "speed",
    "goal_receive": "receive",
    "goal_backhand": "backhand",
    "goal_forehand": "forehand",
    "goal_level_up": "level_up",
    "goal_disrupt": "disrupt",
    "goal_block": "block",
    "goal_support": "support",
    "goal_lightness": "lightness",
    "goal_care": "care",
    "goal_training": "training",
    "goal_case": "case",
    "goal_glue": "glue",
    "goal_net": "net",
    "goal_bag": "bag",
}

GOAL_TEXT = {
    "first_racket": "Первая нормальная сборка",
    "control": "Больше контроля",
    "less_errors": "Меньше ошибок",
    "spin": "Больше вращения",
    "speed": "Больше скорости",
    "receive": "Лучше приём и короткая игра",
    "backhand": "Стабильнее бэкхенд",
    "forehand": "Сильнее форхенд",
    "level_up": "Инвентарь на уровень выше",
    "disrupt": "Мешать сопернику",
    "block": "Лучше блокировать",
    "support": "Поддержка стопы",
    "lightness": "Лёгкость перемещений",
    "care": "Уход / защита",
    "training": "Мячи / тренировки",
    "case": "Чехол / защита ракетки",
    "glue": "Клей / сборка ракетки",
    "net": "Сетка для стола",
    "bag": "Сумка / рюкзак",
}

SIDE_MAP = {"side_fh": "fh", "side_bh": "bh", "side_both": "both"}
SIDE_TEXT = {"fh": "Форхенд", "bh": "Бэкхенд", "both": "Обе стороны"}

BUDGET_MAP = {
    "budget_low": "low",
    "budget_middle": "middle",
    "budget_high": "high",
    "budget_premium": "premium",
    "budget_unknown": "unknown",
}

BUDGET_TEXT = {
    "low": "Бюджетный вариант",
    "middle": "Средний бюджет",
    "high": "Выше среднего",
    "premium": "Премиум",
    "unknown": "Пока не знаю",
}

ACCESSORY_MAP = {
    "acc_cleaner": "cleaner",
    "acc_film": "film",
    "acc_case": "case",
    "acc_tape": "tape",
    "acc_glue": "glue",
    "acc_match_balls": "match_balls",
    "acc_training_balls": "training_balls",
    "acc_basket": "basket",
    "acc_net": "net",
    "acc_bag": "bag",
}

ACCESSORY_TEXT = {
    "cleaner": "Очиститель / губка",
    "film": "Защитная плёнка",
    "case": "Чехол",
    "tape": "Торцевая лента",
    "glue": "Клей",
    "match_balls": "Мячи 3★ / матчевые",
    "training_balls": "Тренировочные мячи упаковкой",
    "basket": "Корзина для мячей",
    "net": "Сетка",
    "bag": "Сумка / рюкзак",
}

SHOE_FIT_MAP = {
    "shoe_fit_standard": "standard",
    "shoe_fit_wide": "wide",
    "shoe_fit_max_support": "max_support",
    "shoe_fit_light": "light",
    "shoe_fit_unknown": "unknown",
}

SHOE_FIT_TEXT = {
    "standard": "Обычная посадка",
    "wide": "Широкая стопа / нужен простор",
    "max_support": "Максимум поддержки",
    "light": "Максимум лёгкости",
    "unknown": "Пока не знаю",
}


# =========================
# TELEGRAM API
# =========================

def telegram_request(method, params=None):
    if params is None:
        params = {}

    url = API_URL + method
    data = urllib.parse.urlencode(params).encode("utf-8")

    with urllib.request.urlopen(url, data=data, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def send_message(chat_id, text, keyboard=None):
    params = {
        "chat_id": chat_id,
        "text": text,
    }

    if keyboard:
        params["reply_markup"] = json.dumps(keyboard, ensure_ascii=False)

    telegram_request("sendMessage", params)


def answer_callback(callback_query_id):
    telegram_request("answerCallbackQuery", {"callback_query_id": callback_query_id})


# =========================
# КНОПКИ
# =========================

def add_manager_button(buttons):
    buttons.append([{"text": "👨‍💼 Связаться с менеджером", "callback_data": "manager"}])
    return {"inline_keyboard": buttons}


def main_menu():
    return {
        "inline_keyboard": [
            [{"text": "✅ Я знаю, что мне нужно", "callback_data": "known_request"}],
            [{"text": "🎯 Подобрать инвентарь", "callback_data": "open_categories"}],
            [{"text": "👨‍💼 Связаться с менеджером", "callback_data": "manager"}],
        ]
    }


def category_menu():
    buttons = [
        [{"text": "🏓 Ракетка / сборка", "callback_data": "cat_racket"}],
        [{"text": "🔴 Накладки", "callback_data": "cat_rubbers"}],
        [{"text": "🪵 Основание", "callback_data": "cat_blade"}],
        [{"text": "🌵 Шипы / антиспин", "callback_data": "cat_pips"}],
        [{"text": "👟 Обувь", "callback_data": "cat_shoes"}],
        [{"text": "🎒 Аксессуары / уход", "callback_data": "cat_accessories"}],
        [{"text": "🏠 В начало", "callback_data": "restart"}],
    ]
    return add_manager_button(buttons)


def level_menu():
    buttons = [
        [{"text": "Новичок / любитель · ФНТР до 200", "callback_data": "lvl_beginner"}],
        [{"text": "Клубный уровень · ФНТР до 200", "callback_data": "lvl_club"}],
        [{"text": "Играю регулярно · ФНТР 200–500", "callback_data": "lvl_regular"}],
        [{"text": "Продвинутый · ФНТР 500–800", "callback_data": "lvl_advanced"}],
        [{"text": "Сильный игрок / КМС · ФНТР 800–1000", "callback_data": "lvl_strong"}],
        [{"text": "МС · ФНТР 1000+", "callback_data": "lvl_master"}],
        [{"text": "Подбираю для ребёнка", "callback_data": "lvl_child"}],
    ]
    return add_manager_button(buttons)


def style_menu():
    buttons = [
        [{"text": "🎯 Стабильная игра", "callback_data": "style_stable"}],
        [{"text": "🌀 Топспины и вращение", "callback_data": "style_topspin"}],
        [{"text": "⚔️ Атака", "callback_data": "style_attack"}],
        [{"text": "⚡ Быстрая игра у стола", "callback_data": "style_fast"}],
        [{"text": "🧱 Блок и контратака", "callback_data": "style_block"}],
        [{"text": "💥 Мощный первый топс", "callback_data": "style_power_loop"}],
        [{"text": "🛡️ Защита / подрезка", "callback_data": "style_defense"}],
        [{"text": "🔄 Универсальная игра", "callback_data": "style_universal"}],
        [{"text": "❓ Не уверен", "callback_data": "style_unknown"}],
    ]
    return add_manager_button(buttons)


def pips_style_menu():
    buttons = [
        [{"text": "🌵 Длинные шипы / блок у стола", "callback_data": "pips_block"}],
        [{"text": "🛡️ Длинные шипы / защита", "callback_data": "pips_defense"}],
        [{"text": "🧩 Шипы с мешающим эффектом", "callback_data": "pips_disrupt"}],
        [{"text": "⚡ Короткие шипы / атака", "callback_data": "short_pips"}],
        [{"text": "🧊 Антиспин", "callback_data": "anti"}],
        [{"text": "❓ Пока не знаю", "callback_data": "pips_unknown"}],
    ]
    return add_manager_button(buttons)


def goal_menu(level=None, category=None):
    if category == "shoes":
        return add_manager_button([
            [{"text": "🦶 Поддержка стопы", "callback_data": "goal_support"}],
            [{"text": "⚡ Лёгкость перемещений", "callback_data": "goal_lightness"}],
            [{"text": "✅ Универсальная обувь для зала", "callback_data": "goal_control"}],
        ])

    if category == "accessories":
        return add_manager_button([
            [{"text": "🧽 Уход за накладками", "callback_data": "goal_care"}],
            [{"text": "🎒 Чехол / защита ракетки", "callback_data": "goal_case"}],
            [{"text": "🧴 Клей / сборка ракетки", "callback_data": "goal_glue"}],
            [{"text": "🏓 Мячи / тренировки", "callback_data": "goal_training"}],
            [{"text": "🥅 Сетка для стола", "callback_data": "goal_net"}],
            [{"text": "👜 Сумка / рюкзак", "callback_data": "goal_bag"}],
        ])

    if category == "pips":
        return add_manager_button([
            [{"text": "🌵 Мешать сопернику", "callback_data": "goal_disrupt"}],
            [{"text": "🧱 Лучше блокировать", "callback_data": "goal_block"}],
            [{"text": "🎯 Больше контроля", "callback_data": "goal_control"}],
            [{"text": "🧩 Легче принимать вращение", "callback_data": "goal_receive"}],
        ])

    if level in ["beginner", "club"]:
        return add_manager_button([
            [{"text": "🏓 Первая нормальная сборка", "callback_data": "goal_first"}],
            [{"text": "✅ Меньше ошибок", "callback_data": "goal_less_errors"}],
            [{"text": "🎯 Больше контроля", "callback_data": "goal_control"}],
            [{"text": "🧩 Лучше принимать подачи", "callback_data": "goal_receive"}],
        ])

    if level in ["regular", "advanced"]:
        return add_manager_button([
            [{"text": "🌀 Больше вращения", "callback_data": "goal_spin"}],
            [{"text": "🚀 Больше скорости", "callback_data": "goal_speed"}],
            [{"text": "🎯 Больше контроля", "callback_data": "goal_control"}],
            [{"text": "🧱 Стабильнее бэкхенд", "callback_data": "goal_backhand"}],
            [{"text": "💥 Сильнее форхенд", "callback_data": "goal_forehand"}],
            [{"text": "📈 На уровень выше", "callback_data": "goal_level_up"}],
        ])

    return add_manager_button([
        [{"text": "💥 Усилить форхенд / первый топс", "callback_data": "goal_forehand"}],
        [{"text": "🌀 Больше качества вращения", "callback_data": "goal_spin"}],
        [{"text": "🚀 Больше скорости и давления", "callback_data": "goal_speed"}],
        [{"text": "🧩 Лучше приём / короткая игра", "callback_data": "goal_receive"}],
        [{"text": "🧱 Стабильнее бэкхенд", "callback_data": "goal_backhand"}],
        [{"text": "📈 На уровень выше", "callback_data": "goal_level_up"}],
    ])


def side_menu():
    return add_manager_button([
        [{"text": "Форхенд", "callback_data": "side_fh"}],
        [{"text": "Бэкхенд", "callback_data": "side_bh"}],
        [{"text": "Обе стороны", "callback_data": "side_both"}],
    ])


def budget_menu(category=None):
    if category == "racket":
        buttons = [
            [{"text": "до 7 000 ₽", "callback_data": "budget_low"}],
            [{"text": "7 000–15 000 ₽", "callback_data": "budget_middle"}],
            [{"text": "15 000–30 000 ₽", "callback_data": "budget_high"}],
            [{"text": "30 000 ₽+", "callback_data": "budget_premium"}],
            [{"text": "Пока не знаю", "callback_data": "budget_unknown"}],
        ]
    elif category in ["rubbers", "pips"]:
        buttons = [
            [{"text": "до 3 000 ₽ за накладку", "callback_data": "budget_low"}],
            [{"text": "3 000–5 000 ₽", "callback_data": "budget_middle"}],
            [{"text": "5 000–8 000 ₽", "callback_data": "budget_high"}],
            [{"text": "8 000 ₽+", "callback_data": "budget_premium"}],
            [{"text": "Пока не знаю", "callback_data": "budget_unknown"}],
        ]
    elif category == "blade":
        buttons = [
            [{"text": "до 5 000 ₽", "callback_data": "budget_low"}],
            [{"text": "5 000–10 000 ₽", "callback_data": "budget_middle"}],
            [{"text": "10 000–20 000 ₽", "callback_data": "budget_high"}],
            [{"text": "20 000 ₽+", "callback_data": "budget_premium"}],
            [{"text": "Пока не знаю", "callback_data": "budget_unknown"}],
        ]
    elif category == "shoes":
        buttons = [
            [{"text": "до 5 000 ₽", "callback_data": "budget_low"}],
            [{"text": "5 000–10 000 ₽", "callback_data": "budget_middle"}],
            [{"text": "10 000–15 000 ₽", "callback_data": "budget_high"}],
            [{"text": "15 000 ₽+", "callback_data": "budget_premium"}],
            [{"text": "Пока не знаю", "callback_data": "budget_unknown"}],
        ]
    else:
        buttons = [
            [{"text": "Бюджетный вариант", "callback_data": "budget_low"}],
            [{"text": "Средний бюджет", "callback_data": "budget_middle"}],
            [{"text": "Выше среднего", "callback_data": "budget_high"}],
            [{"text": "Премиум", "callback_data": "budget_premium"}],
            [{"text": "Пока не знаю", "callback_data": "budget_unknown"}],
        ]

    return add_manager_button(buttons)


def shoe_fit_menu():
    return add_manager_button([
        [{"text": "👟 Обычная посадка", "callback_data": "shoe_fit_standard"}],
        [{"text": "🦶 Широкая стопа / нужен простор", "callback_data": "shoe_fit_wide"}],
        [{"text": "🛡️ Максимум поддержки", "callback_data": "shoe_fit_max_support"}],
        [{"text": "⚡ Максимум лёгкости", "callback_data": "shoe_fit_light"}],
        [{"text": "❓ Пока не знаю", "callback_data": "shoe_fit_unknown"}],
    ])


def accessory_select_menu(selected=None):
    selected = selected or []

    def mark(key, title):
        prefix = "✅ " if key in selected else ""
        return prefix + title

    return {
        "inline_keyboard": [
            [{"text": mark("cleaner", "🧽 Очиститель / губка"), "callback_data": "acc_cleaner"}],
            [{"text": mark("film", "🛡️ Защитная плёнка"), "callback_data": "acc_film"}],
            [{"text": mark("case", "🎒 Чехол"), "callback_data": "acc_case"}],
            [{"text": mark("tape", "📏 Торцевая лента"), "callback_data": "acc_tape"}],
            [{"text": mark("glue", "🧴 Клей"), "callback_data": "acc_glue"}],
            [{"text": mark("match_balls", "🏓 Мячи 3★ / матчевые"), "callback_data": "acc_match_balls"}],
            [{"text": mark("training_balls", "📦 Тренировочные мячи упаковкой"), "callback_data": "acc_training_balls"}],
            [{"text": mark("basket", "🧺 Корзина для мячей"), "callback_data": "acc_basket"}],
            [{"text": mark("net", "🥅 Сетка"), "callback_data": "acc_net"}],
            [{"text": mark("bag", "👜 Сумка / рюкзак"), "callback_data": "acc_bag"}],
            [{"text": "➡️ Готово, показать варианты", "callback_data": "acc_done"}],
            [{"text": "👨‍💼 Передать менеджеру", "callback_data": "send_lead"}],
            [{"text": "🏠 В начало", "callback_data": "restart"}],
        ]
    }


def after_recommendation_menu(category=None):
    buttons = [
        [{"text": "👨‍💼 Передать подбор менеджеру", "callback_data": "send_lead"}],
        [{"text": "🔁 Подобрать заново", "callback_data": "open_categories"}],
    ]

    if category in ["racket", "rubbers", "blade"]:
        buttons.append([{"text": "🎒 Добавить уход / чехол", "callback_data": "upsell_accessories"}])

    buttons.append([{"text": "🏠 В начало", "callback_data": "restart"}])
    return {"inline_keyboard": buttons}


def manager_or_restart_menu():
    return {
        "inline_keyboard": [
            [{"text": "👨‍💼 Связаться с менеджером", "callback_data": "manager"}],
            [{"text": "🔁 Подобрать заново", "callback_data": "open_categories"}],
            [{"text": "🏠 В начало", "callback_data": "restart"}],
        ]
    }


# =========================
# ЛОГИКА ПОДБОРА
# =========================

def category_name(category):
    return {
        "racket": "Ракетка / сборка",
        "rubbers": "Накладки",
        "blade": "Основание",
        "pips": "Шипы / антиспин",
        "shoes": "Обувь",
        "accessories": "Аксессуары / уход",
        "manager": "Вопрос менеджеру",
        "known": "Клиент знает, что нужно",
    }.get(category, "Инвентарь")


def style_name(style):
    if style in STYLE_TEXT:
        return STYLE_TEXT[style]
    if style in PIPS_STYLE_TEXT:
        return PIPS_STYLE_TEXT[style]
    return "Не указано"


def normalize_text(text):
    return (text or "").lower().replace("ё", "е").strip()


def product_role(product):
    if product.get("role"):
        return product["role"]

    if product["control"] >= 9 and product["difficulty"] <= 5:
        return "control"

    if product["speed"] >= 9 and product["spin"] >= 9:
        return "power"

    if "premium" in product["budgets"]:
        return "premium"

    if "middle" in product["budgets"] or "low" in product["budgets"]:
        return "value"

    return "balanced"


def analyze_current_equipment(text):
    t = normalize_text(text)

    info = {
        "unknown": False,
        "ready_racket": False,
        "beginner_setup": False,
        "carbon": False,
        "premium": False,
        "fast": False,
        "control": False,
        "pips": False,
        "anti": False,
        "names": [],
    }

    if not t or t in ["не знаю", "хз", "нет", "не помню", "-"]:
        info["unknown"] = True
        return info

    groups = {
        "ready_racket": ["готовая", "готовой", "спортмастер", "декатлон", "простая", "double fish", "j5", "j7"],
        "beginner_setup": ["flextra", "allround", "allplay", "vega intro", "vega europe", "729"],
        "carbon": ["alc", "zlc", "super zlc", "super alc", "carbon", "innerforce", "outerforce", "stradivarius", "viscaria", "harimoto", "freitas", "apolonia", "franziska", "mizutani", "zhang jike", "fan zhendong", "lin yun"],
        "premium": ["dignics", "dignix", "dignis", "tenergy", "zyre", "butterfly", "alc", "zlc", "super"],
        "fast": ["dignics 05", "tenergy 05", "zyre", "omega vii tour", "mx-p 50", "bluestar a1", "viscaria", "super zlc", "super alc"],
        "control": ["vega europe", "vega intro", "allround", "allplay", "primorac", "rozena", "flextra", "acuda s3", "fx-p", "fx-s"],
        "pips": ["шип", "grass", "curl", "feint", "killer", "blowfish", "challenger"],
        "anti": ["анти", "anti", "antipower"],
    }

    for key, words in groups.items():
        for word in words:
            if word in t:
                info[key] = True
                if word not in info["names"]:
                    info["names"].append(word)

    return info


def has_word(product, words):
    name = normalize_text(product["name"])
    return any(word.lower() in name for word in words)


def product_name_in_current(product, current_info):
    name = normalize_text(product["name"])
    return any(w and w in name for w in current_info.get("names", []))


def selected_accessories_text(selected):
    if not selected:
        return "Не выбрано"
    return ", ".join(ACCESSORY_TEXT.get(x, x) for x in selected)


def hard_filter(product, answers):
    category = answers.get("category")
    level = answers.get("level")
    side = answers.get("side", "both")
    budget = answers.get("budget")
    goal = answers.get("goal")
    current_info = answers.get("current_info", {})
    selected_accessories = answers.get("selected_accessories", [])
    role = product_role(product)

    if product["category"] != category:
        return False

    if side != "both" and side not in product["sides"] and "both" not in product["sides"]:
        return False

    if budget == "low" and "premium" in product["budgets"]:
        return False

    if budget == "middle" and product["budgets"] == ["premium"] and level not in ["strong", "master"]:
        return False

    # Для аксессуаров фильтруем по выбранным кнопкам.
    if category == "accessories" and selected_accessories:
        name = normalize_text(product["name"])
        family = normalize_text(product.get("family", ""))

        accessory_match = False
        if "cleaner" in selected_accessories and any(x in name for x in ["cleaner", "wiper", "губка", "очиститель", "foam"]):
            accessory_match = True
        if "film" in selected_accessories and any(x in name for x in ["пленк", "плёнк"]):
            accessory_match = True
        if "case" in selected_accessories and any(x in name for x in ["чехол"]):
            accessory_match = True
        if "tape" in selected_accessories and any(x in name for x in ["лента"]):
            accessory_match = True
        if "glue" in selected_accessories and any(x in name for x in ["клей", "free chack", "neofix"]):
            accessory_match = True
        if "match_balls" in selected_accessories and any(x in name for x in ["3***", "3★", "wtt", "dj40"]):
            accessory_match = True
        if "training_balls" in selected_accessories and any(x in name for x in ["120", "100 шт", "трениров"]):
            accessory_match = True
        if "basket" in selected_accessories and "корзин" in name:
            accessory_match = True
        if "net" in selected_accessories and "сетк" in name:
            accessory_match = True
        if "bag" in selected_accessories and any(x in name for x in ["рюкзак", "сумка"]):
            accessory_match = True

        if not accessory_match:
            return False

    if level == "beginner" and category in ["racket", "rubbers", "blade"]:
        if product["speed"] >= 9 or product["difficulty"] >= 7 or product["control"] < 8:
            return False

    if level == "club" and category in ["racket", "rubbers", "blade"]:
        if goal in ["control", "less_errors", "first_racket", "receive"]:
            if product["speed"] >= 10 or product["difficulty"] >= 8 or product["control"] < 7:
                return False

    if level == "regular" and category in ["racket", "rubbers", "blade"]:
        if role == "value" and product["difficulty"] <= 3:
            return False
        if has_word(product, ["J5", "J7", "Flextra", "Vega Intro"]):
            return False

    if level == "advanced" and category in ["racket", "rubbers", "blade"]:
        if role in ["value", "control"] and product["difficulty"] <= 5:
            return False
        if has_word(product, ["J5", "J7", "Flextra", "Vega Intro", "Allplay", "Xiom Allround"]):
            return False

    if level == "strong" and category in ["racket", "rubbers", "blade"]:
        if role in ["value", "control"] and product["difficulty"] < 7:
            return False
        if product["speed"] < 8 and product["spin"] < 8:
            return False
        if has_word(product, ["J5", "J7", "Flextra", "Vega Intro", "Vega Europe", "Allplay", "Allround", "Primorac + Rozena"]):
            return False

    if level == "master" and category in ["racket", "rubbers", "blade"]:
        if role in ["value", "control"]:
            return False
        if "premium" not in product["budgets"] and role != "power":
            return False
        if product["difficulty"] < 8:
            return False
        if product["speed"] < 9 and product["spin"] < 9:
            return False
        if has_word(product, ["J5", "J7", "729", "Flextra", "Vega Intro", "Vega Europe", "Allplay", "Allround", "Primorac +", "Zoran Primorac +", "Xiom Allround", "Neottec", "Galaxy", "Timo Boll TJ", "Maze Advance", "Latika", "Acuda S2", "Acuda S3", "BluFire M3", "Bluestorm Z3", "FX-P", "FX-S"]):
            return False

    if current_info.get("premium") and current_info.get("fast") and category in ["racket", "rubbers", "blade"]:
        if product["difficulty"] <= 5 and product["speed"] <= 8:
            return False

    return True


def score_product(product, answers):
    if not hard_filter(product, answers):
        return -1000

    level = answers.get("level")
    style = answers.get("style")
    goal = answers.get("goal")
    side = answers.get("side", "both")
    budget = answers.get("budget")
    category = answers.get("category")
    current_info = answers.get("current_info", {})
    role = product_role(product)
    shoe_fit = answers.get("shoe_fit")
    selected_accessories = answers.get("selected_accessories", [])

    score = 50

    if level in product["levels"]:
        score += 70
    else:
        nearby = {
            "beginner": ["beginner", "club"],
            "club": ["beginner", "club", "regular"],
            "regular": ["club", "regular", "advanced"],
            "advanced": ["regular", "advanced", "strong"],
            "strong": ["advanced", "strong", "master"],
            "master": ["strong", "master"],
        }
        score += 25 if any(x in product["levels"] for x in nearby.get(level, [])) else -35

    if level in ["strong", "master"] and category in ["racket", "rubbers", "blade"]:
        if role == "premium":
            score += 45
        if role == "power":
            score += 35
        if role in ["value", "control"]:
            score -= 80

    if level == "master":
        if has_word(product, ["Dignics", "Tenergy", "ZYRE", "Super ZLC", "Super ALC", "ZLC", "Harimoto", "Fan Zhendong", "Mizutani", "Zhang Jike", "Innerforce", "Freitas", "Apolonia"]):
            score += 55
        if has_word(product, ["Glayzer", "Vega", "Acuda", "Flextra", "Allplay", "Allround", "Primorac + Rozena"]):
            score -= 100

    if style in product["styles"]:
        score += 38
    elif style == "stable" and level in ["strong", "master"]:
        if product["control"] >= 6 and product["speed"] >= 9:
            score += 20
    elif style == "universal" and any(x in product["styles"] for x in ["topspin", "attack", "stable"]):
        score += 12

    if goal in product["goals"]:
        score += 50

    if side in product["sides"] or "both" in product["sides"] or side == "both":
        score += 20
    else:
        score -= 50

    if budget == "unknown":
        score += 10
    elif budget in product["budgets"]:
        score += 35
    else:
        if level in ["strong", "master"] and "premium" in product["budgets"]:
            score += 5
        elif budget == "middle" and "high" in product["budgets"]:
            score -= 10
        elif budget == "high" and "premium" in product["budgets"]:
            score -= 5
        else:
            score -= 25

    if goal in ["control", "less_errors", "backhand"]:
        score += product["control"] * 4 - product["difficulty"] * 2

    if goal in ["speed", "forehand"]:
        score += product["speed"] * 4
        if level in ["beginner", "club"] and product["difficulty"] >= 8:
            score -= 25

    if goal in ["spin", "receive"]:
        score += product["spin"] * 5 + product["control"] * 2
        if has_word(product, ["09C", "Aibiss", "Hybrid", "Omega 7 China", "BluGrip", "ZGR", "Hurricane"]):
            score += 25

    if goal == "level_up":
        score += product["speed"] * 2 + product["spin"] * 2 + product["control"]

    if goal in ["disrupt", "block"] and category == "pips":
        score += 50

    if category == "shoes":
        if goal == "support":
            score += product["control"] * 4
            if has_word(product, ["Levalis", "Rifones"]):
                score += 25

        if goal == "lightness":
            score += product["speed"] * 4
            if has_word(product, ["Vilata", "Zero"]):
                score += 25

        if shoe_fit == "wide" and has_word(product, ["Vilata"]):
            score += 40
        elif shoe_fit == "max_support" and has_word(product, ["Levalis", "Rifones"]):
            score += 40
        elif shoe_fit == "light" and has_word(product, ["Vilata", "Zero"]):
            score += 35

    if category == "accessories":
        name = normalize_text(product["name"])

        if "cleaner" in selected_accessories and any(x in name for x in ["cleaner", "wiper", "губка", "очиститель", "foam"]):
            score += 80
        if "film" in selected_accessories and any(x in name for x in ["пленк", "плёнк"]):
            score += 80
        if "case" in selected_accessories and "чехол" in name:
            score += 80
        if "tape" in selected_accessories and "лента" in name:
            score += 80
        if "glue" in selected_accessories and any(x in name for x in ["клей", "free chack", "neofix"]):
            score += 80
        if "match_balls" in selected_accessories and any(x in name for x in ["3***", "3★", "wtt", "dj40"]):
            score += 80
        if "training_balls" in selected_accessories and any(x in name for x in ["120", "100 шт", "трениров"]):
            score += 80
        if "basket" in selected_accessories and "корзин" in name:
            score += 80
        if "net" in selected_accessories and "сетк" in name:
            score += 80
        if "bag" in selected_accessories and any(x in name for x in ["рюкзак", "сумка"]):
            score += 80

    if current_info.get("ready_racket") or current_info.get("beginner_setup"):
        if category in ["racket", "rubbers", "blade"]:
            if level in ["beginner", "club", "regular"] and product["difficulty"] <= 6 and product["control"] >= 8:
                score += 25
            if product["difficulty"] >= 9 and level in ["beginner", "club"]:
                score -= 60

    if current_info.get("carbon") or current_info.get("premium"):
        if category in ["racket", "rubbers", "blade"]:
            if product["difficulty"] <= 5 and product["speed"] <= 8:
                score -= 40
            if product["difficulty"] >= 7:
                score += 20

    if current_info.get("fast") and goal in ["control", "less_errors", "backhand"]:
        if product["control"] >= 8 and product["difficulty"] <= 8:
            score += 25

    if current_info.get("control") and goal in ["speed", "forehand", "level_up"]:
        if product["speed"] >= 8 and product["difficulty"] <= 8:
            score += 20

    if product_name_in_current(product, current_info):
        score -= 50

    return score


def get_recommendations(answers, limit=3):
    scored = []

    for product in PRODUCTS:
        score = score_product(product, answers)
        if score > 0:
            scored.append((score, product))

    scored.sort(key=lambda item: item[0], reverse=True)

    result = []
    used_names = set()

    for score, product in scored:
        if len(result) >= limit:
            break
        if product["name"] in used_names:
            continue
        result.append(product)
        used_names.add(product["name"])

    return result


def recommendation_label(index, product):
    role = product_role(product)

    if index == 1:
        return "Основной вариант"
    if role == "premium":
        return "Топовый вариант"
    if role == "power":
        return "Мощнее / быстрее"
    if role == "control":
        return "Спокойнее / контрольнее"
    if role == "value":
        return "Практичный вариант"

    return "Альтернатива"


def recommendation_footer(category):
    """
    Финальная фраза под разные категории.
    Чтобы бот не писал про ручку/толщину там, где это неуместно.
    """
    if category == "racket":
        return "Можно передать подбор менеджеру, чтобы он проверил наличие, ручку основания, цвет и толщину накладок, итоговую цену и помог со сборкой."

    if category == "rubbers":
        return "Можно передать подбор менеджеру, чтобы он проверил наличие, цвет, толщину накладки и актуальную цену."

    if category == "blade":
        return "Можно передать подбор менеджеру, чтобы он проверил наличие, форму ручки, вес основания и актуальную цену."

    if category == "pips":
        return "Можно передать подбор менеджеру, чтобы он проверил наличие, цвет, толщину, сторону установки и актуальную цену."

    if category == "shoes":
        return "Можно передать подбор менеджеру, чтобы он проверил наличие нужного размера, посадку, цвет и актуальную цену."

    if category == "accessories":
        return "Можно передать подбор менеджеру, чтобы он проверил наличие, подходящую модель, количество и актуальную цену."

    return "Можно передать подбор менеджеру, чтобы он проверил наличие и актуальную цену."


def build_recommendation_text(answers, recommendations):
    category_key = answers.get("category")
    category = category_name(category_key)
    level = LEVEL_TEXT.get(answers.get("level"), "Не указано")
    style = style_name(answers.get("style"))
    goal = GOAL_TEXT.get(answers.get("goal"), "Не указано")
    side = SIDE_TEXT.get(answers.get("side"), "Обе стороны")
    budget = BUDGET_TEXT.get(answers.get("budget"), "Не указано")
    current = answers.get("current_equipment", "Не указано")

    text = (
        "По ответам подходят варианты из текущего ассортимента MLSport:\n\n"
        f"{category} · {level}\n"
        f"Игра: {style}\n"
        f"Задача: {goal}\n"
    )

    if category_key in ["rubbers", "pips"]:
        text += f"Сторона: {side}\n"

    if category_key == "shoes":
        text += f"Размер: {answers.get('shoe_size', 'Не указан')}\n"
        text += f"Посадка: {SHOE_FIT_TEXT.get(answers.get('shoe_fit'), 'Не указано')}\n"

    if category_key == "accessories":
        text += f"Выбрано: {selected_accessories_text(answers.get('selected_accessories', []))}\n"

    text += f"Бюджет: {budget}\n"

    # Для обуви и аксессуаров строка "Сейчас играет" выглядит странно.
    if category_key in ["racket", "rubbers", "blade", "pips"]:
        text += f"Сейчас играет: {current}\n\n"
    else:
        text += f"Комментарий: {current}\n\n"

    for index, product in enumerate(recommendations, start=1):
        label = recommendation_label(index, product)
        text += (
            f"{index}. {product['name']}\n"
            f"{label}: {product['short']}.\n"
            f"Кому: {product['best_for']}.\n"
            f"Сравнение: {product['compare']}.\n"
        )

        if category_key in ["racket", "rubbers", "blade", "pips"]:
            text += (
                f"Скорость {product['speed']}/10 · "
                f"вращение {product['spin']}/10 · "
                f"контроль {product['control']}/10\n\n"
            )
        elif category_key == "shoes":
            text += (
                f"Лёгкость/скорость {product['speed']}/10 · "
                f"поддержка {product['control']}/10\n\n"
            )
        else:
            text += "\n"

    text += recommendation_footer(category_key)
    return text


def build_upsell_text():
    return (
        "Что добавить к ракетке или накладкам?\n\n"
        "Выберите один или несколько вариантов кнопками ниже. "
        "После выбора нажмите «Готово, показать варианты»."
    )


def send_recommendations(chat_id, user_id):
    answers = user_data.get(user_id, {})
    answers["current_info"] = analyze_current_equipment(answers.get("current_equipment", ""))
    recommendations = get_recommendations(answers, limit=3)

    if not recommendations:
        send_message(
            chat_id,
            "По этим ответам я не хочу советовать неподходящий инвентарь. Лучше подключить менеджера — он уточнит детали и проверит наличие.",
            manager_or_restart_menu(),
        )
        user_states[user_id] = "contact"
        return

    answers["recommendations"] = [p["name"] for p in recommendations]
    send_message(chat_id, build_recommendation_text(answers, recommendations), after_recommendation_menu(answers.get("category")))
    user_states[user_id] = "after_recommendation"


def start_bot(chat_id):
    send_message(chat_id, "🏓 Добро пожаловать в MLSport.\n\nПодберём инвентарь под вашу игру.", main_menu())


# =========================
# ЗАЩИТА ОТ ДУБЛЕЙ
# =========================

def should_skip_callback(user_id, callback_id, data):
    # Один и тот же callback_id не обрабатываем повторно.
    if callback_id in processed_callback_ids:
        return True

    processed_callback_ids.add(callback_id)

    # Чтобы set не рос бесконечно.
    if len(processed_callback_ids) > 2000:
        processed_callback_ids.clear()
        processed_callback_ids.add(callback_id)

    now = time.monotonic()
    last_data, last_time = last_callback_by_user.get(user_id, (None, 0))

    # Игнорируем только тот же самый callback_data, если кликнули почти одновременно.
    if data == last_data and now - last_time < CALLBACK_DEBOUNCE_SECONDS:
        return True

    last_callback_by_user[user_id] = (data, now)
    return False


# =========================
# ОБРАБОТКА CALLBACK
# =========================

def process_callback(update):
    callback = update["callback_query"]
    callback_id = callback["id"]
    chat_id = callback["message"]["chat"]["id"]
    user_id = callback["from"]["id"]
    data = callback["data"]

    if should_skip_callback(user_id, callback_id, data):
        try:
            answer_callback(callback_id)
        except Exception:
            pass
        return

    answer_callback(callback_id)

    if data == "restart":
        user_states.pop(user_id, None)
        user_data.pop(user_id, None)
        start_bot(chat_id)
        return

    if data == "open_categories":
        user_states.pop(user_id, None)
        user_data[user_id] = {}
        send_message(chat_id, "Что подбираем?", category_menu())
        return

    if data == "known_request":
        user_data[user_id] = {"category": "known"}
        user_states[user_id] = "known_request"
        send_message(chat_id, "Напишите, что нужно.\n\nНапример: «Tenergy 05, красная, 2.1» или «хочу узнать наличие Innerforce ALC FL».")
        return

    if data == "manager":
        saved = user_data.get(user_id, {})
        saved["category"] = saved.get("category", "manager")
        user_data[user_id] = saved
        user_states[user_id] = "contact"
        send_message(chat_id, "Напишите вопрос или что хотите подобрать.\n\nМожно оставить телефон или Telegram, если удобно.")
        return

    if data == "upsell_accessories":
        saved = user_data.get(user_id, {})
        saved["category"] = "accessories"
        saved["level"] = saved.get("level", "club")
        saved["style"] = saved.get("style", "stable")
        saved["goal"] = "care"
        saved["side"] = "both"
        saved["budget"] = saved.get("budget", "unknown")
        saved["selected_accessories"] = saved.get("selected_accessories", [])
        user_data[user_id] = saved
        user_states[user_id] = "accessory_select"

        send_message(chat_id, build_upsell_text(), accessory_select_menu(saved["selected_accessories"]))
        return

    if data in ACCESSORY_MAP:
        saved = user_data.get(user_id, {})
        saved["category"] = "accessories"
        saved["level"] = saved.get("level", "club")
        saved["style"] = saved.get("style", "stable")
        saved["goal"] = saved.get("goal", "care")
        saved["side"] = "both"
        saved["budget"] = saved.get("budget", "unknown")

        selected = saved.get("selected_accessories", [])
        item = ACCESSORY_MAP[data]

        if item in selected:
            selected.remove(item)
        else:
            selected.append(item)

        saved["selected_accessories"] = selected
        user_data[user_id] = saved
        user_states[user_id] = "accessory_select"

        text = (
            "Выберите один или несколько аксессуаров.\n\n"
            f"Сейчас выбрано: {selected_accessories_text(selected)}\n\n"
            "Когда закончите, нажмите «Готово, показать варианты»."
        )
        send_message(chat_id, text, accessory_select_menu(selected))
        return

    if data == "acc_done":
        saved = user_data.get(user_id, {})
        if not saved.get("selected_accessories"):
            send_message(chat_id, "Сначала выберите хотя бы один аксессуар кнопкой.", accessory_select_menu([]))
            return

        saved["category"] = "accessories"
        saved["level"] = saved.get("level", "club")
        saved["style"] = saved.get("style", "stable")
        saved["side"] = "both"
        saved["budget"] = saved.get("budget", "unknown")
        saved["current_equipment"] = saved.get("current_equipment", "Не указано")
        user_data[user_id] = saved

        send_recommendations(chat_id, user_id)
        return

    if data in ["tweak_control", "tweak_speed", "tweak_cheaper", "tweak_more"]:
        send_message(chat_id, "Эти быстрые кнопки больше не используются. Лучше пройти подбор заново или передать текущий подбор менеджеру.", manager_or_restart_menu())
        return

    category_map = {
        "cat_racket": "racket",
        "cat_rubbers": "rubbers",
        "cat_blade": "blade",
        "cat_pips": "pips",
        "cat_shoes": "shoes",
        "cat_accessories": "accessories",
    }

    if data in category_map:
        category = category_map[data]
        user_data[user_id] = {"category": category}

        if category == "accessories":
            user_data[user_id]["level"] = "club"
            user_data[user_id]["style"] = "stable"
            user_data[user_id]["side"] = "both"
            user_data[user_id]["budget"] = "unknown"
            user_data[user_id]["selected_accessories"] = []
            user_states[user_id] = "accessory_select"
            send_message(chat_id, "Что нужно из аксессуаров? Можно выбрать несколько вариантов.", accessory_select_menu([]))
        else:
            user_states[user_id] = "level"
            send_message(chat_id, "Какой у вас уровень?", level_menu())

        return

    if data in LEVEL_MAP:
        if user_id not in user_data:
            user_data[user_id] = {}

        user_data[user_id]["level"] = LEVEL_MAP[data]
        category = user_data[user_id].get("category")

        if category == "shoes":
            user_data[user_id]["style"] = "stable"
            user_data[user_id]["side"] = "both"
            user_states[user_id] = "goal"
            send_message(chat_id, "Что важнее в обуви?", goal_menu(user_data[user_id].get("level"), category))
        elif category == "pips":
            user_states[user_id] = "pips_style"
            send_message(chat_id, "Какой вариант ближе?", pips_style_menu())
        else:
            user_states[user_id] = "style"
            send_message(chat_id, "Как вы чаще выигрываете очки?", style_menu())

        return

    if data in STYLE_MAP:
        user_data[user_id]["style"] = STYLE_MAP[data]
        user_states[user_id] = "goal"
        send_message(chat_id, "Что хотите улучшить?", goal_menu(user_data[user_id].get("level"), user_data[user_id].get("category")))
        return

    if data in PIPS_STYLE_MAP:
        user_data[user_id]["style"] = PIPS_STYLE_MAP[data]
        user_states[user_id] = "goal"
        send_message(chat_id, "Что хотите получить от шипов / антиспина?", goal_menu(user_data[user_id].get("level"), user_data[user_id].get("category")))
        return

    if data in GOAL_MAP:
        user_data[user_id]["goal"] = GOAL_MAP[data]
        category = user_data[user_id].get("category")

        if category in ["rubbers", "pips"]:
            user_states[user_id] = "side"
            send_message(chat_id, "Для какой стороны подбираем?", side_menu())
        elif category == "accessories":
            user_states[user_id] = "accessory_select"
            send_message(chat_id, "Выберите конкретные аксессуары. Можно выбрать несколько вариантов.", accessory_select_menu(user_data[user_id].get("selected_accessories", [])))
        else:
            user_data[user_id]["side"] = "both"
            user_states[user_id] = "budget"
            send_message(chat_id, "Какой бюджет?", budget_menu(category))

        return

    if data in SIDE_MAP:
        user_data[user_id]["side"] = SIDE_MAP[data]
        user_states[user_id] = "budget"
        send_message(chat_id, "Какой бюджет?", budget_menu(user_data[user_id].get("category")))
        return

    if data in BUDGET_MAP:
        user_data[user_id]["budget"] = BUDGET_MAP[data]
        category = user_data[user_id].get("category")

        if category == "shoes":
            user_states[user_id] = "shoe_size"
            send_message(chat_id, "Напишите размер обуви.\n\nНапример: 42 или 26.5 см.")
        elif category == "accessories":
            user_states[user_id] = "accessory_select"
            send_message(chat_id, "Выберите конкретные аксессуары. Можно выбрать несколько вариантов.", accessory_select_menu(user_data[user_id].get("selected_accessories", [])))
        elif category == "pips":
            user_states[user_id] = "current_equipment"
            send_message(chat_id, "Напишите, чем играете сейчас и был ли опыт с шипами / антиспином.")
        else:
            user_states[user_id] = "current_equipment"
            send_message(chat_id, "Напишите, чем играете сейчас.\n\nНапример: основание Korbel, справа Tenergy 05, слева Dignics 80.\nЕсли не знаете — напишите «не знаю».")

        return

    if data in SHOE_FIT_MAP:
        saved = user_data.get(user_id, {})
        saved["shoe_fit"] = SHOE_FIT_MAP[data]
        saved["current_equipment"] = f"Размер обуви: {saved.get('shoe_size', 'Не указан')}; посадка: {SHOE_FIT_TEXT.get(saved.get('shoe_fit'), 'Не указано')}"
        user_data[user_id] = saved
        send_recommendations(chat_id, user_id)
        return

    if data == "send_lead":
        user_states[user_id] = "lead_contact"
        send_message(chat_id, "Оставьте контакт для связи или просто напишите, как удобнее продолжить.")
        return


# =========================
# ОБРАБОТКА СООБЩЕНИЙ
# =========================

def process_message(update):
    message = update["message"]
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    username = message["from"].get("username", "username скрыт")
    text = message.get("text", "")

    if text == "/start":
        start_bot(chat_id)
        return

    state = user_states.get(user_id)

    if state == "known_request":
        admin_text = (
            "🏓 Клиент знает, что ему нужно\n\n"
            f"Запрос: {text}\n"
            f"Telegram пользователя: @{username}"
        )

        send_message(ADMIN_ID, admin_text)
        send_message(chat_id, "Готово ✅\n\nПередал запрос менеджеру. Он проверит наличие и ответит.", main_menu())

        user_states.pop(user_id, None)
        user_data.pop(user_id, None)
        return

    if state == "shoe_size":
        user_data[user_id]["shoe_size"] = text.strip()
        user_states[user_id] = "shoe_fit"
        send_message(chat_id, "Какая посадка или ощущение важнее?", shoe_fit_menu())
        return

    if state == "current_equipment":
        user_data[user_id]["current_equipment"] = text
        send_recommendations(chat_id, user_id)
        return

    if state == "lead_contact":
        user_data[user_id]["contact"] = text
        data = user_data.get(user_id, {})
        recommendations_text = "\n".join([f"— {item}" for item in data.get("recommendations", [])]) or "Не сформированы"

        admin_text = (
            "🏓 Новая заявка MLSport\n\n"
            f"Категория: {category_name(data.get('category'))}\n"
            f"Уровень: {LEVEL_TEXT.get(data.get('level'), 'Не указано')}\n"
            f"Стиль / вариант игры: {style_name(data.get('style'))}\n"
            f"Задача: {GOAL_TEXT.get(data.get('goal'), 'Не указано')}\n"
            f"Сторона: {SIDE_TEXT.get(data.get('side'), 'Не указано')}\n"
            f"Бюджет: {BUDGET_TEXT.get(data.get('budget'), 'Не указано')}\n"
            f"Сейчас играет: {data.get('current_equipment', 'Не указано')}\n"
            f"Размер обуви: {data.get('shoe_size', 'Не указано')}\n"
            f"Посадка обуви: {SHOE_FIT_TEXT.get(data.get('shoe_fit'), 'Не указано')}\n"
            f"Аксессуары: {selected_accessories_text(data.get('selected_accessories', []))}\n"
            f"Комментарий по допродаже: {data.get('upsell_comment', 'Не указано')}\n\n"
            f"Рекомендации бота:\n{recommendations_text}\n\n"
            f"Контакт / комментарий клиента: {data.get('contact', 'Не указано')}\n"
            f"Telegram пользователя: @{username}"
        )

        send_message(ADMIN_ID, admin_text)
        send_message(chat_id, "Готово ✅\n\nПередал подбор менеджеру.", main_menu())

        user_states.pop(user_id, None)
        user_data.pop(user_id, None)
        return

    if state == "contact":
        data = user_data.get(user_id, {})
        recommendations_text = "\n".join([f"— {item}" for item in data.get("recommendations", [])]) or "Не сформированы"

        admin_text = (
            "🏓 Вопрос менеджеру MLSport\n\n"
            f"Сообщение клиента: {text}\n"
            f"Категория: {category_name(data.get('category'))}\n"
            f"Уровень: {LEVEL_TEXT.get(data.get('level'), 'Не указано')}\n"
            f"Стиль / вариант игры: {style_name(data.get('style'))}\n"
            f"Задача: {GOAL_TEXT.get(data.get('goal'), 'Не указано')}\n"
            f"Бюджет: {BUDGET_TEXT.get(data.get('budget'), 'Не указано')}\n"
            f"Сейчас играет: {data.get('current_equipment', 'Не указано')}\n"
            f"Размер обуви: {data.get('shoe_size', 'Не указано')}\n"
            f"Посадка обуви: {SHOE_FIT_TEXT.get(data.get('shoe_fit'), 'Не указано')}\n"
            f"Аксессуары: {selected_accessories_text(data.get('selected_accessories', []))}\n"
            f"Рекомендации бота:\n{recommendations_text}\n\n"
            f"Telegram пользователя: @{username}"
        )

        send_message(ADMIN_ID, admin_text)
        send_message(chat_id, "Готово ✅\n\nПередал менеджеру.", main_menu())

        user_states.pop(user_id, None)
        user_data.pop(user_id, None)
        return

    if state == "upsell_contact":
        user_data[user_id]["upsell_comment"] = text
        user_states[user_id] = "lead_contact"
        send_message(chat_id, "Оставьте контакт или напишите, как удобнее продолжить.")
        return

    send_message(chat_id, "Нажмите /start, чтобы открыть меню.")


# =========================
# ЗАПУСК
# =========================

def get_start_offset():
    # Важно: при перезапуске бота сбрасываем старые pending updates,
    # иначе Telegram может снова прислать старые нажатия и бот повторит вопросы.
    try:
        result = telegram_request("getUpdates", {"timeout": 0})
        updates = result.get("result", [])
        if updates:
            return updates[-1]["update_id"] + 1
    except Exception as e:
        print("Не удалось сбросить старые updates:")
        print(type(e).__name__)
        print(e)

    return 0


def main():
    print("Бот запущен")
    offset = get_start_offset()

    while True:
        try:
            result = telegram_request("getUpdates", {"offset": offset, "timeout": 5})
            updates = result.get("result", [])

            for update in updates:
                offset = update["update_id"] + 1

                if "message" in update:
                    process_message(update)
                elif "callback_query" in update:
                    process_callback(update)

        except Exception as e:
            print("Ошибка:")
            print(type(e).__name__)
            print(e)
            time.sleep(5)


if __name__ == "__main__":
    main()
