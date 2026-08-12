from ortools.sat.python import cp_model

def solve_albion_route(T):
    model = cp_model.CpModel()

    # ==========================================
    # DONNÉES DU PROBLÈME (Mock Data)
    # ==========================================
    cities = ['Martlock', 'FortSterling', 'Caerleon']
    items = ['Wood', 'Plank', 'Bow']
    
    C_max = 50  # Capacité maximale de poids
    MAX_QTY = 100
    SCALE = 1000

    masses = {'Wood': 2, 'Plank': 1, 'Bow': 3}
    
    # Recettes : {Produit: {Ressource: Qté}}
    recipes = {
        'Plank': {'Wood': 2},  # 2 Wood -> 1 Plank
        'Bow': {'Plank': 3}    # 3 Plank -> 1 Bow
    }

    # Lieux autorisés
    cities_selling = {'Wood': ['Martlock']}
    cities_crafting = {'Plank': ['FortSterling'], 'Bow': ['FortSterling']}
    cities_buying = {'Bow': ['Caerleon']} # Les villes où on peut VENDRE nos produits finis

    # Distances (symétriques ici, mais peuvent être asymétriques)
    distances = {
        ('Martlock', 'FortSterling'): 15, ('FortSterling', 'Martlock'): 15,
        ('Martlock', 'Caerleon'): 30, ('Caerleon', 'Martlock'): 30,
        ('FortSterling', 'Caerleon'): 10, ('Caerleon', 'FortSterling'): 10,
        ('Martlock', 'Martlock'): 0, ('FortSterling', 'FortSterling'): 0, ('Caerleon', 'Caerleon'): 0
    }

    # Objectif final : Quantités à avoir vendues à la toute fin
    target_sales = {'Bow': 2}

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
        model.Add(sum((inv_var[(i, t-1)] if t > 0 else 0 - sell_var[(i, t)]) * masses[i] for i in items) <= C_max)
        model.Add(sum((inv_var[(i, t-1)] if t > 0 else 0 - sell_var[(i, t)] + craft_var[(i, t)] - consume_var[(i, t)]) * masses[i] for i in items) <= C_max)
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
                
                if b > 0: print(f"  🛒 Achat de {b} {i}")
                if c > 0: print(f"  🔨 Craft de {c} {i}")
                if s > 0: print(f"  💰 Vente de {s} {i}")
            
            # Affichage de l'inventaire
            current_inv = {i: solver.Value(inv_var[(i, t)]) for i in items if solver.Value(inv_var[(i, t)]) > 0}
            poids = sum(solver.Value(inv_var[(i, t)]) * masses[i] for i in items)
            print(f"  🎒 Sac: {current_inv} (Poids: {poids}/{C_max}kg)\n")
        return True
    else:
        return False

# ==========================================
# RECHERCHE ITÉRATIVE (Iterative Deepening)
# ==========================================
if __name__ == "__main__":
    print("Démarrage du solveur d'itinéraire Albion...")
    # On teste de 1 à 6 étapes maximum pour trouver le chemin le plus court
    for horizon in range(1, 7):
        print(f"Test avec {horizon} étapes...")
        if solve_albion_route(horizon):
            break
    else:
        print("\n❌ Impossible de trouver une route. Vérifie que la capacité de poids permet de transporter les ressources nécessaires.")