from ortools.sat.python import cp_model
from item_database import build_item_database

def solve_albion_route(target_sales: dict, start_city: str, payload_kg: float, max_steps: int = 5, max_budget: int = 10_000_000, lang: str = "fr"):
    db = build_item_database()
    cities = ['Thetford', 'Fort Sterling', 'Lymhurst', 'Bridgewatch', 'Martlock']
    
    # 1. Identification de tous les objets et de LEUR VILLE D'ACHAT CIBLE
    items_set = set(target_sales.keys())
    item_buy_cities = {}
    
    for info in target_sales.values():
        for mat_id, mat_data in info['flat_recipe'].items():
            items_set.add(mat_id)
            item_buy_cities[mat_id] = mat_data['buy_city']
            
    items = list(items_set)
    
    # 2. Poids des objets (Extraction dynamique du Tier)
    C_max = int(payload_kg * 10)
    masses = {}
    
    for i in items:
        if any(x in i for x in ["RUNE", "SOUL", "RELIC", "SHARD", "TOKEN"]): 
            mass_kg = 0.1
        else:
            item_tier = 4 # Tier par défaut
            if i.startswith('T') and '_' in i:
                try:
                    item_tier = int(i.split('_')[0][1:])
                except ValueError:
                    pass
            
            base_id = i.split('@')[0]
            if base_id.startswith('T'): base_id = base_id.split('_', 1)[1]
            
            if base_id in db: 
                mass_kg = db[base_id].get_mass(item_tier)
            else: 
                mass_kg = 1.0 
                
        masses[i] = int(mass_kg * 10)
        
    distances = {
        ('Thetford', 'Thetford'): 0, ('Thetford', 'Fort Sterling'): 1, ('Thetford', 'Lymhurst'): 2, ('Thetford', 'Bridgewatch'): 2, ('Thetford', 'Martlock'): 1,
        ('Fort Sterling', 'Thetford'): 1, ('Fort Sterling', 'Fort Sterling'): 0, ('Fort Sterling', 'Lymhurst'): 1, ('Fort Sterling', 'Bridgewatch'): 2, ('Fort Sterling', 'Martlock'): 2,
        ('Lymhurst', 'Thetford'): 2, ('Lymhurst', 'Fort Sterling'): 1, ('Lymhurst', 'Lymhurst'): 0, ('Lymhurst', 'Bridgewatch'): 1, ('Lymhurst', 'Martlock'): 2,
        ('Bridgewatch', 'Thetford'): 2, ('Bridgewatch', 'Fort Sterling'): 2, ('Bridgewatch', 'Lymhurst'): 1, ('Bridgewatch', 'Bridgewatch'): 0, ('Bridgewatch', 'Martlock'): 1,
        ('Martlock', 'Thetford'): 1, ('Martlock', 'Fort Sterling'): 2, ('Martlock', 'Lymhurst'): 2, ('Martlock', 'Bridgewatch'): 1, ('Martlock', 'Martlock'): 0
    }

    # ==========================================
    # MOTEUR DE RÉSOLUTION (CP-SAT)
    # ==========================================
    model = cp_model.CpModel()
    T = max_steps
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

    sold_qty_var = {}
    for i, info in target_sales.items():
        sold_qty_var[i] = model.NewIntVar(0, info['quantity'], f'tot_sold_{i}')

    for t in range(T):
        I_prev_t = {i: (inv_var[(i, t-1)] if t > 0 else 0) for i in items}
        
        for i in items:
            total_consumed = sum(
                info['flat_recipe'].get(i, {}).get('qty', 0) * craft_var[(product_id, t)] 
                for product_id, info in target_sales.items() if i in info['flat_recipe']
            )
            model.Add(consume_var[(i, t)] == total_consumed)
            
            model.Add(I_prev_t[i] - sell_var[(i, t)] >= 0)
            model.Add(I_prev_t[i] - sell_var[(i, t)] - consume_var[(i, t)] >= 0)
            model.Add(inv_var[(i, t)] == I_prev_t[i] - sell_var[(i, t)] + craft_var[(i, t)] - consume_var[(i, t)] + buy_var[(i, t)])
            
            if i in target_sales:
                craft_c = target_sales[i]['craft_city']
                sell_c = target_sales[i]['sell_city']
                
                model.Add(buy_var[(i, t)] == 0) # Anti-triche : Interdiction d'acheter l'objet fini
                
                for c in cities:
                    if c != craft_c: model.Add(craft_var[(i, t)] == 0).OnlyEnforceIf(city_var[(c, t)])
                    if c != sell_c: model.Add(sell_var[(i, t)] == 0).OnlyEnforceIf(city_var[(c, t)])
            else:
                buy_c = item_buy_cities.get(i, cities[0])
                for c in cities:
                    model.Add(craft_var[(i, t)] == 0)
                    model.Add(sell_var[(i, t)] == 0)
                    if c != buy_c: 
                        model.Add(buy_var[(i, t)] == 0).OnlyEnforceIf(city_var[(c, t)])

        model.Add(sum((I_prev_t[i] - sell_var[(i, t)]) * masses[i] for i in items) <= C_max)
        model.Add(sum((I_prev_t[i] - sell_var[(i, t)] + craft_var[(i, t)] - consume_var[(i, t)]) * masses[i] for i in items) <= C_max)
        model.Add(sum(inv_var[(i, t)] * masses[i] for i in items) <= C_max)

    for i in target_sales.keys():
        total_sold = sum(sell_var[(i, t)] for t in range(T))
        total_crafted = sum(craft_var[(i, t)] for t in range(T))
        
        model.Add(total_sold == sold_qty_var[i])
        model.Add(total_sold <= total_crafted) # Anti-Arbitrage
        
    model.Add(sum(sold_qty_var[i] * info['upfront_cost'] for i, info in target_sales.items()) <= max_budget)

    route_costs = []
    for t in range(T - 1):
        for o in cities:
            for d in cities:
                trans = model.NewBoolVar(f't_{o}_{d}_{t}')
                model.Add(trans >= city_var[(o, t)] + city_var[(d, t+1)] - 1)
                route_costs.append(trans * distances[(o, d)])
                
    total_purchases = sum(buy_var[(i, t)] for i in items for t in range(T))
    total_profit_expr = sum(sold_qty_var[i] * info['profit_per_unit'] for i, info in target_sales.items())
    
    model.Maximize(total_profit_expr * 1000 - sum(route_costs) * 10 - total_purchases)
    
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 8
    solver.parameters.max_time_in_seconds = 20.0
    
    status = solver.Solve(model)
    
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        actual_profit = sum(solver.Value(sold_qty_var[i]) * info['profit_per_unit'] for i, info in target_sales.items())
        actual_invest = sum(solver.Value(sold_qty_var[i]) * info['upfront_cost'] for i, info in target_sales.items())
        
        print(f"\n✅ PLAN OPTIMAL TROUVÉ ! (Marge: {actual_profit:,} 🪙 | Investissement: {actual_invest:,} 🪙)")
        print("=" * 60)
        
        def format_name(item_id):
            item_tier = 4
            if item_id.startswith('T') and '_' in item_id:
                try: item_tier = int(item_id.split('_')[0][1:])
                except ValueError: pass

            if "QUESTITEM" in item_id: name = "Sigil Royal" if lang == 'fr' else "Royal Sigil"
            elif "RUNE" in item_id: name = "Runes" if lang == 'fr' else "Runes"
            elif "SOUL" in item_id: name = "Âmes" if lang == 'fr' else "Souls"
            elif "RELIC" in item_id: name = "Reliques" if lang == 'fr' else "Relics"
            else:
                base_id = item_id.split('_', 1)[1].split('@')[0] if '_' in item_id else item_id
                name = db[base_id].get_name(item_tier, lang) if base_id in db else item_id

            if '@' in item_id: name += f" .{item_id.split('@')[1]}"
            return f"{name} ({item_id})"

        for t in range(T):
            current_city = next(c for c in cities if solver.Value(city_var[(c, t)]) == 1)
            actions = []
            for i in items:
                b = solver.Value(buy_var[(i, t)])
                c = solver.Value(craft_var[(i, t)])
                s = solver.Value(sell_var[(i, t)])
                
                if b > 0 or c > 0 or s > 0:
                    buy_price = 0
                    for info in target_sales.values():
                        if i in info['flat_recipe']:
                            buy_price = info['flat_recipe'][i]['unit_price']
                            break
                    
                    sell_price = target_sales[i]['sell_price'] if i in target_sales else 0
                    
                    if b > 0: actions.append(f"🛒 Achat : {b}x {format_name(i)} (à ~{buy_price:,} 🪙/u)")
                    if c > 0: actions.append(f"🔨 Craft : {c}x {format_name(i)}")
                    if s > 0: actions.append(f"💰 Vente : {s}x {format_name(i)} (à ~{sell_price:,} 🪙/u)")
            
            print(f"📍 ÉTAPE {t} : {current_city}")
            for act in actions: print(f"    {act}")
            
            current_inv = {format_name(i): solver.Value(inv_var[(i, t)]) for i in items if solver.Value(inv_var[(i, t)]) > 0}
            poids = sum(solver.Value(inv_var[(i, t)]) * masses[i] for i in items) / 10
            
            if current_inv:
                sac_display = ", ".join(f"{v}x {k}" for k, v in list(current_inv.items())[:3])
                if len(current_inv) > 3: sac_display += " ..."
                print(f"    🎒 Sac: {sac_display}")
                print(f"    ⚖️  Poids: {poids}/{payload_kg}kg\n")
            else:
                print(f"    🎒 Sac vide\n")
        return True
        
    print("\n❌ Aucun profit réalisable (ou monture trop petite / budget trop faible).")
    return False