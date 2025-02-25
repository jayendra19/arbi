import requests
import time
import hmac
import hashlib
#import ccxt
import json
import websocket
from flask import Flask,request,render_template,jsonify,flash, redirect,make_response
from flask import Flask, request, jsonify
import mysql.connector
from mysql.connector import Error
import bcrypt
#from flask_cors import CORS
# Replace with your own API key and secret for both exchanges
'''bitmart_api_key = '9935ff7064f62790aa225c8d6e390df381e3ef6b'
bitmart_api_secret = '37b4458fcbdc3f5d20d6bd75b30ce6b89fbfe79c9972b166e5e4265450c6dc32'
mexc_api_key = 'mx0vglD2hg4NpEtIuE'
mexc_api_secret = 'f7b4796e681347f3b7ce4846fc87d64c'
memo = 'rbot'''

def fetch_bitmart_balance(api_key, api_secret, memo):
    url = "https://api-cloud.bitmart.com/account/v1/wallet"
    timestamp = str(int(time.time() * 1000))
    method = "GET"
    query_string = ""
    payload = ""
    sign = hmac.new(api_secret.encode('utf-8'), (timestamp + '#' + memo + '#' + method + '#' + query_string + '#' + payload).encode('utf-8'), hashlib.sha256).hexdigest()

    headers = {
        'X-BM-KEY': api_key,
        'X-BM-SIGN': sign,
        'X-BM-TIMESTAMP': timestamp,
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)
    data = response.json()
    if data['code'] == 1000:
        wallet = data['data']['wallet']
        balances = {}
        for currency in wallet:
            if currency['currency'] in ['DEOD', 'USDT']:
                available = float(currency['available'])
                total = available + float(currency['frozen'])
                balances[currency['currency']] = {
                    'available': available,
                    'total': total
                }
        balance=balances['USDT']['total']
        quantity=balances['DEOD']['total']
        return balance,quantity
    else:
        print(f"Error: {data['message']}")
        return None


