print("DEBUG: app.py - Inizio esecuzione script") # DEBUGGING

from flask import Flask, render_template, request
import requests
import random
import json

print("DEBUG: app.py - Moduli importati") # DEBUGGING

app = Flask(__name__)
print(f"DEBUG: app.py - Istanza Flask creata con nome: {app.name}") # DEBUGGING

API_BASE_URL = "https://api.sampleapis.com/beers/"
STYLES_ENDPOINTS = {
    "ale": "ale",
    "stout": "stouts",
    "red_ale": "red-ale",
    "any": ["ale", "stouts", "red-ale"]
}

print("DEBUG: app.py - Costanti definite") # DEBUGGING

def fetch_beers_from_api(style_key="any"):
    print(f"DEBUG: fetch_beers_from_api - Chiamata con style_key: {style_key}") # DEBUGGING
    beers_list = []
    endpoints_to_fetch = []

    if style_key == "any":
        endpoints_to_fetch = STYLES_ENDPOINTS["any"]
    elif style_key in STYLES_ENDPOINTS:
        endpoints_to_fetch = [STYLES_ENDPOINTS[style_key]]
    else: 
        endpoints_to_fetch = STYLES_ENDPOINTS["any"]
    
    print(f"DEBUG: fetch_beers_from_api - Endpoints da contattare: {endpoints_to_fetch}") # DEBUGGING

    for endpoint_suffix in endpoints_to_fetch:
        url = f"{API_BASE_URL}{endpoint_suffix}"
        print(f"DEBUG: fetch_beers_from_api - Tentativo fetch da URL: {url}") # DEBUGGING
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        beers_list.append(item)
            elif isinstance(data, dict):
                beers_list.append(data)
            print(f"DEBUG: fetch_beers_from_api - Dati ricevuti da {url}") # DEBUGGING
        except requests.exceptions.Timeout:
            print(f"ERROR: fetch_beers_from_api - Timeout per {url}") # DEBUGGING
        except requests.exceptions.HTTPError as e:
            print(f"ERROR: fetch_beers_from_api - Errore HTTP per {url}: {e}") # DEBUGGING
        except requests.exceptions.RequestException as e:
            print(f"ERROR: fetch_beers_from_api - Errore di rete per {url}: {e}") # DEBUGGING
        except json.JSONDecodeError:
             print(f"ERROR: fetch_beers_from_api - Errore JSONDecode per {url}") # DEBUGGING
        except Exception as e:
            print(f"ERROR: fetch_beers_from_api - Errore imprevisto per {url}: {e}") # DEBUGGING

    if len(endpoints_to_fetch) > 1 and beers_list:
        seen_names = set()
        unique_beers = []
        for beer in beers_list:
            if isinstance(beer, dict) and beer.get('name'):
                if beer['name'] not in seen_names:
                    unique_beers.append(beer)
                    seen_names.add(beer['name'])
            else:
                print(f"DEBUG: fetch_beers_from_api - Item birra non valido o senza nome: {beer}") # DEBUGGING
        print(f"DEBUG: fetch_beers_from_api - Ritornate {len(unique_beers)} birre uniche") # DEBUGGING
        return unique_beers
    print(f"DEBUG: fetch_beers_from_api - Ritornate {len(beers_list)} birre") # DEBUGGING
    return beers_list

def parse_price(price_str):
    # ... (codice di parse_price come prima, puoi aggiungere print se vuoi) ...
    if price_str is None: return None
    if isinstance(price_str, (int, float)): return float(price_str)
    if isinstance(price_str, str):
        try:
            cleaned_price = price_str.replace('$', '').replace(',', '.').strip()
            if cleaned_price: return float(cleaned_price)
        except ValueError: return None
    return None

