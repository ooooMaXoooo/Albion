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
    category: str
    slot: ItemSlot
    main_category: str = ""
    
    base_recipe: Dict[str, int] = field(default_factory=dict)
    static_recipe: Dict[str, int] = field(default_factory=dict)
    
    # NOUVEAU : Dictionnaire pour stocker les masses par Tier
    masses_kg: Dict[int, float] = field(default_factory=dict)
    
    localized_names: Dict[int, Dict[str, str]] = field(default_factory=dict)
    
    def get_mass(self, tier: int) -> float:
        """Retourne la masse exacte de l'objet selon son Tier."""
        return self.masses_kg.get(tier, 1.0)
    
    def get_name(self, tier: int, lang: str = "fr") -> str:
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
        if not self.base_recipe and not self.static_recipe:
            return recipes

        craft_mats = {}
        for res_base_id, qty in self.base_recipe.items():
            res_id = f"T{tier}_{res_base_id}"
            if enchantment > 0:
                res_id += f"@{enchantment}"
            craft_mats[res_id] = qty
            
        for static_id, qty in self.static_recipe.items():
            craft_mats[static_id] = qty
            
        recipes["craft_station"] = craft_mats

        if enchantment > 0 and self.base_recipe:
            ench_recipe = {}
            for res_base_id, qty in self.base_recipe.items():
                ench_recipe[f"T{tier}_{res_base_id}"] = qty
                
            for static_id, qty in self.static_recipe.items():
                ench_recipe[static_id] = qty
                
            ench_mat = self._get_enchantment_material_id(tier)
            ench_qty = self.get_enchantment_cost()
            if ench_qty > 0:
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

        shop_category = element.get("shopcategory", "").lower()
        subcategory = element.get("shopsubcategory1", "").lower()
        
        try:
            weight = float(element.get("weight", "0.0"))
        except ValueError:
            weight = 0.0
            
        slot = determine_slot(base_id, shop_category)
        if slot == ItemSlot.UNKNOWN:
            continue
            
        if base_id not in database:
            internal_name = base_id.split("_")[-1].title()
            base_recipe = {}
            static_recipe = {}
            
            craft_reqs = element.findall("craftingrequirements")
            if craft_reqs:
                for res in craft_reqs[0].findall("craftresource"):
                    res_uniquename = res.get("uniquename", "")
                    res_count = int(res.get("count", "0"))
                    
                    res_match = re.match(r"^T\d+_(PLANKS|LEATHER|METALBAR|CLOTH)$", res_uniquename)
                    if res_match:
                        base_recipe[res_match.group(1)] = res_count
                    else:
                        static_recipe[res_uniquename] = res_count

            # L'indentation de cette création est très importante !
            database[base_id] = Item(
                internal_name=internal_name,
                base_id=base_id,
                category=subcategory,
                main_category=shop_category,
                slot=slot,
                base_recipe=base_recipe,
                static_recipe=static_recipe
            )
            
        # NOUVEAU : On ajoute le poids spécifique au Tier actuel
        database[base_id].masses_kg[tier] = weight
        
    with open(NAMES_FILE, 'r', encoding='utf-8') as f:
        names_data = json.load(f)
        
    for item_info in names_data:
        uniquename = item_info.get("UniqueName", "")
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