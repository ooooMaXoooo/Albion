from ortools.sat.python import cp_model
from item_database import build_item_database

def solve_albion_route(target_sales: dict, start_city: str, payload_kg: float):
    print("Chargement de la base de données Albion...")
    db = build_item_database()
    cities = ['Thetford', 'Fort Sterling', 'Lymhurst', 'Bridgewatch', 'Martlock']
    
    # ==========================================
    # 1. GÉNÉRATION DYNAMIQUE DES DONNÉES
    # ==========================================
    items_set = set(target_sales.keys())
    recipes = {}
    cities_crafting = {}
    cities_selling = {}
    
    for product_id, info in target_sales.items():
        cities_crafting[product_id] = [info['craft_city']]
        cities_selling[product_id] = [info['sell_city']]
        
        item_obj = db.get(product_id)
        if not item_obj:
            print(f"⚠️ Objet inconnu ignoré: {product_id}")
            continue
            
        recipe = {}
        for mat_id, qty in item_obj.base_recipe.items():
            recipe[mat_id] = qty
            items_set.add(mat_id)
            
        if item_obj.base_artifact:
            recipe[item_obj.base_artifact] = 1
            items_set.add(item_obj.base_artifact)
            
        if info['method'] == 'energy_manipulator':
            rune_id = "RUNE"
            recipe[rune_id] = item_obj.get_enchantment_cost()
            items_set.add(rune_id)
            
        recipes[product_id] = recipe

    items = list(items_set)
    
    # --- CORRECTION 1 : GESTION DES POIDS ---
    C_max = int(payload_kg * 10)
    masses = {}
    for i in items:
        # On force manuellement le poids des éléments magiques à 0.1 kg
        if i in ["RUNE", "SOUL", "RELIC", "SHARD_AVALONIAN"]:
            mass_kg = 0.1
        elif i in db:
            mass_kg = db[i].mass_kg
        else:
            mass_kg = 0.5
            
        masses[i] = int(mass_kg * 10)
        
    cities_buying_mats = {i: cities for i in items if i not in target_sales}

    distances = {
        ('Thetford', 'Thetford'): 0, ('Thetford', 'Fort Sterling'): 1, ('Thetford', 'Lymhurst'): 2, ('Thetford', 'Bridgewatch'): 2, ('Thetford', 'Martlock'): 1,
        ('Fort Sterling', 'Thetford'): 1, ('Fort Sterling', 'Fort Sterling'): 0, ('Fort Sterling', 'Lymhurst'): 1, ('Fort Sterling', 'Bridgewatch'): 2, ('Fort Sterling', 'Martlock'): 2,
        ('Lymhurst', 'Thetford'): 2, ('Lymhurst', 'Fort Sterling'): 1, ('Lymhurst', 'Lymhurst'): 0, ('Lymhurst', 'Bridgewatch'): 1, ('Lymhurst', 'Martlock'): 2,
        ('Bridgewatch', 'Thetford'): 2, ('Bridgewatch', 'Fort Sterling'): 2, ('Bridgewatch', 'Lymhurst'): 1, ('Bridgewatch', 'Bridgewatch'): 0, ('Bridgewatch', 'Martlock'): 1,
        ('Martlock', 'Thetford'): 1, ('Martlock', 'Fort Sterling'): 2, ('Martlock', 'Lymhurst'): 2, ('Martlock', 'Bridgewatch'): 1, ('Martlock', 'Martlock'): 0
    }

    # ==========================================
    # 2. MOTEUR DE RÉSOLUTION (CP-SAT)
    # ==========================================
    def try_solve_for_horizon(T):
        model = cp_model.CpModel()
        MAX_QTY = 999999
        
        city_var, inv_var, buy_var, sell_var, craft_var, consume_var = {}, {}, {}, {}, {}, {}
        
        for t in range(T):
            for c in cities:
                city_var[(c, t)] = model.NewBoolVar(f'loc_{c}_{t}')
            model.AddExactlyOne([city_var[(c, t)] for c in cities])
            
            if t == 0:
                model.Add(city_var[(start_city, t)] == 1)
                
            for i in items:
                inv_var[(i, t)] = model.NewIntVar(0, MAX_QTY, f'I_{i}_{t}')
                buy_var[(i, t)] = model.NewIntVar(0, MAX_QTY, f'buy_{i}_{t}')
                sell_var[(i, t)] = model.NewIntVar(0, MAX_QTY, f'sell_{i}_{t}')
                craft_var[(i, t)] = model.NewIntVar(0, MAX_QTY, f'craft_{i}_{t}')
                consume_var[(i, t)] = model.NewIntVar(0, MAX_QTY, f'cons_{i}_{t}')

        for t in range(T):
            I_prev_t = {i: (inv_var[(i, t-1)] if t > 0 else 0) for i in items}
            
            for i in items:
                I_prev = I_prev_t[i]
                model.Add(I_prev - sell_var[(i, t)] >= 0)
                model.Add(I_prev - sell_var[(i, t)] - consume_var[(i, t)] >= 0)
                
                total_consumed = sum(int(recipes[j].get(i, 0)) * craft_var[(j, t)] for j in items if j in recipes)
                model.Add(consume_var[(i, t)] == total_consumed)
                
                model.Add(inv_var[(i, t)] == I_prev - sell_var[(i, t)] + craft_var[(i, t)] - consume_var[(i, t)] + buy_var[(i, t)])
                
                allowed_buy = cities_buying_mats.get(i, [])
                allowed_craft = cities_crafting.get(i, [])
                allowed_sell = cities_selling.get(i, [])
                
                for c in cities:
                    if c not in allowed_buy: model.Add(buy_var[(i, t)] == 0).OnlyEnforceIf(city_var[(c, t)])
                    if c not in allowed_craft: model.Add(craft_var[(i, t)] == 0).OnlyEnforceIf(city_var[(c, t)])
                    if c not in allowed_sell: model.Add(sell_var[(i, t)] == 0).OnlyEnforceIf(city_var[(c, t)])

            model.Add(sum((I_prev_t[i] - sell_var[(i, t)]) * masses[i] for i in items) <= C_max)
            model.Add(sum((I_prev_t[i] - sell_var[(i, t)] + craft_var[(i, t)] - consume_var[(i, t)]) * masses[i] for i in items) <= C_max)
            model.Add(sum(inv_var[(i, t)] * masses[i] for i in items) <= C_max)

        for i, info in target_sales.items():
            model.Add(sum(sell_var[(i, t)] for t in range(T)) >= info['quantity'])
            
        route_costs = []
        for t in range(T - 1):
            for o in cities:
                for d in cities:
                    trans = model.NewBoolVar(f't_{o}_{d}_{t}')
                    model.Add(trans >= city_var[(o, t)] + city_var[(d, t+1)] - 1)
                    route_costs.append(trans * distances[(o, d)])
                    
        total_purchases = sum(buy_var[(i, t)] for i in items for t in range(T))
        
        # --- CORRECTION 2 : PROTECTION DU SCORE ---
        # On multiplie par 1 000 000 pour que le nombre de ressources n'impacte pas le score de distance
        model.Minimize(sum(route_costs) * 1_000_000 + total_purchases)
        
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 8
        solver.parameters.max_time_in_seconds = 15.0 
        
        status = solver.Solve(model)
        
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # Affichage correct du nombre de zones
            zones_traversees = int(solver.ObjectiveValue() / 1_000_000)
            print(f"\n✅ ITINÉRAIRE TROUVÉ EN {T} ÉTAPES ! (Zones traversées : {zones_traversees})")
            print("=" * 60)
            
            def get_fr(item_id):
                return db[item_id].get_name(4, 'fr') if item_id in db else item_id
            
            for t in range(T):
                current_city = next(c for c in cities if solver.Value(city_var[(c, t)]) == 1)
                
                actions = []
                for i in items:
                    b = solver.Value(buy_var[(i, t)])
                    c = solver.Value(craft_var[(i, t)])
                    s = solver.Value(sell_var[(i, t)])
                    
                    if b > 0: actions.append(f"🛒 Achat : {b}x {get_fr(i)}")
                    if c > 0: actions.append(f"🔨 Craft : {c}x {get_fr(i)}")
                    if s > 0: actions.append(f"💰 Vente : {s}x {get_fr(i)}")
                
                if t == 0 or actions or t == T-1:
                    print(f"📍 ÉTAPE {t} : {current_city}")
                    for act in actions:
                        print(f"    {act}")
                        
                    # Formatage plus joli du sac (sur plusieurs lignes si beaucoup d'objets)
                    current_inv = {get_fr(i): solver.Value(inv_var[(i, t)]) for i in items if solver.Value(inv_var[(i, t)]) > 0}
                    poids = sum(solver.Value(inv_var[(i, t)]) * masses[i] for i in items) / 10
                    
                    if current_inv:
                        sac_str = ", ".join(f"{k}: {v}" for k, v in current_inv.items())
                        print(f"    🎒 Sac: {{{sac_str}}}")
                        print(f"    ⚖️  Poids: {poids}/{payload_kg}kg\n")
                    else:
                        print(f"    🎒 Sac vide\n")
            return True
        return False

    print("\nLancement du calculateur de route stratégique (Iterative Deepening)...")
    for horizon in range(1, 20):
        print(f"Recherche de route en {horizon} arrêts...")
        if try_solve_for_horizon(horizon):
            return True
        
    print("\n❌ Impossible de trouver une route. Ta monture est probablement trop petite pour transporter toutes les ressources !")
    return False

# ==========================================
# POINT D'ENTRÉE DU SCRIPT
# ==========================================
if __name__ == "__main__":
    # Test avec la sortie extraite de l'analyseur financier (Mets les données que tu avais ici)
    target_sales_mock = {
        '2H_DUALSWORD': {  
            'quantity': 10,
            'profit_per_unit': 9753,
            'method': 'energy_manipulator',
            'craft_city': 'Lymhurst',
            'sell_city': 'Fort Sterling'
        },
        '2H_DOUBLEBLADEDSTAFF': {  
            'quantity': 10,
            'profit_per_unit': 11549,
            'method': 'energy_manipulator',
            'craft_city': 'Martlock',
            'sell_city': 'Bridgewatch'
        },
        'ARMOR_CLOTH_HELL': {  
            'quantity': 10,
            'profit_per_unit': 18678,
            'method': 'energy_manipulator',
            'craft_city': 'Thetford',
            'sell_city': 'Fort Sterling'
        },
    }
    
    solve_albion_route(target_sales_mock, start_city='Martlock', payload_kg=1200.0)