from flask import Flask, render_template, make_response, request, redirect
from pymongo import MongoClient
from datetime import datetime
from random import randint

app = Flask(__name__, template_folder = 'templates')

def create_database_connection():
    CONNECTION_STRING = 'mongodb://localhost'
    client = MongoClient(CONNECTION_STRING)
    return client['restaurant-app']

database = create_database_connection()
database['logs'].insert_one({ 'connection-time': datetime.now().__str__() })


# Normal user routes
# Route for Landing page
@app.route('/')
def landing_page():
    try:
        logged_in = bool(request.cookies.get('user_id'))
        if not logged_in: raise ValueError('Not logged in')
        id = request.cookies.get('user_id')
        if id[0] == 'r': return redirect('/restaurant')
        elif id[0] == 'm': return redirect('/manager')
        elif id[0] == 'd': return redirect('/delivery')
    except:
        logged_in = False
    return render_template('./main/index.html', **{ 'logged_in': logged_in})

@app.route('/select_user')
def select_user():
    return render_template('/main/select_user.html')

# Route for menu: Fetches menu items and displays them
@app.route('/menu')
def display_menu():
    try:
        user = database['users'].find_one({ '_id': request.cookies.get('user_id') })
        if user['_id'][0] != 'c': return redirect({ 'r': 'restaurant', 'm': 'manager', 'd': 'delivery' }[user['_id'][0]] + '/' )
    except:
        return redirect('/select_user')
    menu_database = database['menu-items'].find()
    menu_items = {}
    for item in menu_database:
        if item['restaurant'] not in menu_items:
            menu_items[item['restaurant']] = [item]
        else:
            menu_items[item['restaurant']].append(item)
    # print(menu_items.items())
    return render_template('./customer/menu.html', **{ 'menu_items': menu_items.items() })

# Route for displaying cart
@app.route('/cart')
def display_cart():
    try:
        user = database['users'].find_one({ '_id': request.cookies.get('user_id') })
        if not user: return redirect('/login')
    except:
        return redirect('/login')
    return render_template('./customer/cart.html')

# Route for placing order
@app.route('/place_order', methods=['POST'])
def place_order():
    # Fetch roder details from the page
    items = eval(request.data.decode())['items'].items()
    orders = {}
    for item in items:
        if item[1]['restaurant'] not in orders: 
            orders[item[1]['restaurant']] = { 'restaurant': item[1]['restaurant'], 'price': (item[1]['price'] * item[1]['qty']), 'order': [{ 'name': item[0], 'price': item[1]['price'], 'qty': item[1]['qty'] }] }
        else:
            orders[item[1]['restaurant']]['price'] += (item[1]['price'] * item[1]['qty'])
            orders[item[1]['restaurant']]['order'].append({ 'name': item[0], 'price': item[1]['price'], 'qty': item[1]['qty'] })
    # Save in the database
    user = database['users'].find_one({ '_id': request.cookies.get('user_id') })
    for order in orders:
        orders[order]['_id'] = order[:3] + ''.join([str(randint(0,9)) for i in range(5)])
        orders[order]['user'] = user['_id']
        orders[order]['status'] = 'Waiting for restaurant'
        orders[order]['price'] = orders[order]['price'] * 0.9 + 30
        database['orders'].insert_one(orders[order])
    # Send response to client
    return make_response(render_template('main/message.html', message = 'Order placed successfully'), 200)

# Route for displaying order placed
@app.route('/order_placed')
def order_placed():
    return render_template('/main/message.html', message='Your order has been placed successfully')

# Route for customer sign up page
@app.route('/signup', methods=['GET'])
def customer_signup_page():
    try:
        if request.cookies.get('user_id'): 
            return make_response(render_template('main/message.html', message = 'Already logged in'), 403)
        return render_template('customer/signup.html')
    except Exception as exception:
        return render_template('customer/signup.html')

