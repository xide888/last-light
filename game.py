#!/usr/bin/env python3
"""
ПОСЛЕДНИЙ СВЕТ — терминальная пошаговая выживалка-стратегия.
Python stdlib only, один файл, без curses.
"""
import argparse
import json
import random
import sys
def print_banner():
    """Выводит ASCII-баннер."""
    banner = r"""
  ____             _      __  __           _       _
 |  _ \           (_)    |  \/  |         | |     | |
 | |_) |_   _ _ __ _ ___ | \  / | __ _ ___| |_ ___| | __
 |  _ <| | | | '__| / __|| |\/| |/ _` / __| __/ __| |/ /
 | |_) | |_| | |  | \__ \| |  | | (_| \__ \ || (__|   <
 |____/ \__,_|_|  |_|___/|_|  |_|\__,_|___/\__\___|_|\_\
          ПОСЛЕДНИЙ СВЕТ
"""
    print(banner)
class GameState:
    def __init__(self, seed, perk):
        self.rng = random.Random(seed)
        self.perk = perk
        # Старт (seed=42, перк по умолчанию = engineer)
        self.food = 15
        self.scrap = 10
        self.fuel = 10
        self.generators = 1
        self.crew = 3
        self.hp = 5
        self.level = 1
        self.drones = 0
        # Соперники
        self.rivals = {
            1: {"name": "Ржавые", "level": 1, "drones": 0, "hostile": True, "scrap": 10, "fuel": 8, "food": 12, "crew": 3, "generators": 1, "subjugated": False, "destroyed": False},
            2: {"name": "Теплицы", "level": 1, "drones": 0, "hostile": False, "scrap": 10, "fuel": 8, "food": 12, "crew": 3, "generators": 1, "subjugated": False, "destroyed": False}
        }
        # Разведка (снятие тумана)
        self.scouted = {1: False, 2: False}
        # События текущего хода
        self.events = []
        # Номер хода
        self.turn = 0
        # Флаги окончания игры
        self.game_over = False
        self.victory = False
        # Энергия текущего хода (вычисляется)
        self.energy = 0
        # Дань от подчинённых соперников
        self.tribute_scrap = 0
    def compute_energy(self):
        """Вычисляет доступную энергию от генераторов."""
        return self.generators * 2
    def consume_fuel(self):
        """Генераторы потребляют топливо."""
        fuel_needed = self.generators
        if self.fuel >= fuel_needed:
            self.fuel -= fuel_needed
            # Топливо потрачено успешно, генераторы работают
            return True
        else:
            # Если топлива не хватает, генераторы останавливаются
            self.fuel = 0
            return False
    def spend_food(self):
        """Тратит еду на экипаж. При нехватке — урон герою и смерть выживших."""
        needed = self.crew
        if self.food >= needed:
            self.food -= needed
        else:
            deficit = needed - self.food
            self.food = 0
            # Сначала HP героя (урон = min(deficit, 2) за ход)
            if self.hp > 0:
                damage = min(deficit, 2, self.hp)
                self.hp -= damage
                deficit -= damage
                self.events.append(f"Герой потерял {damage} HP от голода")
            # Потом умирают выжившие
            if deficit > 0 and self.crew > 0:
                deaths = min(deficit, self.crew)
                self.crew -= deaths
                self.events.append(f"От голода погибло {deaths} выживших")
    def check_game_over(self):
        """Проверяет условия поражения и победы."""
        if self.crew <= 0:
            self.game_over = True
            return True
        # Победа: оба соперника подчинены или уничтожены
        rival1_done = self.rivals[1]["subjugated"] or self.rivals[1]["destroyed"]
        rival2_done = self.rivals[2]["subjugated"] or self.rivals[2]["destroyed"]
        if rival1_done and rival2_done:
            self.game_over = True
            self.victory = True
            return True
        return False
    def to_json(self):
        """Возвращает состояние в виде JSON-совместимого dict."""
        return {
            "turn": self.turn,
            "hp": self.hp,
            "crew": self.crew,
            "food": self.food,
            "scrap": self.scrap,
            "fuel": self.fuel,
            "energy": self.energy,
            "generators": self.generators,
            "level": self.level,
            "drones": self.drones,
            "rivals": {
                str(k): {
                    "level": v["level"],
                    "drones": v["drones"],
                    "hostile": v["hostile"]
                } for k, v in self.rivals.items()
            },
            "events": self.events,
            "game_over": self.game_over,
            "victory": self.victory
        }
