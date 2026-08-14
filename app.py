import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import io
from contextlib import redirect_stdout
import streamlit_antd_components as sac

# Importation de nos modules de backend
from item_database import build_item_database
from market_analyst import analyze_crafting_profitability
from logistic_solver import solve_albion_route

# ==========================================
# CONFIGURATION ET CACHE
# ==========================================
st.set_page_config(
    page_title="Albion Market & Logistics",
    page_icon="⚔️",
    layout="wide"
)

@st.cache_resource
def load_db():
    return build_item_database()

db = load_db()

@st.cache_data(ttl=600)
def fetch_albion_data(serveur, item, villes, qualites, start, end, scale):
    if not villes or not qualites:
        return []
    locations_str = ",".join(villes).replace(" ", "%20")
    qualities_str = ",".join(map(str, qualites))
    url = (
        f"https://{serveur}.albion-online-data.com/api/v2/stats/charts/{item}.json"
        f"?locations={locations_str}&qualities={qualities_str}"
        f"&date={start.strftime('%Y-%m-%d')}&end_date={end.strftime('%Y-%m-%d')}&time-scale={scale}"
    )
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []

# ==========================================
# INTERFACE UTILISATEUR (UI)
# ==========================================
st.title("⚔️ Albion Online - Trading Empire")
st.markdown("Plateforme d'analyse financière et d'optimisation logistique.")

st.sidebar.header("⚙️ Paramètres Globaux")
serveur = st.sidebar.selectbox("Serveur", ["europe", "west", "east"], index=0)
lang = st.sidebar.selectbox("Langue / Language", ["fr", "en"], index=0)

if 'item_pool' not in st.session_state:
    st.session_state.item_pool = []

tab1, tab2 = st.tabs(["📈 Historique des Prix", "🛠️ Optimiseur de Craft & Logistique"])