# Route for customer sign up POST request
@app.route('/signup', methods=['POST'])
def customer_signup():
    user = {}
    # Fetch data from request
    user['_id'] = 'c-' + ''.join([str(randint(0, 9)) for i in range(8)])
    while database['users'].find_one({ '_id': user['_id'] }): user['_id'] = 'c-' + [str(randint(0, 9)) for i in range(8)].join('')
    user['name'] = request.form.get('name')
    user['email'] = request.form.get('email')
    if database['users'].find_one({ 'email': user['email'] }): return make_response('Email already exists', 403)
    user['address'] = request.form.get('address')
    user['phone'] = request.form.get('phone')
    user['password'] = request.form.get('password')
    # Save in database
    database['users'].insert_one(user)
    # Send response to customer
    response = redirect('/menu')
    response.set_cookie('user_id', user['_id'])
    return response

# Route for customer login page
@app.route('/login', methods=['GET'])
def customer_login_page():
    try:
        if request.cookies.get('user_id'): 
            return make_response('Already logged in', 403)
        return render_template('customer/login.html')
    except Exception as exception:
        return render_template('customer/login.html')

# Route for customer login POST request
@app.route('/login', methods=['POST'])
def customer_login():
    user = database['users'].find_one({ 'email': request.form.get('email'), 'password': request.form.get('password') })
    if user:
        response = redirect('/menu')
        response.set_cookie('user_id', user['_id'])
        return response
    else:
        return render_template('customer/login.html')

# Route for logout
@app.route('/logout')
def logout():
    response = make_response(render_template('main/message.html', message='Logged out successfully'))
    response.delete_cookie('user_id')
    return response

# Route for customer past orders
@app.route('/past_orders')
def customer_past_orders():
    try:
        request.cookies.get('user_id')
    except:
        return redirect('/login')
    orders = [order for order in database['orders'].find({ 'user': request.cookies.get('user_id') })]
    for order in orders:
        restaurant = database['users'].find_one({ 'name': order['restaurant'] }) 
        order['restaurant_id'] = restaurant['_id'] if restaurant else '404'
    return render_template('/customer/past_orders.html', **{ 'orders': orders, 'self_user': request.cookies.get('user_id') })

# Route for rating users
@app.route('/rate', methods=['POST'])
def rate():
    data = eval(request.data.decode())
    database['ratings'].insert_one({ 'from': data['from'], 'to': data['to'], 'rating': data['rating'] })
    return make_response('Rated the user', 200)

# Restaurant routes
# Route for restaurant landing page/order status
@app.route('/restaurant')
@app.route('/restaurant/orders')
def restaurant_orders():
    try:
        if request.cookies.get('user_id')[0] != 'r': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    except:
        return redirect('/select_user')
    restaurant = database['users'].find_one(request.cookies.get('user_id'))
    orders = [order for order in database['orders'].find({ 'restaurant': restaurant['name'], 'status': 'Waiting for restaurant' })]
    for order in orders:
        order['customer'] = database['users'].find_one({ '_id': order['user'] })['name']
        # print(order)
    return render_template('restaurant/orders.html', orders=orders)

# Route for restaurant login
@app.route('/restaurant/login', methods=['GET'])
def restaurant_login_page():
    user_id = request.cookies.get('user_id')
    if user_id:
        if user_id[0] != 'r': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
        else: return redirect('/restaurant')
    return render_template('restaurant/login.html')

# Route for restaurant login POST request
@app.route('/restaurant/login', methods=['POST'])
def restaurant_login():
    user = database['users'].find_one({ 'email': request.form.get('email'), 'password': request.form.get('password') })
    if user:
        if user['_id'][0] != 'r': return make_response(render_template('main/message.html', message='The credentials are not valid for a restaurant owner. Please check the details once again.'), 403)
        response = redirect('/restaurant')
        response.set_cookie('user_id', user['_id'])
        return response
    else:
        return render_template('restaurant/login.html')

# Route for restaurant signup
@app.route('/restaurant/signup', methods=['GET'])
def restaurant_signup_page():
    user_id = request.cookies.get('user_id')
    if user_id:
        if user_id[0] != 'r': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
        else: return redirect('/restaurant')
    return render_template('restaurant/signup.html')