def filter_beers(beers_data, preferences):
    print(f"DEBUG: filter_beers - Ricevute {len(beers_data) if isinstance(beers_data, list) else 'dati non validi'} birre, preferenze: {preferences}") # DEBUGGING
    # ... (resto del codice di filter_beers come prima, puoi aggiungere print se vuoi) ...
    if not isinstance(beers_data, list):
        return [], ["Errore interno: i dati delle birre non sono nel formato atteso."]
    filtered_list = list(beers_data) 
    feedback_messages = []
    price_pref = preferences.get('price_range')
    if price_pref and price_pref != "any":
        # ... (logica filtro prezzo) ...
        pass # Riempi con la logica come prima
    min_rating_str = preferences.get('min_rating', '').strip()
    if min_rating_str:
        # ... (logica filtro rating) ...
        pass # Riempi con la logica come prima
    # ... (tutti gli altri feedback) ...
    # Mantieni la logica di sort e il return come prima
    def get_rating_for_sort(beer_item):
        if isinstance(beer_item, dict) and isinstance(beer_item.get('rating'), dict) and isinstance(beer_item['rating'].get('average'), (int, float)):
            return beer_item['rating']['average']
        return 0 
    valid_items_for_sort = [item for item in filtered_list if isinstance(item, dict)]
    valid_items_for_sort.sort(key=get_rating_for_sort, reverse=True)
    filtered_list = valid_items_for_sort
    return filtered_list, feedback_messages


print("DEBUG: app.py - Funzioni definite") # DEBUGGING

@app.route('/', methods=['GET', 'POST'])
def index():
    print(f"DEBUG: index - Richiesta ricevuta per '/', Metodo: {request.method}") # DEBUGGING
    suggestions = []
    feedback = []
    form_data_retained = {} 

    try:
        if request.method == 'POST':
            print("DEBUG: index - Richiesta POST rilevata") # DEBUGGING
            form_data_retained = request.form.to_dict() 
            style_choice = form_data_retained.get('style', 'any')
            print(f"DEBUG: index - Scelta stile: {style_choice}") # DEBUGGING
            
            try:
                all_beers_data = fetch_beers_from_api(style_choice)
            except Exception as e_fetch:
                print(f"CRITICAL ERROR: index - Eccezione in fetch_beers_from_api: {e_fetch}") # DEBUGGING
                all_beers_data = [] 
                feedback.append("☠️ Ops! Problema gravissimo nel recuperare i dati. Riprova più tardi.")

            if all_beers_data:
                print(f"DEBUG: index - Ricevuti {len(all_beers_data)} dati birra dall'API") # DEBUGGING
                valid_beers_data_for_filter = [b for b in all_beers_data if isinstance(b, dict)]
                
                if not valid_beers_data_for_filter and all_beers_data:
                     feedback.append("🤔 I dati ricevuti dall'API erano un po' strani.")

                suggestions, filter_feedback = filter_beers(valid_beers_data_for_filter, form_data_retained)
                feedback.extend(filter_feedback)
                print(f"DEBUG: index - Suggerimenti dopo filtro: {len(suggestions)}") # DEBUGGING
                
                if suggestions:
                    if len(suggestions) >= 5:
                        suggestions = suggestions[:min(len(suggestions), 7)] 
                
                if not suggestions and valid_beers_data_for_filter and not filter_feedback and not any("☠️" in msg for msg in feedback):
                    feedback.append("🤔 Nessuna birra trovata con i filtri. Prova a cambiare ricerca!")
            
            elif not feedback: 
                feedback.append("🔎 Nessuna birra per lo stile scelto o API non raggiungibile.")
        
        print("DEBUG: index - Sto per renderizzare index.html") # DEBUGGING
        return render_template('index.html', suggestions=suggestions, feedback=feedback, form_data=form_data_retained)

    except Exception as e:
        print(f"CRITICAL ERROR: index - Eccezione non gestita nella route '/': {e}") # DEBUGGING
        feedback.append("🔧 Ops! Qualcosa è andato molto storto. Riprova tra un attimo.")
        suggestions = [] 
        form_data_retained = request.form.to_dict() if request.method == 'POST' else {}
        # In caso di errore grave, potresti voler renderizzare una pagina di errore dedicata
        # o semplicemente index.html con il messaggio di errore.
        return render_template('index.html', suggestions=suggestions, feedback=feedback, form_data=form_data_retained), 500


print("DEBUG: app.py - Route definite") # DEBUGGING

if __name__ == '__main__':
    print("DEBUG: app.py - Esecuzione blocco __main__ (solo per test locale)") # DEBUGGING
    app.run(debug=True)

print("DEBUG: app.py - Fine esecuzione script (dopo definizione app e route)") # DEBUGGING