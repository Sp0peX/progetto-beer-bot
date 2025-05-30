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
    beers = []
    endpoints_to_try = []

    if style_key == "any":
        endpoints_to_try = STYLES_ENDPOINTS["any"]
    elif style_key in STYLES_ENDPOINTS:
        endpoints_to_try = [STYLES_ENDPOINTS[style_key]]
    else: 
        # Fallback se lo style_key non è valido, prova comunque tutti
        endpoints_to_try = STYLES_ENDPOINTS["any"]

    actual_endpoints_tried = []
    for endpoint_suffix in endpoints_to_try:
        url = f"{API_BASE_URL}{endpoint_suffix}"
        actual_endpoints_tried.append(url)
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            # Assicurati che i dati siano una lista di dizionari
            if isinstance(data, list):
                beers.extend(d for d in data if isinstance(d, dict))
            elif isinstance(data, dict): # A volte API singole tornano un dict se c'è un solo item
                beers.append(data)
            # Altri formati di dati non sono gestiti e verranno ignorati

        except requests.exceptions.Timeout:
            print(f"Timeout durante la richiesta a {url}")
        except requests.exceptions.RequestException as e:
            print(f"Errore nel contattare l'API {url}: {e}")
        except ValueError: # Errore nella decodifica JSON
            print(f"Errore nel decodificare JSON da {url}")
    
    # Rimuovi duplicati se abbiamo aggregato da più endpoint (basato sul nome)
    if len(actual_endpoints_tried) > 1:
        seen_names = set()
        unique_beers = []
        for beer in beers:
            # Assicurati che beer sia un dizionario e abbia un nome prima di accedere a beer.get('name')
            if isinstance(beer, dict) and beer.get('name') and beer.get('name') not in seen_names:
                unique_beers.append(beer)
                seen_names.add(beer.get('name'))
        return unique_beers
    return beers


def parse_price(price_str):
    if isinstance(price_str, (int, float)):
        return float(price_str)
    if isinstance(price_str, str):
        try:
            # Pulisce la stringa del prezzo rimuovendo '$' e ',' e gestendo '.' come decimale
            cleaned_price = price_str.replace('$', '').replace(',', '').strip()
            if cleaned_price:
                return float(cleaned_price)
        except ValueError:
            return None # Non è stato possibile convertire
    return None # Formato non riconosciuto o stringa vuota/None


