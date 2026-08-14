from market_data_fetcher import fetch_market_prices
from item_database import build_item_database, Item
import statistics

def get_bonus_city(item: Item) -> str:
    cat = item.category.lower()
    if any(x in cat for x in ["quarterstaff", "axe", "froststaff", "plateshoes", "offhand"]): return "Martlock"
    if any(x in cat for x in ["sword", "bow", "arcanestaff", "leatherhelmet", "leathershoes"]): return "Lymhurst"
    if any(x in cat for x in ["hammer", "spear", "holystaff", "platehelmet", "clotharmor"]): return "Fort Sterling"
    if any(x in cat for x in ["crossbow", "dagger", "cursedstaff", "platearmor", "clothshoes"]): return "Bridgewatch"
    if any(x in cat for x in ["mace", "naturestaff", "firestaff", "leatherarmor", "clothhelmet"]): return "Thetford"
    return "Thetford"

def analyze_crafting_profitability(
    target_base_ids: list,
    has_premium: bool = False,
    target_market_share: float = 0.10,
    station_fee_estimate: int = 1000,
    target_tier: int = 4, 
    target_enchantment: int = 1
):
    db = build_item_database()
    cities = ['Thetford', 'Fort Sterling', 'Lymhurst', 'Bridgewatch', 'Martlock']
    
    # On récupère uniquement les objets demandés qui existent dans la base
    target_items = [db[b_id] for b_id in target_base_ids if b_id in db]

    # --- PARAMÈTRES ÉCONOMIQUES DYNAMIQUES ---
    RRR_BONUS = 0.248
    MARKET_TAX = 0.065 if has_premium else 0.105 

    print(f"\nPréparation de l'analyse pour le Tier {target_tier}.{target_enchantment}...")
    api_ids_to_fetch = set()
    
    for item in target_items:
        api_ids_to_fetch.add(item.get_id(target_tier, target_enchantment))
        for method, recipe in item.get_recipes(target_tier, target_enchantment).items():
            for res_id in recipe.keys():
                api_ids_to_fetch.add(res_id)

    print(f"Interrogation de l'API pour {len(api_ids_to_fetch)} objets de marché...")
    buying_prices, selling_prices, selling_volumes = fetch_market_prices(list(api_ids_to_fetch), cities)

    profitable_items = []
    print("\n==========================================")
    print("ANALYSE DES MARGES DE CRAFT")
    print("==========================================")
    
    for item in target_items:
        item_id = item.get_id(target_tier, target_enchantment)
        
        sell_options = selling_prices.get(item_id, {})
        if not sell_options:
            continue
            
        # Filtre anti-manipulation (Médiane)
        if len(sell_options) >= 3:
            med_price = statistics.median(sell_options.values())
            valid_sells = {city: p for city, p in sell_options.items() if p <= med_price * 1.5}
            if not valid_sells: 
                valid_sells = sell_options
        else:
            valid_sells = sell_options
            
        best_sell_city = max(valid_sells, key=valid_sells.get)
        sell_price = valid_sells[best_sell_city]
        
        # Calcul de la quantité basée sur la part de marché ciblée
        daily_volume = selling_volumes.get(item_id, {}).get(best_sell_city, 1)
        target_qty = int(daily_volume * target_market_share)
        target_qty = max(1, min(target_qty, 30)) # On limite entre 1 et 30 par défaut
        
        best_craft_city = get_bonus_city(item)

        best_net_profit = -999999
        best_method = ""
        best_cost = 0
        
        for method, recipe in item.get_recipes(target_tier, target_enchantment).items():
            base_materials_cost = 0
            enchant_materials_cost = 0
            missing_resource = False
            
            for res_id, qty in recipe.items():
                res_options = buying_prices.get(res_id, {})
                if not res_options:
                    missing_resource = True
                    break
                
                best_buy_price = min(res_options.values())
                
                if any(x in res_id for x in ["RUNE", "SOUL", "RELIC", "SHARD_AVALONIAN"]):
                    enchant_materials_cost += (qty * best_buy_price)
                else:
                    base_materials_cost += (qty * best_buy_price)

            if missing_resource:
                continue

            effective_cost = (base_materials_cost * (1 - RRR_BONUS)) + enchant_materials_cost
            market_tax_cost = sell_price * MARKET_TAX
            total_cost = effective_cost + market_tax_cost + station_fee_estimate
            net_profit = sell_price - total_cost
            
            if net_profit > best_net_profit:
                best_net_profit = net_profit
                best_method = method
                best_cost = total_cost

        if best_net_profit == -999999:
            continue
            
        status = "✅ RENTABLE" if best_net_profit > 0 else "❌ PERTE"
        method_str = "Forge (Matériaux .1)" if best_method == "craft_station" else "Forge (.0) + Runes"
        
        name_fr = item.get_name(target_tier, "fr")
        name_en = item.get_name(target_tier, "en")
        print(f"\n{status} : {name_fr.upper()} ({name_en})")
        print(f"  Méthode optimale: {method_str}")
        print(f"  Ville de Craft  : {best_craft_city} (RRR: {RRR_BONUS*100:.1f}%)")
        print(f"  Ville de Vente  : {best_sell_city} à {sell_price:,} Silver (Vol: {daily_volume}/j)")
        print(f"  Quantité Cible  : {target_qty} unités (Part de marché: {target_market_share*100}%)")
        print(f"  Coût total estimé : {int(best_cost):,} Silver")
        print(f"  Marge Nette     : {int(best_net_profit):,} Silver par unité")

        if best_net_profit > 0:
            profitable_items.append({
                'base_id': item.base_id,
                'name_fr': name_fr,
                'name_en': name_en,
                'quantity': target_qty,
                'profit': int(best_net_profit),
                'method': best_method,
                'craft_city': best_craft_city,
                'sell_city': best_sell_city
            })

    return profitable_items