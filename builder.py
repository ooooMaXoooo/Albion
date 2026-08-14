from market_analyst import analyze_crafting_profitability
from logistic_solver import solve_albion_route

def main():
    print("==========================================")
    print("🛡️ ALBION ONLINE - TRADING EMPIRE V1.1 🛡️")
    print("==========================================")
    
    # ---------------------------------------------------------
    # PARAMÈTRES GLOBAUX (Interface utilisateur "Console")
    # ---------------------------------------------------------
    # Profil du joueur
    HAS_PREMIUM = False
    START_CITY = 'Martlock'      
    MOUNT_CAPACITY_KG = 1200.0   
    
    # Paramètres Économiques
    TARGET_MARKET_SHARE = 0.10   # 10% des ventes journalières
    STATION_FEE = 1000           # Frais de la station de craft
    MAX_ITEMS_TO_CRAFT = 5       # Nombre max d'objets différents à produire
    TARGET_TIER = 4
    TARGET_ENCHANTMENT = 1
    
    # Liste des objets à analyser (Ce qui sera coché dans Streamlit)
    TARGET_ITEMS = [
        "2H_DUALSWORD", "2H_DOUBLEBLADEDSTAFF", "ARMOR_CLOTH_HELL", 
        "HEAD_PLATE_SET1", "SHOES_LEATHER_MORGANA", "SHOES_PLATE_SET1", "SHOES_PLATE_SET2"
    ]
    # ---------------------------------------------------------

    # ÉTAPE 1 : Le Cerveau Financier
    print(f"\n[1/2] Lancement de l'analyse financière (Tier {TARGET_TIER}.{TARGET_ENCHANTMENT})...")
    profitable_items = analyze_crafting_profitability(
        target_base_ids=TARGET_ITEMS,
        has_premium=HAS_PREMIUM,
        target_market_share=TARGET_MARKET_SHARE,
        station_fee_estimate=STATION_FEE,
        target_tier=TARGET_TIER,
        target_enchantment=TARGET_ENCHANTMENT
    )
    
    if not profitable_items:
        print("\n❌ Aucun objet n'est rentable avec les conditions actuelles du marché.")
        return

    # Tri par profit global (Marge unitaire * Quantité) pour remplir le sac des meilleurs plans
    profitable_items = sorted(
        profitable_items, 
        key=lambda x: (x['profit'] * x['quantity']), 
        reverse=True
    )[:MAX_ITEMS_TO_CRAFT]
    
    target_sales = {}
    total_expected_profit = 0
    
    for item in profitable_items:
        target_sales[item['base_id']] = {
            'quantity': item['quantity'],
            'profit_per_unit': item['profit'],
            'method': item['method'],
            'craft_city': item['craft_city'],
            'sell_city': item['sell_city']
        }
        total_expected_profit += (item['quantity'] * item['profit'])
        
    print("\n==========================================")
    print("BILAN FINANCIER")
    print("==========================================")
    print(f">> {len(target_sales)} objets ultra-rentables sélectionnés.")
    print(f">> Marge totale estimée de l'expédition : {total_expected_profit:,} Silver 🪙")

    # ÉTAPE 2 : Le Cerveau Logistique
    print(f"\n[2/2] Transmission au solveur CP-SAT OR-Tools...")
    print(f"      Ville de départ : {START_CITY} | Monture : {MOUNT_CAPACITY_KG} kg")
    print("-" * 42)
    
    success = solve_albion_route(
        target_sales=target_sales, 
        start_city=START_CITY, 
        payload_kg=MOUNT_CAPACITY_KG
    )
    
    if not success:
        print("\n⚠️ ALERTE LOGISTIQUE : Le solveur n'a pas pu trouver de route.")
        print("   Raison probable : Ta monture est trop petite pour porter toutes les ressources.")
        print("   Solution : Augmente 'MOUNT_CAPACITY_KG' ou réduis 'TARGET_MARKET_SHARE'.")

if __name__ == "__main__":
    main()