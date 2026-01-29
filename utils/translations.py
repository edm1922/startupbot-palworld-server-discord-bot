import os
import json
import logging

class Translator:
    def __init__(self, language="en"):
        self.language = language
        self.translations = {}
        self.load_translations()

    def load_translations(self):
        # For now, we return empty dict or basic fallback
        # If the user has i18n folder, we load from it
        path = os.path.join('i18n', f"{self.language}.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.translations = json.load(f)
            except Exception as e:
                logging.error(f"Error loading translations: {e}")
        else:
             # Default dummy translations for PalguardCog if needed
             self.translations = {}

    def translate(self, cog, key):
        keys = key.split('.')
        value = self.translations.get(cog, {})
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, None)
            else:
                value = None
            if value is None:
                return f"{cog}.{key}"
        return value

    def t(self, cog, key):
        return self.translate(cog, key)

translator = Translator("en")

def t(cog, key):
    return translator.translate(cog, key)
