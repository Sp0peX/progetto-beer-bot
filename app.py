from flask import Flask, render_template, request
import requests
import random

app = Flask(__name__)

API_BASE_URL = "https://api.sampleapis.com/beers/"
STYLES_ENDPOINTS = {
    "ale": "ale",
    "stout": "stouts",
    "red_ale": "red-ale",
    "any": ["ale", "stouts", "red-ale"]
}

def fetch_beers_from_api(style_key="any"):
    # ... (stessa funzione di prima) ...
    beers = []
    endpoints_to_try = []

    if style_key == "any":
        endpoints_to_try = STYLES_ENDPOINTS["any"]
    elif style_key in STYLES_ENDPOINTS:
        endpoints_to_try = [STYLES_ENDPOINTS[style_key]]
    else: 
        endpoints_to_try = STYLES_ENDPOINTS["any"]

    actual_endpoints_tried = []
    for endpoint_suffix in endpoints_to_try:
        url = f"{API_BASE_URL}{endpoint_suffix}"
        actual_endpoints_tried.append(url)
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list): # Assicurati che sia una lista
                 beers.extend(data)
            elif isinstance(data, dict): # A volte API singole tornano un dict se c'è un solo item
                 beers.append(data)

        except requests.exceptions.Timeout:
            print(f"Timeout durante la richiesta a {url}")
        except requests.exceptions.RequestException as e:
            print(f"Errore nel contattare l'API {url}: {e}")
        except ValueError: 
             print(f"Errore nel decodificare JSON da {url}")
    
    if len(actual_endpoints_tried) > 1:
        seen_names = set()
        unique_beers = []
        for beer in beers:
            if isinstance(beer, dict) and beer.get('name') and beer.get('name') not in seen_names:
                unique_beers.append(beer)
                seen_names.add(beer.get('name'))
        return unique_beers
    return beers


def parse_price(price_str):
    # ... (stessa funzione di prima) ...
    if isinstance(price_str, (int, float)):
        return float(price_str)
    if isinstance(price_str, str):
        try:
            cleaned_price = ''.join(filter(lambda x: x.isdigit() or x == '.', price_str.strip().replace(',', '.')))
            if cleaned_price:
                return float(cleaned_price)
        except ValueError:
            return None
    return None

