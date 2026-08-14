import os
import requests
import re
import json
import xml.etree.ElementTree as ET
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict

# ==========================================
# 1. ÉNUMÉRATIONS ET LOGIQUE MÉTIER
# ==========================================
class ItemSlot(str, Enum):
    RESOURCE = "resource"
    HEAD = "head"           
    CHEST = "chest"         
    SHOES = "shoes"         
    MAIN_HAND = "main_hand" 
    TWO_HAND = "two_hand"   
    OFF_HAND = "off_hand"   
    UNKNOWN = "unknown"

@dataclass(eq=False)
class Item:
    internal_name: str    
    base_id: str   
    mass_kg: float
    category: str         
    slot: ItemSlot
    base_recipe: Dict[str, int] = field(default_factory=dict)
    base_artifact: str = "" 
    
    # Dictionnaire des noms trié par Tier. Ex: {4: {"fr": "Épée...", "en": "Sword..."}}
    localized_names: Dict[int, Dict[str, str]] = field(default_factory=dict)
    
    def get_name(self, tier: int, lang: str = "fr") -> str:
        """Récupère le nom correct selon le Tier (Adept's, Expert's, etc.)"""
        names = self.localized_names.get(tier, {})
        return names.get(lang, f"T{tier} {self.internal_name}")
    
    def get_id(self, tier: int, enchantment: int = 0) -> str:
        item_id = f"T{tier}_{self.base_id}"
        if enchantment > 0:
            item_id += f"@{enchantment}"
        return item_id

    def _get_enchantment_material_id(self, tier: int) -> str:
        if tier == 4: return "RUNE"
        if tier == 5: return "SOUL"
        if tier == 6: return "RELIC"
        if tier == 7: return "SHARD_AVALONIAN"
        return "RUNE"

    def get_enchantment_cost(self) -> int:
        """Coût exact des runes basé sur l'emplacement de l'objet (Slot)."""
        cost_map = {
            ItemSlot.HEAD: 96,
            ItemSlot.SHOES: 96,
            ItemSlot.CHEST: 192,
            ItemSlot.MAIN_HAND: 192,
            ItemSlot.OFF_HAND: 192,
            ItemSlot.TWO_HAND: 384
        }
        return cost_map.get(self.slot, 0)

    def get_recipes(self, tier: int, enchantment: int = 0) -> Dict[str, Dict[str, int]]:
        recipes = {}
        if not self.base_recipe:
            return recipes

        # Méthode 1: Forge avec des matériaux déjà enchantés (.1, .2)
        craft_mats = {}
        for res_base_id, qty in self.base_recipe.items():
            res_id = f"T{tier}_{res_base_id}"
            if enchantment > 0:
                res_id += f"@{enchantment}"
            craft_mats[res_id] = qty
            
        if self.base_artifact:
            craft_mats[f"T{tier}_{self.base_artifact}"] = 1
            
        recipes["craft_station"] = craft_mats

        # Méthode 2: Forge avec des matériaux basiques (.0) PUIS Manipulateur d'énergie
        if enchantment > 0:
            ench_recipe = {}
            # Ajout des ressources de base (.0)
            for res_base_id, qty in self.base_recipe.items():
                ench_recipe[f"T{tier}_{res_base_id}"] = qty
                
            if self.base_artifact:
                ench_recipe[f"T{tier}_{self.base_artifact}"] = 1
                
            # Ajout des runes
            ench_mat = self._get_enchantment_material_id(tier)
            ench_qty = self.get_enchantment_cost()
            ench_recipe[f"T{tier}_{ench_mat}"] = ench_qty
            
            recipes["energy_manipulator"] = ench_recipe

        return recipes

# ==========================================
# 2. GESTION DES FICHIERS (XML + JSON)
# ==========================================
XML_FILE = "items.xml"
XML_URL = "https://raw.githubusercontent.com/broderickhyman/ao-bin-dumps/master/items.xml"

NAMES_FILE = "items_names.json"
NAMES_URL = "https://raw.githubusercontent.com/broderickhyman/ao-bin-dumps/master/formatted/items.json"

def download_file_if_needed(filename, url):
    if not os.path.exists(filename):
        print(f"Téléchargement de {filename}...")
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

