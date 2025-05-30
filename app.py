from flask import Flask, render_template, request
import requests
import random
import json # Importa json per gestire potenziali errori di decodifica in modo più esplicito

app = Flask(__name__)

API_BASE_URL = "https://api.sampleapis.com/beers/"
STYLES_ENDPOINTS = {
    "ale": "ale",
    "stout": "stouts",
    "red_ale": "red-ale",
    "any": ["ale", "stouts", "red-ale"] # Se "any", li proviamo tutti
}

def fetch_beers_from_api(style_key="any"):
    beers_list = []
    endpoints_to_fetch = []

    if style_key == "any":
        endpoints_to_fetch = STYLES_ENDPOINTS["any"]
    elif style_key in STYLES_ENDPOINTS:
        endpoints_to_fetch = [STYLES_ENDPOINTS[style_key]]
    else: 
        # Fallback se lo style_key non è valido (improbabile con un select HTML)
        endpoints_to_fetch = STYLES_ENDPOINTS["any"]

    for endpoint_suffix in endpoints_to_fetch:
        url = f"{API_BASE_URL}{endpoint_suffix}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status() # Solleva un'eccezione per errori HTTP (4xx o 5xx)
            data = response.json()
            
            # Assicurati che i dati siano una lista e che ogni elemento sia un dizionario
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        beers_list.append(item)
            elif isinstance(data, dict): # A volte API singole tornano un dict se c'è un solo item
                beers_list.append(data)
            # Altri formati di dati (es. stringa di errore) non verranno aggiunti

        except requests.exceptions.Timeout:
            print(f"Timeout durante la richiesta a {url}")
        except requests.exceptions.HTTPError as e:
            print(f"Errore HTTP nel contattare l'API {url}: {e}")
        except requests.exceptions.RequestException as e: # Altri errori di rete/connessione
            print(f"Errore di rete nel contattare l'API {url}: {e}")
        except json.JSONDecodeError: # Errore specifico se il JSON non è valido
             print(f"Errore nel decodificare JSON da {url}. Risposta non era JSON valido.")
        except Exception as e: # Catch-all per altri errori imprevisti durante il fetch
            print(f"Errore imprevisto durante il fetch da {url}: {e}")

    # Rimuovi duplicati basati sul nome se abbiamo aggregato da più endpoint
    if len(endpoints_to_fetch) > 1 and beers_list:
        seen_names = set()
        unique_beers = []
        for beer in beers_list:
            # Controlla che beer sia un dizionario e abbia una chiave 'name'
            if isinstance(beer, dict) and beer.get('name'):
                if beer['name'] not in seen_names:
                    unique_beers.append(beer)
                    seen_names.add(beer['name'])
            else:
                # Se un item non è un dizionario o non ha nome, potresti volerlo loggare o gestire
                print(f"Attenzione: item birra non valido o senza nome: {beer}")
        return unique_beers
    return beers_list

def parse_price(price_str):
    if price_str is None:
        return None
    if isinstance(price_str, (int, float)):
        return float(price_str)
    if isinstance(price_str, str):
        try:
            # Rimuove il simbolo '$', spazi e sostituisce ',' con '.' per lo standard float
            cleaned_price = price_str.replace('$', '').replace(',', '.').strip()
            if cleaned_price: # Assicura che non sia una stringa vuota dopo la pulizia
                return float(cleaned_price)
        except ValueError:
            # La stringa non può essere convertita in float
            return None
    return None # Altri tipi non gestiti o conversione fallita