# ==========================================
# ONGLET 1 : ANALYSEUR DE PRIX
# ==========================================
with tab1:
    st.header("Analyseur de Prix Historique")
    
    with st.expander("Filtres de recherche", expanded=True):
        col1, col2, col3 = st.columns(3)
        item_id = col1.text_input("Identifiant (Item ID)", value="T4_SHOES_PLATE_SET1")
        time_scale = col1.selectbox("Échelle de temps (heures)", [1, 6, 24], index=2)
        
        villes_dispo = ["Bridgewatch", "Fort Sterling", "Lymhurst", "Martlock", "Thetford", "Caerleon"]
        villes_sel = col2.multiselect("Villes", villes_dispo, default=["Bridgewatch", "Fort Sterling", "Lymhurst"])
        
        qualites_dispo = {1: "Normal", 2: "Bon", 3: "Exceptionnel", 4: "Excellent", 5: "Chef-d'œuvre"}
        qualites_sel = col3.multiselect(
            "Qualités", options=list(qualites_dispo.keys()), 
            format_func=lambda x: f"{x} - {qualites_dispo[x]}", default=[1, 2]
        )
        
        col_d1, col_d2 = st.columns(2)
        d_start = col_d1.date_input("Date début", datetime.today() - timedelta(days=7))
        d_end = col_d2.date_input("Date fin", datetime.today())

    if st.button("Mettre à jour les graphiques", type="primary"):
        raw_data = fetch_albion_data(serveur, item_id, villes_sel, qualites_sel, d_start, d_end, time_scale)
        records = []
        if raw_data:
            for block in raw_data:
                v = block.get('location')
                q = block.get('quality')
                d_block = block.get('data', {})
                for t, p in zip(d_block.get('timestamps', []), d_block.get('prices_avg', [])):
                    records.append({
                        'Date': pd.to_datetime(t), 'Ville': v,
                        'Qualité': f"Qualité {q} ({qualites_dispo.get(q, '')})", 'Prix Moyen': p
                    })
        
        df = pd.DataFrame(records)
        if not df.empty:
            fig = px.line(df, x='Date', y='Prix Moyen', color='Ville', line_dash='Qualité', markers=True, title=f"Historique : {item_id}")
            fig.update_layout(hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("Voir les données brutes"):
                st.dataframe(df.sort_values(by='Date', ascending=False), use_container_width=True)
        else:
            st.warning("Aucune donnée trouvée. L'objet n'a peut-être pas été vendu récemment ou l'ID est incorrect.")

# ==========================================
# ONGLET 2 : OPTIMISEUR DE ROUTE & CRAFT
# ==========================================
with tab2:
    st.header("Solveur Logistique & Sac à Dos")
    
    col_prof, col_eco, col_log = st.columns(3)
    
    with col_prof:
        st.subheader("Profil Joueur")
        has_premium = st.checkbox("Compte Premium (Taxes réduites)", value=False)
        start_city = st.selectbox("Ville de départ", ["Martlock", "Lymhurst", "Fort Sterling", "Bridgewatch", "Thetford"])
        mount_capacity = st.number_input("Capacité monture (kg)", min_value=100.0, value=1200.0, step=100.0)
        
    with col_eco:
        st.subheader("Économie")
        target_market_share = st.slider("Part de marché visée (%)", min_value=1, max_value=50, value=10) / 100.0
        slippage_pct = st.slider("Marge de sécurité Prix (%)", min_value=0, max_value=30, value=10) / 100.0
        station_fee = st.number_input("Taxe station de craft", min_value=100, value=1000, step=100)
        max_budget = st.number_input("Budget Max (Argent investi)", min_value=10000, value=500000, step=50000)
        
    with col_log:
        st.subheader("Logistique")
        max_steps = st.slider("Nombre max d'étapes (Villes)", min_value=1, max_value=10, value=5)
    
    st.markdown("---")
    st.subheader("Sélection des objets (Catalogue d'artisanat)")
    
    name_to_id = {}
    tree_items = []
    main_cats = sorted(list(set(item.main_category for item in db.values() if item.main_category)))
    
    for main_cat in main_cats:
        sub_items = []
        sub_cats = sorted(list(set(item.category for item in db.values() if item.main_category == main_cat and item.category)))
        
        for sub_cat in sub_cats:
            leaf_items = []
            items_in_sub = {b_id: itm for b_id, itm in db.items() if itm.category == sub_cat and itm.main_category == main_cat}
            
            for base_id, item_obj in items_in_sub.items():
                item_name = item_obj.get_name(4, lang)
                name_to_id[item_name] = base_id
                leaf_items.append(sac.TreeItem(label=item_name))
                
            if leaf_items:
                sub_items.append(sac.TreeItem(label=sub_cat.capitalize(), children=leaf_items))
                
        if sub_items:
            tree_items.append(sac.TreeItem(label=main_cat.upper(), icon='folder-fill', children=sub_items))

    # CORRECTION : Le composant gère sa propre hauteur directement sans st.container()
    selected_labels = sac.tree(
        items=tree_items,
        checkbox=True,
        checkbox_strict=False,
        show_line=True,
        return_index=False,
        height=500
    )
    
    selected_base_ids = []
    if selected_labels:
        selected_base_ids = [name_to_id[label] for label in selected_labels if label in name_to_id]

    st.markdown("### Configuration de la sélection")
    col_t, col_e, col_b = st.columns([1, 1, 2])
    tier = col_t.selectbox("Tier à appliquer", [4, 5, 6, 7, 8], index=0)
    enchantment = col_e.selectbox("Enchantement à appliquer", [0, 1, 2, 3, 4], index=1)
    
    if col_b.button("➕ Ajouter au panier d'analyse", use_container_width=True):
        added_count = 0
        for b_id in selected_base_ids:
            entry = {"base_id": b_id, "tier": tier, "enchantment": enchantment}
            if entry not in st.session_state.item_pool:
                st.session_state.item_pool.append(entry)
                added_count += 1
        st.success(f"{added_count} objets ajoutés au panier !")

    if st.session_state.item_pool:
        st.markdown("### 🛒 Panier d'analyse actuel")
        pool_df = pd.DataFrame(st.session_state.item_pool)
        pool_df['Nom'] = pool_df.apply(lambda row: f"{db[row['base_id']].get_name(row['tier'], lang)} ({row['base_id']})" if row['base_id'] in db else row['base_id'], axis=1)
        st.dataframe(pool_df[['Nom', 'tier', 'enchantment']], use_container_width=True)
        
        if st.button("🗑️ Vider le panier"):
            st.session_state.item_pool = []
            st.rerun()

    # Lancement du calcul
    if st.button("🚀 Calculer le plan d'affaires optimal", type="primary", use_container_width=True):
        if not st.session_state.item_pool:
            st.error("Veuillez ajouter au moins un objet dans le panier d'analyse.")
        else:
            with st.spinner("Analyse du marché en cours..."):
                profitable_items = analyze_crafting_profitability(
                    target_pool=st.session_state.item_pool,
                    has_premium=has_premium,
                    target_market_share=target_market_share,
                    station_fee_estimate=station_fee,
                    lang=lang,
                    slippage=slippage_pct
                )
            
            if not profitable_items:
                st.warning("Aucun objet sélectionné n'est rentable actuellement. (Vous pouvez essayer de baisser la marge de sécurité).")
            else:
                st.success(f"{len(profitable_items)} opportunités trouvées !")
                
                df_profits = pd.DataFrame(profitable_items)
                df_profits = df_profits[['name_display', 'quantity', 'upfront_cost', 'profit', 'method', 'craft_city', 'sell_city']]
                df_profits.columns = ['Objet', 'Qté Max', 'Investissement/u', 'Marge/u', 'Méthode', 'Ville Craft', 'Ville Vente']
                st.dataframe(df_profits, use_container_width=True)
                
                target_sales = {}
                for item in profitable_items:
                    target_sales[item['item_id']] = { 
                        'quantity': item['quantity'],
                        'profit_per_unit': item['profit'],
                        'upfront_cost': item['upfront_cost'],
                        'sell_price': item['sell_price'], 
                        'method': item['method'],
                        'flat_recipe': item['flat_recipe'],
                        'craft_city': item['craft_city'],
                        'sell_city': item['sell_city']
                    }
                
                st.markdown("### 🗺️ Itinéraire Généré par OR-Tools")
                with st.spinner("Le solveur (Knapsack + TSP) calcule la meilleure route sous contrainte de budget..."):
                    f = io.StringIO()
                    with redirect_stdout(f):
                        success = solve_albion_route(
                            target_sales=target_sales, 
                            start_city=start_city, 
                            payload_kg=mount_capacity,
                            max_steps=max_steps,
                            max_budget=int(max_budget),
                            lang=lang
                        )
                    console_output = f.getvalue()
                
                if success:
                    st.code(console_output, language="text")
                    st.balloons()
                else:
                    st.error("Le solveur n'a trouvé aucune route (Budget trop faible ou Monture trop petite).")
                    st.code(console_output, language="text")