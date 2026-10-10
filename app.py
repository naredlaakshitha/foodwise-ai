import os, re, json, secrets, hmac
from datetime import datetime, date, timedelta
from functools import wraps
from itertools import combinations
from pathlib import Path

import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='customer')
    organization_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default='')
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class FoodItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default='')
    category = db.Column(db.String(60), default='Main')
    cuisine = db.Column(db.String(60), default='Indian')
    meal_type = db.Column(db.String(30), default='Lunch')
    price = db.Column(db.Float, nullable=False)
    vegetarian = db.Column(db.Boolean, default=True)
    ingredients = db.Column(db.Text, default='')
    allergens = db.Column(db.Text, default='')
    tags = db.Column(db.Text, default='')
    available = db.Column(db.Boolean, default=True)
    image_url = db.Column(db.String(500), default='')
    @property
    def ingredient_list(self): return [x.strip().lower() for x in (self.ingredients or '').split(',') if x.strip()]
    @property
    def allergen_list(self): return [x.strip().lower() for x in (self.allergens or '').split(',') if x.strip()]
    @property
    def tag_list(self): return [x.strip().lower() for x in (self.tags or '').split(',') if x.strip()]

class MealPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    diet = db.Column(db.String(30), default='any')
    allergies = db.Column(db.Text, default='')
    dislikes = db.Column(db.Text, default='')
    budget = db.Column(db.Float, default=200)
    cuisine = db.Column(db.String(60), default='any')
    meal_type = db.Column(db.String(30), default='Dinner')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(30), default='Confirmed')
    payment_method = db.Column(db.String(30), default='Cash on Delivery')
    payment_status = db.Column(db.String(30), default='Pending')
    total = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan')

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    food_id = db.Column(db.Integer, db.ForeignKey('food_item.id'), nullable=True)
    food_name = db.Column(db.String(120), nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

class InventoryRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    item_name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0)
    unit = db.Column(db.String(20), default='portions')
    low_stock_threshold = db.Column(db.Float, default=5)
    expiry_date = db.Column(db.Date, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DemandHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    food_name = db.Column(db.String(120), nullable=False)
    demand_date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)