def filter_beers(beers_data, preferences):
    if not isinstance(beers_data, list): # Assicurati che l'input sia una lista
        return [], ["Errore interno: i dati delle birre non sono nel formato atteso."]

    filtered_list = list(beers_data) # Lavora su una copia
    feedback_messages = []

    # Filtro per Prezzo
    price_pref = preferences.get('price_range')
    if price_pref and price_pref != "any":
        temp_list = []
        for beer in filtered_list:
            if not isinstance(beer, dict): continue 
            beer_price_val = parse_price(beer.get('price'))
            
            passes_price_filter = False
            if beer_price_val is not None:
                if price_pref == 'economical' and beer_price_val < 8.0: passes_price_filter = True
                elif price_pref == 'medium' and 8.0 <= beer_price_val <= 15.0: passes_price_filter = True
                elif price_pref == 'premium' and beer_price_val > 15.0: passes_price_filter = True
            
            if passes_price_filter:
                temp_list.append(beer)
            # Le birre con prezzo non valido o non corrispondente al range vengono escluse
            # a meno che la preferenza non fosse "any" (gestita implicitamente non filtrando)
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
                    # Assicurati che rating_data sia un dizionario e average sia un numero
                    if isinstance(rating_data, dict) and isinstance(rating_data.get('average'), (int, float)):
                        if rating_data['average'] >= min_r:
                            temp_list.append(beer)
                filtered_list = temp_list
            else:
                feedback_messages.append("⚠️ Valutazione minima non valida (1-5). Filtro non applicato.")
        except ValueError:
            feedback_messages.append("⚠️ Valore per valutazione minima non numerico. Filtro non applicato.")

    # Feedback per le altre preferenze (non usate per filtrare attivamente i dati dall'API attuale)
    flavor_map = {'amaro': "Amaro", 'dolce': "Dolce", 'agrumato': "Agrumato/Fruttato", 'tostato': "Tostato"}
    if preferences.get('flavor_profile') and preferences.get('flavor_profile') != 'any':
        feedback_messages.append(f"👍 Profilo sapore: '{flavor_map.get(preferences.get('flavor_profile'), preferences.get('flavor_profile'))}'. Ottima scelta!")
    
    alcohol_map = {'leggera': "Leggera", 'media': "Media", 'forte': "Forte"}
    if preferences.get('alcohol_pref') and preferences.get('alcohol_pref') != 'any':
        feedback_messages.append(f"🍺 Gradazione '{alcohol_map.get(preferences.get('alcohol_pref'), preferences.get('alcohol_pref'))}': L'API attuale non mi dà questo dettaglio, ma è una tua indicazione di gusto!")

    food_pairing_text = preferences.get('food_pairing_text','').strip()
    if food_pairing_text:
        style_chosen_key = preferences.get('style', 'any')
        style_map = {"ale": "Ale", "stout": "Stout", "red_ale": "Red Ale", "any": "qualsiasi stile"}
        style_chosen_display = style_map.get(style_chosen_key, style_chosen_key.replace('_', ' ').title())
        feedback_messages.append(f"🍕 Per l'abbinamento con '{food_pairing_text}': le birre tipo '{style_chosen_display}' di solito sono un'ottima compagnia!")
    
    origin_country_preference = preferences.get('origin_text', '').strip()
    origin_choice_made = preferences.get('origin_q') == 'yes'
    if origin_choice_made and origin_country_preference:
        feedback_messages.append(f"🌍 Preferenza Paese: '{origin_country_preference}'. Bello! Purtroppo, l'API che usiamo non mi dice da dove vengono le birre, quindi non posso usarlo come filtro. Ma è un ottimo spunto!")
    elif origin_choice_made and not origin_country_preference:
        feedback_messages.append("🌍 Hai indicato una preferenza per l'origine ma non specificato un paese. In ogni caso, con l'attuale API non potrei filtrare per questo criterio.")

    occasion_map = {'relax': "Relax", 'party': "Festa", 'aperitivo': "Aperitivo", 'meal': "Pasto"}
    if preferences.get('occasion') and preferences.get('occasion') != 'any':
        feedback_messages.append(f"🎉 Occasione '{occasion_map.get(preferences.get('occasion'), preferences.get('occasion'))}': speriamo queste birre siano perfette!")

    adventure_map = {'classic': "😎 Classico, vai sul sicuro!", 'curious': "🧐 Curioso/a di provare cose nuove? Bene!", 'daredevil': "🤘 Modalità spericolata? Vediamo!"}
    if preferences.get('adventure_level') and preferences.get('adventure_level') != 'any': # 'any' non dovrebbe esserci ma per sicurezza
        feedback_messages.append(adventure_map.get(preferences.get('adventure_level'), "Scelta avventurosa!"))

    intensity_map = {'delicate': "Delicata", 'medium': "Media", 'intense': "Intensa"}
    if preferences.get('flavor_intensity') and preferences.get('flavor_intensity') != 'any':
        feedback_messages.append(f"💥 Intensità sapore '{intensity_map.get(preferences.get('flavor_intensity'), preferences.get('flavor_intensity'))}'. Buona dritta per te!")
    
    body_map = {'light': "💧 Leggera e scorrevole", 'medium': "👌 Media consistenza", 'full': "🏋️‍♀️ Corposa e piena"}
    if preferences.get('body_preference') and preferences.get('body_preference') != 'any':
        feedback_messages.append(f"🥤 Corpo '{body_map.get(preferences.get('body_preference'), preferences.get('body_preference'))}'. Info utile!")
    
    color_map = {'light': "Chiara/Bionda", 'amber': "Ambrata/Rossa", 'dark': "Scura/Nera"}
    if preferences.get('color_preference') and preferences.get('color_preference') != 'any':
        color_pref = preferences.get('color_preference')
        style_feedback = ""
        current_style = preferences.get('style')
        if current_style == 'stout' and color_pref != 'dark': style_feedback = " (Interessante, dato che le Stout sono tipicamente scure!)"
        elif current_style == 'red_ale' and color_pref != 'amber': style_feedback = " (Curioso, le Red Ale tendono all'ambrato!)"
        feedback_messages.append(f"🎨 Colore '{color_map.get(color_pref, color_pref)}'{style_feedback}. Dipende molto dallo stile!")
    
    def get_rating_for_sort(beer_item):
        # Assicurati che beer_item sia un dizionario e abbia 'rating' che è un dizionario con 'average'
        if isinstance(beer_item, dict) and isinstance(beer_item.get('rating'), dict) and isinstance(beer_item['rating'].get('average'), (int, float)):
            return beer_item['rating']['average']
        return 0 # Ritorna 0 se la struttura non è come attesa, così va in fondo

    # Filtra ulteriormente per assicurare che solo dizionari validi vengano ordinati
    valid_items_for_sort = [item for item in filtered_list if isinstance(item, dict)]
    valid_items_for_sort.sort(key=get_rating_for_sort, reverse=True)
    filtered_list = valid_items_for_sort

    return filtered_list, feedback_messages