def fetch_mexc_balance(api_key, api_secret):
    url = "https://api.mexc.com/api/v3/account"
    timestamp = str(int(time.time() * 1000))
    query_string = f"timestamp={timestamp}"
    sign = hmac.new(api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

    headers = {
        'X-MEXC-APIKEY': api_key
    }

    response = requests.get(f"{url}?{query_string}&signature={sign}", headers=headers)
    data = response.json()
    if 'balances' in data:
        usdt_balance = None
        deod_balance = None
        for balance in data['balances']:
            if balance['asset'] == 'USDT':
                usdt_balance = balance['free']
            elif balance['asset'] == 'DEOD':
                deod_balance = balance['free']
        
        return usdt_balance, deod_balance
    else:
        print(f"Error: 'balances' key not found in response. Response data: {data}")
        return None, None



def get_timestamp():
    return str(int(time.time() * 1000))

def generate_signature(api_secret, message):
    return hmac.new(api_secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()

def place_order_bit(bitmart_api_key, api_secret,api_memo,size,current_price,side,tokken_name_bit):
    base_url = 'https://api-cloud.bitmart.com'
    endpoint = '/spot/v2/submit_order'
    url = base_url + endpoint

    '''# Fetch the current price of DEOD/USDT
    price_endpoint = '/spot/v1/ticker'
    price_url = f"{base_url}{price_endpoint}?symbol=DEOD_USDT"
    price_response = requests.get(price_url)
    
    if price_response.status_code != 200:
        print(f"Error fetching price: {price_response.text}")
        return

    price_data = price_response.json()
    current_price = float(price_data['data']['tickers'][0]['last_price'])'''

    # Calculate the size of DEOD to buy with the available USDT balance
    #size = usdt_balance / current_price
    if size <= 0:
        print("Insufficient balance to buy DEOD bitmart.")
        return "Insufficient balance to buy DEOD bitmart."

    timestamp = str(int(time.time() * 1000))
    body = {
        'size': str(size),  # Order size
        'price': str(current_price),  # Order price
        'side': side,  # 'buy' or 'sell'
        'symbol': str(tokken_name_bit),#'DEOD_USDT',  # Trading pair
        'type': 'limit'  # Order type: 'limit' or 'market'
    }
    body_json = json.dumps(body)
    message = f"{timestamp}#{api_memo}#{body_json}"
    signature = generate_signature(api_secret, message)

    headers = {
        'Content-Type': 'application/json',
        'X-BM-KEY': bitmart_api_key,
        'X-BM-TIMESTAMP': timestamp,
        'X-BM-SIGN': signature
    }

    response = requests.post(url, headers=headers, json=body)
    if response.status_code == 200:
        print(f"Order placed on BitMart: {response.json()}")
    else:
        print(f'Error placing order on BitMart: {response.text}')
        print(f'Generated Signature: {signature}')
        print(f'Timestamp: {timestamp}')
        print(f'Body: {body_json}')




def place_order_mexc(api_key, api_secret,size,current_price,side,tokken_name_mex):
    base_url = 'https://api.mexc.com'
    price_endpoint = '/api/v3/ticker/price'
    '''price_url = f"{base_url}{price_endpoint}?symbol=DEODUSDT"
    
    # Fetch the current price of DEOD/USDT
    price_response = requests.get(price_url)
    if price_response.status_code != 200:
        print(f"Error fetching price: {price_response.text}")
        return

    price_data = price_response.json()
    current_price = float(price_data['price'])'''

    # Calculate the size of DEOD to buy with the available USDT balance
    #size = usdt_balance / current_price
    if size <= 0:
        print("Insufficient balance to buy Deod Mexc.")
        return "Insufficient balance to buy Deod Mexc."

    timestamp = str(int(time.time() * 1000))
    body = {
        'symbol': str(tokken_name_mex),#'DEODUSDT',
        'side': side,
        'type': 'LIMIT',
        'quantity': str(size),
        'price': str(current_price),
        'timestamp': timestamp
    }

    query_string = f"symbol={body['symbol']}&side={body['side']}&type={body['type']}&quantity={body['quantity']}&price={body['price']}&timestamp={body['timestamp']}"
    signature = generate_signature(api_secret, query_string)

    headers = {
        'X-MEXC-APIKEY': api_key
    }

    response = requests.post(f"{base_url}/api/v3/order?{query_string}&signature={signature}", headers=headers)
    if response.status_code == 200:
        print(f"Order placed on MEXC: {response.json()}")
    else:
        print(f'Error placing order on MEXC: {response.text}')
        print(f'Generated Signature: {signature}')
        print(f'Timestamp: {timestamp}')
        print(f'Query String: {query_string}')
        
        
        
        
        


    
''''bitmart_price = None
bitmart_selling=None
mexc_price = None
mexc_selling=None
    
def on_message_bitmart(ws, message):
    global bitmart_price, bitmart_selling
    data = json.loads(message)
    #print(data)
    if 'table' in data and data['table'] == 'spot/ticker':
        for ticker in data['data']:
            if ticker['symbol'] == 'DEOD_USDT':
                bitmart_price = float(ticker['bid_px'])
                bitmart_quantity = ticker['bid_sz']
                bitmart_selling = float(ticker['ask_px'])
                selling_quantity = ticker['ask_sz']  # Selling quantity
                #print(f"BitMart DEOD/USDT Price: {bitmart_price}, Size: {bitmart_quantity}")
                #print(f"Bitmart Selling Price: {sell_price}, Selling quantity: {ask_sz}")
                
                # Optionally return or process the data further
                return bitmart_price,bitmart_selling

def on_message_mexc(ws, message):
    global mexc_price,mexc_selling
    data = json.loads(message)
    #print(data)
    
    if 'd' in data:
        ticker_data = data['d']
        
        # Check if the message is a deal
        if 'deals' in ticker_data:
            for deal in ticker_data['deals']:
                #mexc_price = float(deal['p'])
                mexc_quantity = deal['v']
                #print(f"Mexc DEOD/USDT Current Price: {mexc_price}, Current Quantity: {mexc_quantity}")
                break  # Exit the loop after processing the first deal
        
        # Check if the message is a book ticker update
        if 'a' in ticker_data and 'A' in ticker_data and 'b' in ticker_data and 'B' in ticker_data:
            mexc_selling = float(ticker_data['a'])
            selling_quantity = ticker_data['A']
            mexc_price = float(ticker_data['b'])
            bid_quantity = ticker_data['B']
            #print(f"Mexc DEOD/USDT Selling Price: {ask_price}, Selling Quantity: {ask_quantity}")
            
            return mexc_price,mexc_selling
            
    

def on_error(ws, error):
    print(error)

def on_close(ws, close_status_code, close_msg):
    print("### closed ###")

def on_open_bitmart(ws):
    subscribe_message = {
        "op": "subscribe",
        "args": ["spot/ticker:DEOD_USDT"]
    }
    ws.send(json.dumps(subscribe_message))

def on_open_mexc(ws):
    message = {
        "method": "SUBSCRIPTION",
        "params": [
            "spot@public.deals.v3.api@DEODUSDT",
            "spot@public.bookTicker.v3.api@DEODUSDT"
        ]
    }
    ws.send(json.dumps(message)) 

def fetch_bitmart_price():
    websocket.enableTrace(False)
    ws = websocket.WebSocketApp("wss://ws-manager-compress.bitmart.com/api?protocol=1.1",
                                on_open=on_open_bitmart,
                                on_message=on_message_bitmart,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever(ping_interval=5, ping_timeout=4)

def fetch_mexc_price():
    websocket.enableTrace(False)
    ws = websocket.WebSocketApp("wss://wbs.mexc.com/ws",
                                on_open=on_open_mexc,
                                on_message=on_message_mexc,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever(ping_interval=5, ping_timeout=4)              
                    

import threading

bitmart_thread = threading.Thread(target=fetch_bitmart_price)
mexc_thread = threading.Thread(target=fetch_mexc_price)

bitmart_thread.start()
mexc_thread.start()'''    
    
    
'''def bitmart_prices():
    url = f"https://api-cloud.bitmart.com/spot/v1/symbols/book?symbol=DEOD_USDT"
    response = requests.get(url)
    data = response.json()
    #print(data)

    if data['code'] == 1000:
        bitmart_price = data['data']['buys'][0]['price']
        bitmart_selling = data['data']['sells'][0]['price']
        return bitmart_price,bitmart_selling 
    else:
        raise Exception(f"Error fetching data: {data['message']}")'''  
        
        
def get_current_price():
    base_url = 'https://api-cloud.bitmart.com'
    price_endpoint = '/spot/quotation/v3/ticker?'
    params = {'symbol': 'DEOD_USDT'}
    price_url = f"{base_url}{price_endpoint}"

    # Fetch the current price
    price_response = requests.get(price_url, params=params)
    price_data = price_response.json()

    if 'data' in price_data and 'last' in price_data['data']:
        return float(price_data['data']['last'])
    else:
        raise Exception(f"Error fetching current price: {price_data.get('msg', 'Unknown error')}")

def get_best_bid_ask(tokken_name_bit):
    url = f"https://api-cloud.bitmart.com/spot/v1/symbols/book?symbol={tokken_name_bit}"
    response = requests.get(url)
    data = response.json()
    #print(data)
    current_price=get_current_price()
    
    if data['code'] == 1000:
        bitmart_price = float(data['data']['buys'][0]['price'])
        bitmart_selling = float(data['data']['sells'][1]['price'])
        
        # Check if the current price matches the selling price
        '''if current_price == bitmart_selling:
            # Use the second selling price
            bitmart_selling = float(data['data']['sells'][1]['price'])'''
        
        return bitmart_price, bitmart_selling 
    else:
        raise Exception(f"Error fetching data: {data['message']}")

    
     
     
def mexc_prices(tooken_name_mex):
    url = f"https://api.mexc.com/api/v3/depth?symbol={tooken_name_mex}"
    response = requests.get(url)
    data = response.json()

    if 'bids' in data and 'asks' in data:
        mexc_price = data['bids'][0][0]
        mexc_selling = data['asks'][0][0]
        return mexc_price,mexc_selling
    else:
        raise Exception("Error fetching data")
    
'''bitmart_api_key = '89db284cbefc2fba25d7460b8e1e2ed70cfd8573'
bitmart_api_secret = '6255080761902819625754b6d634a92e8c9c3b9aedab7e51c1bc301c583cb90d'
memo='vbot'
mexc_api_key = 'mx0vglD2hg4NpEtIuE'
mexc_api_secret = 'f7b4796e681347f3b7ce4846fc87d64c' ''' 



def bitmart(token_name_bit):
    url = f"https://api-cloud.bitmart.com/spot/v1/symbols/book?symbol={token_name_bit}"
    response = requests.get(url)
    data = response.json()
    #print(data)
    
    if data['code'] == 1000:
        # Extract all buys and sells
        buys = data['data']['buys']
        sells = data['data']['sells']
        
        # Create lists to store price-quantity pairs
        buy_orders = []
        sell_orders = []

        # Iterate through all buy entries
        for buy in buys:
            buy_orders.append((float(buy['price']), float(buy['total'])))

        # Iterate through all sell entries
        for sell in sells:
            sell_orders.append((float(sell['price']), float(sell['total'])))
            
        return {
            'buy_orders': buy_orders,
            'sell_orders': sell_orders
        }
         
    else:
        raise Exception(f"Error fetching data: {data['message']}")
  
  


def mexc(token_name_mex):
    url = f"https://api.mexc.com/api/v3/depth?symbol={token_name_mex}"
    response = requests.get(url)
    data = response.json()
    
    
    # Check if the response contains 'bids' and 'asks'
    if 'bids' in data and 'asks' in data:
        # Extract all bids and asks
        bids = data['bids']
        asks = data['asks']
        
        # Create lists to store price-quantity pairs
        buy_orders = []
        sell_orders = []

        # Iterate through all bid entries (buy orders)
        for bid in bids:
            buy_orders.append((float(bid[0]), float(bid[1])))  # Price and quantity

        # Iterate through all ask entries (sell orders)
        for ask in asks:
            sell_orders.append((float(ask[0]), float(ask[1])))  # Price and quantity
            
        return {
            'buy_orders': buy_orders,
            'sell_orders': sell_orders
        }
    else:
        raise Exception("Invalid response structure: Missing 'bids' or 'asks'.")
running = False
continuous_thread = None
logs = []

def filter_orders(orders, desired_price): 
    results = [] 
    for price, quantity in orders: 
        amount_to_trade = desired_price / price 
        #print(amount_to_trade)
        #print(quantity)
        if  quantity>=amount_to_trade : 
            results.append((price, amount_to_trade)) 
            return results
  
def check_arbitrage(bitmart_api_key, bitmart_api_secret, memo, mexc_api_key, mexc_api_secret, profit_threshold_percentage, transaction_fee_percentage, desired_deod_price, tokken_name_bit, tokken_name_mex):
    global logs
    
    usdt_balance_bitmart, deod_quantity_bitmart = fetch_bitmart_balance(bitmart_api_key, bitmart_api_secret, memo)
    log_message = f"usdt_balance_bitmart: {usdt_balance_bitmart}, deod_quantity_bitmart: {deod_quantity_bitmart}"
    logs.append(log_message)
    
    usdt_balance_mexc, deod_quantity_mexc = fetch_mexc_balance(mexc_api_key, mexc_api_secret)
    log_message = f"usdt_balance_mexc: {usdt_balance_mexc}, deod_quantity_mexc: {deod_quantity_mexc}"
    logs.append(log_message)

    
    # Fetch buy and sell orders
    bitmart_orders = bitmart('DEOD_USDT')
    mexc_orders = mexc('DEODUSDT')     
    
    bitmart_selling,amount_to_tradebit=filter_orders(bitmart_orders['sell_orders'],desired_deod_price)[0]
    bitmart_price=filter_orders(bitmart_orders['buy_orders'],desired_deod_price)[0][0]
    log_message = f"Bitmart price: {bitmart_price}, bitmart selling: {bitmart_selling}"
    logs.append(log_message)
    mexc_price=filter_orders(mexc_orders['buy_orders'],desired_deod_price)[0][0]
    mexc_selling,amount_to_trademex=filter_orders(mexc_orders['sell_orders'],desired_deod_price)[0]
    log_message = f"mexc_price: {mexc_price}, mexc_selling: {mexc_selling}"
    logs.append(log_message)



    # Convert prices and balances to float
    bitmart_price = float(bitmart_price)
    bitmart_selling = float(bitmart_selling)
    mexc_price = float(mexc_price)
    mexc_selling = float(mexc_selling)
    
    usdt_balance_bitmart = float(usdt_balance_bitmart)
    deod_quantity_bitmart = float(deod_quantity_bitmart)
    usdt_balance_mexc = float(usdt_balance_mexc)
    deod_quantity_mexc = float(deod_quantity_mexc)
    desired_deod_price = float(desired_deod_price)

    if bitmart_price and mexc_price:
        if bitmart_selling < mexc_price:
            #amount_to_trade = (desired_deod_price / bitmart_selling)

            if amount_to_tradebit > 0:
                profit = (mexc_price - bitmart_selling) / bitmart_selling * 100
                net_profit = profit - transaction_fee_percentage
                
                log_message = f"net_profit buying in BitMart: {net_profit}%"
                logs.append(log_message)

                if net_profit >= profit_threshold_percentage:
                    place_order_bit(bitmart_api_key, bitmart_api_secret, memo, amount_to_tradebit, bitmart_selling, 'buy', tokken_name_bit)
                    
                    place_order_mexc(mexc_api_key, mexc_api_secret, amount_to_tradebit, mexc_price, 'SELL', tokken_name_mex)

                    log_message = f"Executed arbitrage: Quantity bought and sold: {amount_to_tradebit}, Bought on BitMart at {bitmart_selling}, Sold on Mexc at {mexc_price}, Profit: {net_profit}%"
                    logs.append(log_message)

        elif mexc_selling < bitmart_price:
            #amount_to_trade = (desired_deod_price / mexc_selling)

            if amount_to_trademex > 0:
                profit = (bitmart_price - mexc_selling) / mexc_selling * 100
                net_profit = profit - transaction_fee_percentage
                
                log_message = f"net_profit buying on Mexc: {net_profit}%"
                logs.append(log_message)

                if net_profit >= profit_threshold_percentage:
                    place_order_mexc(mexc_api_key, mexc_api_secret, amount_to_trademex, mexc_selling, 'BUY', tokken_name_mex)
           
                    place_order_bit(bitmart_api_key, bitmart_api_secret, memo, amount_to_trademex, bitmart_price, 'sell', tokken_name_bit)

                    log_message = f"Executed arbitrage: Quantity bought and sold: {amount_to_trademex}, Bought on Mexc at {mexc_selling}, Sold on BitMart at {bitmart_price}, Profit: {net_profit}%"
                    logs.append(log_message)


app=Flask(__name__)


import threading
def run_continuously(bitmart_api_key, bitmart_api_secret, memo, mexc_api_key, mexc_api_secret, profit_percentage, transaction_fee_percentage, desired_deod_price, tokken_name_bit, tokken_name_mex):
    global running
    while running:
        check_arbitrage(bitmart_api_key, bitmart_api_secret, memo, mexc_api_key, mexc_api_secret, profit_percentage, transaction_fee_percentage, desired_deod_price,tokken_name_bit, tokken_name_mex)
        time.sleep(3)

 # Now matches function signature # Wait for 5 seconds before checking again

@app.route("/", methods=["GET", "POST"])
def arbi():
    global running
    data = request.get_json()
    
    # Check if all required keys are present in the request data
    if all(key in data for key in ['bitmart_api_key', 'bitmart_api_secret', 'memo', 
                                     'mexc_api_key', 'mexc_api_secret', 
                                     'profit_percentage', 'transaction_fee_percentage', 
                                     'desired_deod_price','tokken_name_bit','tokken_name_mex']):
        
        bitmart_api_key = data['bitmart_api_key']
        bitmart_api_secret = data['bitmart_api_secret']
        memo = data['memo']
        mexc_api_key = data['mexc_api_key']
        mexc_api_secret = data['mexc_api_secret']
        profit_percentage = float(data['profit_percentage'])
        transaction_fee_percentage = float(data['transaction_fee_percentage'])
        desired_deod_price = float(data['desired_deod_price'])
        tokken_name_bit=data['tokken_name_bit']
        tokken_name_mex=data['tokken_name_mex']

        # Start the continuous thread if it's not already running
        if not running:
            running = True
            global continuous_thread
            continuous_thread = threading.Thread(target=run_continuously,
                                                 args=(bitmart_api_key, bitmart_api_secret,
                                                       memo, mexc_api_key,
                                                       mexc_api_secret,
                                                       profit_percentage,
                                                       transaction_fee_percentage,
                                                       desired_deod_price,
                                                       tokken_name_bit,
                                                       tokken_name_mex))
            continuous_thread.start()
            return jsonify({"message": "Arbitrage checking started."}), 200
        
        return jsonify({"message": "Arbitrage checking is already running."}), 200

@app.route("/stop", methods=["POST"])
def stop_arbi():
    global running
    if running:
        running = False
        continuous_thread.join()  # Wait for the thread to finish
        return jsonify({"message": "Arbitrage checking stopped."}), 200
    
    return jsonify({"message": "Arbitrage checking is not running."}), 200


@app.route("/logs", methods=["GET"])
def get_logs():
    """Endpoint to retrieve logs."""
    return jsonify({"logs": logs}), 200

# MySQL database configuration
db_config = {
    'host': 'localhost',
    'user': 'flaskuser',
    'password': 'admin@1234',
    'database': 'jaytest'
}

def get_db_connection():
    connection = mysql.connector.connect(**db_config)
    return connection

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data.get('email')   # Will be None if not provided
    phone = data.get('phone')   # Will be None if not provided
    password = data.get('password')

    # Ensure at least one identifier (email or phone) is provided
    if not (email or phone):
        return jsonify({'error': 'Please provide either email or phone.'}), 400
    if not password:
        return jsonify({'error': 'Please provide a password.'}), 400

    # Hash the password before storing it
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = "INSERT INTO users (email, phone, password) VALUES (%s, %s, %s)"
        cursor.execute(sql, (email, phone, hashed_password))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'message': 'User registered successfully'}), 201
    except Error as err:
        return jsonify({'error': str(err)}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')

    if not ((email or phone) and password):
        return jsonify({'error': 'Please provide login credentials.'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if email:
            sql = "SELECT * FROM users WHERE email = %s"
            cursor.execute(sql, (email,))
        else:
            sql = "SELECT * FROM users WHERE phone = %s"
            cursor.execute(sql, (phone,))

        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user is None:
            return jsonify({'error': 'User not found'}), 400

        # Verify the password using bcrypt
        if not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            return jsonify({'error': 'Invalid credentials'}), 400

        return jsonify({'message': 'Login successful'}), 200

    except Error as err:
        return jsonify({'error': str(err)}), 500

@app.route('/reset', methods=['POST'])
def reset_password():
    data = request.get_json()
    email = data.get('email')
    phone = data.get('phone')
    new_password = data.get('new_password')

    if not ((email or phone) and new_password):
        return jsonify({'error': 'Please provide either email or phone along with a new password.'}), 400

    # Hash the new password before updating it
    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if email:
            sql = "UPDATE users SET password = %s WHERE email = %s"
            cursor.execute(sql, (hashed_password, email))
        else:
            sql = "UPDATE users SET password = %s WHERE phone = %s"
            cursor.execute(sql, (hashed_password, phone))
        
        conn.commit()

        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 400

        cursor.close()
        conn.close()
        return jsonify({'message': 'Password updated successfully'}), 200

    except Error as err:
        return jsonify({'error': str(err)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000, debug=True)