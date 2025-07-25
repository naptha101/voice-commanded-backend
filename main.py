import os
import spacy
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime

# --- App & Database Configuration ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'shopping.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- NLP Model Loading ---
# Load models for multilingual support.
# Make sure you have downloaded them:
# python -m spacy download en_core_web_sm
# python -m spacy download es_core_news_sm
nlp_models = {
    'en': spacy.load('en_core_web_sm'),
    'es': spacy.load('es_core_news_sm')
}

# --- Pre-defined Data for Smart Features ---
ITEM_CATEGORIES = {
    'milk': 'Dairy', 'cheese': 'Dairy', 'yogurt': 'Dairy', 'leche': 'Lácteos',
    'bread': 'Bakery', 'pan': 'Panadería',
    'apple': 'Produce', 'banana': 'Produce', 'manzana': 'Frutas',
    'chicken': 'Meat', 'pollo': 'Carne',
    'rice': 'Pantry', 'arroz': 'Despensa',
}

# NEW: Data for seasonal recommendations
SEASONAL_ITEMS = {
    'summer': ['watermelon', 'corn on the cob', 'iced tea'],
    'winter': ['oranges', 'soup mix', 'hot chocolate']
}

# NEW: Data for substitute suggestions
SUBSTITUTE_MAP = {
    'milk': ['almond milk', 'soy milk', 'oat milk'],
    'sugar': ['honey', 'stevia'],
    'leche': ['leche de almendras', 'leche de soya']
}

# NEW: Keywords for multilingual command processing
COMMAND_KEYWORDS = {
    'en': {'add': ['add', 'buy', 'get', 'want', 'need'], 'remove': ['remove', 'delete'], 'search': ['find', 'search']},
    'es': {'add': ['añadir', 'comprar', 'quiero', 'necesito'], 'remove': ['quitar', 'eliminar'], 'search': ['buscar', 'encontrar']}
}


# --- Database Models ---
class ShoppingItem(db.Model):
    """Represents an item currently on the user's list."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    quantity = db.Column(db.String(50), nullable=True, default='1')
    category = db.Column(db.String(50), nullable=False, default='General')
    added_on = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'quantity': self.quantity, 'category': self.category}

# NEW: Product catalog model for search functionality
class Product(db.Model):
    """Represents a product in the store's searchable catalog."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    brand = db.Column(db.String(100))
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False, default='General')

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'brand': self.brand, 'price': self.price, 'category': self.category}


# --- Helper Functions ---
def get_current_season():
    """Determines the current season for recommendations."""
    month = datetime.now().month
    if 3 <= month <= 5: return 'spring' # Adjusted for general use
    if 6 <= month <= 8: return 'summer'
    if 9 <= month <= 11: return 'autumn'
    return 'winter'

def categorize_item(item_name):
    """Assigns a category to an item based on keywords."""
    for keyword, category in ITEM_CATEGORIES.items():
        if keyword in item_name.lower():
            return category
    return 'General'

def process_command(text, lang='en'):
    """
    Processes transcribed text to extract intent, item, and quantity.
    Now supports multiple languages and search intent.
    """
    nlp = nlp_models.get(lang, nlp_models['en']) # Default to English if lang not supported
    keywords = COMMAND_KEYWORDS.get(lang, COMMAND_KEYWORDS['en'])
    doc = nlp(text.lower())
    
    action, item_name, quantity, price_filter = None, [], None, None

    # Determine action
    if any(token.lemma_ in keywords['add'] for token in doc): action = 'add'
    elif any(token.lemma_ in keywords['remove'] for token in doc): action = 'remove'
    elif any(token.lemma_ in keywords['search'] for token in doc): action = 'search'

    # Extract entities (item, quantity, price)
    for ent in doc.ents:
        if ent.label_ in ['PRODUCT', 'ORG', 'GPE']: item_name.append(ent.text)
        if ent.label_ in ['QUANTITY', 'CARDINAL']: quantity = ent.text
        if ent.label_ == 'MONEY':
            # Extract number from money entity (e.g., "$5", "under 10 dollars")
            price_digits = [token.text for token in ent if token.is_digit]
            if price_digits:
                price_filter = float(price_digits[0])

    # Fallback to find item name if no entity is found
    if not item_name:
        item_name = [token.text for token in doc if token.pos_ in ['NOUN', 'PROPN'] and not token.is_stop and not token.is_punct]
    
    final_item = ' '.join(item_name).strip()
    # Clean action words from the item name
    for verb_list in keywords.values():
        for verb in verb_list:
            final_item = final_item.replace(verb, '')

    return action, final_item.strip(), quantity or '1', price_filter