def get_scavenge_result(state):
    """Результат вылазки (scavenge)."""
    roll = state.rng.random()
    scrap_gain = 0
    fuel_gain = 0
    food_gain = 0
    danger = False
    empty = False
    # 10% пусто, 10% опасность
    if roll < 0.1:
        empty = True
        state.events.append("Вылазка: пусто")
    elif roll < 0.2:
        danger = True
        state.hp -= 1
        state.events.append("Вылазка: опасность! HP -1")
    else:
        # Добыча
        base_scrap = state.rng.randint(1, 3)
        base_fuel = state.rng.randint(1, 3)
        base_food = state.rng.randint(2, 4)
        if state.perk == "scavenger":
            base_scrap += 1
            base_fuel += 1
            base_food += 1
        state.scrap += base_scrap
        state.fuel += base_fuel
        state.food += base_food
        state.events.append(f"Вылазка: +{base_scrap} лом, +{base_fuel} топливо, +{base_food} еда")
def cmd_scavenge(state, energy_spent):
    """Команда scavenge — 1⚡."""
    if energy_spent < 1:
        print("Недостаточно энергии!")
        return False
    get_scavenge_result(state)
    return True
def cmd_build_gen(state, energy_spent):
    """Команда build_gen — 2⚡: 6 лома + 2 топливо → +1 генератор."""
    if energy_spent < 2:
        print("Недостаточно энергии!")
        return False
    cost_scrap = 6
    if state.perk == "engineer":
        cost_scrap -= 1
    cost_fuel = 2
    if state.scrap >= cost_scrap and state.fuel >= cost_fuel:
        state.scrap -= cost_scrap
        state.fuel -= cost_fuel
        state.generators += 1
        state.events.append(f"Построен генератор (-{cost_scrap} лом, -{cost_fuel} топливо)")
        return True
    else:
        print(f"Недостаточно ресурсов (нужно {cost_scrap} лома и {cost_fuel} топлива)")
        return False
def cmd_upgrade(state, energy_spent):
    """Команда upgrade — 3⚡: апгрейд уровня убежища."""
    if energy_spent < 3:
        print("Недостаточно энергии!")
        return False
    current_level = state.level
    if current_level == 1:
        # Требуется 12 лома + 2 генератора
        required_scrap = 12
        required_generators = 2
        if state.scrap >= required_scrap and state.generators >= required_generators:
            state.scrap -= required_scrap
            state.level = 2
            state.events.append("Убежище upgraded до уровня 2! Открыты: дроны, теплица, разведка")
            return True
        else:
            missing = []
            if state.scrap < required_scrap:
                missing.append(f"{required_scrap - state.scrap} лома")
            if state.generators < required_generators:
                missing.append(f"{required_generators - state.generators} генераторов")
            print(f"Не хватает: {', '.join(missing)}")
            return False
    elif current_level == 2:
        # Требуется 20 лома + 3 генератора
        required_scrap = 20
        required_generators = 3
        if state.scrap >= required_scrap and state.generators >= required_generators:
            state.scrap -= required_scrap
            state.level = 3
            state.events.append("Убежище upgraded до уровня 3! Открыты: стены")
            return True
        else:
            missing = []
            if state.scrap < required_scrap:
                missing.append(f"{required_scrap - state.scrap} лома")
            if state.generators < required_generators:
                missing.append(f"{required_generators - state.generators} генераторов")
            print(f"Не хватает: {', '.join(missing)}")
            return False
    else:
        print("Максимальный уровень убежища")
        return False