# Route for restaurant sign up POST request
@app.route('/restaurant/signup', methods=['POST'])
def restaurant_signup():
    user = {}
    # Fetch data from request
    user['_id'] = 'r-' + ''.join([str(randint(0, 9)) for i in range(8)])
    while database['users'].find_one({ '_id': user['_id'] }): user['_id'] = 'r-' + [str(randint(0, 9)) for i in range(8)].join('')
    user['name'] = request.form.get('name')
    user['email'] = request.form.get('email')
    if database['users'].find_one({ 'email': user['email'] }): return make_response(render_template('main/message.html', message='Email already exists'), 403)
    user['address'] = request.form.get('address')
    user['phone'] = request.form.get('phone')
    user['password'] = request.form.get('password')
    # Save in database
    database['users'].insert_one(user)
    # Send response to customer
    response = redirect('/restaurant')
    response.set_cookie('user_id', user['_id'])
    return response

# Route for accepting or declining orders
@app.route('/restaurant/update_order', methods=['POST'])
def restaurant_update_order():
    try:
        if request.cookies.get('user_id')[0] != 'r': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    except:
        return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    # Fetch data from request
    data = eval(request.data.decode())
    # data = { '_id', 'status' }
    try:
        database['orders'].update_one({ '_id': data['_id'] }, { '$set': { 'status': data['status'], 'cooking_time': data['est_time'] } })
        # print(data['_id'], database['orders'].find_one({ '_id': data['_id'] }))
        return make_response('Order status updated', 200)
    except Exception as exception:
        print('Error in updating data:\n', exception)
        return make_response('Server issue', 500)

# Route for past orders of restaurant
@app.route('/restaurant/past_orders')
def restaurant_past_orders():
    try:
        if request.cookies.get('user_id')[0] != 'r': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    except:
        return redirect('/select_user')
    restaurant = database['users'].find_one(request.cookies.get('user_id'))
    orders = [order for order in database['orders'].find({ 'restaurant': restaurant['name'] })]
    for order in orders:
        if order['status'] == 'Waiting for customer': orders.remove[order]
        order['customer'] = database['users'].find_one({ '_id': order['user'] })['name']
        # print(order)
    return render_template('restaurant/past_orders.html', orders=orders)

# Route for restaurant menu page
@app.route('/restaurant/menu')
def restaurant_menu_page():
    try:
        if request.cookies.get('user_id')[0] != 'r': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    except:
        return redirect('/select_user')
    restaurant = database['users'].find_one(request.cookies.get('user_id'))['name']
    menu_items = database['menu-items'].find({ 'restaurant': restaurant })
    return render_template('restaurant/menu.html', menu_items=menu_items, restaurant=restaurant)

# Route for restaurant add item page
@app.route('/restaurant/add_item', methods=['GET'])
def restaurant_add_item_page():
    try:
        if request.cookies.get('user_id')[0] != 'r': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    except:
        return redirect('/select_user')
    restaurant = database['users'].find_one(request.cookies.get('user_id'))['name']
    return render_template('restaurant/add_item.html', restaurant=restaurant)

# Route for restaurant add item
@app.route('/restaurant/add_item', methods=['POST'])
def restaurant_add_item():
    try:
        if request.cookies.get('user_id')[0] != 'r': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    except:
        return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    restaurant = request.form.get('restaurant')
    name = request.form.get('name')
    image = request.form.get('image')
    description = request.form.get('description')
    price = request.form.get('price')
    database['menu-items'].insert_one({ 'name': name, 'description': description, 'image': image, 'price': price, 'restaurant': restaurant})
    return redirect('/restaurant/menu')

# Route for restaurant remove item
@app.route('/restaurant/remove_item', methods=['POST'])
def restaurant_remove_item():
    try:
        if request.cookies.get('user_id')[0] != 'r': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    except:
        return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    data = eval(request.data.decode())
    database['menu-items'].delete_one({ 'name': data['item'], 'restaurant': data['restaurant'] })
    return make_response('Removed item successfully', 200)