def filter_beers(beers, preferences):
    filtered_list = list(beers) 
    feedback_messages = []

    # Filtro per Prezzo
    price_pref = preferences.get('price_range')
    if price_pref and price_pref != "any":
        temp_list = []
        for beer in filtered_list:
            if not isinstance(beer, dict): continue # Salta se l'item non è un dizionario
            beer_price_val = parse_price(beer.get('price'))
            
            passes_price_filter = False
            if beer_price_val is not None:
                if price_pref == 'economical' and beer_price_val < 8.0:
                    passes_price_filter = True
                elif price_pref == 'medium' and 8.0 <= beer_price_val <= 15.0:
                    passes_price_filter = True
                elif price_pref == 'premium' and beer_price_val > 15.0:
                    passes_price_filter = True
            
            if passes_price_filter:
                temp_list.append(beer)
            elif price_pref == "any" and beer_price_val is None: # Includi se il prezzo è "any" e non parsabile
                 temp_list.append(beer)


        filtered_list = temp_list
    
    # Filtro per Valutazione Minima
    min_rating_str = preferences.get('min_rating', '').strip() # Prendi la stringa e puliscila
    if min_rating_str: # Prova a convertire solo se non è vuota
        try:
            min_r = float(min_rating_str)
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
                            except (ValueError, TypeError): pass # Ignora se la valutazione non è un numero valido
                filtered_list = temp_list
            else:
                feedback_messages.append("⚠️ La valutazione minima che hai inserito non è valida (deve essere tra 1.0 e 5.0).")
        except ValueError:
            feedback_messages.append("⚠️ Il valore per la valutazione minima non è un numero valido.")

    # Feedback per domande non direttamente filtrabili con l'API attuale
    if preferences.get('flavor_profile') and preferences.get('flavor_profile') != 'any':
        feedback_messages.append(f"👍 Profilo di sapore: '{preferences.get('flavor_profile')}'. Ottima scelta!")
    
    if preferences.get('alcohol_pref') and preferences.get('alcohol_pref') != 'any':
        feedback_messages.append(f"🍺 Gradazione '{preferences.get('alcohol_pref')}': l'API attuale non mi dà questo dettaglio, ma è una tua indicazione di gusto!")

    if preferences.get('food_pairing_text','').strip(): # Se c'è testo per l'abbinamento
        food = preferences.get('food_pairing_text').strip()
        style_chosen = preferences.get('style', 'qualsiasi stile') # Usa lo stile selezionato nel form
        feedback_messages.append(f"🍕 Per l'abbinamento con '{food}': le birre tipo '{style_chosen.replace('_', ' ').title()}' di solito sono un'ottima compagnia!")
    
    origin_country_preference = preferences.get('origin_text', '').strip()
    origin_choice_made = preferences.get('origin_q') == 'yes'
    if origin_choice_made and origin_country_preference:
        feedback_messages.append(f"🌍 Preferenza Paese: '{origin_country_preference}'. Bello! Purtroppo, l'API che usiamo non mi dice da dove vengono le birre, quindi non posso usarlo come filtro. Ma è un ottimo spunto!")
    elif origin_choice_made and not origin_country_preference:
        feedback_messages.append("🌍 Hai indicato una preferenza per l'origine ma non hai specificato un paese. In ogni caso, con l'attuale API non potrei filtrare per questo criterio.")

    occasion = preferences.get('occasion')
    if occasion and occasion != 'any':
        feedback_messages.append(f"🎉 Occasione '{occasion}': speriamo queste birre siano perfette!")

    adventure = preferences.get('adventure_level')
    if adventure:
        adventure_map = {'classic': "😎 Classico, vai sul sicuro!", 'curious': "🧐 Curioso/a di provare cose nuove? Bene!", 'daredevil': "🤘 Modalità spericolata? Vediamo!"}
        feedback_messages.append(adventure_map.get(adventure, "Interessante scelta di avventura!"))

    intensity = preferences.get('flavor_intensity')
    if intensity and intensity != 'any':
        feedback_messages.append(f"💥 Intensità sapore '{intensity}'. Non la misuro, ma è una buona dritta per te!")
    
    body_pref = preferences.get('body_preference')
    if body_pref and body_pref != 'any':
        body_map = {'light': "💧 Leggera e scorrevole", 'medium': "👌 Media consistenza", 'full': "🏋️‍♀️ Corposa e piena"}
        feedback_messages.append(f"🥤 Corpo '{body_map.get(body_pref, body_pref)}'. Altra info utile!")
    
    color_pref = preferences.get('color_preference')
    if color_pref and color_pref != 'any':
        style_feedback = ""
        current_style = preferences.get('style')
        if current_style == 'stout' and color_pref != 'dark':
            style_feedback = " (Interessante, dato che le Stout sono tipicamente scure!)"
        elif current_style == 'red_ale' and color_pref != 'amber':
            style_feedback = " (Curioso, le Red Ale tendono all'ambrato!)"
        feedback_messages.append(f"🎨 Colore '{color_pref}'{style_feedback}. Dipende molto dallo stile!")
    
    # Ordina per valutazione (decrescente), assicurandoti che gli item siano dizionari
    def get_rating_for_sort(b):
        # Assicurati che b sia un dizionario e abbia 'rating' che è un dizionario con 'average'
        if isinstance(b, dict) and isinstance(b.get('rating'), dict) and isinstance(b['rating'].get('average'), (int, float)):
            return b['rating']['average']
        return 0 # Ritorna 0 se la struttura non è come attesa, così va in fondo

    # Filtra ulteriormente per assicurare che solo dizionari validi vengano ordinati
    valid_items_for_sort = [item for item in filtered_list if isinstance(item, dict)]
    valid_items_for_sort.sort(key=get_rating_for_sort, reverse=True)
    filtered_list = valid_items_for_sort

    return filtered_list, feedback_messages


@app.route('/', methods=['GET', 'POST'])
def index():
    beers_data = []
    suggestions = []
    feedback = []
    form_data = {} 

    if request.method == 'POST':
        form_data = request.form.to_dict() 
        style_choice = form_data.get('style', 'any')
        beers_data = fetch_beers_from_api(style_choice)

        if beers_data:
            # Assicurati che beers_data contenga solo dizionari prima di filtrare
            valid_beers_data = [b for b in beers_data if isinstance(b, dict)]
            suggestions, feedback = filter_beers(valid_beers_data, form_data)
            
            if suggestions:
                # Se meno di 5 suggerimenti, mostrali tutti. Altrimenti, i primi (fino a 7).
                if len(suggestions) < 5:
                    pass # suggestions contiene già tutti quelli trovati
                else: 
                    suggestions = suggestions[:min(len(suggestions), 7)] 
            
            # Aggiungi un messaggio se non ci sono suggerimenti MA c'erano dati dall'API
            # E non ci sono già altri messaggi di feedback che spiegano la situazione
            if not suggestions and not feedback: 
                feedback.append("🤔 Non ho trovato birre con i filtri applicabili. Prova a cambiare qualcosa!")
        else:
            # Se fetch_beers_from_api ritorna vuoto o None
            feedback.append("☠️ Ops! Non riesco a parlare con il mio spacciatore di dati sulle birre (API) o non ci sono birre per lo stile scelto. Riprova tra un po' o cambia stile.")

    return render_template('index.html', suggestions=suggestions, feedback=feedback, form_data=form_data)

# Questo blocco serve solo quando esegui il file direttamente con 'python app.py'
# per testare localmente. Gunicorn (usato da Render) non lo esegue.
if __name__ == '__main__':
    app.run(debug=True)