def cmd_make_drone(state, energy_spent):
    """Команда make_drone — 2⚡: 5 лома + 1 топливо → +1 дрон (нужен ур. 2)."""
    if energy_spent < 2:
        print("Недостаточно энергии!")
        return False
    if state.level < 2:
        print("Нужен уровень убежища 2!")
        return False
    cost_scrap = 5
    if state.perk == "engineer":
        cost_scrap -= 1
    cost_fuel = 1
    if state.scrap >= cost_scrap and state.fuel >= cost_fuel:
        state.scrap -= cost_scrap
        state.fuel -= cost_fuel
        state.drones += 1
        state.events.append(f"Создан дрон (-{cost_scrap} лом, -{cost_fuel} топливо)")
        return True
    else:
        print(f"Недостаточно ресурсов (нужно {cost_scrap} лома и {cost_fuel} топлива)")
        return False
def cmd_scout(state, energy_spent, rival_id):
    """Команда scout N — 1⚡: снять «туман» с соперника N."""
    if energy_spent < 1:
        print("Недостаточно энергии!")
        return False
    if rival_id not in [1, 2]:
        print("Неверный номер соперника (1 или 2)")
        return False
    state.scouted[rival_id] = True
    rival = state.rivals[rival_id]
    state.events.append(f"Разведка соперника '{rival['name']}': уровень {rival['level']}, дронов {rival['drones']}, враждебен: {rival['hostile']}")
    return True