# Manager side page
@app.route('/manager')
@app.route('/manager/orders')
def manager_orders():
    try:
        if request.cookies.get('user_id')[0] != 'm': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    except:
        return redirect('/select_user')
    restaurant = database['users'].find_one(request.cookies.get('user_id'))
    orders = [order for order in database['orders'].find({ 'status': 'Delivery agent to be assigned' })]
    for order in orders:
        order['customer'] = database['users'].find_one({ '_id': order['user'] })['name']
        # print(order)
    return render_template('management/index.html', orders=orders)


# Route for manager login
@app.route('/manager/login', methods=['GET'])
def manager_login_page():
    user_id = request.cookies.get('user_id')
    if user_id:
        if user_id[0] != 'm': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
        else: return redirect('/manager')
    return render_template('management/login.html')

# Route for restaurant login POST request
@app.route('/manager/login', methods=['POST'])
def manager_login():
    user = database['users'].find_one({ 'username': request.form.get('username'), 'password': request.form.get('password') })
    if user:
        if user['_id'][0] != 'm': return make_response(render_template('main/message.html', message='The credentials are not valid for a restaurant owner. Please check the details once again.'), 403)
        response = redirect('/manager')
        response.set_cookie('user_id', user['_id'])
        return response
    else:
        return render_template('management/login.html')

# Route for assigning a delivery agent page
@app.route('/manager/assign/<id>', methods=['GET'])
def manager_assign_delivery_page(id):
    try:
        if request.cookies.get('user_id')[0] != 'm': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    except:
        return redirect('/select_user')
    order = database['orders'].find_one({ '_id': id, 'status': 'Delivery agent to be assigned'})
    if not order:
        return make_response('', 404)
    delivery_guys = database['users'].find({ '_id': { '$regex': '^d-' }, 'assigned': False })
    # print(delivery_guys)
    return render_template('management/assign_delivery.html', delivery_guys=delivery_guys, order_id=order['_id'])

# Route for assigning a delivery agent
@app.route('/manager/assign', methods=['POST'])
def manager_assign_delivery():
    try:
        if request.cookies.get('user_id')[0] != 'm': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    except:
        return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    data = eval(request.data.decode())
    order = database['orders'].update_one({ '_id': data['order'] }, { '$set': { 'status': 'Waiting for delivery agent confirmation', 'delivery_agent': data['agent'] } })
    return make_response('Delivery agent has been assigned', 200)

# Route for listing users
@app.route('/manager/show_user/<type>')
def manager_show_user_page(type):
    try:
        if request.cookies.get('user_id')[0] != 'm': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    except:
        return redirect('/select_user')
    users = [user for user in database['users'].find({ '_id': { '$regex': f"^{type[0]}-" } })]
    for user in users:
        ratings = [info['rating'] for info in database['ratings'].find({ 'to': user['_id'] })]
        user['avg_rating'] = sum(ratings)/len(ratings) if sum(ratings) else 0
    return render_template('management/show_user.html', users=users, type=type.capitalize())

# Route for removing user
@app.route('/manager/remove_user', methods=['POST'])
def manager_remove_user():
    try:
        if request.cookies.get('user_id')[0] != 'm': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    except:
        return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    database['users'].delete_one({ '_id': eval(request.data.decode())['_id'] })
    return make_response('User deleted', 200)

# Delivery agent routes
@app.route('/delivery')
@app.route('/delivery/orders')
def delivery_guy_orders():
    try:
        if request.cookies.get('user_id')[0] != 'd': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    except:
        return redirect('/select_user')
    current_order = database['orders'].find_one({ 'delivery_agent': request.cookies.get('user_id'), 'status': 'Accepted by delivery agent' })
    orders = [order for order in database['orders'].find({ 'delivery_agent': request.cookies.get('user_id'), 'status': 'Waiting for delivery agent confirmation' })]
    for order in orders:
        user = database['users'].find_one({ '_id': order['user'] })
        order['customer'] = user['name']
        order['address'] = user['address']
        order['phone'] = user['phone']
    print(current_order)
    return render_template('delivery/page.html', orders=orders, current_order=current_order)