@app.route('/', methods=['GET', 'POST'])
def index():
    suggestions = []
    feedback = []
    form_data_retained = {} # Per ripopolare il form con le scelte precedenti

    try:
        if request.method == 'POST':
            form_data_retained = request.form.to_dict() 
            style_choice = form_data_retained.get('style', 'any')
            
            # Avvolgi fetch_beers_from_api in un try-except per maggiore robustezza
            try:
                all_beers_data = fetch_beers_from_api(style_choice)
            except Exception as e_fetch:
                # Questo print sarà visibile solo nei log del server (es. terminale locale o log di Render)
                print(f"ERRORE CRITICO durante fetch_beers_from_api: {e_fetch}")
                all_beers_data = [] # Assicura che sia una lista vuota in caso di errore grave
                feedback.append("☠️ Ops! C'è stato un problema serissimo nel recuperare i dati delle birre. Il capo tecnico è stato avvisato (speriamo!). Riprova più tardi.")

            if all_beers_data: # Prosegui solo se all_beers_data non è None e non è vuoto
                # Assicurati che all_beers_data contenga solo dizionari prima di filtrare
                valid_beers_data_for_filter = [b for b in all_beers_data if isinstance(b, dict)]
                
                if not valid_beers_data_for_filter and all_beers_data: # Se c'erano dati ma nessuno valido
                    feedback.append("🤔 I dati ricevuti dall'API delle birre erano un po' strani. Non sono riuscito a processarli.")

                suggestions, filter_feedback = filter_beers(valid_beers_data_for_filter, form_data_retained)
                feedback.extend(filter_feedback) # Aggiungi i feedback dal filtro
                
                if suggestions:
                    # Se meno di 5 suggerimenti, mostrali tutti. Altrimenti, i primi (fino a 7).
                    if len(suggestions) >= 5:
                        suggestions = suggestions[:min(len(suggestions), 7)] 
                    # Se meno di 5, 'suggestions' contiene già tutti quelli trovati (nessuna azione necessaria)
                
                # Aggiungi un messaggio se non ci sono suggerimenti MA c'erano dati validi dall'API
                # E non ci sono già altri messaggi di feedback che spiegano la situazione (es. errori di filtro)
                if not suggestions and valid_beers_data_for_filter and not filter_feedback and not any("☠️" in msg for msg in feedback):
                    feedback.append("🤔 Non ho trovato birre che corrispondono esattamente ai tuoi filtri. Prova ad allargare un po' la ricerca!")
            
            elif not feedback: # Se all_beers_data è vuoto e non ci sono già messaggi di errore API
                feedback.append("🔎 Non ho trovato birre per lo stile selezionato o l'API non ha risposto. Prova un altro stile o più tardi.")
        
    except Exception as e:
        # Log dell'errore generale lato server (visibile nei log di Render o nel tuo terminale)
        print(f"ERRORE NON GESTITO nella route index: {e}")
        # Messaggio generico per l'utente
        feedback.append("🔧 Ops! Qualcosa è andato storto da questa parte del bancone. Il barista sta cercando di risolvere. Riprova tra un attimo.")
        # Pulisci i suggerimenti in caso di errore grave per non mostrare dati potenzialmente corrotti
        suggestions = [] 
        # Ripopola il form con i dati inviati se disponibili, altrimenti vuoto
        form_data_retained = request.form.to_dict() if request.method == 'POST' else {}

    return render_template('index.html', suggestions=suggestions, feedback=feedback, form_data=form_data_retained)

# Questo blocco serve solo quando esegui il file direttamente con 'python app.py'
# per testare localmente. Gunicorn (usato da Render) non lo esegue.
if __name__ == '__main__':
    app.run(debug=True)