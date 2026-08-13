from ortools.sat.python import cp_model

def swap(i, j, T):
    temp = T[i]
    T[i] = T[j]
    T[j] = temp

def solve_albion_route(T, start_city):
    model = cp_model.CpModel()

    # ==========================================
    # DONNÉES DU PROBLÈME (Mock Data)
    # ==========================================
    cities = ['Thetford', 'Fort Sterling', 'Lymhurst', 'Bridgewatch', 'Martlock']

    items = [
        'double bladed staff', 'dual sword', 'fiend robe', 'soldier armor',
        'soldier helmet', 'stalker shoes (recipe 2)', 'soldier boots', 'knight boots',
        'Steel Bar', 'Worked Leather', 'Fine Cloth', 'Travertine Block', 'Pine Planks',
        "Adept's Rune", 'Infernal Cloth Folds', 'Crystallized Spirit'
    ]

    C_max = 1997  # Renseigne ici la capacité de la monture (en kg)
    MAX_QTY = 999999
    SCALE = 1000

    masses = {
        'double bladed staff': 6.8, 'dual sword': 6.8, 'fiend robe': 3.4,
        'soldier armor': 3.4, 'soldier helmet': 1.7, 'stalker shoes (recipe 2)': 1.7,
        'soldier boots': 1.7, 'knight boots': 1.7, 'Steel Bar': 0.5, 'Worked Leather': 0.5,
        'Fine Cloth': 0.5, 'Travertine Block': 0.5, 'Pine Planks': 0.5,
        "Adept's Rune": 0.1, 'Infernal Cloth Folds': 2.0, 'Crystallized Spirit': 2.0
    }

    C_max *= 10
    for name in masses:
        masses[name] = int(10 * masses[name])

    recipes = {
        'double bladed staff': {'Steel Bar': 12, 'Worked Leather': 20, "Adept's Rune": 384},
        'dual sword': {'Steel Bar': 20, 'Worked Leather': 12, "Adept's Rune": 384},
        'fiend robe': {'Fine Cloth': 16, "Adept's Rune": 192, 'Infernal Cloth Folds': 1},
        'soldier armor': {'Steel Bar': 16, "Adept's Rune": 192},
        'soldier helmet': {'Steel Bar': 8, "Adept's Rune": 96},
        'stalker shoes (recipe 2)': {'Worked Leather': 8, "Adept's Rune": 96, 'Crystallized Spirit': 1},
        'soldier boots': {'Steel Bar': 8, "Adept's Rune": 96},
        'knight boots': {'Steel Bar': 8, "Adept's Rune": 96}
    }

    # Lieux d'achat des ressources (cities_selling)
    cities_selling = {
        'Steel Bar': ['Thetford'], 'Worked Leather': ['Martlock'], 'Fine Cloth': ['Lymhurst'],
        'Travertine Block': ['Bridgewatch'], 'Pine Planks': ['Fort Sterling'],
        "Adept's Rune": cities, 'Infernal Cloth Folds': cities, 'Crystallized Spirit': cities
    }

    # Lieux de craft
    cities_crafting = {
        'double bladed staff': ['Martlock'], 'dual sword': ['Lymhurst'], 'fiend robe': ['Fort Sterling'],
        'soldier helmet': ['Fort Sterling'],
        'stalker shoes (recipe 2)': ['Lymhurst'], 'soldier boots': ['Martlock'], 'knight boots': ['Martlock']
    }

    # Lieux de vente finale
    cities_buying = {
        'double bladed staff': ['Thetford'], 'dual sword': ['Lymhurst'], 'fiend robe': ['Lymhurst'],
        'soldier helmet': ['Lymhurst'],
        'stalker shoes (recipe 2)': ['Lymhurst'], 'soldier boots': ['Lymhurst'], 'knight boots': ['Fort Sterling']
    }

    # Objectif final (runs)
    target_sales = {
        'double bladed staff': 3, 'dual sword': 11, 'fiend robe': 2,
        'soldier helmet': 20, 'stalker shoes (recipe 2)': 17, 'soldier boots': 67, 'knight boots': 7
    }

    # Matrice des distances (En zones traversées)
    distances = {
        ('Thetford', 'Thetford'): 0, ('Thetford', 'Fort Sterling'): 1, ('Thetford', 'Lymhurst'): 2, ('Thetford', 'Bridgewatch'): 2, ('Thetford', 'Martlock'): 1,
        ('Fort Sterling', 'Thetford'): 1, ('Fort Sterling', 'Fort Sterling'): 0, ('Fort Sterling', 'Lymhurst'): 1, ('Fort Sterling', 'Bridgewatch'): 2, ('Fort Sterling', 'Martlock'): 2,
        ('Lymhurst', 'Thetford'): 2, ('Lymhurst', 'Fort Sterling'): 1, ('Lymhurst', 'Lymhurst'): 0, ('Lymhurst', 'Bridgewatch'): 1, ('Lymhurst', 'Martlock'): 2,
        ('Bridgewatch', 'Thetford'): 2, ('Bridgewatch', 'Fort Sterling'): 2, ('Bridgewatch', 'Lymhurst'): 1, ('Bridgewatch', 'Bridgewatch'): 0, ('Bridgewatch', 'Martlock'): 1,
        ('Martlock', 'Thetford'): 1, ('Martlock', 'Fort Sterling'): 2, ('Martlock', 'Lymhurst'): 2, ('Martlock', 'Bridgewatch'): 1, ('Martlock', 'Martlock'): 0
    }

    # ==========================================
    # VARIABLES DE DÉCISION
    # ==========================================
    inv_var = {}
    buy_var, sell_var, craft_var, consume_var = {}, {}, {}, {}
    city_var = {}

    for t in range(T):
        # 1. Variables de position
        for c in cities:
            city_var[(c, t)] = model.NewBoolVar(f'loc_{c}_{t}')
        model.AddExactlyOne([city_var[(c, t)] for c in cities])

        # Ville de départ imposée par l'utilisateur (t = 0)
        if t == 0:
            if start_city not in cities:
                raise ValueError(f"Ville de départ inconnue : {start_city!r}. Villes valides : {cities}")
            model.Add(city_var[(start_city, t)] == 1)

        # 2. Variables de flux par objet
        for i in items:
            inv_var[(i, t)] = model.NewIntVar(0, MAX_QTY, f'I_{i}_{t}')
            buy_var[(i, t)] = model.NewIntVar(0, MAX_QTY, f'buy_{i}_{t}')
            sell_var[(i, t)] = model.NewIntVar(0, MAX_QTY, f'sell_{i}_{t}')
            craft_var[(i, t)] = model.NewIntVar(0, MAX_QTY, f'craft_{i}_{t}')
            consume_var[(i, t)] = model.NewIntVar(0, MAX_QTY, f'cons_{i}_{t}')

    # ==========================================
    # CONTRAINTES
    # ==========================================
    for t in range(T):
        for i in items:
            I_prev = inv_var[(i, t-1)] if t > 0 else 0

            # 1. Positivité (on ne manipule que ce qu'on possède)
            model.Add(I_prev - sell_var[(i, t)] >= 0)
            model.Add(I_prev - sell_var[(i, t)] - consume_var[(i, t)] >= 0)

            # 2. Consommation exacte via recettes
            total_consumed = sum(
                int(recipes[j].get(i, 0) * SCALE) * craft_var[(j, t)]
                for j in items if j in recipes
            )
            model.Add(consume_var[(i, t)] * SCALE == total_consumed)

            # 3. Conservation du flux
            model.Add(
                inv_var[(i, t)] == I_prev - sell_var[(i, t)] + craft_var[(i, t)] - consume_var[(i, t)] + buy_var[(i, t)]
            )

            # 4. Autorisations géographiques (OnlyEnforceIf)
            for c in cities:
                if c not in cities_selling.get(i, []):
                    model.Add(buy_var[(i, t)] == 0).OnlyEnforceIf(city_var[(c, t)])
                if c not in cities_crafting.get(i, []):
                    model.Add(craft_var[(i, t)] == 0).OnlyEnforceIf(city_var[(c, t)])
                if c not in cities_buying.get(i, []):
                    model.Add(sell_var[(i, t)] == 0).OnlyEnforceIf(city_var[(c, t)])

        # 5. Poids (Vente -> Craft -> Achat)
        I_prev_t = {i: (inv_var[(i, t-1)] if t > 0 else 0) for i in items}

        model.Add(sum((I_prev_t[i] - sell_var[(i, t)]) * masses[i] for i in items) <= C_max)
        model.Add(sum((I_prev_t[i] - sell_var[(i, t)] + craft_var[(i, t)] - consume_var[(i, t)]) * masses[i] for i in items) <= C_max)
        model.Add(sum(inv_var[(i, t)] * masses[i] for i in items) <= C_max)

    # 6. Objectif final : Atteindre les ventes demandées
    for i, target in target_sales.items():
        model.Add(sum(sell_var[(i, t)] for t in range(T)) >= target)

    # 7. Routage et Fonction Objectif (Minimiser la distance)
    route_costs = []
    for t in range(T - 1):
        for o in cities:
            for d in cities:
                # Variable de transition o -> d
                trans = model.NewBoolVar(f't_{o}_{d}_{t}')
                # Astuce mathématique : Si loc(o,t) et loc(d,t+1) sont vrais (1+1=2), trans doit valoir 1
                model.Add(trans >= city_var[(o, t)] + city_var[(d, t+1)] - 1)
                route_costs.append(trans * distances[(o, d)])

    # On ajoute la somme de tous les achats
    total_purchases = sum(buy_var[(i, t)] for i in items for t in range(T))

    # On donne un poids énorme (ex: 1000) à la distance pour que le trajet reste
    # le critère n°1, et un poids faible (1) aux achats pour qu'à trajet égal,
    # il n'achète que le strict minimum.
    model.Minimize(sum(route_costs) * 1000 + total_purchases)

    # ==========================================
    # RÉSOLUTION
    # ==========================================
    solver = cp_model.CpSolver()

    # Multithreading : CP-SAT lance plusieurs stratégies de recherche en parallèle
    # (LNS, portfolio de branchements, etc.) et garde la meilleure. Sur un modèle
    # combinatoire comme celui-ci, ça accélère nettement la résolution.
    solver.parameters.num_search_workers = 8

    # Limite de temps par horizon T, pour garder quelque chose d'opérationnel
    # même si le solveur n'a pas fini de prouver l'optimalité.
    solver.parameters.max_time_in_seconds = 30.0

    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f"\n✅ SOLUTION TROUVÉE EN {T} ÉTAPES ! (Coût distance: {solver.ObjectiveValue() / 1000})")
        print("-" * 50)

        for t in range(T):
            # Trouver la ville actuelle
            current_city = next(c for c in cities if solver.Value(city_var[(c, t)]) == 1)
            print(f"ÉTAPE {t} :📍 {current_city}")

            for i in items:
                b = solver.Value(buy_var[(i, t)])
                c = solver.Value(craft_var[(i, t)])
                s = solver.Value(sell_var[(i, t)])
                inv = solver.Value(inv_var[(i, t)])

                if s > 0: print(f"  💰 Vente de {s} {i}")
                if c > 0: print(f"  🔨 Craft de {c} {i}")
                if b > 0: print(f"  🛒 Achat de {b} {i}")

            # Affichage de l'inventaire
            current_inv = {i: solver.Value(inv_var[(i, t)]) for i in items if solver.Value(inv_var[(i, t)]) > 0}
            poids = sum(solver.Value(inv_var[(i, t)]) * masses[i] for i in items)
            print(f"  🎒 Sac: {current_inv} (Poids: {poids * 0.1}/{C_max * 0.1}kg)\n")
        return True
    else:
        return False

# ==========================================
# RECHERCHE ITÉRATIVE (Iterative Deepening)
# ==========================================
if __name__ == "__main__":
    print("Démarrage du solveur d'itinéraire Albion...")


    START_CITY = 'Thetford'  # Renseigne ici la ville de départ souhaitée

    # On teste de 1 à 6 étapes maximum pour trouver le chemin le plus court
    for horizon in range(1, 60):
        print(f"Test avec {horizon} étapes...")
        if solve_albion_route(horizon, START_CITY):
            break
    else:
        print("\n❌ Impossible de trouver une route. Vérifie que la capacité de poids permet de transporter les ressources nécessaires.")