def filter_beers(beers, preferences):
    # ... (logica di filtro per prezzo e rating come prima) ...
    filtered_list = list(beers) 
    feedback_messages = []

    # Filtro per Prezzo
    price_pref = preferences.get('price_range')
    if price_pref and price_pref != "any":
        temp_list = []
        for beer in filtered_list:
            if not isinstance(beer, dict): continue
            beer_price_val = parse_price(beer.get('price'))
            if beer_price_val is not None:
                if price_pref == 'economical' and beer_price_val < 8.0:
                    temp_list.append(beer)
                elif price_pref == 'medium' and 8.0 <= beer_price_val <= 15.0:
                    temp_list.append(beer)
                elif price_pref == 'premium' and beer_price_val > 15.0:
                    temp_list.append(beer)
            elif price_pref == "any": # Se il prezzo non è parsabile e l'utente ha detto "any", includila
                 temp_list.append(beer)

        filtered_list = temp_list
    
    # Filtro per Valutazione Minima
    min_rating_pref = preferences.get('min_rating')
    if min_rating_pref:
        try:
            min_r = float(min_rating_pref)
            if 1.0 <= min_r <= 5.0:
                temp_list = []
                for beer in filtered_list:
                    if not isinstance(beer, dict): continue
                    rating_data = beer.get('rating', {})
                    if isinstance(rating_data, dict):
                        average_rating = rating_data.get('average')
                        if average_rating is not None:
                            try:
                                if float(average_rating) >= min_r:
                                    temp_list.append(beer)
                            except (ValueError, TypeError): pass
                filtered_list = temp_list
            else:
                feedback_messages.append("⚠️ La valutazione minima che hai messo non è valida (deve essere 1-5).")
        except ValueError:
            feedback_messages.append("⚠️ Valore per valutazione minima non numerico.")

    # Feedback per nuove domande (e alcune vecchie non filtrabili)
    if preferences.get('flavor_profile') and preferences.get('flavor_profile') != 'any':
        feedback_messages.append(f"👍 Hai scelto un profilo di sapore '{preferences.get('flavor_profile')}'. Cercherò di tenerne conto!")
    
    if preferences.get('alcohol_pref') and preferences.get('alcohol_pref') != 'any':
        feedback_messages.append(f"🍺 Per la gradazione '{preferences.get('alcohol_pref')}': l'API non mi dà questo dettaglio, quindi è una tua indicazione di gusto generale!")

    if preferences.get('food_pairing_text'):
        food = preferences.get('food_pairing_text')
        style_chosen = preferences.get('style', 'qualsiasi stile')
        feedback_messages.append(f"🍕 Ottimo che vuoi abbinarla con '{food}'! Le birre tipo '{style_chosen}' di solito ci stanno bene.")
    
    if preferences.get('origin_text'):
        feedback_messages.append(f"🌍 Vorresti una birra da '{preferences.get('origin_text')}'! Purtroppo non ho info sull'origine, ma è un bel desiderio!")

    # Nuovi feedback
    occasion = preferences.get('occasion')
    if occasion and occasion != 'any':
        feedback_messages.append(f"🎉 Per l'occasione '{occasion}', speriamo queste birre siano all'altezza!")

    adventure = preferences.get('adventure_level')
    if adventure:
        if adventure == 'classic':
            feedback_messages.append("😎 Vai sul classico! Scelta solida.")
        elif adventure == 'curious':
            feedback_messages.append("🧐 Curioso/a di provare cose nuove? Bene!")
        elif adventure == 'daredevil':
            feedback_messages.append("🤘 Modalità spericolata? Vediamo cosa salta fuori!")

    intensity = preferences.get('flavor_intensity')
    if intensity and intensity != 'any':
        feedback_messages.append(f"💥 Preferisci un sapore '{intensity}'. Non posso misurarlo, ma è una buona dritta per te!")
    
    body_pref = preferences.get('body_preference')
    if body_pref and body_pref != 'any':
        feedback_messages.append(f"🥤 Corpo '{body_pref}'. Altra info utile per la tua scelta finale, anche se non posso filtrarla.")
    
    color_pref = preferences.get('color_preference')
    if color_pref and color_pref != 'any':
        style_feedback = ""
        if preferences.get('style') == 'stout' and color_pref != 'dark':
            style_feedback = " (Anche se le Stout sono tipicamente scure!)"
        elif preferences.get('style') == 'red_ale' and color_pref != 'amber':
            style_feedback = " (Anche se le Red Ale tendono all'ambrato!)"
        feedback_messages.append(f"🎨 Ti piacerebbe una birra dal colore '{color_pref}'{style_feedback}. Questo può dipendere molto dallo stile!")
    
    # Ordina per valutazione (decrescente)
    def get_rating_for_sort(b):
        if isinstance(b,dict) and isinstance(b.get('rating'), dict):
            return b.get('rating', {}).get('average', 0)
        return 0
    filtered_list.sort(key=get_rating_for_sort, reverse=True)

    return filtered_list, feedback_messages


@app.route('/', methods=['GET', 'POST'])
def index():
    # ... (stessa logica di prima per GET/POST, fetch, chiamata a filter_beers) ...
    beers_data = []
    suggestions = []
    feedback = []
    form_data = {} 

    if request.method == 'POST':
        form_data = request.form.to_dict() 

        style_choice = form_data.get('style', 'any')
        beers_data = fetch_beers_from_api(style_choice)

        if beers_data:
            # Pulisci i dati ricevuti: assicurati che ogni "beer" sia un dizionario
            valid_beers_data = [b for b in beers_data if isinstance(b, dict)]
            suggestions, feedback = filter_beers(valid_beers_data, form_data)
            
            if suggestions:
                if len(suggestions) < 5:
                    pass 
                else: 
                    # random.shuffle(suggestions) # Opzionale
                    suggestions = suggestions[:min(len(suggestions), 7)] # Mostra fino a 7
            if not suggestions and not feedback: # Se non ci sono suggerimenti e nessun feedback particolare
                feedback.append("🤔 Non ho trovato birre con i filtri applicabili. Prova a cambiare qualcosa!")


        else:
            feedback.append("☠️ Ops! Non riesco a parlare con il mio spacciatore di dati sulle birre (API). Riprova tra un po'.")

    return render_template('index.html', suggestions=suggestions, feedback=feedback, form_data=form_data)


if __name__ == '__main__':
    app.run