class SurplusListing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    food_name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    prepared_at = db.Column(db.DateTime, nullable=False)
    collection_deadline = db.Column(db.DateTime, nullable=False)
    storage_conditions = db.Column(db.String(250), nullable=False)
    notes = db.Column(db.Text, default='')
    status = db.Column(db.String(30), default='Available')
    safety_confirmed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DonationRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('surplus_listing.id'), nullable=False)
    listing = db.relationship('SurplusListing')
    organization_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    pickup_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(30), default='Requested')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    food_id = db.Column(db.Integer, db.ForeignKey('food_item.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id','food_id','order_id', name='unique_review_per_order_item'),)

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles: abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return deco

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.getenv('SECRET_KEY', 'dev-only-change-this-secret'), SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///foodwise.db'), SQLALCHEMY_TRACK_MODIFICATIONS=False, MAX_CONTENT_LENGTH=5*1024*1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','0')=='1')
    if test_config: app.config.update(test_config)
    db.init_app(app); login_manager.init_app(app)

    @app.before_request
    def protect_state_changes():
        if request.method == 'POST' and request.endpoint != 'chat':
            expected=session.get('_csrf_token','')
            supplied=request.form.get('_csrf_token','') or request.headers.get('X-CSRFToken','')
            if not expected or not supplied or not hmac.compare_digest(expected, supplied):
                abort(400, description='Security token missing or invalid. Refresh the page and try again.')

    def owned_restaurant():
        return Restaurant.query.filter_by(owner_id=current_user.id).first()

    @app.context_processor
    def inject_globals():
        if '_csrf_token' not in session: session['_csrf_token']=secrets.token_urlsafe(32)
        return {'today': date.today(), 'timedelta': timedelta, 'money': lambda n: f'₹{n:,.0f}', 'csrf_token': lambda: session.get('_csrf_token','')}

    @app.route('/')
    def index():
        foods = FoodItem.query.filter_by(available=True).order_by(FoodItem.id).limit(6).all()
        return render_template('index.html', foods=foods)

    @app.route('/register', methods=['GET','POST'])
    def register():
        if request.method == 'POST':
            name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); password=request.form.get('password',''); role=request.form.get('role','customer')
            if role not in ('customer','restaurant','organization'): flash('Please choose a valid account type.','danger')
            elif not name or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$',email): flash('Enter your name and a valid email.','danger')
            elif len(password)<8: flash('Password must contain at least 8 characters.','danger')
            elif User.query.filter_by(email=email).first(): flash('That email is already registered.','danger')
            else:
                user=User(name=name,email=email,role=role,organization_verified=False); user.set_password(password); db.session.add(user); db.session.flush()
                if role=='restaurant': db.session.add(Restaurant(name=f"{name}'s Kitchen", description='Manage your menu and reduce food waste.', owner_id=user.id))
                if role=='customer': db.session.add(MealPreference(user_id=user.id))
                db.session.commit(); login_user(user); flash('Welcome to FoodWise AI!','success'); return redirect(url_for('dashboard'))
        return render_template('auth.html', mode='register')

    @app.route('/login', methods=['GET','POST'])
    def login():
        if request.method=='POST':
            user=User.query.filter_by(email=request.form.get('email','').strip().lower()).first()
            if user and user.check_password(request.form.get('password','')):
                login_user(user); return redirect(url_for('dashboard'))
            flash('Email or password is incorrect.','danger')
        return render_template('auth.html', mode='login')

    @app.route('/logout')
    @login_required
    def logout(): logout_user(); return redirect(url_for('index'))

    @app.route('/dashboard')
    @login_required
    def dashboard():
        if current_user.role=='restaurant': return redirect(url_for('restaurant_dashboard'))
        if current_user.role=='organization': return redirect(url_for('rescue'))
        orders=Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).limit(5).all()
        pref=MealPreference.query.filter_by(user_id=current_user.id).first()
        return render_template('customer_dashboard.html', orders=orders, pref=pref, foods=FoodItem.query.filter_by(available=True).all())

    @app.route('/menu')
    def menu():
        query=request.args.get('q','').strip(); category=request.args.get('category',''); diet=request.args.get('diet','')
        foods=FoodItem.query.filter_by(available=True).all()
        if query: foods=[f for f in foods if query.lower() in f.name.lower() or query.lower() in f.ingredients.lower() or query.lower() in f.cuisine.lower()]
        if category: foods=[f for f in foods if f.category==category]
        if diet=='veg': foods=[f for f in foods if f.vegetarian]
        if diet=='nonveg': foods=[f for f in foods if not f.vegetarian]
        return render_template('menu.html', foods=foods, query=query, category=category, diet=diet)

    def preferences_from_form(user_id):
        pref=MealPreference.query.filter_by(user_id=user_id).first()
        if not pref: pref=MealPreference(user_id=user_id); db.session.add(pref)
        pref.diet=request.form.get('diet','any'); pref.allergies=request.form.get('allergies','')[:500]; pref.dislikes=request.form.get('dislikes','')[:500]
        try: pref.budget=max(0,min(100000,float(request.form.get('budget',200))))
        except ValueError: pref.budget=200
        pref.cuisine=request.form.get('cuisine','any'); pref.meal_type=request.form.get('meal_type','Dinner'); db.session.commit(); return pref

    def recommend_foods(diet='any', allergies='', dislikes='', budget=200, cuisine='any', meal_type='any', query=''):
        allergens={x.strip().lower() for x in re.split(r'[,;]',allergies) if x.strip()}; dislikes={x.strip().lower() for x in re.split(r'[,;]',dislikes) if x.strip()}
        result=[]
        for f in FoodItem.query.filter_by(available=True).all():
            if diet=='vegetarian' and not f.vegetarian: continue
            if diet=='non-vegetarian' and f.vegetarian: continue
            if f.price>budget: continue
            # Exclude declared allergens if they appear in either declared allergens or ingredients.
            if any(a in f.allergen_list or any(a in ing for ing in f.ingredient_list) for a in allergens): continue
            if any(any(d in ing for ing in f.ingredient_list) or d in f.name.lower() for d in dislikes): continue
            score=0; reasons=[]
            if cuisine.lower() not in ('','any'):
                if cuisine.lower() in f.cuisine.lower(): score+=3; reasons.append(f"matches your {f.cuisine} cuisine preference")
                else: score-=1
            if meal_type.lower() not in ('','any'):
                if meal_type.lower()==f.meal_type.lower(): score+=2; reasons.append(f"fits your {f.meal_type.lower()} meal")
            if f.price<=budget: score+=1; reasons.append(f"fits your ₹{budget:.0f} budget")
            if diet=='vegetarian' and f.vegetarian: reasons.append('matches your vegetarian preference')
            if query and query.lower() in (f.name+' '+f.ingredients+' '+f.cuisine).lower(): score+=4; reasons.append('matches your request')
            if not reasons: reasons=['available now and within budget']
            result.append({'food':f,'score':score,'reasons':reasons})
        result.sort(key=lambda x:(x['score'],-x['food'].price),reverse=True)
        return result

    @app.route('/recommendations', methods=['GET','POST'])
    @login_required
    def recommendations():
        pref=MealPreference.query.filter_by(user_id=current_user.id).first() if current_user.role=='customer' else None
        if request.method=='POST': pref=preferences_from_form(current_user.id)
        values={'diet':pref.diet if pref else 'any','allergies':pref.allergies if pref else '', 'dislikes':pref.dislikes if pref else '', 'budget':pref.budget if pref else 200,'cuisine':pref.cuisine if pref else 'any','meal_type':pref.meal_type if pref else 'Dinner'}
        results=recommend_foods(**values)
        return render_template('recommendations.html', results=results, values=values)

    @app.route('/planner', methods=['GET','POST'])
    def planner():
        foods=FoodItem.query.filter_by(available=True).all(); plan=[]; budget=200; meal_type='Dinner'; diet='any'
        if request.method=='POST':
            try: budget=max(0,min(100000,float(request.form.get('budget','200'))))
            except ValueError: budget=200
            meal_type=request.form.get('meal_type','Dinner'); diet=request.form.get('diet','any')
            foods=[f for f in foods if f.price<=budget and (meal_type=='any' or f.meal_type.lower()==meal_type.lower()) and (diet=='any' or (diet=='vegetarian' and f.vegetarian) or (diet=='non-vegetarian' and not f.vegetarian))]
            # Greedy by price gives a clear, deterministic plan; enforce total server-side.
            foods.sort(key=lambda f:f.price)
            total=0
            for food in foods:
                if total+food.price<=budget and len(plan)<4: plan.append(food); total+=food.price
            if not plan: flash('No available items fit those filters and budget. Try increasing the budget.','warning')
        total=sum(f.price for f in plan)
        return render_template('planner.html', plan=plan, budget=budget, meal_type=meal_type, diet=diet, total=total)

    @app.route('/scanner', methods=['GET','POST'])
    def scanner():
        result=None
        if request.method=='POST':
            file=request.files.get('photo')
            if not file or not file.filename: flash('Choose a food image to continue.','warning')
            else:
                # Honest fallback: no pretrained food model bundled; do not pretend classification occurred.
                result={'filename':file.filename,'message':'Food recognition model is not installed in this demo. Image classification is unavailable; browse the menu or use the assistant to search by food name.','predictions':[]}
        return render_template('scanner.html', result=result)

    @app.route('/assistant', methods=['GET','POST'])
    def assistant(): return render_template('assistant.html')

    @app.route('/api/chat', methods=['POST'])
    def chat():
        data=request.get_json(silent=True) or {}; msg=str(data.get('message',''))[:500].strip(); low=msg.lower()
        if not msg: return jsonify(reply='Tell me what kind of meal you are looking for.', foods=[])
        diet='vegetarian' if any(x in low for x in ['vegetarian','veg ',' veg','plant-based']) else ('non-vegetarian' if any(x in low for x in ['non-veg','non vegetarian','chicken','fish','meat']) else 'any')
        budget_match=re.search(r'(?:under|below|within|budget(?: of)?|₹|rs\.?\s*)(?:₹|rs\.?\s*)?(\d{2,6})',low)
        budget=float(budget_match.group(1)) if budget_match else 100000
        allergies='peanuts' if 'peanut' in low else ''
        cuisine=next((c for c in ['Indian','Italian','Chinese','Mexican'] if c.lower() in low),'any')
        meal=next((m for m in ['Breakfast','Lunch','Dinner','Snack'] if m.lower() in low),'any')
        foods=recommend_foods(diet=diet,allergies=allergies,budget=budget,cuisine=cuisine,meal_type=meal,query=msg)
        popular='popular' in low or 'most ordered' in low
        if popular:
            counts={}
            for oi in OrderItem.query.all(): counts[oi.food_id]=counts.get(oi.food_id,0)+oi.quantity
            foods.sort(key=lambda x:counts.get(x['food'].id,0),reverse=True)
        payload=[{'id':x['food'].id,'name':x['food'].name,'price':x['food'].price,'reason':', '.join(x['reasons'][:2])} for x in foods[:5]]
        if payload: reply=f"I found {len(payload)} available match(es)" + (f" under ₹{budget:.0f}" if budget<100000 else '') + ". These are rule-based suggestions, not medical or nutrition advice."
        else: reply='I could not find an available item matching those constraints. Try a larger budget or different preferences.'
        if allergies: reply+=' I excluded menu items whose recorded ingredients/allergens mention peanuts; please verify allergen information with the restaurant before ordering.'
        return jsonify(reply=reply,foods=payload)

    @app.route('/cart')
    @login_required
    def cart():
        cart_data=request.args.get('items','')
        return render_template('cart.html', foods=FoodItem.query.filter_by(available=True).all())

    @app.route('/checkout', methods=['POST'])
    @login_required
    def checkout():
        data=request.get_json(silent=True) or {}; items=data.get('items',[]); payment=data.get('payment','Cash on Delivery')
        if payment not in ('Cash on Delivery','Simulated Payment'): return jsonify(error='Invalid payment method.'),400
        if not isinstance(items,list) or not items: return jsonify(error='Your cart is empty.'),400
        try:
            quantities={}
            for it in items:
                fid=int(it.get('id')); qty=int(it.get('quantity'))
                if qty<1 or qty>20: raise ValueError
                quantities[fid]=quantities.get(fid,0)+qty
            if any(q>20 for q in quantities.values()): raise ValueError
        except (ValueError,TypeError,AttributeError): return jsonify(error='Invalid item or quantity.'),400
        foods=FoodItem.query.filter(FoodItem.id.in_(quantities),FoodItem.available.is_(True)).all()
        if len(foods)!=len(quantities): return jsonify(error='One or more items are unavailable. Refresh your menu.'),409
        total=round(sum(f.price*quantities[f.id] for f in foods),2)
        if total<=0 or total>1000000: return jsonify(error='Invalid order total.'),400
        try:
            order=Order(user_id=current_user.id,total=total,payment_method=payment,payment_status='Simulated - not charged' if payment=='Simulated Payment' else 'Pending')
            db.session.add(order); db.session.flush()
            for f in foods: db.session.add(OrderItem(order_id=order.id,food_id=f.id,food_name=f.name,unit_price=f.price,quantity=quantities[f.id]))
            db.session.commit()
        except Exception:
            db.session.rollback(); app.logger.exception('Checkout failed'); return jsonify(error='Could not save order. Please try again.'),500
        return jsonify(ok=True,order_id=order.id,total=total,redirect=url_for('order_detail',order_id=order.id))

    @app.route('/orders')
    @login_required
    def orders():
        records=Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
        return render_template('orders.html', orders=records)

    @app.route('/orders/<int:order_id>')
    @login_required
    def order_detail(order_id):
        order=Order.query.get_or_404(order_id)
        if order.user_id!=current_user.id and current_user.role!='restaurant': abort(403)
        return render_template('order_detail.html', order=order)

    @app.route('/restaurant/orders/<int:order_id>/status', methods=['POST'])
    @role_required('restaurant')
    def update_order_status(order_id):
        order=Order.query.get_or_404(order_id); rest=owned_restaurant()
        if not any(item.food_id and db.session.get(FoodItem,item.food_id) and db.session.get(FoodItem,item.food_id).restaurant_id==rest.id for item in order.items): abort(403)
        status=request.form.get('status')
        if status not in ('Preparing','Out for delivery','Completed','Cancelled'): abort(400)
        order.status=status; db.session.commit(); flash('Order status updated.','success'); return redirect(url_for('restaurant_dashboard'))

    @app.route('/reviews', methods=['GET','POST'])
    @role_required('customer')
    def reviews():
        if request.method=='POST':
            try: food_id=int(request.form.get('food_id')); order_id=int(request.form.get('order_id')); rating=int(request.form.get('rating'))
            except ValueError: flash('Please select a valid order, food, and rating.','danger'); return redirect(url_for('reviews'))
            order=Order.query.filter_by(id=order_id,user_id=current_user.id,status='Completed').first()
            if not order or not any(i.food_id==food_id for i in order.items): flash('Reviews are available only for items in completed orders.','danger')
            elif rating not in range(1,6): flash('Rating must be between 1 and 5.','danger')
            elif Review.query.filter_by(user_id=current_user.id,food_id=food_id,order_id=order_id).first(): flash('You already reviewed this item for that order.','warning')
            else: db.session.add(Review(user_id=current_user.id,food_id=food_id,order_id=order_id,rating=rating,comment=request.form.get('comment','')[:500])); db.session.commit(); flash('Thanks for sharing your feedback!','success')
        completed=Order.query.filter_by(user_id=current_user.id,status='Completed').all()
        return render_template('reviews.html', orders=completed)

    @app.route('/restaurant')
    @role_required('restaurant')
    def restaurant_dashboard():
        rest=owned_restaurant()
        if not rest: abort(403)
        foods=FoodItem.query.filter_by(restaurant_id=rest.id).all(); inventory=InventoryRecord.query.filter_by(restaurant_id=rest.id).all()
        orders=Order.query.join(OrderItem).join(FoodItem,OrderItem.food_id==FoodItem.id).filter(FoodItem.restaurant_id==rest.id).distinct().order_by(Order.created_at.desc()).limit(10).all()
        return render_template('restaurant.html', restaurant=rest, foods=foods, inventory=inventory, orders=orders)

    @app.route('/restaurant/menu/add', methods=['POST'])
    @role_required('restaurant')
    def add_food():
        rest=owned_restaurant()
        try: price=float(request.form.get('price','0'))
        except ValueError: price=0
        name=request.form.get('name','').strip()
        if not name or price<=0 or price>100000: flash('Enter a name and a valid positive price.','danger')
        else:
            food=FoodItem(restaurant_id=rest.id,name=name,description=request.form.get('description','')[:500],category=request.form.get('category','Main'),cuisine=request.form.get('cuisine','Indian'),meal_type=request.form.get('meal_type','Lunch'),price=price,vegetarian=request.form.get('vegetarian')=='yes',ingredients=request.form.get('ingredients','')[:500],allergens=request.form.get('allergens','')[:500],tags=request.form.get('tags','')[:250],available=True)
            db.session.add(food); db.session.commit(); flash('Menu item added.','success')
        return redirect(url_for('restaurant_dashboard'))

    @app.route('/restaurant/menu/<int:food_id>/toggle', methods=['POST'])
    @role_required('restaurant')
    def toggle_food(food_id):
        food=FoodItem.query.get_or_404(food_id); rest=owned_restaurant()
        if food.restaurant_id!=rest.id: abort(403)
        food.available=not food.available; db.session.commit(); flash('Availability updated.','success'); return redirect(url_for('restaurant_dashboard'))

    @app.route('/restaurant/inventory/add', methods=['POST'])
    @role_required('restaurant')
    def add_inventory():
        rest=owned_restaurant(); name=request.form.get('item_name','').strip()
        try: qty=float(request.form.get('quantity','0')); threshold=float(request.form.get('threshold','5'))
        except ValueError: qty=-1; threshold=-1
        expiry=None
        try:
            if request.form.get('expiry_date'): expiry=date.fromisoformat(request.form['expiry_date'])
        except ValueError: pass
        if not name or qty<0 or threshold<0: flash('Enter valid inventory details.','danger')
        else: db.session.add(InventoryRecord(restaurant_id=rest.id,item_name=name,quantity=qty,unit=request.form.get('unit','portions'),low_stock_threshold=threshold,expiry_date=expiry)); db.session.commit(); flash('Inventory record saved.','success')
        return redirect(url_for('restaurant_dashboard'))

    @app.route('/restaurant/inventory/<int:record_id>/update', methods=['POST'])
    @role_required('restaurant')
    def update_inventory(record_id):
        rec=InventoryRecord.query.get_or_404(record_id); rest=owned_restaurant()
        if rec.restaurant_id!=rest.id: abort(403)
        try: rec.quantity=max(0,float(request.form.get('quantity','0')))
        except ValueError: flash('Quantity must be numeric.','danger'); return redirect(url_for('restaurant_dashboard'))
        db.session.commit(); return redirect(url_for('restaurant_dashboard'))

    @app.route('/forecast')
    @role_required('restaurant')
    def forecast():
        rest=owned_restaurant(); history=DemandHistory.query.filter_by(restaurant_id=rest.id).order_by(DemandHistory.demand_date).all()
        # Include real completed/confirmed order items as historical demand observations by date.
        orders=Order.query.join(OrderItem).join(FoodItem,OrderItem.food_id==FoodItem.id).filter(FoodItem.restaurant_id==rest.id).all()
        obs=[{'date':o.created_at.date(),'food':oi.food_name,'qty':oi.quantity} for o in orders for oi in o.items if oi.food_id and db.session.get(FoodItem,oi.food_id) and db.session.get(FoodItem,oi.food_id).restaurant_id==rest.id]
        obs += [{'date':h.demand_date,'food':h.food_name,'qty':h.quantity} for h in history]
        frame=pd.DataFrame(obs,columns=['date','food','qty'])
        forecast_rows=[]; chart_labels=[]; chart_actual=[]; chart_pred=[]; method='Baseline (insufficient historical data)'
        if not frame.empty:
            daily=frame.groupby('date')['qty'].sum().sort_index()
            last=daily.tail(7).tolist(); baseline=max(0,round(sum(last)/len(last))) if last else 0
            # Fit only when there are enough observations and date variation; no fabricated accuracy claim.
            if len(daily)>=10:
                ds=pd.DataFrame({'day':[(d-daily.index.min()).days for d in daily.index],'qty':daily.values})
                from sklearn.ensemble import RandomForestRegressor
                model=RandomForestRegressor(n_estimators=80,random_state=42,max_depth=4)
                model.fit(ds[['day']],ds['qty'])
                future_day=(date.today()-daily.index.min()).days+1
                prediction=max(0,round(float(model.predict(pd.DataFrame({'day':[future_day]}))[0])))
                method='Random Forest regression trained on recorded daily totals (exploratory; not validated)'
            else: prediction=baseline
            for food_name, group in frame.groupby('food'):
                vals=group.sort_values('date')['qty'].tail(7).tolist(); pred=round(sum(vals)/len(vals)) if vals else 0
                forecast_rows.append({'name':food_name,'historical':sum(vals),'forecast':max(0,pred),'method':'7-observation mean baseline'})
            chart_labels=[d.strftime('%d %b') for d in daily.index[-14:]]; chart_actual=[int(x) for x in daily.values[-14:]]; chart_pred=[None]*max(0,len(chart_labels)-1)+([prediction] if chart_labels else [])
        else: prediction=0
        return render_template('forecast.html', rows=forecast_rows, method=method, prediction=prediction, labels=json.dumps(chart_labels), actual=json.dumps(chart_actual), predicted=json.dumps(chart_pred))

    @app.route('/rescue', methods=['GET','POST'])
    @login_required
    def rescue():
        if request.method=='POST':
            if current_user.role!='restaurant': abort(403)
            rest=owned_restaurant()
            try: qty=int(request.form.get('quantity')); prepared=datetime.fromisoformat(request.form.get('prepared_at')); deadline=datetime.fromisoformat(request.form.get('collection_deadline'))
            except (ValueError,TypeError): flash('Check quantity and date/time fields.','danger'); return redirect(url_for('rescue'))
            name=request.form.get('food_name','').strip(); storage=request.form.get('storage_conditions','').strip()
            if not name or not storage or qty<1 or prepared>datetime.now() or deadline<=datetime.now() or deadline<=prepared or request.form.get('safety_confirmed')!='yes': flash('Enter valid dates and quantity, and confirm that staff have assessed this food as safe and eligible for donation.','danger')
            else: db.session.add(SurplusListing(restaurant_id=rest.id,food_name=name,quantity=qty,prepared_at=prepared,collection_deadline=deadline,storage_conditions=storage,notes=request.form.get('notes','')[:500],safety_confirmed=True)); db.session.commit(); flash('Surplus listing created. Please continue to verify handling and safety requirements.','success')
            return redirect(url_for('rescue'))
        if current_user.role=='restaurant':
            rest=owned_restaurant(); listings=SurplusListing.query.filter_by(restaurant_id=rest.id).order_by(SurplusListing.created_at.desc()).all() if rest else []
            requests=DonationRequest.query.join(SurplusListing).filter(SurplusListing.restaurant_id==rest.id).all() if rest else []
        else:
            listings=SurplusListing.query.filter_by(status='Available').filter(SurplusListing.collection_deadline>datetime.now()).order_by(SurplusListing.collection_deadline).all(); requests=[]
        return render_template('rescue.html', listings=listings, requests=requests)

    @app.route('/rescue/<int:listing_id>/request', methods=['POST'])
    @role_required('organization')
    def request_donation(listing_id):
        if not current_user.organization_verified: flash('Your community organization must be verified before requesting donations. The demo community account is pre-verified.','danger'); return redirect(url_for('rescue'))
        listing=SurplusListing.query.get_or_404(listing_id)
        try: qty=int(request.form.get('quantity','0'))
        except ValueError: qty=0
        if listing.status!='Available' or listing.collection_deadline<=datetime.now() or qty<1 or qty>listing.quantity: flash('This listing is no longer available or quantity is invalid.','danger')
        elif DonationRequest.query.filter_by(listing_id=listing.id,organization_id=current_user.id,status='Requested').first(): flash('You already requested this listing.','warning')
        else: db.session.add(DonationRequest(listing_id=listing.id,organization_id=current_user.id,quantity=qty)); db.session.commit(); flash('Donation request sent. Pickup details are shared only after restaurant confirmation.','success')
        return redirect(url_for('rescue'))

    @app.route('/rescue/request/<int:request_id>/status', methods=['POST'])
    @role_required('restaurant')
    def donation_status(request_id):
        dr=DonationRequest.query.get_or_404(request_id); rest=owned_restaurant()
        if dr.listing.restaurant_id!=rest.id: abort(403)
        status=request.form.get('status')
        if status not in ('Accepted','Declined','Collected'): abort(400)
        if status=='Accepted' and dr.listing.status!='Available': flash('Listing is not available.','danger')
        else:
            dr.status=status
            if status=='Accepted': dr.listing.status='Reserved'
            if status=='Collected': dr.listing.status='Collected'
            db.session.commit(); flash('Donation status updated.','success')
        return redirect(url_for('rescue'))

    @app.route('/api/stats')
    @role_required('restaurant')
    def stats():
        rest=owned_restaurant(); foods=FoodItem.query.filter_by(restaurant_id=rest.id).count(); inv=InventoryRecord.query.filter_by(restaurant_id=rest.id).all()
        return jsonify(menu_items=foods, inventory_records=len(inv), low_stock=sum(x.quantity<=x.low_stock_threshold for x in inv), expiring_soon=sum(x.expiry_date and x.expiry_date<=date.today()+timedelta(days=2) for x in inv))

    @app.errorhandler(403)
    def forbidden(e): return render_template('error.html', code=403, message='You do not have permission to view this page.'),403
    @app.errorhandler(404)
    def missing(e): return render_template('error.html', code=404, message='We could not find that page.'),404

    with app.app_context():
        db.create_all()
        if app.config.get('SEED_DEMO', True): seed_demo()
    return app