# --- API Routes ---
@app.route('/')
def index():
    """Renders a simple UI. Creates DB tables if they don't exist."""
    db.create_all()
    # NEW: Populate the product catalog with sample data on first run
    if not Product.query.first():
        sample_products = [
            Product(name='organic milk', brand='Happy Cow', price=4.50, category='Dairy'),
            Product(name='whole wheat bread', brand='Good Grains', price=3.20, category='Bakery'),
            Product(name='toothpaste', brand='Sparkle', price=2.99, category='Health'),
            Product(name='toothpaste', brand='FreshBreeze', price=5.50, category='Health'),
            Product(name='organic apples', brand='Orchard Fresh', price=6.00, category='Produce'),
            Product(name='soda', brand='FizzUp', price=1.50, category='Drinks'),
        ]
        db.session.bulk_save_objects(sample_products)
        db.session.commit()
    return "App is running succesfully on port 5000."







@app.route('/list', methods=['GET'])
def get_list():
    """Returns the current shopping list."""
    items = ShoppingItem.query.order_by(ShoppingItem.added_on.desc()).all()
    return jsonify([item.to_dict() for item in items])

# NEW: Endpoint for smart suggestions
@app.route('/suggestions', methods=['GET'])
def get_suggestions():
    """Provides smart suggestions based on season and purchase history."""
    # 1. Seasonal Suggestions
    season = get_current_season()
    seasonal = SEASONAL_ITEMS.get(season, [])
    
    # 2. History-Based Suggestions
    # Suggests top 3 most frequently bought items that aren't on the list now
    current_list_names = [item.name.lower() for item in ShoppingItem.query.all()]
    most_frequent = db.session.query(
        ShoppingItem.name, func.count(ShoppingItem.name).label('freq')
    ).group_by(ShoppingItem.name).order_by(func.count(ShoppingItem.name).desc()).limit(5).all()
    
    history_suggestions = [name for name, freq in most_frequent if name.lower() not in current_list_names]

    return jsonify({
        'seasonal_suggestions': seasonal,
        'frequently_bought': history_suggestions[:3] # Limit to top 3
    })

# NEW: Endpoint for voice-activated search
@app.route('/search', methods=['POST'])
def search_products():
    """Searches the product catalog based on a voice query."""
    data = request.get_json()
    text = data.get('text')
    lang = data.get('lang', 'en')
    if not text:
        return jsonify({'status': 'error', 'message': 'No text provided'}), 400

    _, item_name, _, max_price = process_command(text, lang)
    if not item_name:
        return jsonify({'status': 'error', 'message': 'Could not identify an item to search for.'}), 400

    query = Product.query.filter(Product.name.ilike(f'%{item_name}%'))
    if max_price:
        query = query.filter(Product.price <= max_price)
    
    results = query.all()
    return jsonify({
        'status': 'success',
        'search_query': text,
        'found_items': [product.to_dict() for product in results]
    })


@app.route('/voice-command', methods=['POST'])
def handle_voice_command():
    """Main endpoint to process add/remove commands."""
    data = request.get_json()
    text = data.get('text')
    lang = data.get('lang', 'en') # Accept language from the client
    if not text:
        return jsonify({'status': 'error', 'message': 'No text provided'}), 400

    action, item_name, quantity, _ = process_command(text, lang)

    if not action or not item_name:
        return jsonify({'status': 'error', 'message': 'Could not understand the command.'}), 400

    if action == 'add':
        # NEW: Check for substitutes
        substitutes = SUBSTITUTE_MAP.get(item_name.lower(), [])
        category = categorize_item(item_name)
        new_item = ShoppingItem(name=item_name.title(), quantity=quantity, category=category)
        db.session.add(new_item)
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': f'Added {item_name}.',
            'item': new_item.to_dict(),
            'substitute_suggestions': substitutes
        })
    
    elif action == 'remove':
        item_to_remove = ShoppingItem.query.filter(ShoppingItem.name.ilike(f'%{item_name}%')).first()
        if item_to_remove:
            db.session.delete(item_to_remove)
            db.session.commit()
            return jsonify({'status': 'success', 'message': f'Removed {item_name}.'})
        else:
            return jsonify({'status': 'error', 'message': f'Could not find {item_name} on the list.'}), 404
            
    return jsonify({'status': 'error', 'message': 'Action not recognized.'}), 400


@app.route('/item/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    """Deletes an item from the shopping list by its ID."""
    item_to_remove = ShoppingItem.query.get(item_id)
    if item_to_remove:
        db.session.delete(item_to_remove)
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': f'Removed {item_to_remove.name} from the list.'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': f'Item with ID {item_id} not found.'
        }), 404




if __name__ == '__main__':
    app.run(debug=True)