import statistics
from market_data_fetcher import fetch_market_prices
from item_database import build_item_database, Item

def get_bonus_city(item: Item) -> str:
    cat = item.category.lower()
    if any(x in cat for x in ["quarterstaff", "axe", "froststaff", "plateshoes", "offhand"]): return "Martlock"
    if any(x in cat for x in ["sword", "bow", "arcanestaff", "leatherhelmet", "leathershoes"]): return "Lymhurst"
    if any(x in cat for x in ["hammer", "spear", "holystaff", "platehelmet", "clotharmor"]): return "Fort Sterling"
    if any(x in cat for x in ["crossbow", "dagger", "cursedstaff", "platearmor", "clothshoes"]): return "Bridgewatch"
    if any(x in cat for x in ["mace", "naturestaff", "firestaff", "leatherarmor", "clothhelmet"]): return "Thetford"
    return "Thetford"

def collect_required_api_ids(base_id: str, tier: int, enchantment: int, db: dict, api_ids_set: set):
    full_id = f"T{tier}_{base_id}" + (f"@{enchantment}" if enchantment > 0 else "")
    if full_id in api_ids_set: return
    api_ids_set.add(full_id)
    
    if base_id not in db: return
    item = db[base_id]
    
    for res_base in item.base_recipe.keys():
        collect_required_api_ids(res_base, tier, enchantment, db, api_ids_set)
        
    for res_base in item.static_recipe.keys():
        sub_ench = enchantment if res_base in db else 0
        collect_required_api_ids(res_base, tier, sub_ench, db, api_ids_set)
        
    if enchantment > 0:
        collect_required_api_ids(base_id, tier, enchantment - 1, db, api_ids_set)
        ench_mat = item._get_enchantment_material_id(tier)
        api_ids_set.add(f"T{tier}_{ench_mat}")

# NOUVEAU : Ajout de l'argument slippage
def get_optimal_flat_recipe(base_id: str, tier: int, enchantment: int, db: dict, buying_prices: dict, RRR_BONUS: float, STATION_FEE: int, target_base_id: str, slippage: float, depth=0):
    if depth > 10: return 9999999, 9999999, {}, "Erreur Boucle"
    item_full_id = f"T{tier}_{base_id}" + (f"@{enchantment}" if enchantment > 0 else "")
    
    # --- OPTION 1 : ACHAT DIRECT ---
    if base_id != target_base_id:
        options = buying_prices.get(item_full_id, {})
        if options:
            best_city = min(options, key=options.get)
            # APPLICATION DU SLIPPAGE SUR LE PRIX D'ACHAT DES RESSOURCES
            market_price = int(options[best_city] * (1.0 + slippage))
        else:
            best_city = "Thetford"
            market_price = 9999999
    else:
        market_price = 9999999
        best_city = "Thetford"
        
    best_cost = market_price
    best_invest = market_price
    best_recipe = {item_full_id: {'qty': 1, 'buy_city': best_city, 'unit_price': market_price}}
    best_method = "Achat direct"
    
    if base_id not in db:
        return best_cost, best_invest, best_recipe, best_method
        
    item = db[base_id]
    
    # --- OPTION 2 : FORGE À LA STATION ---
    if item.base_recipe or item.static_recipe:
        craft_cost, craft_invest = 0, 0
        flat_recipe = {}
        possible = True
        
        for res_base, qty in item.base_recipe.items():
            # PASSAGE DU SLIPPAGE DANS LA RÉCURSION
            c, inv, rec, _ = get_optimal_flat_recipe(res_base, tier, enchantment, db, buying_prices, RRR_BONUS, STATION_FEE, target_base_id, slippage, depth+1)
            if c >= 9999999: possible = False
            
            eff_qty = qty * (1 - RRR_BONUS)
            craft_cost += c * eff_qty
            craft_invest += inv * qty
            for k, v in rec.items():
                if k not in flat_recipe:
                    flat_recipe[k] = {'qty': 0, 'buy_city': v['buy_city'], 'unit_price': v['unit_price']}
                flat_recipe[k]['qty'] += v['qty'] * qty
                
        for res_base, qty in item.static_recipe.items():
            sub_ench = enchantment if res_base in db else 0 
            c, inv, rec, _ = get_optimal_flat_recipe(res_base, tier, sub_ench, db, buying_prices, RRR_BONUS, STATION_FEE, target_base_id, slippage, depth+1)
            if c >= 9999999: possible = False
            
            craft_cost += c * qty
            craft_invest += inv * qty
            for k, v in rec.items():
                if k not in flat_recipe:
                    flat_recipe[k] = {'qty': 0, 'buy_city': v['buy_city'], 'unit_price': v['unit_price']}
                flat_recipe[k]['qty'] += v['qty'] * qty
                
        if possible:
            total_cost = craft_cost + STATION_FEE
            total_invest = craft_invest + STATION_FEE
            if total_cost < best_cost:
                best_cost = total_cost
                best_invest = total_invest
                best_recipe = flat_recipe
                best_method = "Forge"

    # --- OPTION 3 : ENCHANTEMENT ---
    if enchantment > 0:
        prev_c, prev_inv, prev_rec, _ = get_optimal_flat_recipe(base_id, tier, enchantment - 1, db, buying_prices, RRR_BONUS, STATION_FEE, target_base_id, slippage, depth+1)
        ench_mat = item._get_enchantment_material_id(tier)
        ench_qty = item.get_enchantment_cost()
        
        if ench_qty > 0:
            mat_c, mat_inv, mat_rec, _ = get_optimal_flat_recipe(ench_mat, tier, 0, db, buying_prices, RRR_BONUS, STATION_FEE, target_base_id, slippage, depth+1)
            
            total_cost = prev_c + (mat_c * ench_qty)
            total_invest = prev_inv + (mat_inv * ench_qty)
            
            if prev_c < 9999999 and mat_c < 9999999 and total_cost < best_cost:
                best_cost = total_cost
                best_invest = total_invest
                
                flat_recipe = {k: {'qty': v['qty'], 'buy_city': v['buy_city'], 'unit_price': v['unit_price']} for k, v in prev_rec.items()}
                for k, v in mat_rec.items():
                    if k not in flat_recipe:
                        flat_recipe[k] = {'qty': 0, 'buy_city': v['buy_city'], 'unit_price': v['unit_price']}
                    flat_recipe[k]['qty'] += v['qty'] * ench_qty
                    
                best_recipe = flat_recipe
                best_method = f"Forge (.0) + Enchantement (.{enchantment})"
                
    return best_cost, best_invest, best_recipe, best_method