def seed_demo():
    if User.query.filter_by(email='customer@foodwise.demo').first(): return
    customer=User(name='Demo Customer',email='customer@foodwise.demo',role='customer'); customer.set_password('Foodwise123!')
    owner=User(name='Demo Kitchen',email='restaurant@foodwise.demo',role='restaurant'); owner.set_password('Foodwise123!')
    org=User(name='Community Partner',email='community@foodwise.demo',role='organization',organization_verified=True); org.set_password('Foodwise123!')
    db.session.add_all([customer,owner,org]); db.session.flush()
    rest=Restaurant(name='Green Spoon Kitchen',description='Seasonal bowls, Indian comfort food, and smart surplus rescue.',owner_id=owner.id); db.session.add(rest); db.session.flush()
    db.session.add(MealPreference(user_id=customer.id))
    sample=[
      ('Paneer Millet Bowl','Millet, paneer, tomato, cucumber','milk','Bowl','Indian','Lunch',149,True,'high-protein,balanced'),
      ('Masala Veg Wrap','Wheat, potato, peas, tomato','gluten','Wrap','Indian','Lunch',99,True,'quick,vegetarian'),
      ('Chickpea Salad','Chickpeas, cucumber, tomato, lemon','', 'Salad','Mediterranean','Dinner',129,True,'fresh,vegan'),
      ('Peanut Noodle Bowl','Noodles, peanuts, soy, vegetables','peanuts,soy,gluten','Noodles','Chinese','Dinner',169,True,'spicy'),
      ('Chicken Rice Bowl','Chicken, rice, carrot, soy','soy','Bowl','Indian','Dinner',189,False,'popular'),
      ('Mushroom Pasta','Wheat, mushroom, cream, cheese','milk,gluten','Pasta','Italian','Dinner',179,True,'comfort'),
      ('Idli Sambar','Rice, lentil, vegetables','', 'Breakfast','South Indian','Breakfast',69,True,'classic,vegetarian'),
      ('Egg Frankie','Egg, wheat, onion, tomato','egg,gluten','Wrap','Indian','Snack',109,False,'quick'),
      ('Seasonal Fruit Cup','Apple, banana, papaya','', 'Snack','Indian','Snack',59,True,'vegan,fresh'),
      ('Lentil Khichdi','Rice, lentil, carrot, cumin','', 'Main','Indian','Dinner',119,True,'comfort,vegetarian')]
    for name,ingredients,allergens,category,cuisine,meal,price,veg,tags in sample:
        db.session.add(FoodItem(restaurant_id=rest.id,name=name,description='Freshly prepared with ingredient details listed for informed choices.',category=category,cuisine=cuisine,meal_type=meal,price=price,vegetarian=veg,ingredients=ingredients,allergens=allergens,tags=tags,image_url=''))
    db.session.add_all([InventoryRecord(restaurant_id=rest.id,item_name='Millet portions',quantity=4,unit='portions',low_stock_threshold=8,expiry_date=date.today()+timedelta(days=5)),InventoryRecord(restaurant_id=rest.id,item_name='Fresh tomatoes',quantity=2,unit='kg',low_stock_threshold=3,expiry_date=date.today()+timedelta(days=1)),InventoryRecord(restaurant_id=rest.id,item_name='Paneer',quantity=6,unit='kg',low_stock_threshold=2,expiry_date=date.today()+timedelta(days=3))])
    # Seed dated history to make the forecasting demo useful, explicitly synthetic demo data.
    for offset in range(14,0,-1):
        day=date.today()-timedelta(days=offset)
        for fname,base in [('Paneer Millet Bowl',8),('Masala Veg Wrap',12),('Chicken Rice Bowl',7),('Idli Sambar',15)]:
            db.session.add(DemandHistory(restaurant_id=rest.id,food_name=fname,demand_date=day,quantity=max(0,base+((offset*3+len(fname))%7)-3)))
    db.session.add(SurplusListing(restaurant_id=rest.id,food_name='Seasonal fruit cups (demo)',quantity=5,prepared_at=datetime.now()-timedelta(minutes=30),collection_deadline=datetime.now()+timedelta(hours=3),storage_conditions='Keep chilled; collect in insulated container',notes='Seeded demo listing; verify condition before collection.',safety_confirmed=True))
    db.session.commit()

app=create_app()
if __name__=='__main__': app.run(host='127.0.0.1',port=int(os.getenv('PORT','5000')),debug=os.getenv('FLASK_DEBUG','0')=='1')