def cmd_raid(state, energy_spent, rival_id):
    """Команда raid N — 2⚡: рейд на соперника N."""
    if energy_spent < 2:
        print("Недостаточно энергии!")
        return False
    if rival_id not in [1, 2]:
        print("Неверный номер соперника (1 или 2)")
        return False
    if state.drones < 1:
        print("Нужен хотя бы 1 дрон!")
        return False
    if not state.scouted[rival_id]:
        print("Нужна разведка соперника!")
        return False
    rival = state.rivals[rival_id]
    if rival["subjugated"] or rival["destroyed"]:
        print("Соперник уже подчинён или уничтожен")
        return False
    # Атака игрока
    attack_power = state.drones * 2
    if state.perk == "soldier":
        attack_power += 1
    # Защита соперника
    defense_power = rival["drones"] * 2 + rival["level"]
    # Стены на уровне 3
    if rival["level"] >= 3:
        defense_power += 1
    # Определение победителя (seed-рандом)
    total_power = attack_power + defense_power
    if total_power == 0:
        player_wins = state.rng.random() < 0.5
    else:
        player_wins = state.rng.random() < (attack_power / total_power)
    if player_wins:
        # Игрок побеждает
        # Теряет часть дронов
        drone_loss = state.rng.randint(0, state.drones // 2)
        state.drones -= drone_loss
        # Проигравший отдаёт 50% складов
        scrap_take = rival["scrap"] // 2
        fuel_take = rival["fuel"] // 2
        food_take = rival["food"] // 2
        rival["scrap"] -= scrap_take
        rival["fuel"] -= fuel_take
        rival["food"] -= food_take
        state.scrap += scrap_take
        state.fuel += fuel_take
        state.food += food_take
        # Можно подчинить или уничтожить
        # Подчинение при победе в бою при attack_power >= defense_power
        if attack_power >= defense_power:
            rival["subjugated"] = True
            state.events.append(f"Рейд на '{rival['name']}' ПОБЕДА! Соперник подчинён. Получено: +{scrap_take} лом, +{fuel_take} топливо, +{food_take} еда")
            state.tribute_scrap += 1  # дань +1 лом/ход
        else:
            state.events.append(f"Рейд на '{rival['name']}' ПОБЕДА! Получено: +{scrap_take} лом, +{fuel_take} топливо, +{food_take} еда")
    else:
        # Игрок проигрывает
        # Теряет часть дронов
        drone_loss = state.rng.randint(1, state.drones)
        state.drones -= drone_loss
        # Отдаём 50% своих складов сопернику
        scrap_lost = state.scrap // 2
        fuel_lost = state.fuel // 2
        food_lost = state.food // 2
        state.scrap -= scrap_lost
        state.fuel -= fuel_lost
        state.food -= food_lost
        rival["scrap"] += scrap_lost
        rival["fuel"] += fuel_lost
        rival["food"] += food_lost
        state.events.append(f"Рейд на '{rival['name']}' ПОРАЖЕНИЕ! Потеряно дронов: {drone_loss}, отдано 50% складов")
    return True
def process_rivals(state):
    """Обработка хода соперников (ИИ)."""
    for rival_id, rival in state.rivals.items():
        if rival["subjugated"] or rival["destroyed"]:
            continue
        # Простая логика ИИ
        # Каждый ход соперник получает ресурсы и может строить
        # Еда на экипаж
        if rival["food"] >= rival["crew"]:
            rival["food"] -= rival["crew"]
        else:
            rival["crew"] = max(0, rival["crew"] - 1)
        # Топливо на генераторы
        if rival["fuel"] >= rival["generators"]:
            rival["fuel"] -= rival["generators"]
        else:
            rival["fuel"] = 0
        # Добыча ресурсов (упрощённо)
        rival["scrap"] += state.rng.randint(1, 3)
        rival["fuel"] += state.rng.randint(0, 2)
        rival["food"] += state.rng.randint(1, 3)
        # Постройка генераторов
        if rival["scrap"] >= 6 and rival["fuel"] >= 2:
            rival["scrap"] -= 6
            rival["fuel"] -= 2
            rival["generators"] += 1
        # Апгрейд уровня
        if rival["level"] == 1 and rival["scrap"] >= 12 and rival["generators"] >= 2:
            rival["scrap"] -= 12
            rival["level"] = 2
        elif rival["level"] == 2 and rival["scrap"] >= 20 and rival["generators"] >= 3:
            rival["scrap"] -= 20
            rival["level"] = 3
        # Создание дронов (если уровень >= 2, только при drones < 2)
        if rival["level"] >= 2 and rival["drones"] < 2 and rival["scrap"] >= 5 and rival["fuel"] >= 1:
            rival["scrap"] -= 5
            rival["fuel"] -= 1
            rival["drones"] += 1
        # Агрессия "Ржавых"
        if rival["name"] == "Ржавые" and rival["drones"] > state.drones:
            rival["hostile"] = True
        # "Теплицы" рейдят только от отчаяния
        if rival["name"] == "Теплицы" and rival["food"] < rival["crew"]:
            rival["hostile"] = True
def process_events(state):
    """Обработка случайных событий (~25% хода)."""
    if state.rng.random() < 0.25:
        event_type = state.rng.choice(["ash_storm", "stash", "wanderer", "breakdown", "rats"])
        if event_type == "ash_storm":
            fuel_loss = state.rng.randint(1, 3)
            state.fuel = max(0, state.fuel - fuel_loss)
            state.events.append(f"Событие: пепельная буря! Потеряно {fuel_loss} топлива")
        elif event_type == "stash":
            scrap_gain = state.rng.randint(2, 5)
            state.scrap += scrap_gain
            state.events.append(f"Событие: тайник! Найдено {scrap_gain} лома")
        elif event_type == "wanderer":
            state.crew += 1
            state.events.append("Событие: странник присоединился! +1 экипаж")
        elif event_type == "breakdown":
            state.events.append("Событие: поломка генератора! Требуется 1 лом на ремонт")
            # Ремонт автоматический если есть лом
            if state.scrap >= 1:
                state.scrap -= 1
                state.events.append("Генератор отремонтирован (-1 лом)")
            else:
                state.generators = max(0, state.generators - 1)
                state.events.append("Генератор потерян (не хватило лома на ремонт)")
        elif event_type == "rats":
            food_loss = state.rng.randint(1, 3)
            state.food = max(0, state.food - food_loss)
            state.events.append(f"Событие: крысы! Потеряно {food_loss} еды")
def main():
    parser = argparse.ArgumentParser(description="ПОСЛЕДНИЙ СВЕТ — выживалка-стратегия")
    parser.add_argument("--seed", type=int, default=None, help="Seed для детерминизма")
    parser.add_argument("--perk", choices=["engineer", "scavenger", "soldier"], default="engineer",
                        help="Перк героя")
    args = parser.parse_args()
    seed = args.seed if args.seed is not None else 42
    print_banner()
    state = GameState(seed, args.perk)
    # Первый вывод состояния после баннера (опционально, но для ясности)
    # print(json.dumps(state.to_json()))
    while not state.game_over:
        state.turn += 1
        state.events = []
        # Вычисляем энергию
        state.energy = state.compute_energy()
        # Потребление топлива генераторами
        generators_working = state.consume_fuel()
        # Если топливо законилось, генераторы не дают энергию
        if not generators_working:
            state.energy = 0
        # Добавляем дань от подчинённых
        if state.tribute_scrap > 0:
            state.scrap += state.tribute_scrap
            state.events.append(f"Дань от подчинённых: +{state.tribute_scrap} лом")
        available_energy = state.energy
        energy_spent = 0
        print(f"\n=== Ход {state.turn} ===")
        print(f"HP: {state.hp}, Экипаж: {state.crew}, Еда: {state.food}")
        print(f"Лом: {state.scrap}, Топливо: {state.fuel}")
        print(f"Генераторы: {state.generators}, Энергия: {available_energy}")
        print(f"Уровень: {state.level}, Дроны: {state.drones}")
        print(f"Перк: {args.perk}")
        print("Команды: scavenge, build_gen, upgrade, make_drone, scout N, raid N, end")
        commands_this_turn = []
        while True:
            try:
                cmd_input = input("> ").strip()
            except EOFError:
                break
            if not cmd_input:
                continue
            parts = cmd_input.split()
            cmd = parts[0].lower()
            if cmd == "end":
                break
            if cmd == "scavenge":
                if cmd_scavenge(state, available_energy - energy_spent):
                    energy_spent += 1
                commands_this_turn.append(cmd)
            elif cmd == "build_gen":
                if cmd_build_gen(state, available_energy - energy_spent):
                    energy_spent += 2
                commands_this_turn.append(cmd)
            elif cmd == "upgrade":
                if cmd_upgrade(state, available_energy - energy_spent):
                    energy_spent += 3
                commands_this_turn.append(cmd)
            elif cmd == "make_drone":
                if cmd_make_drone(state, available_energy - energy_spent):
                    energy_spent += 2
                commands_this_turn.append(cmd)
            elif cmd == "scout":
                if len(parts) < 2:
                    print("Использование: scout N (N=1 или 2)")
                else:
                    try:
                        rival_id = int(parts[1])
                        if cmd_scout(state, available_energy - energy_spent, rival_id):
                            energy_spent += 1
                        commands_this_turn.append(cmd)
                    except ValueError:
                        print("Неверный номер соперника")
            elif cmd == "raid":
                if len(parts) < 2:
                    print("Использование: raid N (N=1 или 2)")
                else:
                    try:
                        rival_id = int(parts[1])
                        if cmd_raid(state, available_energy - energy_spent, rival_id):
                            energy_spent += 2
                        commands_this_turn.append(cmd)
                    except ValueError:
                        print("Неверный номер соперника")
            else:
                print(f"Неизвестная команда: {cmd}")
        # Обработка соперников
        process_rivals(state)
        # Случайные события
        process_events(state)
        # Трата еды
        state.spend_food()
        # Проверка окончания игры
        state.check_game_over()
        # Вывод JSON состояния
        print(json.dumps(state.to_json()))
        if state.game_over:
            if state.victory:
                print("\n*** ПОБЕДА! Оба соперника подчинены или уничтожены. ***")
            else:
                print("\n*** ПОРАЖЕНИЕ! Экипаж погиб. ***")
            break
    sys.exit(0)
if __name__ == "__main__":
    main()