def analyze_crafting_profitability(
    target_pool: list, 
    has_premium: bool = False,
    target_market_share: float = 0.10,
    station_fee_estimate: int = 1000,
    lang: str = "fr",
    slippage: float = 0.10 # NOUVEAU: Par défaut 10%
):
    db = build_item_database()
    cities = ['Thetford', 'Fort Sterling', 'Lymhurst', 'Bridgewatch', 'Martlock']
    
    RRR_BONUS = 0.248
    MARKET_TAX = 0.065 if has_premium else 0.105 

    api_ids_to_fetch = set()
    for target in target_pool:
        if target['base_id'] in db:
            collect_required_api_ids(target['base_id'], target['tier'], target['enchantment'], db, api_ids_to_fetch)

    buying_prices, selling_prices, selling_volumes = fetch_market_prices(list(api_ids_to_fetch), cities)

    profitable_items = []
    
    for target in target_pool:
        base_id = target['base_id']
        if base_id not in db: continue
        
        tier = target['tier']
        enchantment = target['enchantment']
        item = db[base_id]
        
        item_id = item.get_id(tier, enchantment)
        
        sell_options = selling_prices.get(item_id, {})
        if not sell_options: continue
            
        if len(sell_options) >= 3:
            med_price = statistics.median(sell_options.values())
            valid_sells = {c: p for c, p in sell_options.items() if p <= med_price * 1.5}
            if not valid_sells: valid_sells = sell_options
        else:
            valid_sells = sell_options
            
        best_sell_city = max(valid_sells, key=valid_sells.get)
        # APPLICATION DU SLIPPAGE SUR LE PRIX DE VENTE (on gagne moins que prévu)
        sell_price = int(valid_sells[best_sell_city] * (1.0 - slippage))
        
        daily_vol = selling_volumes.get(item_id, {}).get(best_sell_city, 1)
        target_qty = max(1, min(int(daily_vol * target_market_share), 30))
        
        best_craft_city = get_bonus_city(item)

        # On transmet le slippage pour impacter le prix d'achat des ressources
        best_cost, best_invest, flat_recipe, method = get_optimal_flat_recipe(
            base_id, tier, enchantment, db, buying_prices, RRR_BONUS, station_fee_estimate, target_base_id=base_id, slippage=slippage
        )

        if best_cost >= 9999999: continue

        market_tax_cost = sell_price * MARKET_TAX
        net_profit = sell_price - best_cost - market_tax_cost
        upfront_investment = best_invest + (sell_price * 0.025)

        if net_profit > 0:
            profitable_items.append({
                'item_id': item_id,
                'name_display': f"{item.get_name(tier, lang)} ({item_id})",
                'quantity': target_qty,
                'profit': int(net_profit),
                'upfront_cost': int(upfront_investment),
                'sell_price': int(sell_price), 
                'method': method,
                'flat_recipe': flat_recipe,
                'craft_city': best_craft_city,
                'sell_city': best_sell_city
            })

    return profitable_items