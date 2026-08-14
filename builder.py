from market_analyst import analyze_crafting_profitability
from logistic_solver import solve_albion_route

def main():
    print("==========================================")
    print("🛡️ ALBION ONLINE - TRADING EMPIRE V2.0 🛡️")
    print("==========================================")
    
    # ---------------------------------------------------------
    # PARAMÈTRES GLOBAUX
    # ---------------------------------------------------------
    HAS_PREMIUM = False
    START_CITY = 'Martlock'      
    MOUNT_CAPACITY_KG = 1200.0   
    MAX_ROUTE_STEPS = 5          # NOUVEAU : Horizon de temps autorisé (Le solveur fera max 5 étapes)
    
    TARGET_MARKET_SHARE = 0.10   
    STATION_FEE = 1000           
    TARGET_TIER = 4
    TARGET_ENCHANTMENT = 1
    
    TARGET_ITEMS = [
        "2H_DUALSWORD", "2H_DOUBLEBLADEDSTAFF", "ARMOR_CLOTH_HELL", 
        "HEAD_PLATE_SET1", "SHOES_LEATHER_MORGANA", "SHOES_PLATE_SET1", "SHOES_PLATE_SET2"
    ]
    # ---------------------------------------------------------

    # ÉTAPE 1 : Le Cerveau Financier (On donne tout le catalogue)
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

    # On formate le dictionnaire cible
    target_sales = {}
    for item in profitable_items:
        target_sales[item['base_id']] = {
            'quantity': item['quantity'],
            'profit_per_unit': item['profit'],
            'method': item['method'],
            'craft_city': item['craft_city'],
            'sell_city': item['sell_city']
        }
        
    print(f"\n>> {len(target_sales)} opportunités envoyées au solveur de sac à dos (Knapsack).")

    # ÉTAPE 2 : Le Cerveau Logistique
    print(f"\n[2/2] Transmission au solveur CP-SAT OR-Tools...")
    print(f"      Départ: {START_CITY} | Monture: {MOUNT_CAPACITY_KG} kg | Étapes Max: {MAX_ROUTE_STEPS}")
    print("-" * 42)
    
    solve_albion_route(
        target_sales=target_sales, 
        start_city=START_CITY, 
        payload_kg=MOUNT_CAPACITY_KG,
        max_steps=MAX_ROUTE_STEPS
    )

if __name__ == "__main__":
    main()