# Route for delivery login
@app.route('/delivery/login', methods=['GET'])
def delivery_login_page():
    user_id = request.cookies.get('user_id')
    if user_id:
        if user_id[0] != 'd': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
        else: return redirect('/delivery')
    return render_template('delivery/login.html')

# Route for delivery login POST request
@app.route('/delivery/login', methods=['POST'])
def delivery_login():
    user = database['users'].find_one({ 'email': request.form.get('email'), 'password': request.form.get('password') })
    if user:
        if user['_id'][0] != 'd': return make_response(render_template('main/message.html', message='The credentials are not valid for a restaurant owner. Please check the details once again.'), 403)
        response = redirect('/delivery')
        response.set_cookie('user_id', user['_id'])
        return response
    else:
        return render_template('delivery/login.html')

# Route for delivery signup
@app.route('/delivery/signup', methods=['GET'])
def delivery_signup_page():
    user_id = request.cookies.get('user_id')
    if user_id:
        if user_id[0] != 'd': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
        else: return redirect('/delivery')
    return render_template('delivery/signup.html')

# Route for delivery sign up POST request
@app.route('/delivery/signup', methods=['POST'])
def delivery_signup():
    user = {}
    # Fetch data from request
    user['_id'] = 'd-' + ''.join([str(randint(0, 9)) for i in range(8)])
    while database['users'].find_one({ '_id': user['_id'] }): user['_id'] = 'd-' + [str(randint(0, 9)) for i in range(8)].join('')
    user['name'] = request.form.get('name')
    user['email'] = request.form.get('email')
    if database['users'].find_one({ 'email': user['email'] }): return make_response(render_template('main/message.html', message='Email already exists'), 403)
    user['address'] = request.form.get('address')
    user['phone'] = request.form.get('phone')
    user['password'] = request.form.get('password')
    # Save in database
    database['users'].insert_one(user)
    # Send response to customer
    response = redirect('/delivery')
    response.set_cookie('user_id', user['_id'])
    return response

# Route for updating order status
@app.route('/delivery/update_order', methods=['POST'])
def delivery_update_order():
    try:
        if request.cookies.get('user_id')[0] != 'd': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    except:
        return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    data = eval(request.data.decode())
    print(data)
    try:
        if data['status'] != 'Accepted by delivery agent' :
            database['orders'].update_one({ '_id': data['_id'] }, { '$set': { 'status': data['status'] } })
            database['users'].update_one({ '_id': request.cookies.get('user_id') }, { '$set': { 'assigned': False } })
        else :
            database['orders'].update_one({ '_id': data['_id'] }, { '$set': { 'status': data['status'], 'pickup_time': data['pic_time'], 'delivery_time': data['del_time'] } })
            database['users'].update_one({ '_id': request.cookies.get('user_id') }, { '$set': { 'assigned': True } })
            
        return make_response('Order status updated', 200)
    except Exception as exception:
        print('Error in updating data:\n', exception)
        return make_response('Server issue', 500)

# Route for delivery guy to rate customers
@app.route('/delivery/past_orders')
def delivery_guy_past_orders():
    try:
        if request.cookies.get('user_id')[0] != 'd': return make_response(render_template('main/message.html', message='You do not have access to this page'), 403)
    except:
        return redirect('/select_user')
    orders = [order for order in database['orders'].find({ 'delivery_agent': request.cookies.get('user_id'), 'status': 'Delivered' })]
    for order in orders:
        user = database['users'].find_one({ '_id': order['user'] })
        order['customer'] = user['name']
        order['address'] = user['address']
        order['phone'] = user['phone']
    return render_template('delivery/past_orders.html', orders=orders, self_user=request.cookies.get('user_id'))