def determine_slot(base_id: str, shop_category: str) -> ItemSlot:
    shop_category = shop_category.lower()
    if shop_category in ["resources", "materials", "consumables"]:
        return ItemSlot.RESOURCE
    if "2H_" in base_id: return ItemSlot.TWO_HAND
    if "MAIN_" in base_id: return ItemSlot.MAIN_HAND
    if "HEAD_" in base_id: return ItemSlot.HEAD
    if "ARMOR_" in base_id: return ItemSlot.CHEST
    if "SHOES_" in base_id: return ItemSlot.SHOES
    if "OFF_" in base_id: return ItemSlot.OFF_HAND
    
    if any(x in base_id for x in ["METALBAR", "LEATHER", "CLOTH", "PLANKS", "STONEBLOCK", "RUNE", "SOUL"]):
        return ItemSlot.RESOURCE
        
    return ItemSlot.UNKNOWN

# ==========================================
# 3. LE GÉNÉRATEUR AUTOMATIQUE (FACTORY)
# ==========================================
def build_item_database() -> Dict[str, Item]:
    download_file_if_needed(XML_FILE, XML_URL)
    download_file_if_needed(NAMES_FILE, NAMES_URL)
    
    database: Dict[str, Item] = {}
    
    # ------------------------------------------------
    # ÉTAPE A : Extraire la physique depuis l'XML
    # ------------------------------------------------
    tree = ET.parse(XML_FILE)
    root = tree.getroot()
    
    for element in root:
        uniquename = element.get("uniquename", "")
        if not uniquename or "@" in uniquename:
            continue
            
        match = re.match(r"^T(\d+)_([A-Z0-9_]+)$", uniquename)
        if not match:
            continue
            
        tier = int(match.group(1))
        base_id = match.group(2)
        
        if tier != 4:
            continue

        shop_category = element.get("shopcategory", "").lower()
        subcategory = element.get("shopsubcategory1", "").lower()
        
        try:
            weight = float(element.get("weight", "0.0"))
        except ValueError:
            weight = 0.0
            
        slot = determine_slot(base_id, shop_category)
        if slot == ItemSlot.UNKNOWN:
            continue
            
        internal_name = base_id.split("_")[-1].title()
        
        base_recipe = {}
        base_artifact = ""
        
        craft_reqs = element.findall("craftingrequirements")
        if craft_reqs:
            for res in craft_reqs[0].findall("craftresource"):
                res_uniquename = res.get("uniquename", "")
                res_count = int(res.get("count", "0"))
                
                res_match = re.match(r"^T\d+_([A-Z0-9_]+)$", res_uniquename)
                if res_match:
                    res_base_id = res_match.group(1)
                    if "ARTEFACT" in res_base_id:
                        base_artifact = res_base_id
                    else:
                        base_recipe[res_base_id] = res_count

        database[base_id] = Item(
            internal_name=internal_name,
            base_id=base_id,
            mass_kg=weight,
            category=subcategory,
            slot=slot,
            base_recipe=base_recipe,
            base_artifact=base_artifact
        )
        
    # ------------------------------------------------
    # ÉTAPE B : Appliquer les noms depuis le JSON
    # ------------------------------------------------
    with open(NAMES_FILE, 'r', encoding='utf-8') as f:
        names_data = json.load(f)
        
    for item_info in names_data:
        uniquename = item_info.get("UniqueName", "")
        # On ignore les versions pré-enchantées (@1, @2) pour avoir le nom générique
        if not uniquename or "@" in uniquename:
            continue
            
        match = re.match(r"^T(\d+)_([A-Z0-9_]+)$", uniquename)
        if not match:
            continue
            
        tier = int(match.group(1))
        base_id = match.group(2)
        
        if base_id in database:
            localized = item_info.get("LocalizedNames")
            if localized and isinstance(localized, dict):
                
                if tier not in database[base_id].localized_names:
                    database[base_id].localized_names[tier] = {}
                    
                for lang_key, lang_val in localized.items():
                    if lang_key.upper() == "FR-FR":
                        database[base_id].localized_names[tier]["fr"] = lang_val
                    elif lang_key.upper() == "EN-US":
                        database[base_id].localized_names[tier]["en"] = lang_val

    return database

if __name__ == "__main__":
    db = build_item_database()
    
    if len(db) > 0:
        print("\n--- TEST: DUAL SWORD T4.1 ---")
        sword = db.get("2H_DUALSWORD")
        if sword:
            # On teste la nouvelle fonction de récupération du nom !
            print(f"Nom Français (T4) : {sword.get_name(4, 'fr')}")
            print(f"Nom Anglais (T4)  : {sword.get_name(4, 'en')}")
            print(f"ID API            : {sword.get_id(tier=4, enchantment=1)}")
            print(f"Masse             : {sword.mass_kg} kg")
            print(f"Coût Runes        : {sword.get_enchantment_cost()} Runes")