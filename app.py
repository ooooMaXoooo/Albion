import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Albion Market Tracker",
    page_icon="⚔️",
    layout="wide"
)

st.title("⚔️ Albion Online - Analyseur de Prix")
st.markdown("Suivi dynamique de l'historique des prix via l'API Albion Online Data.")

# --- BARRE LATÉRALE (Paramètres) ---
st.sidebar.header("Paramètres de la requête")

# Choix du serveur
serveur = st.sidebar.selectbox("Serveur", ["europe", "west", "east"], index=0)

# ID de l'objet (Unique Name)
item_id = st.sidebar.text_input("Identifiant de l'objet (Item ID)", value="T4_SHOES_PLATE_SET1")

# Sélection des villes
villes_disponibles = ["Bridgewatch", "Fort Sterling", "Lymhurst", "Martlock", "Thetford", "Caerleon"]
villes_selectionnees = st.sidebar.multiselect("Villes", villes_disponibles, default=["Bridgewatch", "Fort Sterling", "Lymhurst"])

# Sélection des qualités
qualites_disponibles = {1: "Normal", 2: "Bon", 3: "Exceptionnel", 4: "Excellent", 5: "Chef-d'œuvre"}
qualites_selectionnees = st.sidebar.multiselect(
    "Qualités", 
    options=list(qualites_disponibles.keys()), 
    format_func=lambda x: f"{x} - {qualites_disponibles[x]}",
    default=[1, 2]
)

# Plage de dates
date_fin = datetime.today()
date_debut = date_fin - timedelta(days=7)

col_d1, col_d2 = st.sidebar.columns(2)
d_start = col_d1.date_input("Date début", date_debut)
d_end = col_d2.date_input("Date fin", date_fin)

time_scale = st.sidebar.selectbox("Échelle de temps (heures)", [1, 6, 24], index=2)

# --- TRAITEMENT ET RÉCUPÉRATION DES DONNÉES ---
@st.cache_data(ttl=600)  # Mettre en cache la requête pendant 10 minutes pour optimiser les performances
def fetch_albion_data(serveur, item, villes, qualites, start, end, scale):
    if not villes or not qualites:
        return []
    
    locations_str = ",".join(villes).replace(" ", "%20")
    qualities_str = ",".join(map(str, qualites))
    
    url = (
        f"https://{serveur}.albion-online-data.com/api/v2/stats/charts/{item}.json"
        f"?locations={locations_str}"
        f"&qualities={qualities_str}"
        f"&date={start.strftime('%Y-%m-%d')}"
        f"&end_date={end.strftime('%Y-%m-%d')}"
        f"&time-scale={scale}"
    )
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Erreur API ({response.status_code}) : Vérifiez l'ID de l'objet.")
            return []
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")
        return []

# Lancement de la requête
if st.sidebar.button("Mettre à jour les données", type="primary"):
    st.cache_data.clear()

raw_data = fetch_albion_data(serveur, item_id, villes_selectionnees, qualites_selectionnees, d_start, d_end, time_scale)

# --- STRUCTURATION DES DONNÉES EN DATAFRAME ---
records = []
if raw_data:
    for block in raw_data:
        ville = block.get('location')
        qualite = block.get('quality')
        data_block = block.get('data', {})
        timestamps = data_block.get('timestamps', [])
        prices = data_block.get('prices_avg', [])
        
        for t, p in zip(timestamps, prices):
            records.append({
                'Date': pd.to_datetime(t),
                'Ville': ville,
                'Qualité': f"Qualité {qualite} ({qualites_disponibles.get(qualite, '')})",
                'Prix Moyen': p
            })

df = pd.DataFrame(records)

# --- AFFICHAGE DES GRAPHIQUES ---
if not df.empty:
    st.subheader(f"Historique des prix pour `{item_id}`")
    
    # Graphique général interactif avec Plotly
    fig = px.line(
        df, 
        x='Date', 
        y='Prix Moyen', 
        color='Ville', 
        line_dash='Qualité',
        markers=True,
        title="Comparaison des prix par ville et qualité"
    )
    fig.update_layout(hovermode="x unified", xaxis_title="Date", yaxis_title="Prix moyen (Argent)")
    st.plotly_chart(fig, width='stretch')
    
    # Affichage séparé par ville si demandé
    st.markdown("---")
    st.subheader("Détail par ville")
    
    villes_presentes = df['Ville'].unique()
    cols = st.columns(min(len(villes_presentes), 2))
    
    for idx, ville in enumerate(villes_presentes):
        col = cols[idx % 2]
        df_ville = df[df['Ville'] == ville]
        
        fig_ville = px.line(
            df_ville, 
            x='Date', 
            y='Prix Moyen', 
            color='Qualité',
            markers=True,
            title=f"Prix à {ville}"
        )
        fig_ville.update_layout(xaxis_title="Date", yaxis_title="Argent")
        col.plotly_chart(fig_ville, width='stretch')

    # Affichage du tableau brut sous forme de menu déroulant
    with st.expander("Voir les données brutes"):
        st.dataframe(df.sort_values(by='Date', ascending=False), width='stretch')
else:
    st.warning("Aucune donnée trouvée pour ces critères. Vérifiez que l'ID de l'objet est correct et que des données ont été collectées par les joueurs sur cette période.")